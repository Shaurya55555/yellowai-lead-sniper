# Sample run transcripts

Run 2026-09-11 against `Shaurya55555/yellowai-lead-sniper-demo` with
`GITHUB_TOKEN=$(gh auth token)`, no LLM key, no Slack webhook.

## 1. Baseline run (repo has 0 stars)

```
[verify] repo=Shaurya55555/yellowai-lead-sniper-demo etag=none watermark=none (baseline run)
  discovery: last_page=1 rate_remaining=4988
  baseline run: recorded watermark 1970-01-01T00:00:00Z, emitting 0
```

## 2. After a new star, default thresholds -> negative case (Test B)

```
[verify] repo=Shaurya55555/yellowai-lead-sniper-demo etag=set watermark=1970-01-01T00:00:00Z
  discovery: last_page=1 rate_remaining=4986
  1 new stargazer(s) since 1970-01-01T00:00:00Z
  filter Shaurya55555: followers=1 public_repos=21 -> dropped
```

`1 > 100 OR 21 > 50` is false, so the flow stops. No Slack payload built.

## 3. Second poll with nothing changed -> conditional request

```
[verify] repo=Shaurya55555/yellowai-lead-sniper-demo etag=set watermark=2026-09-10T21:32:29Z
  discovery: last_page=1 rate_remaining=4989
  poll: 304 Not Modified (no new stars; primary quota not consumed)
```

## 4. New star with thresholds lowered -> positive path (Test A shape)

```
[verify] repo=Shaurya55555/yellowai-lead-sniper-demo etag=set watermark=1970-01-01T00:00:00Z
  discovery: last_page=1 rate_remaining=4978
  1 new stargazer(s) since 1970-01-01T00:00:00Z
  filter Shaurya55555: followers=1 public_repos=21 -> QUALIFIES
  pitch: no LLM key set; using fallback
  pitch: (pitch unavailable)
  slack payload:
{
  "text": ":dart: New high-value lead starred Shaurya55555/yellowai-lead-sniper-demo",
  "blocks": [
    { "type": "section", "text": { "type": "mrkdwn", "text": "*:dart: New high-value lead starred Shaurya55555/yellowai-lead-sniper-demo*" } },
    { "type": "section", "fields": [
      { "type": "mrkdwn", "text": "*Name:*\nSHAURYA BAJPAI" },
      { "type": "mrkdwn", "text": "*Company:*\n-" },
      { "type": "mrkdwn", "text": "*Followers:*\n1" },
      { "type": "mrkdwn", "text": "*Public repos:*\n21" }
    ] },
    { "type": "section", "text": { "type": "mrkdwn", "text": "*Bio:*\n-" } },
    { "type": "section", "text": { "type": "mrkdwn", "text": "*AI sales pitch:*\n(pitch unavailable)" } },
    { "type": "context", "elements": [ { "type": "mrkdwn", "text": "<https://github.com/Shaurya55555|github.com/Shaurya55555>" } ] }
  ]
}
```

With a funded `OPENAI_API_KEY` (or `GROQ_API_KEY` / `GEMINI_API_KEY`) the
`(pitch unavailable)` line is replaced by a one-sentence pitch; with
`SLACK_WEBHOOK_URL` set the payload is POSTed instead of printed.

The repo was left at **0 stars** after these runs so your recorded demo starts clean.
