# Logic Log - GitHub API rate-limit handling

The brief asks whether I used "a delay or a specific header". Both, but a delay
is the last line of defence, not the strategy. The strategy is: **make almost
every poll cost zero requests, then defend what's left.** Four layers, then the
retry rules.

## GitHub API compatibility note

GitHub restricted the public stargazer-listing endpoint
(`GET /repos/{owner}/{repo}/stargazers`) in July 2026: it now works only for
callers who are an **admin or collaborator** on the repository. Requests for
other repositories return `404`. This workflow therefore points at a repository
the workflow owner controls (`Set Config` -> `repoOwner` / `repoName`), and the
demonstration stars that repository from a second account.

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
  the watermark, or drop polling for a webhook (see end).

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

**What the workflow automates today:** the fixed 3x/5s retry-on-fail on every
HTTP node (covers the transient case), and a pre-flight guard,
*Guard: Rate Budget OK*, which reads `X-RateLimit-Remaining` from the discovery
response and skips the whole cycle when it is below `minRateRemaining` (default
100) so the primary quota is never pushed to zero. Dynamic `Retry-After` /
`X-RateLimit-Reset` waiting is designed for as above but is not fully automated
in n8n's built-in retry (it retries on a fixed delay); a header-aware wait node
would close that gap.

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
