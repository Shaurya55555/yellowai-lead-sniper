"""Reference implementation of the Lead Sniper workflow, for validation only.

This is NOT the deliverable. `lead-sniper.workflow.json` is. This script runs the
exact same logic (same endpoints, headers, filter, Slack payload) against the
live GitHub API so the pipeline can be verified without standing up n8n, and so
the workflow's claims can be checked against real responses.

Mirrors, node for node:
  Load Sync State           -> _load_state / _save_state (state.json here)
  Discover Last Page        -> _discover_last_page       (Link: rel="last")
  Guard: Rate Budget OK     -> _rate_guard              (X-RateLimit-Remaining)
  Poll Stargazers (cond.)   -> _poll_stargazers          (If-None-Match / 304)
  Filter New Stargazers     -> _new_stargazers           (starred_at watermark)
  Enrich: Get User Profile  -> _enrich
  Filter: High-Value Lead   -> followers > N OR public_repos > M
  Generate Sales Pitch      -> _pitch  (OpenAI / Groq / Gemini / fallback)
  Build Slack Message       -> _slack_blocks
  Post to Slack             -> _post_slack (only if SLACK_WEBHOOK_URL set)

Env:
  GITHUB_TOKEN         required. `gh auth token` works.
  OPENAI_API_KEY       optional. Uses OpenAI chat completions.
  GROQ_API_KEY         optional. Free tier, OpenAI-compatible.
  GEMINI_API_KEY       optional. Google AI Studio free tier.
  SLACK_WEBHOOK_URL    optional. If set, the card is POSTed; else printed.

Usage:
  python verify_pipeline.py --owner Shaurya55555 --repo yellowai-lead-sniper-demo
  python verify_pipeline.py ... --reset          # wipe state.json first
  python verify_pipeline.py ... --min-followers 0 --min-public-repos 0
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

API = "https://api.github.com"
API_VERSION = "2026-03-10"
STATE_FILE = Path(__file__).with_name("state.json")

DELAY_CONDITIONS_NOTE = "followers > min_followers OR public_repos > min_public_repos"


def _gh_headers(token: str, star_json: bool = False) -> dict:
    accept = "application/vnd.github.star+json" if star_json else "application/vnd.github+json"
    return {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "X-GitHub-Api-Version": API_VERSION,
    }


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"stargazersEtag": "", "lastStarredAt": ""}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _discover_last_page(client: httpx.Client, owner: str, repo: str, token: str) -> tuple[int, int]:
    """Return (last_page, x_ratelimit_remaining). Mirrors Discover/Resolve Last Page."""
    r = client.get(
        f"{API}/repos/{owner}/{repo}/stargazers",
        params={"per_page": 100, "page": 1},
        headers=_gh_headers(token, star_json=True),
        timeout=20,
    )
    r.raise_for_status()
    link = r.headers.get("link", "")
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    last_page = int(m.group(1)) if m else 1
    remaining = int(r.headers.get("x-ratelimit-remaining", "9999"))
    print(f"  discovery: last_page={last_page} rate_remaining={remaining}")
    return last_page, remaining


def _rate_guard(remaining: int, floor: int) -> bool:
    if remaining < floor:
        print(f"  guard: rate_remaining {remaining} < {floor}, skipping this cycle")
        return False
    return True


def _poll_stargazers(
    client: httpx.Client, owner: str, repo: str, page: int, etag: str, token: str
) -> tuple[int, str, list]:
    """Conditional GET of the newest page. Returns (status, new_etag, stargazers)."""
    headers = _gh_headers(token, star_json=True)
    if etag:
        headers["If-None-Match"] = etag
    r = client.get(
        f"{API}/repos/{owner}/{repo}/stargazers",
        params={"per_page": 100, "page": page},
        headers=headers,
        timeout=20,
    )
    if r.status_code == 304:
        print("  poll: 304 Not Modified (no new stars; primary quota not consumed)")
        return 304, etag, []
    if r.status_code in (403, 429):
        print(
            f"  poll: {r.status_code} rate limited. retry-after="
            f"{r.headers.get('retry-after', 'n/a')} "
            f"x-ratelimit-reset={r.headers.get('x-ratelimit-reset', 'n/a')}. skipping cycle"
        )
        return r.status_code, etag, []
    r.raise_for_status()
    return 200, r.headers.get("etag", etag), r.json()


def _new_stargazers(state: dict, stargazers: list) -> list:
    """Watermark filter. First run records a baseline and emits nothing."""
    prev = state.get("lastStarredAt") or ""
    newest = prev or "1970-01-01T00:00:00Z"  # epoch floor, matches n8n's new Date(0)
    for s in stargazers:
        if s["starred_at"] > newest:
            newest = s["starred_at"]
    state["lastStarredAt"] = newest

    if not prev:
        print(f"  baseline run: recorded watermark {newest}, emitting 0")
        return []

    fresh = [s for s in stargazers if s["starred_at"] > prev]
    print(f"  {len(fresh)} new stargazer(s) since {prev}")
    return [{"login": s["user"]["login"], "starred_at": s["starred_at"]} for s in fresh]


def _enrich(client: httpx.Client, login: str, token: str) -> dict | None:
    time.sleep(1.5)  # same serialisation as the n8n batching option
    r = client.get(f"{API}/users/{login}", headers=_gh_headers(token), timeout=20)
    if r.status_code >= 400:
        print(f"  enrich {login}: HTTP {r.status_code}, dropping this lead")
        return None
    return r.json()


def _pitch(user: dict, model: str) -> str:
    """Generate Sales Pitch. Tries OpenAI, then Groq, then Gemini; else fallback."""
    system = (
        "You are a senior sales development rep at a developer-tools company. In ONE "
        "sentence of at most 30 words, say why this GitHub user is worth reaching out "
        "to as a sales lead. No greeting, no preamble, no quotes."
    )
    u = (
        f"Name: {user.get('name') or user.get('login')}\n"
        f"Company: {user.get('company') or 'unknown'}\n"
        f"Bio: {user.get('bio') or 'none'}\n"
        f"Followers: {user.get('followers')}\n"
        f"Public repos: {user.get('public_repos')}"
    )

    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    try:
        if openai_key:
            return _chat_openai_compatible(
                "https://api.openai.com/v1/chat/completions", openai_key, model, system, u
            )
        if groq_key:
            return _chat_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                groq_key,
                os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                system,
                u,
            )
        if gemini_key:
            return _chat_gemini(gemini_key, system, u)
    except Exception as exc:  # noqa: BLE001 - mirror onError: continueRegularOutput
        print(f"  pitch: LLM call failed ({exc}); using fallback")
        return "(pitch unavailable)"

    print("  pitch: no LLM key set; using fallback")
    return "(pitch unavailable)"


def _chat_openai_compatible(url: str, key: str, model: str, system: str, user: str) -> str:
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0.7,
            "max_tokens": 80,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=40,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _chat_gemini(key: str, system: str, user: str) -> str:
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": 80, "temperature": 0.7},
        },
        timeout=40,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _esc(v) -> str:
    s = "" if v is None else str(v)
    for a, b in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
        s = s.replace(a, b)
    return re.sub(r"([*_~`|])", "​\\1", s)


def _slack_blocks(user: dict, pitch: str, owner: str, repo: str) -> dict:
    header = f":dart: New high-value lead starred {owner}/{repo}"
    return {
        "text": header,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{header}*"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Name:*\n{_esc(user.get('name') or user.get('login'))}"},
                    {"type": "mrkdwn", "text": f"*Company:*\n{_esc(user.get('company') or '-')}"},
                    {"type": "mrkdwn", "text": f"*Followers:*\n{user.get('followers')}"},
                    {"type": "mrkdwn", "text": f"*Public repos:*\n{user.get('public_repos')}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Bio:*\n{_esc(user.get('bio') or '-')}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*AI sales pitch:*\n{_esc(pitch)}"}},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"<https://github.com/{user.get('login')}|github.com/{user.get('login')}>"}
                ],
            },
        ],
    }


def _post_slack(payload: dict) -> None:
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        print("  (SLACK_WEBHOOK_URL not set; payload printed above, not sent)")
        return
    r = httpx.post(url, json=payload, timeout=20)
    print(f"  slack: HTTP {r.status_code} {r.text[:100]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--min-followers", type=int, default=100)
    ap.add_argument("--min-public-repos", type=int, default=50)
    ap.add_argument("--min-rate-remaining", type=int, default=100)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set. Try:  export GITHUB_TOKEN=$(gh auth token)")
        return 2

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("state.json reset")

    state = _load_state()
    print(f"[verify] repo={args.owner}/{args.repo} "
          f"etag={'set' if state['stargazersEtag'] else 'none'} "
          f"watermark={state['lastStarredAt'] or 'none (baseline run)'}")

    with httpx.Client() as client:
        last_page, remaining = _discover_last_page(client, args.owner, args.repo, token)
        if not _rate_guard(remaining, args.min_rate_remaining):
            _save_state(state)
            return 0

        status, new_etag, stargazers = _poll_stargazers(
            client, args.owner, args.repo, last_page, state["stargazersEtag"], token
        )
        if status != 200:
            _save_state(state)
            return 0
        state["stargazersEtag"] = new_etag

        fresh = _new_stargazers(state, stargazers)
        _save_state(state)
        if not fresh:
            return 0

        for item in fresh:
            user = _enrich(client, item["login"], token)
            if not user:
                continue
            qualifies = (
                (user.get("followers") or 0) > args.min_followers
                or (user.get("public_repos") or 0) > args.min_public_repos
            )
            print(
                f"  filter {user['login']}: followers={user.get('followers')} "
                f"public_repos={user.get('public_repos')} -> "
                f"{'QUALIFIES' if qualifies else 'dropped'}"
            )
            if not qualifies:
                continue
            pitch = _pitch(user, args.model)
            print(f"  pitch: {pitch}")
            payload = _slack_blocks(user, pitch, args.owner, args.repo)
            print("  slack payload:")
            print(json.dumps(payload, indent=2))
            _post_slack(payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
