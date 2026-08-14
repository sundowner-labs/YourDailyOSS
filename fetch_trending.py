#!/usr/bin/env python3
"""
Fetch today's GitHub Trending repos and write them to JSON in the schema
make_carousel.py / make_captions.py expect.

GitHub has no official API for "trending" (it's a computed, undocumented
page) so this scrapes https://github.com/trending directly, same as a
browser would. Works from any environment with normal outbound network
access (plain VS Code dev machine, GitHub Actions runner) -- unlike the
GitHub Search API, this is the only way to get the "stars gained today"
figure the carousel cards show.

Usage:
    python3 fetch_trending.py --limit 5 --out repo_data.json
    python3 fetch_trending.py --since weekly --language python --limit 10
"""
import argparse
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

TRENDING_URL = "https://github.com/trending"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; YourDailyOSS/1.0)"}


def _int(text):
    match = re.search(r"[\d,]+", text or "")
    return int(match.group(0).replace(",", "")) if match else 0


def fetch_trending(since="daily", language=None, limit=5):
    url = f"{TRENDING_URL}/{language}" if language else TRENDING_URL
    resp = requests.get(url, params={"since": since}, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    repos = []
    for article in soup.select("article.Box-row"):
        h2 = article.select_one("h2")
        if not h2 or not h2.a:
            continue
        full_name = h2.a.get("href", "").strip("/")
        if not full_name:
            continue

        desc_tag = article.select_one("p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        lang_tag = article.select_one("span[itemprop='programmingLanguage']")
        language_name = lang_tag.get_text(strip=True) if lang_tag else None

        stars_tag = article.select_one("a[href$='/stargazers']")
        stars = _int(stars_tag.get_text()) if stars_tag else 0

        today_tag = article.select_one("span.float-sm-right")
        stars_today = _int(today_tag.get_text()) if today_tag else 0

        repos.append({
            "full_name": full_name,
            "description": description,
            "language": language_name,
            "stars": stars,
            "stars_today": stars_today,
            "url": f"https://github.com/{full_name}",
        })
        if len(repos) >= limit:
            break

    return repos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", choices=["daily", "weekly", "monthly"], default="daily")
    ap.add_argument("--language", default=None, help="e.g. python, typescript (omit for all languages)")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--out", default="repo_data.json")
    args = ap.parse_args()

    repos = fetch_trending(since=args.since, language=args.language, limit=args.limit)
    if not repos:
        print("No repos scraped -- GitHub's trending page markup may have changed.", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=2)

    print(f"Wrote {len(repos)} repos to {args.out}")
    for r in repos:
        print(f"  {r['full_name']}  ({r['stars']:,} stars, +{r['stars_today']:,} today)")


if __name__ == "__main__":
    main()
