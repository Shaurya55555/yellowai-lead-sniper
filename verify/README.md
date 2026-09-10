# verify/ - pipeline validation harness

**Not a deliverable.** `../lead-sniper.workflow.json` is the submission. This
script re-implements the same logic (same endpoints, headers, filter rule, Slack
Block Kit payload) in plain Python so the pipeline can be exercised against the
**live GitHub API** without standing up n8n, and so every claim in
`../LOGIC_LOG.md` can be checked against real responses.

Node-for-node mapping is in the module docstring.

## Run it

```bash
export GITHUB_TOKEN=$(gh auth token)          # any token with repo access works
# optional: export OPENAI_API_KEY / GROQ_API_KEY / GEMINI_API_KEY for a real pitch
# optional: export SLACK_WEBHOOK_URL to actually POST the card

python verify_pipeline.py --owner <you> --repo <your-demo-repo>
python verify_pipeline.py --owner <you> --repo <your-demo-repo> --reset
python verify_pipeline.py ... --min-followers 0 --min-public-repos 0   # force a qualifying lead
```

State (ETag + watermark) is kept in `state.json` (git-ignored), the same role as
n8n's workflow static data.

## What was verified (2026-09-11, against `Shaurya55555/yellowai-lead-sniper-demo`)

See `SAMPLE_RUN.md` for full transcripts. Summary:

| Behaviour | Result |
| --- | --- |
| `X-GitHub-Api-Version: 2026-03-10` + `Accept: application/vnd.github.star+json` on `/stargazers` | 200, `starred_at` present |
| Stargazer read on a repo the token **admins** (post-July-2026 restriction) | 200 (works) |
| `Link` header -> last page | resolves (1 page on a small repo, falls back cleanly) |
| `X-RateLimit-Remaining` read for the budget guard | ~4980 / 5000 |
| First run with no watermark | records baseline, emits 0 |
| Conditional GET with `If-None-Match` when nothing changed | **HTTP 304**, pipeline stops, primary quota not consumed |
| Conditional GET after a new star | 200, new `ETag` captured |
| New-star detection via `starred_at` watermark | 1 new stargazer detected |
| `GET /users/{login}` enrichment | 200, `followers` / `public_repos` / `name` returned |
| Filter `followers > 100 OR public_repos > 50`, real account (1 / 21) | **dropped** (negative case) |
| Same account with thresholds lowered | **qualifies**, Slack Block Kit payload built (see `SAMPLE_RUN.md`) |
| Pitch step with no LLM credits | falls back to `"(pitch unavailable)"`, lead still built (matches `onError: continueRegularOutput`) |

Not verifiable here (need external accounts):

- a real OpenAI/Groq/Gemini pitch (the provided OpenAI key returned
  `insufficient_quota`),
- an actual POST to a Slack Incoming Webhook,
- the n8n import itself.
