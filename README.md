# GitHub High-Value Lead Sniper (n8n)

Yellow.ai AI Intern assignment 1.

An n8n workflow that watches a popular GitHub repo's stargazers. Whenever an
**influential** user (`followers > 100` OR `public_repos > 50`) stars it, an LLM
writes a one-sentence sales pitch and the workflow posts a formatted card to
Slack.

```
Schedule (15 min)
  -> Set Config           (repo, thresholds, Slack webhook)
  -> Load Sync State      (read ETag + watermark from workflow static data)
  -> Discover Last Page   (stargazers page 1, read Link: rel="last" + X-RateLimit-Remaining)
  -> Resolve Last Page
  -> Guard: Rate Budget OK   (skip this cycle if X-RateLimit-Remaining < 100)
  -> Poll Stargazers (conditional)   (last page, If-None-Match: <etag> -> 304 = free, stop)
  -> Filter New Stargazers   (watermark on starred_at; save new ETag)
  -> Enrich: Get User Profile   (/users/{login}, batched 1 / 1.5s, retry 3x)
  -> Filter: High-Value Lead    (followers > 100 OR public_repos > 50)
  -> Generate Sales Pitch       (OpenAI chat completions, 1 sentence)
  -> Build Slack Message        (Block Kit payload)
  -> Post to Slack              (incoming webhook)
```

See **LOGIC_LOG.md** for the rate-limit strategy (authenticate -> conditional
requests -> structural minimisation -> backoff).

## Import

1. In n8n: **Workflows -> Import from File -> `lead-sniper.workflow.json`**.
2. Open **Set Config** and set:
   - `repoOwner` / `repoName` - e.g. `n8n-io` / `n8n`, or `tiangolo` / `fastapi`
   - `slackWebhookUrl` - your Slack Incoming Webhook URL
   - `minFollowers` / `minPublicRepos` - defaults 100 / 50
3. Create credentials (Credentials -> New -> **Header Auth**):
   - **GitHub PAT (Header Auth)** - name `Authorization`, value `Bearer ghp_xxx`
     (a classic PAT with the `public_repo` scope is enough).
     Assign to: *Discover Last Page*, *Poll Stargazers (conditional)*,
     *Enrich: Get User Profile*.
   - **OpenAI (Header Auth)** - name `Authorization`, value `Bearer sk-xxx`.
     Assign to: *Generate Sales Pitch*.
4. Slack webhook needs no credential - the URL itself is the secret and lives in
   **Set Config**.

## Run / test

- Click **Execute Workflow** on the canvas for a manual run.
- On the **first** run the watermark is empty, so it seeds with the **last 5
  stargazers** of the configured repo - that guarantees the pipeline produces
  output for the demo without waiting for a brand-new star.
- After that, each run only processes stargazers newer than the last run.
- Activate the workflow to poll every 15 minutes.

### Tips for the demo

- To force a specific well-known lead through the filter, temporarily set
  `repoOwner`/`repoName` to a small repo you control and star it from an account
  with >100 followers, or lower `minFollowers` to `0` for one run.
- The OpenAI node can be swapped for the native **OpenAI** / **Basic LLM Chain**
  node if you prefer; the HTTP version is used here so the export imports cleanly
  on any n8n instance.

## Swap Slack for Discord

Replace **Post to Slack** with an HTTP POST to a Discord webhook and change the
body in **Build Slack Message** to Discord's shape:

```js
return { json: { content: header + "\n" + pitch + "\n<https://github.com/" + user.login + ">" } };
```

## Files

```
lead-sniper.workflow.json   the importable n8n workflow
LOGIC_LOG.md                required deliverable: how GitHub rate limits are handled
docs/message-example.md     sample of the Slack card this produces
```

## Deliverables checklist

- [x] Workflow JSON - `lead-sniper.workflow.json`
- [x] Logic Log - `LOGIC_LOG.md`
- [ ] Screenshot of a successful Slack message - run it and capture
- [ ] Demo recording - screen-capture one execution end to end
