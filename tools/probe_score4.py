"""Final verification of the /api/v2 scoring surface + route mining from the JS bundle."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"
LIMIT = 4000


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
    print(f"\n=== {label} -> {resp.status_code} [{ctype}] ===")
    t = resp.text
    print(t[:LIMIT] + (f"\n... [TRUNCATED, total {len(t)}]" if len(t) > LIMIT else ""))


def main() -> None:
    env = load_env()
    key = env["COMPETITION_TEAM_API_KEY"]
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        # 1) my submissions
        r = client.get(BASE + "/api/v2/me/submissions")
        show("GET /api/v2/me/submissions", r)
        my_sub = None
        try:
            subs = r.json()
            if subs:
                my_sub = subs[0]
        except Exception:  # noqa: BLE001
            pass

        # 2) my team entry from the leaderboard
        team_code = None
        r = client.get(BASE + "/api/v2/leaderboard/l3b")
        show("GET /api/v2/leaderboard/l3b (truncated view)", r)
        try:
            entries = r.json().get("entries", [])
            print(f"\n[leaderboard: {len(entries)} entries]")
            if my_sub:
                target = my_sub["score"]
                mine = [e for e in entries if abs(e.get("score", 0) - target) < 1e-6]
                if mine:
                    team_code = mine[0]["team_code"]
                    print(f"[my entry] {mine[0]}")
        except Exception as exc:  # noqa: BLE001
            print("parse err", exc)

        # 3) THE breakdown endpoint
        if team_code:
            show(
                f"GET /api/v2/leaderboard/l3b/teams/{team_code}  <-- COMPONENT BREAKDOWN",
                client.get(BASE + f"/api/v2/leaderboard/l3b/teams/{team_code}"),
            )

        # 4) probe a few more v2 shapes
        extra = [
            "/api/v2/me",
            "/api/v2/me/team",
            "/api/v2/me/score",
            "/api/v2/me/submissions?detail=1",
            f"/api/v2/submissions/{my_sub['submission_id']}" if my_sub else "/api/v2/submissions/x",
            "/api/v2/leaderboard",
            "/api/v2/leaderboard/l3b/teams",
            "/api/v2/competitions",
            "/api/v2/runs",
            "/api/v2/health",
        ]
        for p in extra:
            try:
                rr = client.get(BASE + p)
                if rr.status_code != 404:
                    show(f"GET {p}", rr)
                else:
                    print(f"404 {p}")
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {p} {type(exc).__name__}: {exc}")
            sys.stdout.flush()

        # 5) mine routes out of the JS bundle
        print("\n\n########## JS BUNDLE ROUTE MINING ##########")
        bundle_url = "https://n7-competition.pages.dev/assets/index-BBesytlK.js"
        try:
            js = client.get(bundle_url, timeout=60.0).text
            print(f"[bundle len={len(js)}]")
            routes = sorted(set(re.findall(r"[\"'`](/api/[A-Za-z0-9_\-{}$./:?=&]*)", js)))
            print("\n--- /api/... literals in bundle ---")
            for route in routes:
                print("  ", route)
            print("\n--- template-literal api calls ---")
            for m in sorted(set(re.findall(r"`(/api/[^`]*)`", js))):
                print("  ", m)
        except Exception as exc:  # noqa: BLE001
            print(f"bundle err {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
