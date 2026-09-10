# Demo recording plan

## Why the recording carries the weight

Since GitHub restricted the stargazer-listing endpoint to admins and
collaborators (July 2026), a reviewer **cannot re-run this workflow** against
your repo without your token and access. So the exported `lead-sniper.workflow.json`
is a read-only artifact for them, and the **recording plus the Slack screenshot
are the actual proof** that it works end to end. Record it so it is
self-evidently a real event, not a staged screen.

## Before you hit record

1. n8n running, `lead-sniper.workflow.json` imported.
2. Credentials assigned: **GitHub PAT (Header Auth)** on the 3 GitHub nodes,
   **OpenAi account** on *Generate Sales Pitch*.
3. Env var `SLACK_WEBHOOK_URL` set on the n8n instance.
4. `Set Config` -> `repoOwner` / `repoName` = your demo repo
   (`Shaurya55555/yellowai-lead-sniper-demo`).
5. A second GitHub account ready, ideally one with `> 100` followers or
   `> 50` public repos. If not, set `minFollowers` to `0` for the demo run.
6. Open the n8n **executions** panel and the browser **console** (the code
   nodes print `[lead-sniper] ...` trace lines).

## Recording (target 2 to 3 minutes)

| Time | Show | Say |
| --- | --- | --- |
| 0:00-0:20 | The workflow canvas, left to right | "Scheduled poll of one repo's stargazers. New influential star becomes an AI-written lead in Slack." |
| 0:20-0:35 | `Set Config` + the two sticky notes | "Config in one node. The GitHub stargazer endpoint is admin/collaborator-only since July 2026, so this points at a repo I own." |
| 0:35-0:50 | Click **Execute Workflow** (run 1) | "First run is a baseline: it records the current newest star and posts nothing." Show the `[lead-sniper] baseline run` log and the empty output. |
| 0:50-1:05 | The GitHub demo repo, then star it from the second account | "Now a genuinely new star from an account with N followers." |
| 1:05-1:30 | **Execute Workflow** again (run 2). Walk the execution: Discover Last Page -> Resolve Last Page -> Guard -> Poll -> Filter New Stargazers | Point at the trace lines: `discovery: lastPage=1 rateRemaining=...`, `1 new stargazer(s) since ...`. |
| 1:30-1:45 | *Enrich: Get User Profile* output, then *Filter: High-Value Lead* | "Full profile pulled, `followers > 100 OR public_repos > 50` passes." |
| 1:45-2:00 | *Generate Sales Pitch* output | The one-sentence pitch. |
| 2:00-2:15 | Slack channel | The Block Kit card: name, company, followers, repos, bio, AI pitch, profile link. |
| 2:15-2:45 | `LOGIC_LOG.md` on screen | "Rate limits: PAT auth, ETag conditional requests returning 304 that don't spend the primary quota, Link-header paging, watermark, and typed retry rules." |

## Optional second take: the quiet path

Run the workflow once more with no new star and show the
`[lead-sniper] 304 Not Modified: no new stars, ending cycle` line. That proves
the conditional-request path works, which is the core of the Logic Log.
