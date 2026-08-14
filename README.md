# YourDailyOSS
Finds the best GitHub repos trending today and turns them into scroll-stopping carousels for social.

## Pipeline
```
fetch_trending.py  ->  repo_data.json
make_captions.py   ->  captions.json   (Mastodon + Bluesky caption text, plus the
                                        title card tagline and CTA card headline/
                                        subtext -- captions runs BEFORE the
                                        carousel because the carousel needs this)
make_carousel.py   ->  out/*.png       (title card + one card per repo + CTA card)
post_bluesky.py / post_mastodon.py  -> posts the carousel as a reply-thread
                                        (both platforms cap 4 images/post)
```

Run locally:
```
pip install -r requirements.txt
python fetch_trending.py --limit 5 --out repo_data.json
python make_captions.py repo_data.json --out captions.json

# pull the carousel copy make_captions.py just wrote (jq, or read captions.json by hand)
TAGLINE=$(jq -r '.tagline' captions.json)
CTA_HEADLINE=$(jq -r '.cta_headline' captions.json)
CTA_SUBTEXT=$(jq -r '.cta_subtext' captions.json)

python make_carousel.py repo_data.json out --handle "@yourdailyoss.bsky.social" \
  --tagline "$TAGLINE" --cta-headline "$CTA_HEADLINE" --cta-subtext "$CTA_SUBTEXT"

python post_bluesky.py out repo_data.json captions.json --dry-run
python post_mastodon.py out repo_data.json captions.json --dry-run
```
Drop `--dry-run` to actually post. `make_captions.py` calls the Claude API for
punchier copy -- including a specific, non-generic reason to follow on the CTA
card -- if `ANTHROPIC_API_KEY` is set, and falls back to flatter boilerplate
otherwise. Pass `--link "your-url"` to both `make_carousel.py` and
`make_captions.py` once there's a real CTA destination (newsletter/affiliate
link) -- omitted above since there isn't one yet.

## GitHub Actions
- **daily-draft.yml** (cron, see file for run time) fetches trending repos,
  generates the carousel + captions into `content/<date>/`, and opens a PR
  for review with the images and captions inline.
- **publish-on-merge.yml** fires when a `draft/*` PR is merged and posts
  that day's content to Bluesky + Mastodon. Closing the PR instead of
  merging skips the day -- nothing posts automatically.

Repo secrets required for the workflows:
| Secret | Where to get it |
|---|---|
| `BLUESKY_HANDLE` | your `*.bsky.social` handle |
| `BLUESKY_APP_PASSWORD` | bsky.app -> Settings -> App Passwords |
| `MASTODON_INSTANCE_URL` | e.g. `https://mastodon.social` |
| `MASTODON_ACCESS_TOKEN` | your instance -> Settings -> Development -> New Application |
| `ANTHROPIC_API_KEY` | optional, for punchier LLM-written captions |
