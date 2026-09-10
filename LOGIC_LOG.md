# Logic Log - GitHub API rate-limit handling

The brief asks whether I used "a delay or a specific header". Both, but a delay
is the last line of defence, not the strategy. The strategy is: **make almost
every poll cost zero requests, then defend what's left.** Four layers, then the
retry rules.

## GitHub API compatibility note

GitHub restricted the public stargazer-listing endpoint
(`GET /repos/{owner}/{repo}/stargazers`) in July 2026: it is now limited to
callers who are an **admin or collaborator** on the repository. An unauthorised
caller gets an authorisation failure, and GitHub may answer `404` rather than
confirm the resource exists. A direct test against `n8n-io/n8n` with a normal
PAT returned `404`. This workflow therefore points at a repository the workflow
owner controls (`Set Config` -> `repoOwner` / `repoName`), and the demonstration
stars that repository from a second account.

All GitHub calls pin `X-GitHub-Api-Version: 2026-03-10` (the current REST API
version) for reproducibility.

The pitch step is a plain HTTP call to an OpenAI-compatible `chat/completions`
endpoint (tested against Groq's free tier, model `qwen/qwen3.8-27b`); swap the
URL, key and `openAiModel` for any other provider.

## Layer 1 - Authenticate: raise the primary ceiling

Every GitHub call carries `Authorization: Bearer <PAT>` through an n8n Header
Auth credential. This moves the primary limit from **60 requests/hour**
(anonymous, per IP) to **5,000 requests/hour**. A classic PAT with the `repo`
scope (or `public_repo` if the demo repository is public) is enough. Nodes:
*Discover Last Page*, *Poll Stargazers (conditional)*, *Enrich: Get User Profile*.

## Layer 2 - Conditional requests: the poll that does not count

*Poll Stargazers (conditional)* sends `If-None-Match: <etag>`, where `<etag>` is
the `ETag` response header saved from the previous run in workflow static data
(`Load Sync State` reads it, `Filter New Stargazers` writes the new one).

When nothing has been starred since the last poll, GitHub returns
**HTTP 304 Not Modified**. Per GitHub's REST documentation, an authorised
conditional request that returns `304` **does not consume the primary REST API
rate limit**. The node uses `neverError` so a 304 does not fail it, and
*Filter New Stargazers* ends the run immediately on a 304.

Steady state for a low-traffic repo: most 15-minute polls are free.

## Layer 3 - Structural minimisation

- **Request the newest page, don't hard-code page 1.**
  `GET /repos/{o}/{r}/stargazers` returns stargazers **oldest-first**, so new
  stars are on the *last* page. *Discover Last Page* reads the
  `Link: <...&page=N>; rel="last"` header and the next call targets page N. On a
  small repo there is one page and the header is absent, so it falls back to
  page 1. This is about not paginating blindly, not a performance win on a small
  repo.
- **The specific header for timestamps.**
  `Accept: application/vnd.github.star+json` makes the API include `starred_at`
  on each stargazer, which is what the "is this new?" check runs on.
- **Watermark.** *Filter New Stargazers* keeps a `lastStarredAt` timestamp in
  static data and forwards only stargazers newer than it, so the
  `GET /users/{login}` enrichment fires for genuinely new users only.
  **Limitation:** this assumes fewer than one page (100) of new stars arrive
  between two polls. A production version would page backward until it reaches
  the watermark, or drop polling for a webhook (see end). When no watermark is
  stored - a genuine first run, or n8n Cloud not persisting static data across
  manual editor executions - it falls back to an epoch floor and processes the
  current stargazers; scheduled (production) runs persist the watermark
  normally.

## Layer 4 - Defend the remainder

**Serialisation.** *Enrich: Get User Profile* is run at **1 request per
1,500 ms** via the HTTP node's batching. This is a conservative
application-level safeguard against burst traffic, not a GitHub-published
number. GitHub's own guidance is to avoid concurrent requests and, for large
volumes of *mutating* requests, wait about a second between them; every call
here is a GET, so the spacing is purely precautionary.

**Retry rules**, by failure type:

| Situation | Signal | Response |
| --- | --- | --- |
| Transient error | `5xx`, connection reset, timeout | retry-on-fail: 3 tries, 5 s apart (bounded backoff) |
| Secondary / abuse limit | `403` or `429` with `Retry-After` | honour `Retry-After`; if absent, back off and retry, escalating if it persists |
| Primary quota exhausted | `X-RateLimit-Remaining: 0` | do **not** retry on a fixed timer; wait until `X-RateLimit-Reset` |

**What the workflow does today, node by node:**

- **Transient errors:** fixed 3x / 5 s retry-on-fail on every HTTP node.
- **Primary budget:** *Guard: Rate Budget OK* reads `X-RateLimit-Remaining` from
  the discovery response and skips the whole cycle when it is below
  `minRateRemaining` (default 100), so the quota is never pushed to zero.
- **`403` / `429` on the poll:** *Filter New Stargazers* inspects the status,
  logs `Retry-After` and `X-RateLimit-Reset`, and ends the cycle. The next
  scheduled run (15 min later) re-polls, which for a scheduled workflow is a
  cleaner recovery than blocking one execution on a long `Wait`.
- **`403` / `429` or any error on enrichment:** the node has
  `onError: continueRegularOutput`, so one failed user is passed through without
  a `followers` / `public_repos` field and is dropped by *Filter: High-Value
  Lead*. The other users in the batch are unaffected.

This is a deliberate "detect, log, defer to the next tick" model rather than an
in-execution retry loop. A production version behind a webhook (see below) would
instead honour `Retry-After` inline.

### Failure policy for the non-GitHub steps

- **Pitch generation fails** (`Generate Sales Pitch`, after 3 retries): the node
  has `onError: continueRegularOutput`, so the qualifying lead still flows to
  *Build Slack Message*, which substitutes `"(pitch unavailable)"` and posts the
  lead anyway. AI being down never silently drops a lead.
- **Slack post fails** (`Post to Slack`, after 3 retries): the execution is
  marked failed. This is intentional - a notification that did not send should
  be loud, and the full lead data is still visible in the preceding nodes.

## Budget, worst case per 15-minute run

| Step | GitHub requests |
| --- | --- |
| Stargazer poll | 1 discovery + 1 conditional poll (often a free 304) |
| Enrich new users | 0 to a few |
| **Total** | **~2-4 / run  ~=  16 / hour  ~=  0.3% of the 5,000/hour budget** |

## If I took it further

- Move ETag + watermark to a real datastore so they survive a workflow
  re-import (n8n static data does not).
- Replace polling with a repo webhook on the **`watch`** event, which fires the
  instant someone stars the repo: real-time, no pagination, no rate-limit
  exposure on the trigger at all. Repo ownership (already required since the
  July 2026 restriction) is what makes this available.
