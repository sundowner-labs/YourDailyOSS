#!/usr/bin/env python3
"""
Generate a swipeable carousel (title card + one card per repo + CTA card)
from a list of GitHub repos, for posting to Instagram/TikTok (native carousel)
or as a multi-image post on X/Bluesky/Mastodon.

Usage:
    python3 make_carousel.py repo_data.json out_dir --handle "@yourhandle" --link "yourlink.co/repo1"
"""
import json
import os
import sys
import argparse
import textwrap
from datetime import date
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350  # 4:5, works for IG carousel + fine on other platforms

# --- palette (dark, GitHub-adjacent, high contrast) ---
BG = (13, 17, 23)          # GitHub dark bg
BG_ACCENT = (22, 27, 34)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (63, 185, 80)     # GitHub green
ACCENT2 = (88, 166, 255)   # GitHub blue

def _first_existing(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# Searched in order; works on GitHub Actions (ubuntu-latest), Windows, and macOS.
FONT_DIR_BOLD = _first_existing([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
])
FONT_DIR_REG = _first_existing([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
])
FONT_MONO = _first_existing([
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/Library/Fonts/Courier New.ttf",
])

if not (FONT_DIR_BOLD and FONT_DIR_REG and FONT_MONO):
    raise RuntimeError(
        "Could not find system fonts (bold/regular/mono). Install DejaVu fonts "
        "(Linux), or check Arial/Consolas are present (Windows)."
    )

_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def wrap_text(draw, text, f, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def base_canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # subtle top/bottom accent bars
    d.rectangle([0, 0, W, 10], fill=ACCENT)
    return img, d


def draw_star(d, cx, cy, r, color):
    import math
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.4
        points.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    d.polygon(points, fill=color)


def footer(d, handle, page_label):
    d.rectangle([0, H - 90, W, H], fill=BG_ACCENT)
    d.text((60, H - 62), handle, font=font(FONT_DIR_BOLD, 30), fill=ACCENT)
    tw = d.textlength(page_label, font=font(FONT_DIR_REG, 26))
    d.text((W - 60 - tw, H - 58), page_label, font=font(FONT_DIR_REG, 26), fill=MUTED)


def title_card(handle, tagline, n_repos, total_cards, out_path):
    img, d = base_canvas()
    today = date.today().strftime("%B %d, %Y")
    d.text((60, 140), "TODAY'S TOP", font=font(FONT_DIR_BOLD, 46), fill=MUTED)
    d.text((60, 195), "GITHUB REPOS", font=font(FONT_DIR_BOLD, 88), fill=FG)
    d.text((60, 300), today, font=font(FONT_DIR_REG, 34), fill=ACCENT2)

    d.text((60, 460), f"{n_repos} repos worth", font=font(FONT_DIR_REG, 40), fill=FG)
    d.text((60, 510), "your attention today", font=font(FONT_DIR_REG, 40), fill=FG)

    if tagline:
        lines = wrap_text(d, tagline, font(FONT_DIR_REG, 30), W - 120)
        y = 620
        for line in lines:
            d.text((60, y), line, font=font(FONT_DIR_REG, 30), fill=MUTED)
            y += 40

    d.text((60, H - 260), "SWIPE →", font=font(FONT_DIR_BOLD, 42), fill=ACCENT)
    footer(d, handle, f"1 / {total_cards}")
    img.save(out_path)


def repo_card(repo, idx, total_cards, handle, out_path):
    img, d = base_canvas()
    d.text((60, 70), f"#{idx + 1}", font=font(FONT_DIR_BOLD, 40), fill=ACCENT)

    name = repo["full_name"]
    name_font = font(FONT_DIR_BOLD, 58 if len(name) < 26 else 44)
    lines = wrap_text(d, name, name_font, W - 120)
    y = 150
    for line in lines[:2]:
        d.text((60, y), line, font=name_font, fill=FG)
        y += name_font.size + 10

    y += 20
    desc_font = font(FONT_DIR_REG, 34)
    for line in wrap_text(d, repo.get("description") or "", desc_font, W - 120)[:5]:
        d.text((60, y), line, font=desc_font, fill=MUTED)
        y += 44

    # stat chips
    chip_y = y + 40
    chips = [
        (f"{repo['stars']:,} stars", ACCENT2, True),
        (f"+{repo['stars_today']:,} today", ACCENT, False),
        (repo.get("language") or "N/A", FG, False),
    ]
    x = 60
    chip_font = font(FONT_DIR_BOLD, 28)
    for label, color, has_star in chips:
        tw = d.textlength(label, font=chip_font)
        pad = 24
        icon_w = 34 if has_star else 0
        d.rounded_rectangle([x, chip_y, x + tw + pad * 2 + icon_w, chip_y + 56], radius=28,
                             outline=color, width=3)
        text_x = x + pad
        if has_star:
            draw_star(d, x + pad + 14, chip_y + 28, 15, color)
            text_x += icon_w
        d.text((text_x, chip_y + 12), label, font=chip_font, fill=color)
        x += tw + pad * 2 + icon_w + 20
        if x > W - 200:
            x = 60
            chip_y += 76

    url_font = font(FONT_MONO, 26)
    d.text((60, H - 150), repo["url"].replace("https://", ""), font=url_font, fill=MUTED)

    footer(d, handle, f"{idx + 2} / {total_cards}")
    img.save(out_path)


def cta_card(handle, headline, subtext, link, monetization_note, total_cards, out_path):
    img, d = base_canvas()
    headline_font = font(FONT_DIR_BOLD, 64 if len(headline) < 22 else 48)
    y = 200
    for line in wrap_text(d, headline, headline_font, W - 120)[:2]:
        d.text((60, y), line, font=headline_font, fill=FG)
        y += headline_font.size + 10

    y += 30
    for line in wrap_text(d, subtext, font(FONT_DIR_REG, 38), W - 120)[:3]:
        d.text((60, y), line, font=font(FONT_DIR_REG, 38), fill=MUTED)
        y += 48

    y += 40
    if link:
        d.rounded_rectangle([60, y, W - 60, y + 80], radius=16, fill=BG_ACCENT, outline=ACCENT, width=3)
        d.text((90, y + 20), link, font=font(FONT_DIR_BOLD, 34), fill=ACCENT)
        y += 80 + 60

    if monetization_note:
        lines = wrap_text(d, monetization_note, font(FONT_DIR_REG, 28), W - 120)
        for line in lines:
            d.text((60, y), line, font=font(FONT_DIR_REG, 28), fill=MUTED)
            y += 38

    footer(d, handle, f"{total_cards} / {total_cards}")
    img.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_json")
    ap.add_argument("out_dir")
    ap.add_argument("--handle", default="@yourhandle")
    ap.add_argument("--link", default="")
    ap.add_argument("--tagline", default="Hand-picked from GitHub Trending, no fluff.")
    ap.add_argument("--cta-headline", default="DON'T MISS TOMORROW'S FIND")
    ap.add_argument("--cta-subtext", default="Follow now -- the next repo like this drops in 24 hours.")
    ap.add_argument("--monetization-note", default="")
    args = ap.parse_args()

    with open(args.repo_json) as f:
        repos = json.load(f)

    os.makedirs(args.out_dir, exist_ok=True)
    total_cards = len(repos) + 2

    paths = []
    p0 = os.path.join(args.out_dir, "00_title.png")
    title_card(args.handle, args.tagline, len(repos), total_cards, p0)
    paths.append(p0)

    for i, repo in enumerate(repos):
        p = os.path.join(args.out_dir, f"{i+1:02d}_repo.png")
        repo_card(repo, i, total_cards, args.handle, p)
        paths.append(p)

    pN = os.path.join(args.out_dir, f"{len(repos)+1:02d}_cta.png")
    cta_card(args.handle, args.cta_headline, args.cta_subtext, args.link, args.monetization_note, total_cards, pN)
    paths.append(pN)

    print("\n".join(paths))


if __name__ == "__main__":
    main()
