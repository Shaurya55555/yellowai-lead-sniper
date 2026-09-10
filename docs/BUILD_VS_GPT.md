# Assignment 1: build vs GPT guidance - detailed comparison

Repo: https://github.com/Shaurya55555/yellowai-lead-sniper

This document compares the workflow actually built (`lead-sniper.workflow.json`)
against the plain-English guidance ChatGPT produced for the same assignment:
where they agree, where they differ, why the build chose differently, and the
list of improvements added on top of the brief.

---

## 1. Verdict

GPT's guidance is an accurate description of the **minimum** workflow the brief
asks for. Its 9-step chain is correct and nothing in it conflicts with the
build. The build is that same chain plus a rate-limit layer, because the
Logic Log is the one graded item where submissions visibly differ.

- **Same page on:** the pipeline shape, the enrichment endpoint, the OR filter,
  keeping the AI step simple, the Slack payload contents, polling over webhook
  for this scope, the 4 submission artefacts.
- **Deliberately different on:** how the "watch stargazers" step is built,
  `Filter` vs `IF`, a plain LLM call vs an "AI Agent" node, timestamp watermark
  vs a processed-users set, and the depth of the Logic Log.

---

## 2. The brief, as a checklist

| # | Requirement | In the build |
|---|---|---|
| 1 | Trigger monitoring a repo's stargazers (polling or webhook) | Schedule Trigger + conditional stargazer poll |
| 2 | Enrich each new star via `GET /users/{username}` | `Enrich: Get User Profile` |
| 3 | Proceed only if `followers > 100` OR `public_repos > 50`, else stop | `Filter: High-Value Lead` (combinator OR, strict `gt`) |
| 4 | LLM reads bio + company, returns a 1-sentence sales pitch | `Generate Sales Pitch` (OpenAI chat completions) |
| 5 | Post to Slack/Discord with name, bio, AI pitch | `Build Slack Message` + `Post to Slack` (Block Kit) |
| S | Workflow JSON, Slack screenshot, Logic Log, demo recording | JSON + LOGIC_LOG.md done; screenshot + recording need a run |

---

## 3. Where the build and GPT agree

1. **Pipeline shape.** Trigger, get stargazers, identify new ones, enrich,
   filter, LLM, format, send. Identical ordering.
2. **Enrichment endpoint.** Both use `GET https://api.github.com/users/{login}`
   exactly as the brief names it.
3. **The filter is OR, not AND.** GPT stresses this with worked examples
   (150 followers / 10 repos still qualifies). The build's `Filter` node uses
   `combinator: "or"` with two `gt` conditions. This is the most common place
   people get the brief wrong, and both agree.
4. **"Stop" path.** GPT: `followers <= 100 AND public_repos <= 50 -> STOP`.
   The build's `Filter` node emits only matching items and drops the rest, which
   is the same outcome with no explicit branch.
5. **Keep the AI step simple.** GPT: "You don't need a huge AI agent here."
   The build makes one chat completion call with a constrained prompt
   (one sentence, max 30 words, no preamble). No agent loop, no tools.
6. **Slack message contents.** Both include name, bio, and the AI pitch. The
   build adds company, followers, public repos, and a profile link.
7. **Polling over webhook for this assignment.** GPT recommends polling to avoid
   "a complicated GitHub webhook." The build polls on a schedule. Both treat a
   real webhook as out of scope for the deliverable (the build notes it as the
   better production design in "if I took it further").
8. **Four submission items.** Workflow JSON, screenshot, Logic Log, recording.

---

## 4. Where the build contradicts GPT, and why

### 4.1 "GitHub API" as one step vs a five-node discovery + conditional chain

**GPT:** a single "GitHub API" box that gets stargazers.

**Build:** `Load Sync State -> Discover Last Page -> Resolve Last Page ->
Guard: Rate Budget OK -> Poll Stargazers (conditional)`.

**Why:** two practical facts GPT's description skips.

- `GET /repos/{o}/{r}/stargazers` returns stargazers **oldest-first**. Taking
  page 1, as GPT's wording implies, gives the oldest users and never surfaces a
  new star. The build reads the `Link: <...&page=N>; rel="last"` header and goes
  straight to page N.
- Detecting "new" needs a per-star timestamp. That only appears if you send
  `Accept: application/vnd.github.star+json`. GPT never mentions this header.

The extra nodes also carry the rate-limit strategy: read the saved ETag, check
`X-RateLimit-Remaining`, and issue a conditional request. See section 6.

### 4.2 `Filter` node vs `IF` node

**GPT:** `IF` with two branches.

**Build:** `Filter` (single output, non-matching items dropped).

**Why:** the brief has no action on the "not a lead" side, it just stops.
`Filter` expresses that with one output and no dangling branch. `IF` is the
right choice only if you later want to log, count, or notify on rejected users.
This is a preference, not a correctness issue; swapping in `IF` would not be
wrong.

### 4.3 Plain LLM HTTP call vs "AI Agent / LLM" node

**GPT:** "AI Agent / LLM."

**Build:** HTTP Request to `POST https://api.openai.com/v1/chat/completions`.

**Why:**

- An n8n **AI Agent** node is built for multi-step tool-calling loops.
  Turning a bio into one sentence is a single prompt and a single response, so
  an agent adds machinery with no benefit.
- The HTTP call imports on any n8n instance with no extra node packages.

**Trade-off:** the native **OpenAI ("Message a Model")** node would read more
obviously as "an AI node" in a screenshot. Swapping to it is a reasonable
demo-clarity change; the prompt and wiring stay the same. Left as HTTP for
portability, flagged as optional.

### 4.4 Timestamp watermark vs "compare against previously processed users"

**GPT:** "Compare against previously processed users."

**Build:** stores the newest `starred_at` timestamp in workflow static data and
forwards only stars newer than it.

**Why:** the watermark is O(1) storage and needs no growing list. GPT's
set-of-logins approach is more robust against unstar-then-restar and clock
skew, but grows without bound and still needs somewhere to live (GPT does not
say where). The build notes the seen-set as a possible hardening step. For the
assignment, the watermark is lighter and sufficient.

### 4.5 Poll interval

**GPT:** every 5 minutes. **Build:** every 15 minutes.

**Why:** 15 min keeps the request budget trivial. 5 min is also fine and more
responsive for a demo. One field in the Schedule Trigger. Not a real
disagreement.

### 4.6 The Logic Log itself

**GPT's sample Logic Log:** "poll at controlled intervals, check response
headers for rate-limit info, delay when remaining is low."

**Build's `LOGIC_LOG.md`:** four layers.

1. Authenticate with a PAT (60/h -> 5,000/h).
2. Conditional requests with `If-None-Match` / ETag, so an unchanged poll
   returns **HTTP 304, which does not count against the rate limit**.
3. Structural minimisation: `Link: rel="last"` to jump to the newest page in
   O(1), `star+json` for `starred_at`, a watermark so only genuinely new users
   are enriched.
4. Defend the rest: 1-per-1.5s batching for the secondary (abuse) limit,
   retry-on-fail 3x/5s honouring `Retry-After`, and a guard that skips the
   cycle when `X-RateLimit-Remaining` drops below 100.

Plus a worst-case budget table (~2 to 4 requests per run, about 0.3% of the
hourly budget) and one forward-looking line (repo webhook on the `watch`
event).

**Why against GPT here:** GPT's version is the median answer most candidates
will submit. The brief explicitly asks whether you used "a delay or a specific
header," so naming the specific headers (`If-None-Match`, `ETag`,
`Accept: ...star+json`, `X-RateLimit-Remaining`, `Retry-After`) and the 304
behaviour is what separates the submission from the pack.

---

## 5. Improvements added on top of the brief

### Implemented in the workflow

| Improvement | Where |
|---|---|
| PAT via Header Auth (primary limit 60 -> 5,000/h) | all GitHub HTTP nodes |
| Conditional GET with ETag, 304 short-circuit | `Poll Stargazers (conditional)` + `Filter New Stargazers` |
| ETag + watermark persisted between runs | `Load Sync State` reads, `Filter New Stargazers` writes |
| Jump to newest page via `Link: rel="last"` (O(1), not O(pages)) | `Discover Last Page` + `Resolve Last Page` |
| `Accept: application/vnd.github.star+json` for `starred_at` | both stargazer nodes |
| `starred_at` watermark so only new users are enriched | `Filter New Stargazers` |
| First-run seeding (last 5 stargazers) so a demo produces output | `Filter New Stargazers` |
| Rate-budget guard: skip the cycle if `X-RateLimit-Remaining` < 100 | `Resolve Last Page` + `Guard: Rate Budget OK` |
| 1-per-1.5s batching on enrichment (secondary limit) | `Enrich: Get User Profile` |
| retry-on-fail 3x / 5s on every GitHub, OpenAI, Slack node | all HTTP nodes |
| Pitch degrades to "(pitch unavailable)" instead of breaking the message | `Build Slack Message` |
| Config centralised in one node | `Set Config` |
| On-canvas sticky notes documenting setup + the rate-limit strategy | two Sticky Note nodes |

### Recommended, not yet done

| Improvement | Note |
|---|---|
| Swap HTTP OpenAI call for the native OpenAI node | demo-screenshot clarity only |
| Move the Slack webhook URL out of `Set Config` into a credential or env var | it is a secret sitting in the workflow JSON |
| Escape user bio before putting it in Slack mrkdwn | a bio with `*_<>` can distort formatting |
| Seen-logins dedupe set alongside the watermark | robust against unstar/restar and clock skew |
| Move ETag + watermark to a real datastore | workflow static data is wiped on re-import and not shared across instances |
| Replace polling with a repo webhook on the `watch` event | true real-time, zero trigger-side rate-limit exposure; needs repo admin |
| Enrich the pitch with the user's top repos or languages | currently only bio, company, counts |
| Set a timezone on the Schedule Trigger | |
| Pinned-data smoke test on the trigger node | exercises the two Code nodes without live calls |
| Lead scoring / ranking instead of a flat pass or fail | |

---

## 6. Final build: node-by-node

| Node | Type | Role |
|---|---|---|
| Setup notes / Rate-limit notes | Sticky Note | on-canvas docs |
| Schedule Trigger | scheduleTrigger | every 15 min |
| Set Config | set | repoOwner, repoName, minFollowers (100), minPublicRepos (50), minRateRemaining (100), slackWebhookUrl |
| Load Sync State | code | read `stargazersEtag` + `lastStarredAt` from static data, carry config forward |
| Discover Last Page | httpRequest | stargazers page 1, `star+json`, full response for headers, retry 3x/5s |
| Resolve Last Page | code | parse `Link: rel="last"` -> `lastPage`; read `X-RateLimit-Remaining` |
| Guard: Rate Budget OK | filter | pass only if `rateRemaining >= minRateRemaining`, else the run ends here |
| Poll Stargazers (conditional) | httpRequest | last page, `If-None-Match: <etag>`, `star+json`, full response, `neverError`, retry |
| Filter New Stargazers | code | 304 -> return nothing; else save new ETag, update watermark, return stars newer than watermark (first run: last 5) |
| Enrich: Get User Profile | httpRequest | `GET /users/{login}`, batch 1 / 1500 ms, retry |
| Filter: High-Value Lead | filter | `followers > minFollowers` OR `public_repos > minPublicRepos` |
| Generate Sales Pitch | httpRequest | OpenAI `chat/completions`, gpt-4o-mini, one sentence <= 30 words, retry |
| Build Slack Message | code (per item) | Block Kit payload: header, fields grid, bio, pitch, profile link |
| Post to Slack | httpRequest | POST the payload to the webhook URL, retry |

---

## 7. Left to submit

- [x] Workflow JSON
- [x] Logic Log
- [ ] Screenshot of a successful Slack message (run it in n8n)
- [ ] Demo recording of one execution
