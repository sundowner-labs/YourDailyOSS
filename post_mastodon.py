#!/usr/bin/env python3
"""
Post a generated carousel to Mastodon.

Mastodon caps media attachments at 4 per status (same as Bluesky), so
this posts the images as a reply-thread: each status carries up to 4
images, and every status after the first replies to the previous one.

Requires env vars MASTODON_INSTANCE_URL (e.g. https://mastodon.social)
and MASTODON_ACCESS_TOKEN (Settings -> Development -> New Application on
that instance, with read/write scopes for statuses and media).

Usage:
    python3 post_mastodon.py out/ repo_data.json captions.json
    python3 post_mastodon.py out/ repo_data.json captions.json --dry-run
"""
import argparse
import glob
import json
import os
import sys

CHUNK_SIZE = 4


def build_alts(repos):
    alts = ["Today's top GitHub repos -- title card."]
    for r in repos:
        stars = f"{r['stars']:,} stars, +{r['stars_today']:,} today"
        lang = r.get("language") or "unknown language"
        desc = r.get("description") or ""
        alts.append(f"{r['full_name']} ({lang}, {stars}). {desc}".strip())
    alts.append("Follow for more -- link and info in this post.")
    return alts


def chunk(seq, size):
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images_dir")
    ap.add_argument("repo_json")
    ap.add_argument("captions_json")
    ap.add_argument("--visibility", default="public", choices=["public", "unlisted", "private"])
    ap.add_argument("--dry-run", action="store_true", help="build the thread but don't call the Mastodon API")
    args = ap.parse_args()

    instance_url = os.environ.get("MASTODON_INSTANCE_URL")
    access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not args.dry_run and not (instance_url and access_token):
        print("Set MASTODON_INSTANCE_URL and MASTODON_ACCESS_TOKEN.", file=sys.stderr)
        sys.exit(1)

    with open(args.repo_json, encoding="utf-8") as f:
        repos = json.load(f)
    with open(args.captions_json, encoding="utf-8") as f:
        captions = json.load(f)

    image_paths = sorted(glob.glob(os.path.join(args.images_dir, "*.jpg")))
    alts = build_alts(repos)
    if len(image_paths) != len(alts):
        print(
            f"Expected {len(alts)} images (title + {len(repos)} repos + CTA), "
            f"found {len(image_paths)} in {args.images_dir}.",
            file=sys.stderr,
        )
        sys.exit(1)

    image_chunks = chunk(image_paths, CHUNK_SIZE)
    alt_chunks = chunk(alts, CHUNK_SIZE)
    thread_text = [captions["mastodon"]] + [
        f"({i}/{len(image_chunks)}) more from today's trending ↓" for i in range(2, len(image_chunks) + 1)
    ]

    if args.dry_run:
        print(f"[dry-run] would post {len(image_chunks)}-part thread to Mastodon at {instance_url or '<unset>'}:")
        for i, (imgs, text) in enumerate(zip(image_chunks, thread_text), 1):
            print(f"  part {i}: {[os.path.basename(p) for p in imgs]}")
            print(f"    text: {text!r}")
        return

    from mastodon import Mastodon

    mastodon = Mastodon(access_token=access_token, api_base_url=instance_url)

    prev_status_id = None
    for imgs, alt_group, text in zip(image_chunks, alt_chunks, thread_text):
        media_ids = [
            mastodon.media_post(path, description=alt).id
            for path, alt in zip(imgs, alt_group)
        ]
        status = mastodon.status_post(
            status=text,
            media_ids=media_ids,
            in_reply_to_id=prev_status_id,
            visibility=args.visibility,
        )
        prev_status_id = status.id
        print(f"Posted: {status.url}")

    print("Mastodon thread complete.")


if __name__ == "__main__":
    main()
