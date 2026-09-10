# Demo recording plan

## Why the recording carries the weight

Since GitHub restricted the stargazer-listing endpoint to admins and
collaborators (July 2026), a reviewer **cannot re-run this workflow** against
your repo without your token and access. So `lead-sniper.workflow.json` is a
read-only artifact for them, and the **recording plus the Slack screenshot are
the actual proof** it works end to end.

## Before you hit record

1. n8n Cloud instance, `lead-sniper.workflow.json` imported.
2. Credentials assigned:
   - **GitHub PAT (Header Auth)** (`Authorization: Bearer <token>`) on
     *Discover Last Page*, *Poll Stargazers (conditional)*, *Enrich: Get User Profile*.
   - **LLM API (Header Auth)** (`Authorization: Bearer <groq or openai key>`) on
     *Generate Sales Pitch*.
3. *Post to Slack* URL set to your real webhook (n8n Cloud blocks `$env`, so
   paste it in **Fixed** mode for the recording; swap back to
   `{{ $env.SLACK_WEBHOOK_URL }}` before the final export).
4. `Set Config`: `repoOwner`/`repoName` = your demo repo
   (`Shaurya55555/yellowai-lead-sniper-demo`), `openAiModel` = `qwen/qwen3.8-27b`.
5. Repo starred by your account (with the epoch fallback, every manual Execute
   re-detects the current star, so you don't need a fresh star each run).

## Recording (target 2 to 3 minutes)

| Time | Show | Say |
| --- | --- | --- |
| 0:00-0:20 | The canvas, left to right | "Scheduled poll of a repo's stargazers. A new influential star becomes an AI-written lead in Slack." |
| 0:20-0:35 | `Set Config` + the sticky notes; set `minFollowers`/`minPublicRepos` to `0` | "Stargazer listing is admin/collaborator-only since July 2026, so this points at a repo I own. Lowering the threshold so my own account qualifies for the demo." |
| 0:35-0:45 | The GitHub demo repo in a browser tab; click **Star** (unstar first if needed) | "A new star." |
| 0:45-1:30 | Back in n8n -> **Execute workflow**. Walk: *Poll Stargazers* (the `starred_at`), *Filter New Stargazers* (1 item), *Enrich* (followers / public_repos), *Filter: High-Value Lead* (kept) | Point at each node's output. |
| 1:30-1:45 | *Generate Sales Pitch* output | The one-sentence Groq pitch. |
| 1:45-2:00 | Slack channel | The Block Kit card: name, company, followers, repos, bio, AI pitch, profile link. |
| 2:00-2:20 | `Set Config` -> thresholds back to `100` / `50` -> **Execute** -> *Filter: High-Value Lead* **Discarded (1 item)**, nothing after it, no Slack | "A non-qualifying lead is stopped, per the brief." |
| 2:20-2:45 | `LOGIC_LOG.md` on screen | "Rate limits: PAT auth, ETag conditional requests returning 304 that don't spend the primary quota, Link-header paging, watermark, typed retry rules." |

## What was actually tested (2026-09-11, n8n Cloud 2.39.2)

| Run | Set Config | Result |
| --- | --- | --- |
| Baseline | 100 / 50, repo had 0 stars | ran through, *Filter New Stargazers* emitted 0, nothing posted |
| Test A | 0 / 0, repo starred | qualified -> Groq pitch -> **Slack card posted** (HTTP 200) |
| Test B | 100 / 50, repo starred | *Filter: High-Value Lead* -> **Discarded**, no Slack |
| Test C1 (boundary) | `minPublicRepos` = 21 (== actual repo count) | `21 > 21` false -> **Discarded**, no Slack (proves strict `>`, not `>=`) |
| Test C2 (boundary + 1) | `minPublicRepos` = 20 | `21 > 20` true -> qualified -> **Slack card** with a fresh pitch (proves the OR and that Groq is called live each run) |

## Before you export and submit the workflow JSON

Swap *Post to Slack* URL back to `{{ $env.SLACK_WEBHOOK_URL }}`, set thresholds
to `100` / `50`, then Export JSON and confirm none of these appear as a real
value:

```
hooks.slack.com   ghp_<real>   gho_<real>   gsk_<real>   sk-<real>   Bearer <realtoken>
```

Credentials export as `{ id, name }` references, so a clean export has no secret
material. (The committed `lead-sniper.workflow.json` in this repo is already
scrubbed.)
