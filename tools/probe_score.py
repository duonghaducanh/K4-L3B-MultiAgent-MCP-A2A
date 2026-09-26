"""Exhaustive discovery of the competition scoring API.

Reports every response verbatim (status, content-type, body truncated).
Never prints the API key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


BASE = "https://n7-competition.pages.dev"
LIMIT = 2000


def show(label: str, resp) -> None:
    ctype = resp.headers.get("content-type", "")
    allow = resp.headers.get("allow", "")
    extra = f" ALLOW={allow}" if allow else ""
    print(f"\n=== {label} -> {resp.status_code} [{ctype}]{extra} ===")
    text = resp.text
    if len(text) > LIMIT:
        print(text[:LIMIT] + f"\n... [TRUNCATED, total {len(text)} chars]")
    else:
        print(text)


def main() -> None:
    import httpx2 as httpx

    env = load_env()
    key = env.get("COMPETITION_TEAM_API_KEY", "")
    assert key.startswith("sk-team-"), "key not loaded"
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    paths = [
        # OpenAPI / docs
        "/api/openapi.json",
        "/openapi.json",
        "/api/docs",
        "/api/redoc",
        "/docs",
        "/redoc",
        # health / root
        "/",
        "/api",
        "/api/health",
        "/api/healthz",
        "/api/version",
        # identity
        "/api/me",
        "/api/team",
        "/api/teams",
        "/api/teams/me",
        "/api/me/score",
        "/api/team/score",
        # l3b score surface
        "/api/l3b",
        "/api/l3b/me",
        "/api/l3b/score",
        "/api/l3b/scores",
        "/api/l3b/feedback",
        "/api/l3b/report",
        "/api/l3b/results",
        "/api/l3b/result",
        "/api/l3b/breakdown",
        "/api/l3b/submission",
        "/api/l3b/submissions",
        "/api/l3b/submissions/latest",
        "/api/l3b/submissions/me",
        "/api/l3b/submissions/latest/score",
        # generic
        "/api/score",
        "/api/scores",
        "/api/feedback",
        "/api/report",
        "/api/results",
        "/api/result",
        "/api/submission",
        "/api/submissions",
        "/api/submissions/latest",
        "/api/breakdown",
        "/api/leaderboard",
        "/api/l3b/leaderboard?track=l3b",
        "/api/leaderboard?track=l3b",
        "/api/tracks",
        "/api/l3b/tracks",
        # guesses around naming
        "/api/competition",
        "/api/competition/score",
        "/api/scorecard",
        "/api/metrics",
        "/api/evaluation",
        "/api/l3b/evaluation",
        "/api/runs",
        "/api/l3b/runs",
    ]

    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
        results: dict[str, int] = {}
        for path in paths:
            try:
                resp = client.get(BASE + path)
                results[path] = resp.status_code
                show(f"GET {path}", resp)
            except Exception as exc:  # noqa: BLE001
                results[path] = -1
                print(f"\n=== GET {path} -> ERR {type(exc).__name__}: {exc} ===")
            sys.stdout.flush()

        # OPTIONS on the interesting ones
        for path in ["/api/l3b/submissions", "/api/l3b/score", "/api/submissions"]:
            try:
                resp = client.options(BASE + path)
                show(f"OPTIONS {path}", resp)
            except Exception as exc:  # noqa: BLE001
                print(f"\n=== OPTIONS {path} -> ERR {type(exc).__name__}: {exc} ===")
            sys.stdout.flush()

    print("\n\n########## SUMMARY ##########")
    for path, code in results.items():
        if code != 404:
            print(f"  {code}  {path}")
    print("\n--- 404s (for completeness) ---")
    print(", ".join(p for p, c in results.items() if c == 404))


if __name__ == "__main__":
    main()
