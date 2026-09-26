"""Probe 2: reveal the submission schema via FastAPI validation errors, and
sweep more score paths. No API key is ever printed."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"
LIMIT = 2000


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def show(label: str, resp) -> None:
    ctype = resp.headers.get("content-type", "")
    allow = resp.headers.get("allow", "")
    extra = f" ALLOW={allow}" if allow else ""
    print(f"\n=== {label} -> {resp.status_code} [{ctype}]{extra} ===")
    t = resp.text
    print(t[:LIMIT] + (f"\n... [TRUNCATED, total {len(t)}]" if len(t) > LIMIT else ""))


def main() -> None:
    env = load_env()
    key = env["COMPETITION_TEAM_API_KEY"]
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    # more GET guesses
    paths = [
        "/api/l3b/submissions/",
        "/api/l3b/submissions/score",
        "/api/l3b/submissions/latest/",
        "/api/l3b/submissions/me/score",
        "/api/l3b/status",
        "/api/l3b/team",
        "/api/l3b/evaluate",
        "/api/l3b/evaluation",
        "/api/l3b/metrics",
        "/api/l3b/leaderboard",
        "/api/l3b/rank",
        "/api/l3b/standing",
        "/api/scoreboard",
        "/api/l3b/scoreboard",
        "/api/l3b/score/me",
        "/api/l3b/score/latest",
        "/api/l3b/feedback/latest",
        "/api/l3b/report/latest",
        "/api/l3b/runs/latest",
        "/api/l3b/breakdown/latest",
        "/api/l3b/me/score",
        "/api/l3b/me/feedback",
        "/api/l3b/me/submissions",
        "/api/teams/me/score",
        "/api/teams/me/submissions",
        "/api/teams/me/feedback",
        "/api/l3b/team/score",
        "/api/l3b/team/submissions",
        "/api/v1/l3b/score",
        "/api/v1/score",
        "/api/v1/l3b/submissions",
        "/api/public/score",
        "/api/l3b/public/score",
        "/api/config",
        "/api/l3b/config",
        "/api/cases",
        "/api/l3b/cases",
    ]
    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
        for p in paths:
            try:
                r = client.get(BASE + p)
                if r.status_code != 404:
                    show(f"GET {p}", r)
                else:
                    print(f"404 {p}")
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {p} {type(exc).__name__}: {exc}")
            sys.stdout.flush()

        # retry the root paths that timed out
        for p in ["/", "/api"]:
            try:
                r = client.get(BASE + p, timeout=40.0)
                show(f"GET {p} (retry)", r)
            except Exception as exc:  # noqa: BLE001
                print(f"ERR retry {p} {type(exc).__name__}: {exc}")
            sys.stdout.flush()

        # --- schema reveal: validation errors on the POST endpoint ---
        print("\n\n########## POST /api/l3b/submissions (schema reveal) ##########")
        attempts = [
            ("empty JSON {}", {"json": {}}),
            ("no body", {}),
            ("null body", {"json": None}),
            ("wrong type (string)", {"json": "x"}),
            ("wrong type (list)", {"json": []}),
        ]
        for label, kw in attempts:
            try:
                r = client.post(BASE + "/api/l3b/submissions", **kw)
                show(f"POST /api/l3b/submissions [{label}]", r)
            except Exception as exc:  # noqa: BLE001
                print(f"\nERR POST [{label}] {type(exc).__name__}: {exc}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
