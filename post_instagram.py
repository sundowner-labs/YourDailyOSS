#!/usr/bin/env python3
"""
Post the carousel to Instagram via the "Instagram API with Instagram Login"
(no Facebook Page required -- see https://developers.facebook.com/docs/
instagram-platform/instagram-api-with-instagram-login/). App Review is not
required for posting to your own account.

Instagram's media endpoint only accepts a publicly-fetchable image_url, not
uploaded bytes, and only JPEG. Rather than host images separately, this
relies on the fact that daily-post.yml already commits each day's carousel
to the public GitHub repo before this script runs -- so it builds
raw.githubusercontent.com URLs from --repo/--branch/--content-dir instead
of uploading anything itself.

Instagram's carousel cap is 10 images, so our 7-image carousel (title +
up to 5 repos + CTA) posts as a single post -- no reply-thread chunking
like Bluesky/Mastodon need.

Requires env vars:
  INSTAGRAM_ACCOUNT_ID    -- numeric Instagram professional account ID
                             (GET https://graph.instagram.com/v25.0/me
                             ?fields=user_id,username&access_token=...)
  INSTAGRAM_ACCESS_TOKEN  -- long-lived token minted from the Meta App
                             Dashboard. Valid 60 days -- refresh before
                             it expires with --refresh (below).

Usage:
    python3 post_instagram.py out repo_data.json captions.json \
        --repo owner/name --content-dir content/2026-08-20
    python3 post_instagram.py out repo_data.json captions.json \
        --repo owner/name --content-dir content/2026-08-20 --dry-run

    # Rotate the long-lived token before it expires (run manually, then
    # update the INSTAGRAM_ACCESS_TOKEN repo secret with the printed value):
    python3 post_instagram.py --refresh
"""
import argparse
import glob
import json
import os
import sys
import time

import requests

API_HOST = "https://graph.instagram.com"
API_VERSION = "v25.0"


def api_url(path):
    return f"{API_HOST}/{API_VERSION}/{path}"


def refresh_token():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        print("Set INSTAGRAM_ACCESS_TOKEN.", file=sys.stderr)
        sys.exit(1)
    resp = requests.get(
        f"{API_HOST}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    days = data["expires_in"] // 86400
    print(f"New token (valid {days} days):\n{data['access_token']}")
    print("\nUpdate the INSTAGRAM_ACCESS_TOKEN repo secret with this value.")


def raw_url(repo, branch, content_dir, filename):
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{content_dir}/out/{filename}"


def wait_until_ready(container_id, token, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            api_url(container_id),
            params={"fields": "status_code", "access_token": token},
            timeout=20,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} failed to process")
        time.sleep(3)
    raise TimeoutError(f"Container {container_id} not ready after {timeout}s")


def create_child_container(account_id, token, image_url):
    resp = requests.post(
        api_url(f"{account_id}/media"),
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_carousel_container(account_id, token, child_ids, caption):
    resp = requests.post(
        api_url(f"{account_id}/media"),
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish(account_id, token, creation_id):
    resp = requests.post(
        api_url(f"{account_id}/media_publish"),
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]

    permalink_resp = requests.get(
        api_url(media_id), params={"fields": "permalink", "access_token": token}, timeout=20
    )
    permalink_resp.raise_for_status()
    return permalink_resp.json().get("permalink", f"(media id {media_id})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images_dir", nargs="?")
    ap.add_argument("repo_json", nargs="?")
    ap.add_argument("captions_json", nargs="?")
    ap.add_argument("--repo", help="owner/name of the public GitHub repo the images live in")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--content-dir", help="e.g. content/2026-08-20 -- the path committed to the repo")
    ap.add_argument("--dry-run", action="store_true", help="build the request but don't call the Instagram API")
    ap.add_argument("--refresh", action="store_true", help="refresh the long-lived access token and exit")
    args = ap.parse_args()

    if args.refresh:
        refresh_token()
        return

    if not (args.images_dir and args.repo_json and args.captions_json and args.repo and args.content_dir):
        print("images_dir, repo_json, captions_json, --repo, and --content-dir are all required.", file=sys.stderr)
        sys.exit(1)

    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not args.dry_run and not (account_id and token):
        print("Set INSTAGRAM_ACCOUNT_ID and INSTAGRAM_ACCESS_TOKEN.", file=sys.stderr)
        sys.exit(1)

    with open(args.captions_json, encoding="utf-8") as f:
        captions = json.load(f)

    image_paths = sorted(glob.glob(os.path.join(args.images_dir, "*.jpg")))
    if len(image_paths) < 2:
        print(f"Need at least 2 images for a carousel, found {len(image_paths)}.", file=sys.stderr)
        sys.exit(1)
    if len(image_paths) > 10:
        print(f"Instagram carousels cap at 10 images, found {len(image_paths)}.", file=sys.stderr)
        sys.exit(1)

    urls = [raw_url(args.repo, args.branch, args.content_dir, os.path.basename(p)) for p in image_paths]
    # No Instagram-specific caption yet -- the Mastodon caption fits well
    # within Instagram's 2,200-char limit. Add an "instagram" key to
    # captions.json (with hashtags, which help discovery there unlike on
    # Bluesky/Mastodon) later if it's worth the extra LLM-prompt surface.
    caption = captions.get("instagram") or captions["mastodon"]

    if args.dry_run:
        print(f"[dry-run] would post a {len(urls)}-image carousel to Instagram account {account_id or '<unset>'}:")
        for u in urls:
            print(f"  {u}")
        print(f"  caption: {caption!r}")
        return

    child_ids = []
    for url in urls:
        cid = create_child_container(account_id, token, url)
        wait_until_ready(cid, token)
        child_ids.append(cid)

    carousel_id = create_carousel_container(account_id, token, child_ids, caption)
    wait_until_ready(carousel_id, token)
    permalink = publish(account_id, token, carousel_id)
    print(f"Posted: {permalink}")


if __name__ == "__main__":
    main()
