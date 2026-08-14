#!/usr/bin/env python3
"""Build the review PR body: captions + inline carousel preview images."""
import glob
import json
import os
import sys


def main():
    content_dir = sys.argv[1]
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["BRANCH_NAME"]

    with open(os.path.join(content_dir, "captions.json"), encoding="utf-8") as f:
        captions = json.load(f)

    images = sorted(glob.glob(os.path.join(content_dir, "out", "*.png")))

    lines = [
        "## Review before publishing",
        "",
        "Merge this PR to post the thread to Bluesky + Mastodon. Close it (without merging) to skip today.",
        "",
        "### Mastodon caption",
        "```",
        captions["mastodon"],
        "```",
        "",
        "### Bluesky caption",
        "```",
        captions["bluesky"],
        "```",
        "",
        "### Carousel preview",
    ]
    for img in images:
        rel = img.replace(os.sep, "/")
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"
        lines.append(f"![{os.path.basename(img)}]({url})")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
