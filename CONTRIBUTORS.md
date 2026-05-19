# Contributors

AI Native Lang (AINL) is a **founder-led, multi-contributor, AI-assisted** open-source project. This page is the canonical list of who has built and maintains it. Live commit counts are in [`tooling/token_status.json`](tooling/token_status.json) under `contributors_local_git` and are refreshable by anyone with `python3 scripts/fetch_token_status.py`.

## Active human maintainers

| | Role |
|---|---|
| **Steven B Hooley** ([`@sbhooley`](https://github.com/sbhooley) · [`x.com/sbhooley`](https://x.com/sbhooley) · [`stevenhooley.com`](https://stevenhooley.com) · [`linkedin.com/in/sbhooley`](https://linkedin.com/in/sbhooley)) | Founder + main maintainer |
| **Terrance Schonleber** (git handle `R4vager`) | Co-maintainer |
| **Kobe Welker** ([`@kobeyaki`](https://github.com/kobeyaki)) | Co-maintainer |

The maintainers triage issues, review PRs, set release direction, and own the published claims in this repo's docs and the marketing site.

## External human contributors

People outside the maintainer team who have landed commits in this repo (at least one non-bot, non-merge commit):

- [`@claysauruswrecks`](https://github.com/claysauruswrecks)

If you have contributed and don't see yourself here, please open a PR against this file — we want the list to be accurate, not curated.

## AI co-authors

AINL is AI-led co-developed: a non-trivial fraction of code, docs, and review on this project has been authored by AI agents working under maintainer direction. We treat AI authorship as a real and accountable part of the project's history rather than something to hide. Distinct agent identities that have landed substantive (non-pure-bot) commits include:

- `hermes_ainl` — Hermes agent contributions
- `ainl king` — AINL King agent (multiple identities)
- `plushify` — Plushify agent
- `ainl agent` — AINL agent

Purely automated bots (Dependabot, MseeP security scans, Renovate, GitHub Actions) are deliberately excluded from this list — they are infrastructure, not authorship.

## How counts are computed

The "contributor metric" we publish (on the website, in `tooling/token_status.json`, anywhere we cite "X human contributors / Y AI co-authors") is derived from the local git history with this procedure:

1. `git log --no-merges --format='%aN <%aE>'` — every commit author across the repo's full history
2. Lowercase substring match against the bot pattern list (`dependabot`, `mseep`, `renovate`, `github-actions`) — these are excluded entirely
3. Lowercase substring match against the AI identity pattern list (`hermes_ainl`, `ainl king`, `ainl-king`, `plushify`, `ainl agent`) — counted toward "AI co-authors"
4. Everyone else is treated as a human contributor and canonicalized via the alias table in `scripts/fetch_token_status.py` (so `sbhooley`, `Steven Hooley`, and `clawdbot` collapse to one row, etc.)

The exact patterns and alias table live in **`scripts/fetch_token_status.py`** under `BOT_PATTERNS`, `AI_PATTERNS`, and `HUMAN_ALIASES`. They are intentionally explicit and editable so the classification is reproducible and reviewable.

For cross-repo numbers (the C3 contributors metric on the marketing site spans **`sbhooley/ainativelang`**, **`sbhooley/ainativelangweb`**, **`sbhooley/armaraos`**, and **`sbhooley/ainl-inference-server`**), the same procedure is run inside each checkout and the canonical-name buckets are unioned. The published number is the count of distinct canonical-name buckets, not a sum of commit counts.

## How to contribute

Project conventions, branch policy, and PR style live in [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: pick a thing, open a PR, expect reviewer feedback (often within 24 hours during active sprints; longer on weekends). AI agents who want to contribute should follow [`AGENTS.md`](AGENTS.md) and respect the same review process as humans.

---

*This file is hand-maintained by the maintainers. If a maintainer or contributor's name, handle, or attribution is wrong here, please open a PR — we will correct it on sight.*
