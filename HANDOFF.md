# GitHub Trending → Social Carousel Agent — Handoff

Built in a Claude (Cowork) cloud session; handing off to Claude Code in VS Code
to finish (create the repo, wire up real posting, GitHub Actions schedule).

## Goal
Daily agent that finds the best/trending GitHub repos, turns them into a
swipeable image carousel + caption, and posts to social platforms to build an
audience / generate cash flow (affiliate links, newsletter traffic, and/or
sponsorships once there's an audience).

## Decisions made so far
- **Platforms, phase 1:** Bluesky + Mastodon (both have free, simple REST
  APIs). X was considered but needs a paid API tier (~$100+/mo) to post —
  deferred. Instagram/TikTok have no open posting API for personal
  automation (Meta/TikTok business app review required) — deferred, would
  start as manually-posted carousels if pursued.
- **Workflow:** Draft & review, not fully autonomous — content is generated
  first and approved before it publishes (at least initially; easy to flip
  to auto-post later once there's confidence in output quality).
- **Monetization:** all three of — affiliate/referral links, driving traffic
  to the user's own newsletter/blog, and building an audience for
  sponsorships later. No specific affiliate programs or newsletter URL
  chosen yet — still needed from the user.
- **Repo selection:** GitHub Trending page (daily), general/broad mix (not
  filtered to one topic/language).
- **Post format:** swipeable carousel — title card, one card per repo
  (name, one-liner, star count + stars-today, language), CTA card at the
  end with a link and short monetization note. Works natively on
  Instagram/TikTok; renders as a multi-image post on X/Bluesky/Mastodon.
- **Caption style:** the first draft (see `captions_demo.txt`) was too flat/
  spec-sheet-y. User asked for punchier copy — hook opener leading with the
  most surprising stat, one "why this matters" line per repo instead of the
  raw GitHub description, and an engagement-driving close (a question to
  drive replies/comments, since that's what these platforms' algorithms
  reward). **`make_captions.py` still needs to be rewritten in this style —
  this was the very next task when the session ended.** A sample of the
  target tone is in this conversation's history (search for "A pentesting
  AI just picked up 2.8K stars").

## Key technical finding from the cloud sandbox (may not apply in VS Code)
The Cowork cloud sandbox has locked-down outbound networking — it can reach
a few package registries and do read-only web fetches, but cannot make
direct authenticated API calls to arbitrary hosts like `bsky.social` or
`mastodon.social`, and GitHub API access there is restricted to
pre-configured repos (not a general Search API). This is why:
1. Trending data was pulled via a page-fetch/summarize tool rather than the
   GitHub Search API directly (works, but summarized by a small model —
   worth switching to a real API call for exact numbers once you have
   normal network access in VS Code / GitHub Actions).
2. Real posting was planned via Chrome browser automation (driving the
   user's logged-in browser) rather than direct API calls, as a stopgap.

**In a normal dev environment (VS Code / GitHub Actions), none of these
restrictions apply** — use the real GitHub Search/REST API
(`GET /search/repositories?q=...&sort=stars`, or scrape/call
`github.com/trending` directly) and call the Bluesky (AT Protocol XRPC) and
Mastodon (REST) APIs directly with `requests` — no need for the browser
workaround. This is the better architecture for a repo running on a
schedule via GitHub Actions.

## What's built (this folder)
- `repo_data.json` — sample trending data (today's real GitHub Trending
  list, captured manually) used to test the generators.
- `make_carousel.py` — generates the image carousel with Pillow (title card
  + one card per repo + CTA card). Tested, works, output in `out/`.
- `make_captions.py` — generates captions. **Currently flat/dry —
  needs the punchier rewrite described above.**
- `out/` — sample generated carousel images from a test run.

## Still to do
1. Rewrite `make_captions.py` for punchier, hook-driven, engagement-first
   copy (see style note above).
2. Replace the manual/summarized trending fetch with a real GitHub API call
   or trending scrape (no sandbox restrictions in VS Code).
3. Create the GitHub repo (user is doing this from VS Code directly).
4. Build the actual Bluesky + Mastodon posting calls (`requests` to their
   REST APIs — no SDK required, though `atproto` and `Mastodon.py` PyPI
   packages are fine to use if pip works in that environment).
5. GitHub Actions workflow: daily cron trigger, generate content, then
   either (a) open a PR/issue with the draft for approval before a second
   workflow posts it, or (b) post directly once the user trusts the output
   — matches the "draft & review first, consider autonomous later"
   preference above.
6. Get concrete values still needed from the user: Bluesky handle + app
   password, Mastodon instance + access token, newsletter/blog URL and/or
   specific affiliate programs to link, preferred daily run time, and how
   many repos per carousel (5 was used as a placeholder default).
