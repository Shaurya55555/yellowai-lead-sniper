# Persisted-watermark demo (scheduled runs)

Manual editor runs on n8n Cloud don't persist workflow static data, so the
watermark path only runs under an **activated schedule**. This 15-minute
procedure demonstrates it: run 1 sets the baseline, you star the repo, run 2
detects only that new star, run 3 shows no duplicate (and ideally a `304`).

Run it once, then revert (section 5) and re-export for submission.

---

## 1. Prep (2 min)

1. **Post to Slack** node -> URL -> **Fixed** -> paste your real Slack Incoming
   Webhook URL (`https://hooks.slack.com/services/...`). Swap it back to the
   `{{ $env.SLACK_WEBHOOK_URL }}` placeholder in step 19.
2. **Set Config** -> `minFollowers` = `0`, `minPublicRepos` = `0`
   (your account is the only starrer, so lower the bar for this run).
3. **Schedule Trigger** -> open it -> set **Trigger Interval** to **Minutes**,
   **Minutes Between Triggers** = `1`. (If that field won't take 1, switch the
   node to **Cron expression** mode and enter `* * * * *`.)
4. Make sure the demo repo is **NOT starred** right now:
   github.com/Shaurya55555/yellowai-lead-sniper-demo -> if the button says
   "Starred", click it to unstar.
5. **Save** the workflow (Ctrl+S).

## 2. Activate + baseline run (3 min)

6. Top-right: toggle the workflow **Active** (or **Publish** then set Active).
7. Wait ~90 seconds. Open the **Executions** tab (top of the canvas).
8. You should see **execution #1**. Open it, click **Filter New Stargazers**:
   - OUTPUT = **0 items**
   - This run stored the baseline watermark (epoch, since 0 stars) **and** the
     ETag - and because it's a *scheduled* run, n8n persists them.

## 3. Star the repo -> detection run (3 min)

9. Go to github.com/Shaurya55555/yellowai-lead-sniper-demo -> click **Star**.
10. Wait ~90 seconds for the next scheduled execution.
11. **Executions** tab -> open **execution #2**:
    - **Poll Stargazers (conditional)** -> `statusCode` 200, body has 1 star
    - **Filter New Stargazers** -> **1 item** (`Shaurya55555`) - detected as new
      because its `starred_at` is newer than the persisted watermark
    - **Enrich** -> your profile
    - **Filter: High-Value Lead** -> kept (thresholds are 0/0)
    - **Generate Sales Pitch** -> a Groq sentence
    - **Post to Slack** -> `ok`
12. Check the Slack channel -> a new card. **Screenshot execution #2's node
    trail + the Slack card.**

## 4. No-duplicate run (2 min)

13. Do nothing. Wait ~90 seconds for the next scheduled execution.
14. **Executions** tab -> open **execution #3**:
    - **Poll Stargazers (conditional)** -> ideally `statusCode` **304**
      (`If-None-Match` matched the stored ETag; this response doesn't spend the
      primary rate limit)
    - **Filter New Stargazers** -> **0 items**
    - Nothing after it ran; **no second Slack card**
15. **Screenshot execution #3** (the 304 and the 0 items). This proves the
    watermark + ETag persisted and the same star is not re-notified.

## 5. Revert for submission (2 min)

16. Toggle the workflow **Inactive**.
17. **Schedule Trigger** -> Interval back to **Minutes = 15** (or your original).
18. **Set Config** -> `minFollowers` = `100`, `minPublicRepos` = `50`.
19. **Post to Slack** -> URL -> **Expression** -> `{{ $env.SLACK_WEBHOOK_URL }}`.
20. **Save**. Then **Export JSON** and run the secret grep from `DEMO.md`.
21. Unstar the repo if you want a clean state for the main recording.

## What you now have

The **Executions** list showing:

| # | Filter New Stargazers | Slack | Meaning |
| --- | --- | --- | --- |
| 1 | 0 items | - | baseline watermark + ETag stored |
| 2 | 1 item | card posted | only the genuinely new star detected |
| 3 | 0 items (Poll = 304) | - | persisted state suppresses the duplicate |

In the 2-3 minute recording, open the **Executions** tab and walk these three
rows. That is the persisted-watermark proof.
