# Logic Log - How GitHub API rate limits are handled

GitHub's REST API limits:

- **Unauthenticated:** 60 requests / hour / IP.
- **Authenticated (PAT):** 5,000 requests / hour.
- Plus **secondary rate limits** that trigger on bursts of concurrent or
  rapid-fire requests, regardless of the primary budget.

This workflow does four things to stay comfortably inside those limits.

## 1. Authenticate every call with a Personal Access Token

All three GitHub HTTP Request nodes use a **Header Auth** credential
(`Authorization: Bearer ghp_...`). This alone lifts the ceiling from 60/hr to
5,000/hr. A fine-grained token with only `public_repo` read scope is enough.

## 2. Jump straight to the newest stars instead of paginating

The `/repos/{owner}/{repo}/stargazers` endpoint returns stargazers
**oldest-first**, so the new stars are always on the last page. Walking every
page of a repo like `n8n-io/n8n` would be hundreds of requests per run.

Instead:

- **Get Stargazers (headers)** requests page 1 with `fullResponse` enabled so we
  can read the response headers.
- **Resolve Last Page** parses the `Link` header
  (`<...&page=42>; rel="last"`) to get the last page number.
- **Get Latest Stargazers** fetches only that one page.

Cost per run: **2 requests** for discovery, no matter how popular the repo is.

## 3. A watermark so we only enrich genuinely new stars

**Filter New Stargazers** (Code node) stores the most recent `starred_at`
timestamp in `$getWorkflowStaticData('global').lastStarredAt`. On the next run it
keeps only stargazers newer than that timestamp. Steady state is usually 0-2 new
users per 15-minute run, so the expensive per-user enrichment call almost never
fires more than a couple of times.

(The `Accept: application/vnd.github.star+json` header is what makes the API
include the `starred_at` field needed for this.)

## 4. Throttle the per-user enrichment calls

**Enrich: Get User Profile** uses the HTTP Request node's built-in **Batching**
option: `batchSize = 1`, `batchInterval = 1500 ms`. Even if a burst of new
stargazers arrives, profiles are fetched one every 1.5 s rather than all at once,
which keeps us clear of the secondary abuse-detection limits.

## Budget math (worst case, per 15-min run)

| Step | Requests |
| --- | --- |
| Discover last page | 1 |
| Fetch last page of stargazers | 1 |
| Enrich new users (typical) | 0-2 |
| OpenAI pitch (not GitHub) | per lead |
| Slack post (not GitHub) | per lead |
| **GitHub total** | **~2-4 / run -> ~16 / hour** |

That is 0.3% of the authenticated hourly budget.

## What I'd add for production

- Read `X-RateLimit-Remaining` / `X-RateLimit-Reset` from the response headers
  and pause the workflow if `Remaining` drops below a threshold.
- Handle HTTP 403 + `Retry-After` with an exponential backoff (n8n's HTTP node
  "Retry On Fail" covers the simple case).
- Move the watermark from workflow static data to a real store (Postgres / Redis)
  so it survives workflow re-imports.
