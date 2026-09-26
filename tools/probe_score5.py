"""Final round: legacy v1 endpoints, and hard-gate semantics from the JS bundle."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"


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
    headers = {"Authorization": f"Bearer {env['COMPETITION_TEAM_API_KEY']}", "Accept": "application/json"}

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for p in [
            "/api/l3b/events",
            "/api/l3b/leaderboard",
            "/api/l3b/leaderboard/H209/h209-02859/breakdown",
            "/api/v2/leaderboard/l3b/teams/h209-02859/breakdown",
            "/api/v2/runs/l3b",
        ]:
            try:
                r = client.get(BASE + p)
                print(f"{r.status_code} GET {p}  {r.text[:300]}")
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {p} {type(exc).__name__}")
            sys.stdout.flush()

        print("\n########## BUNDLE: hard gate + scoring semantics ##########")
        js = client.get(BASE + "/assets/index-BBesytlK.js", timeout=60.0).text
        for kw in ["hard_gate", "Hard gates", "private", "gate_reason", "score_private"]:
            for m in re.finditer(re.escape(kw), js):
                i = m.start()
                snippet = js[max(0, i - 350) : i + 450]
                print(f"\n--- {kw} @ {i} ---\n{snippet}")
                break  # first occurrence per keyword

        print("\n########## BUNDLE: component label map ##########")
        for kw in ["weighted_components", "components["]:
            i = js.find(kw)
            if i >= 0:
                print(f"\n--- {kw} @ {i} ---\n{js[max(0,i-900):i+600]}")


if __name__ == "__main__":
    main()
