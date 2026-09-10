# Logic Log - GitHub API rate-limit handling

The brief asks whether I used "a delay or a specific header". The answer is
both, but a delay is the last line of defence, not the strategy. The strategy
is: **make almost every poll cost zero requests, then defend what's left.**
Four layers.

## Layer 1 - Authenticate: raise the primary ceiling

Every GitHub call carries `Authorization: Bearer <PAT>` through an n8n Header
Auth credential. This moves the primary limit from **60 requests/hour**
(anonymous, per IP) to **5,000 requests/hour**. A classic PAT with the
`public_repo` scope is enough. Nodes: *Discover Last Page*,
*Poll Stargazers (conditional)*, *Enrich: Get User Profile*.

## Layer 2 - Conditional requests: the poll that does not count

*Poll Stargazers (conditional)* sends `If-None-Match: <etag>`, where `<etag>` is
the `ETag` response header saved from the previous run in workflow static data
(`Load Sync State` reads it, `Filter New Stargazers` writes the new one).

When nothing has been starred since the last poll, GitHub returns
**HTTP 304 Not Modified**, and per GitHub's REST documentation a **304 does not
count against the rate limit at all**. The node uses `neverError` so a 304 does
not fail it, and `Filter New Stargazers` stops the run immediately on a 304.

Steady state for a normal repo: most 15-minute polls are free.

## Layer 3 - Structural minimisation: O(1), not O(pages)

- **Jump to the newest page.** `GET /repos/{o}/{r}/stargazers` returns
  stargazers **oldest-first**, so new stars are always on the last page.
  *Discover Last Page* reads the `Link: <...&page=N>; rel="last"` header once and
  the next call goes straight to page N. Discovery is 1 request whether the repo
  has 200 stargazers or 200,000.
- **The specific header for timestamps.**
  `Accept: application/vnd.github.star+json` makes the API include `starred_at`
  on each stargazer, which is what the "is this new?" check runs on.
- **Watermark.** `Filter New Stargazers` keeps a `lastStarredAt` timestamp in
  static data and forwards only stargazers newer than it, so the expensive
  `GET /users/{login}` enrichment fires for genuinely new users only (typically
  0-2 per poll), never the whole page.

## Layer 4 - Defend the remainder: secondary limit and backoff

- **Secondary (abuse) limit.** The PAT does not lift GitHub's secondary
  rate limit, which triggers on bursts. *Enrich: Get User Profile* uses the HTTP
  node's **batching** at 1 request per **1,500 ms** to stay under it.
- **Backoff.** Every GitHub node has **retry-on-fail**: 3 tries, 5 s apart. This
  absorbs transient `403`/`5xx` and gives a `Retry-After` window room to clear.
- **Budget guard.** *Resolve Last Page* reads `X-RateLimit-Remaining` from the
  discovery response; *Guard: Rate Budget OK* drops the run for this cycle if it
  is below 100, so a near-exhausted budget is never pushed over. The next
  scheduled run picks up normally.

## Budget, worst case per 15-minute run

| Step | GitHub requests |
| --- | --- |
| Stargazer poll | 1 discovery + 1 poll (the poll is often a free 304) |
| Enrich new users | 0-2 |
| **Total** | **~2-4 / run  ~=  16 / hour  ~=  0.3% of the 5,000/hour budget** |

## If I took it further

- Move ETag + watermark to a real datastore so they survive a workflow
  re-import (static data does not).
- Replace polling entirely with a repo webhook on the **`watch`** event, which
  fires the instant someone stars the repo: real-time, zero polling, zero
  rate-limit exposure on the trigger.
