# GitHub High-Value Lead Sniper (n8n)

Yellow.ai AI Intern assignment 1.

An n8n workflow that watches a GitHub repo's stargazers. Whenever an
**influential** user (`followers > 100` OR `public_repos > 50`) stars it, an LLM
writes a one-sentence sales pitch and the workflow posts a formatted card to
Slack.

> **GitHub API note:** since July 2026 the stargazer-listing endpoint only
> returns data for repos where your token is an **admin or collaborator**
> ([changelog](https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-to-public-api-endpoints-and-ui-views/)).
> Point the workflow at a repo you control. See `LOGIC_LOG.md`.

```
Schedule (15 min)
  -> Set Config           (repo, thresholds)
  -> Load Sync State      (read ETag + watermark from workflow static data)
  -> Discover Last Page   (stargazers page 1, read Link: rel="last" + X-RateLimit-Remaining)
  -> Resolve Last Page
  -> Guard: Rate Budget OK   (skip this cycle if X-RateLimit-Remaining < minRateRemaining)
  -> Poll Stargazers (conditional)   (newest page, If-None-Match: <etag> -> 304 = free, stop)
  -> Filter New Stargazers   (baseline on first run; then watermark on starred_at; save new ETag)
  -> Enrich: Get User Profile   (/users/{login}, serialised 1 / 1.5s, retry 3x)
  -> Filter: High-Value Lead    (followers > 100 OR public_repos > 50)
  -> Generate Sales Pitch       (HTTP POST to an OpenAI-compatible chat API, 1 sentence)
  -> Build Slack Message        (Block Kit payload, bio escaped for mrkdwn)
  -> Post to Slack              (webhook URL from $env.SLACK_WEBHOOK_URL)
```

See **LOGIC_LOG.md** for the rate-limit strategy (authenticate -> conditional
requests -> structural minimisation -> typed retry rules) and **DEMO.md** for the
recording plan.

**Why polling, not a webhook:** a repo webhook on the `watch` event would be
simpler and real-time, but the assignment specifically asks how API rate limits
were handled, and polling is where that question has an answer. The webhook is
noted as the production trigger in `LOGIC_LOG.md`.

## The pitch step (LLM)

`Generate Sales Pitch` is a plain **HTTP Request** to an **OpenAI-compatible**
`chat/completions` endpoint, so any provider works by changing three things:
the node **URL**, the **Header Auth** credential (`Authorization: Bearer <key>`),
and `openAiModel` in **Set Config**.

The demonstration uses **Groq**
(`https://api.groq.com/openai/v1/chat/completions`, model `qwen/qwen3.8-27b`)
because the supplied OpenAI key returned `insufficient_quota`. For OpenAI, use
`https://api.openai.com/v1/chat/completions` + an `sk-...` key + e.g.
`gpt-4o-mini` - no other change.

## Watermark persistence on n8n Cloud

n8n Cloud persists workflow static data (the ETag + `lastStarredAt` watermark)
only across **scheduled/active** executions, not **manual editor** ones. So
*Filter New Stargazers* uses an epoch floor and processes the current stargazers
when no watermark is stored - this keeps manual testing deterministic. An
activated schedule persists the watermark and emits only genuinely new stars.
See `DEMO.md` to demonstrate the persisted path.

## Import

1. In n8n: **Workflows -> Import from File -> `lead-sniper.workflow.json`**
2. Open **Set Config** and set:
   - `repoOwner` / `repoName` - **a repo you admin** (e.g.
     `Shaurya55555` / `yellowai-lead-sniper-demo`)
   - `minFollowers` / `minPublicRepos` - defaults 100 / 50
   - `minRateRemaining` - default 100
   - `openAiModel` - default `qwen/qwen3.8-27b` (Groq); change here, not in the node
3. Slack webhook:
   - Local n8n: set env var `SLACK_WEBHOOK_URL`; *Post to Slack* reads
     `{{ $env.SLACK_WEBHOOK_URL }}`.
   - n8n Cloud (`$env` is blocked): add an n8n **Variable** `SLACK_WEBHOOK_URL`
     and change *Post to Slack* URL to `{{ $vars.SLACK_WEBHOOK_URL }}`, or paste
     the URL directly and remove it before exporting.
4. Create credentials:
   - **GitHub PAT (Header Auth)** (Credentials -> New -> **Header Auth**) - name
     `Authorization`, value `Bearer <token>` (classic PAT `repo` scope, or a
     `gho_` token from `gh auth token`).
     Assign to: *Discover Last Page*, *Poll Stargazers (conditional)*,
     *Enrich: Get User Profile*.
   - **LLM API (Header Auth)** (Credentials -> New -> **Header Auth**) - name
     `Authorization`, value `Bearer <key>` (a free Groq key from
     `console.groq.com`, or an OpenAI `sk-...` key).
     Assign to: *Generate Sales Pitch*.

## Run / test

See `DEMO.md` for the full sequence. Short version:

1. **Execute Workflow** once. With no stored watermark it processes the current
   stargazers (n8n Cloud does not persist static data between manual runs, so it
   falls back to an epoch floor). On an empty repo this emits nothing.
2. Star the repo. **Execute** again -> the star flows through enrichment ->
   filter -> pitch -> Slack (if it clears `followers > 100 OR public_repos > 50`).
3. Lower `minFollowers` / `minPublicRepos` for a run if your account does not
   clear the threshold, to exercise the qualifying path.
4. Activate the workflow to poll every 15 minutes (production runs do persist the
   watermark).

## Swap Slack for Discord

Replace **Post to Slack** with an HTTP POST to a Discord webhook and change the
body in **Build Slack Message** to Discord's shape:

```js
return { json: { content: header + "\n" + pitch + "\n<https://github.com/" + user.login + ">" } };
```

## Files

```
lead-sniper.workflow.json              the n8n workflow (import this)
LOGIC_LOG.md                           required deliverable: GitHub rate-limit handling
DEMO.md                                recording plan and shot list
verify/                                Python re-implementation used to validate the
                                       pipeline against the live GitHub API (not a deliverable)
docs/message-example.md                sample of the Slack card this produces
docs/BUILD_VS_GPT.md                   design-decision comparison notes
```

The pipeline logic (conditional requests / 304, watermark, `Link` paging,
enrichment, the `followers > 100 OR public_repos > 50` filter, Slack payload)
was run end to end against the real GitHub API on 2026-09-11; transcripts in
`verify/SAMPLE_RUN.md`.

## Deliverables checklist

- [x] Workflow JSON - `lead-sniper.workflow.json`
- [x] Logic Log - `LOGIC_LOG.md`
- [ ] Screenshot of a successful Slack message - run it and capture
- [ ] Demo recording - follow `DEMO.md`
