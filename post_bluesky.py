#!/usr/bin/env python3
"""
Post a generated carousel to Bluesky.

Bluesky caps image embeds at 4 per post, and our carousel (title + one
card per repo + CTA) usually runs longer than that, so this posts the
images as a reply-thread: each post carries up to 4 images, and every
post after the first replies to the previous one so they render as one
thread on a viewer's timeline.

Requires env vars BLUESKY_HANDLE and BLUESKY_APP_PASSWORD (an app
password from bsky.app -> Settings -> App Passwords, not the main login
password).

Usage:
    python3 post_bluesky.py out/ repo_data.json captions.json
    python3 post_bluesky.py out/ repo_data.json captions.json --dry-run
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
    ap.add_argument("--dry-run", action="store_true", help="build the thread but don't call the Bluesky API")
    args = ap.parse_args()

    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not args.dry_run and not (handle and app_password):
        print("Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.", file=sys.stderr)
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
    thread_text = [captions["bluesky"]] + [
        f"({i}/{len(image_chunks)}) more from today's trending ↓" for i in range(2, len(image_chunks) + 1)
    ]

    if args.dry_run:
        print(f"[dry-run] would post {len(image_chunks)}-part thread to Bluesky as {handle or '<unset>'}:")
        for i, (imgs, text) in enumerate(zip(image_chunks, thread_text), 1):
            print(f"  part {i}: {[os.path.basename(p) for p in imgs]}")
            print(f"    text: {text!r}")
        return

    from atproto import Client, models

    client = Client()
    client.login(handle, app_password)

    root_ref = None
    parent_ref = None
    for imgs, alt_group, text in zip(image_chunks, alt_chunks, thread_text):
        image_bytes = [open(p, "rb").read() for p in imgs]
        reply_to = None
        if parent_ref is not None:
            reply_to = models.AppBskyFeedPost.ReplyRef(root=root_ref, parent=parent_ref)

        resp = client.send_images(text=text, images=image_bytes, image_alts=alt_group, reply_to=reply_to)
        ref = models.create_strong_ref(resp)
        if root_ref is None:
            root_ref = ref
        parent_ref = ref
        print(f"Posted: {resp.uri}")

    print("Bluesky thread complete.")


if __name__ == "__main__":
    main()
