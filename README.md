# YourDailyOSS
Finds the best GitHub repos trending today and turns them into scroll-stopping carousels for social.

## Pipeline
```
fetch_trending.py  ->  repo_data.json
make_captions.py   ->  captions.json   (Mastodon + Bluesky caption text, plus the
                                        title card tagline and CTA card headline/
                                        subtext -- captions runs BEFORE the
                                        carousel because the carousel needs this)
make_carousel.py   ->  out/*.jpg       (title card + one card per repo + CTA card;
                                        JPEG because Instagram's API requires it)
post_bluesky.py / post_mastodon.py  -> posts the carousel as a reply-thread
                                        (both platforms cap 4 images/post)
post_instagram.py  -> posts the carousel as a single post (cap is 10 images);
                       needs the images already pushed to the public repo --
                       Instagram fetches them from raw.githubusercontent.com
                       rather than accepting an upload
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

python make_carousel.py repo_data.json out --handle "@yourdailyoss" \
  --tagline "$TAGLINE" --cta-headline "$CTA_HEADLINE" --cta-subtext "$CTA_SUBTEXT"

python post_bluesky.py out repo_data.json captions.json --dry-run
python post_mastodon.py out repo_data.json captions.json --dry-run

# --content-dir must be a path already pushed to --repo on GitHub (or will
# be by the time Instagram fetches the images) -- see the pipeline note above
python post_instagram.py out repo_data.json captions.json \
  --repo owner/name --content-dir content/2026-08-20 --dry-run
```
Drop `--dry-run` to actually post. `make_captions.py` calls the Claude API for
punchier copy -- including a specific, non-generic reason to follow on the CTA
card -- if `ANTHROPIC_API_KEY` is set, and falls back to flatter boilerplate
otherwise. Pass `--link "your-url"` to both `make_carousel.py` and
`make_captions.py` once there's a real CTA destination (newsletter/affiliate
link) -- omitted above since there isn't one yet.

## GitHub Actions
- **daily-post.yml** (cron, see file for run time) fetches trending repos,
  generates the carousel + captions, commits `content/<date>/` to `main` as
  an archive, and posts directly to Bluesky, Mastodon, and Instagram --
  fully automatic, no review step. `workflow_dispatch` triggers a real post
  immediately.

  This replaced an earlier draft-PR-then-merge-to-publish flow (open a PR
  for review, merging it triggered the actual post) that ran for the first
  five days while output quality was being validated. Switch back to that
  model by reintroducing a two-workflow split if auto-publish ever produces
  something you'd rather have caught first.

Repo secrets required for the workflows:
| Secret | Where to get it |
|---|---|
| `BLUESKY_HANDLE` | your `*.bsky.social` handle |
| `BLUESKY_APP_PASSWORD` | bsky.app -> Settings -> App Passwords |
| `MASTODON_INSTANCE_URL` | e.g. `https://mastodon.social` |
| `MASTODON_ACCESS_TOKEN` | your instance -> Settings -> Development -> New Application |
| `INSTAGRAM_ACCOUNT_ID` | numeric ID from `GET https://graph.instagram.com/v25.0/me?fields=user_id,username` |
| `INSTAGRAM_ACCESS_TOKEN` | long-lived token from the Meta App Dashboard -- valid 60 days, see below |
| `ANTHROPIC_API_KEY` | optional, for punchier LLM-written captions |

### Instagram setup

Uses the [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/)
(no Facebook Page required, launched July 2024). App Review is **not**
required for posting to your own account.

1. Convert the Instagram account to a **Professional (Business or Creator)**
   account: Instagram app -> Settings -> Account type and tools -> Switch to
   professional account.
2. Create a **Business-type app** at [developers.facebook.com](https://developers.facebook.com/apps).
3. Add the **Instagram Platform** product to the app, select
   "Instagram API with Instagram Login," and connect the account from
   step 1.
4. Generate a long-lived access token from the App Dashboard for that
   account -- valid 60 days.
5. Get the account ID: `GET https://graph.instagram.com/v25.0/me?fields=user_id,username&access_token=<token>`.
6. Set `INSTAGRAM_ACCOUNT_ID` (the `user_id` from step 5) and
   `INSTAGRAM_ACCESS_TOKEN` as repo secrets.

**Token expires every 60 days** -- Bluesky's app password and Mastodon's
access token don't expire, but this one does. Before it does, run
`python post_instagram.py --refresh` (reads `INSTAGRAM_ACCESS_TOKEN` from
the environment, prints a new one valid another 60 days) and update the
repo secret with the printed value. Nothing currently automates this
rotation -- worth calendaring a reminder every ~55 days, or scripting it
into a separate scheduled workflow later.
