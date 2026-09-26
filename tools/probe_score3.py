"""Probe 3: broad path sweep for the score/feedback endpoint + frontend asset hunt."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"
LIMIT = 1200


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def main() -> None:
    env = load_env()
    key = env["COMPETITION_TEAM_API_KEY"]
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    prefixes = ["/api", "/api/l3b", "/api/l3b/me", "/api/me", "/api/team", "/api/teams/me"]
    suffixes = [
        "score", "scores", "scoring", "grade", "grades", "feedback", "report", "reports",
        "result", "results", "evaluation", "eval", "submission", "submissions", "submit",
        "latest", "current", "summary", "breakdown", "components", "metrics", "detail",
        "details", "status", "leaderboard", "rank", "ranking", "standing", "standings",
        "public", "admin", "debug", "internal", "run", "runs", "artifact", "artifacts",
        "output", "outputs", "log", "logs", "trace", "traces", "cost", "efficiency",
        "calibration", "consistency", "provenance", "evidence", "semantic", "schema",
        "workflow", "me", "team", "teams", "mine", "my", "info", "state", "board",
        "judge", "judging", "review", "assessment", "assessment/me", "score/me",
        "submissions/latest", "score/latest", "feedback/latest",
    ]

    hits: list[tuple[str, int, str]] = []
    total = 0
    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
        for pre in prefixes:
            for suf in suffixes:
                p = f"{pre}/{suf}"
                total += 1
                try:
                    r = client.get(BASE + p)
                except Exception as exc:  # noqa: BLE001
                    print(f"ERR {p} {type(exc).__name__}: {exc}")
                    continue
                if r.status_code != 404:
                    allow = r.headers.get("allow", "")
                    body = " ".join(r.text.split())[:LIMIT]
                    print(f"\n>>> {r.status_code} GET {p} ALLOW={allow} [{r.headers.get('content-type','')}]")
                    print(f"    {body}")
                    hits.append((p, r.status_code, body))
                sys.stdout.flush()

    print(f"\n\n########## SWEPT {total} paths; non-404: {len(hits)} ##########")
    for p, c, b in hits:
        print(f"  {c} {p}")

    # --- frontend asset hunt ---
    print("\n\n########## FRONTEND ASSETS ##########")
    for p in ["/", "/index.html", "/_next/static/chunks/main.js", "/app.js", "/main.js"]:
        try:
            r = client.get(BASE + p, timeout=45.0)
            print(f"\n=== GET {p} -> {r.status_code} [{r.headers.get('content-type','')}] len={len(r.text)} ===")
            print(r.text[:3000])
        except Exception as exc:  # noqa: BLE001
            print(f"\n=== GET {p} -> ERR {type(exc).__name__}: {exc} ===")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
