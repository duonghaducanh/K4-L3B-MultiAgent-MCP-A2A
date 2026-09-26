"""Final: legacy leaderboard shape (needs class) + submission detail route."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"
SID = "sub_QdhpOPoypS5eF9n1saoa1GF-AnlmRbB4"


def load_env() -> dict[str, str]:
    v: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, val = line.split("=", 1)
            v[k.strip()] = val.strip()
    return v


def main() -> None:
    env = load_env()
    h = {"Authorization": f"Bearer {env['COMPETITION_TEAM_API_KEY']}", "Accept": "application/json"}
    paths = [
        "/api/l3b/leaderboard?class_id=H209",
        "/api/l3b/leaderboard?class=H209",
        "/api/l3b/leaderboard/H209",
        "/api/l3b/leaderboard/H209?limit=3",
        "/api/v2/leaderboard/l3b?class_id=H209&limit=3",
        f"/api/v2/submissions/{SID}",
        f"/api/v2/submissions/{SID}?variant_id=l3b",
        f"/api/v2/submissions/{SID}/report",
        "/api/v2/runs?variant_id=l3b",
        "/api/v2/runs?track=l3b",
    ]
    with httpx.Client(headers=h, timeout=30.0, follow_redirects=True) as c:
        for p in paths:
            try:
                r = c.get(BASE + p)
                body = r.text
                if len(body) > 700:
                    body = body[:700] + f"...[+{len(r.text)-700}]"
                print(f"{r.status_code} GET {p}\n    {body}\n")
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {p} {type(exc).__name__}: {exc}\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
