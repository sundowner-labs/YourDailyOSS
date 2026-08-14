#!/usr/bin/env python3
"""
Generate the post caption to go with the carousel images.

Style brief (per project handoff): hook opener leading with the most
surprising stat (not "here are today's repos"), one punchy "why this
matters" line per repo instead of the raw GitHub description, and an
engagement-driving close -- a question, since that's what reply/comment
counts reward in these platforms' algorithms.

Two output lengths are produced from the same content:
  - "long"  -- for Mastodon (default instance limit ~500 chars)
  - "short" -- for Bluesky (hard 300 char limit), which can't fit five
    per-repo lines, so it keeps the hook + link + question and leans on
    the carousel images to carry the per-repo detail.

Two generation modes:
  - LLM mode (default): calls the Claude API to write the hook, the
    per-repo lines, and the closing question, so the copy has actual
    variety instead of reading like five iterations of one template.
    Requires ANTHROPIC_API_KEY.
  - --no-llm: rule-based fallback with no external calls, for offline
    testing or if the API key isn't set yet. Noticeably flatter than the
    LLM mode -- use it to sanity-check the pipeline, not to ship posts.

Usage:
    python3 make_captions.py repo_data.json --link yourdailyoss.com --out captions.json
    python3 make_captions.py repo_data.json --no-llm --out captions.json
"""
import argparse
import json
import os
import random
import re
import sys

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

BLUESKY_LIMIT = 300
MASTODON_LIMIT = 480  # stay under the common 500-char instance default

CLOSING_QUESTIONS = [
    "Which one are you starring first?",
    "Which of these is going straight into your stack?",
    "Anyone already using one of these -- worth it?",
    "What'd we miss from today's trending page?",
]


def _int_or(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def call_claude(repos, model):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    repo_lines = "\n".join(
        f"- {r['full_name']} ({r.get('language') or 'unknown'}, "
        f"{r['stars']:,} stars, +{r['stars_today']:,} today): "
        f"{r.get('description') or 'no description'}"
        for r in repos
    )

    prompt = f"""You write social captions for a daily "GitHub Trending" carousel post
(Bluesky + Mastodon). The images already show each repo's name, description,
stars, and language -- your job is the caption text, which should add
punch, not repeat the images.

Today's repos:
{repo_lines}

Write JSON with exactly these keys:
- "hook": one sentence opening the post, leading with the single most
  surprising/impressive stat from the list above (e.g. a huge stars-today
  number, or a wild use case). Do not say "here are today's top repos" --
  lead with the stat itself.
- "repo_lines": an array of {len(repos)} one-liners, one per repo in the
  order given, each a punchy "why this matters" angle -- NOT a restatement
  of the GitHub description. Think: what would make someone stop scrolling.
  Keep each under 100 characters.
- "closing_question": one short question inviting replies (e.g. asking
  which repo people are trying first). Do not use generic phrasing like
  "let us know your thoughts".

Tone: confident, informal, zero corporate voice, no hashtag stuffing, no
emoji spam (a single emoji max, optional). Output ONLY the JSON object,
no markdown fences, no commentary."""

    resp = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = json.loads(text)

    if len(data.get("repo_lines", [])) != len(repos):
        raise ValueError("Claude returned the wrong number of repo lines")
    return data["hook"], data["repo_lines"], data["closing_question"]


def rule_based_fallback(repos):
    top = max(repos, key=lambda r: _int_or(r.get("stars_today")))
    hook = (
        f"{top['full_name']} just picked up {_int_or(top['stars_today']):,} stars "
        f"today on GitHub."
    )

    repo_lines = []
    for r in repos:
        desc = (r.get("description") or "").rstrip(". ")
        lang = r.get("language") or "code"
        repo_lines.append(f"{r['full_name']} ({lang}): {desc}." if desc else f"{r['full_name']} ({lang}).")

    closing_question = random.choice(CLOSING_QUESTIONS)
    return hook, repo_lines, closing_question


def truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_captions(repos, hook, repo_lines, closing_question, link):
    link_line = f"\U0001f517 {link}" if link else ""

    long_parts = [hook, ""] + [f"• {line}" for line in repo_lines] + [""]
    if link_line:
        long_parts.append(link_line)
    long_parts.append(closing_question)
    long_caption = "\n".join(long_parts)
    long_caption = truncate(long_caption, MASTODON_LIMIT)

    short_parts = [hook]
    if link_line:
        short_parts.append(link_line)
    short_parts.append(closing_question)
    short_caption = "\n".join(short_parts)
    short_caption = truncate(short_caption, BLUESKY_LIMIT)

    return {"mastodon": long_caption, "bluesky": short_caption}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_json")
    ap.add_argument("--link", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="skip the Claude API call, use rule-based fallback")
    ap.add_argument("--out", default="captions.json")
    args = ap.parse_args()

    with open(args.repo_json, encoding="utf-8") as f:
        repos = json.load(f)

    if not repos:
        print("No repos in input file.", file=sys.stderr)
        sys.exit(1)

    if args.no_llm:
        hook, repo_lines, closing_question = rule_based_fallback(repos)
        mode = "rule-based"
    else:
        try:
            hook, repo_lines, closing_question = call_claude(repos, args.model)
            mode = f"llm ({args.model})"
        except Exception as e:
            print(f"LLM caption generation failed ({e}); falling back to rule-based.", file=sys.stderr)
            hook, repo_lines, closing_question = rule_based_fallback(repos)
            mode = "rule-based (fallback)"

    captions = build_captions(repos, hook, repo_lines, closing_question, args.link)
    captions["_meta"] = {"mode": mode, "hook": hook, "repo_lines": repo_lines, "closing_question": closing_question}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(captions, f, indent=2, ensure_ascii=False)

    print(f"Generated captions via {mode} -> {args.out}")
    print("\n--- Mastodon ---")
    print(captions["mastodon"])
    print("\n--- Bluesky ---")
    print(captions["bluesky"])


if __name__ == "__main__":
    main()
