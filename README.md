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
  -> Generate Sales Pitch       (native OpenAI node, 1 sentence)
  -> Build Slack Message        (Block Kit payload, bio escaped for mrkdwn)
  -> Post to Slack              (webhook URL from $env.SLACK_WEBHOOK_URL)
```

See **LOGIC_LOG.md** for the rate-limit strategy (authenticate -> conditional
requests -> structural minimisation -> typed retry rules).

## Import

1. In n8n: **Workflows -> Import from File -> `lead-sniper.workflow.json`**.
2. Open **Set Config** and set:
   - `repoOwner` / `repoName` - **a repo you admin** (e.g.
     `Shaurya55555` / `yellowai-lead-sniper-demo`)
   - `minFollowers` / `minPublicRepos` - defaults 100 / 50
   - `minRateRemaining` - default 100
3. Set an environment variable on the n8n instance:
   - `SLACK_WEBHOOK_URL` - your Slack Incoming Webhook URL. Read by
     *Post to Slack* as `{{ $env.SLACK_WEBHOOK_URL }}`; it is never stored in the
     workflow JSON.
4. Create credentials:
   - **GitHub PAT (Header Auth)** (Credentials -> New -> **Header Auth**) - name
     `Authorization`, value `Bearer ghp_xxx` (classic PAT, `repo` scope).
     Assign to: *Discover Last Page*, *Poll Stargazers (conditional)*,
     *Enrich: Get User Profile*.
   - **OpenAi account** (Credentials -> New -> **OpenAI**) - your OpenAI API key.
     Assign to: *Generate Sales Pitch*.

## Run / test

The first run is a **baseline** run:

1. Click **Execute Workflow**. With no stored watermark, *Filter New Stargazers*
   records the current newest star and emits nothing. This is expected: zero
   Slack messages on run 1.
2. Star the repo from a second GitHub account (ideally one with > 100 followers
   or > 50 public repos so it passes the filter).
3. **Execute Workflow** again. The new star is now newer than the watermark, so
   it flows through enrichment -> filter -> pitch -> Slack.
4. Activate the workflow to poll every 15 minutes.

### Tips for the demo

- Lower `minFollowers` to `0` for one run if your second account does not clear
  the threshold.
- `Generate Sales Pitch` uses the native n8n **OpenAI** node (resource *Text*,
  operation *Message a model*). Swap the model in that node if `gpt-4o-mini` is
  not enabled on your key.

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
