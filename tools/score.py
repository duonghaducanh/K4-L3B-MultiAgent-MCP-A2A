"""Read this team's L3B score and per-component breakdown.

Usage:
    ./.venv/Scripts/python.exe tools/score.py            # my team
    ./.venv/Scripts/python.exe tools/score.py --top 10   # leaderboard top N
    ./.venv/Scripts/python.exe tools/score.py --team h209-02470

The API key is read from .env and never printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://n7-competition.pages.dev"
VARIANT = "l3b"

# Component key -> (weight, human label). Weights from README "Tiêu chí chấm điểm công khai".
WEIGHTS: dict[str, tuple[float, str]] = {
    "semantic": (0.40, "Độ chính xác ngữ nghĩa"),
    "evidence": (0.15, "Evidence coverage"),
    "mcp": (0.15, "MCP provenance"),
    "consistency": (0.10, "Tính nhất quán"),
    "schema": (0.05, "Schema"),
    "calibration": (0.05, "Calibration"),
    "workflow": (0.05, "Multi-agent workflow"),
    "efficiency": (0.05, "Hiệu quả tool call"),
}
ORDER = ["semantic", "evidence", "mcp", "consistency", "schema", "calibration", "workflow", "efficiency"]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def client() -> httpx.Client:
    key = load_env()["COMPETITION_TEAM_API_KEY"]
    return httpx.Client(
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )


def render(entry: dict) -> None:
    comps = entry.get("components") or {}
    weighted = entry.get("weighted_components") or {}
    print(f"\n  rank {entry.get('rank')}  {entry.get('team_code')}  ({entry.get('display_name')}, {entry.get('class_id')})")
    print(f"  submitted_at {entry.get('submitted_at')}")
    print(f"  SCORE {entry.get('score')}   hard_gate_count={entry.get('hard_gate_count')}")
    if not comps:
        return
    print(f"\n  {'component':<14} {'raw':>8} {'weight':>7} {'points':>8}   label")
    print(f"  {'-'*14} {'-'*8} {'-'*7} {'-'*8}   {'-'*26}")
    for k in ORDER:
        if k not in comps:
            continue
        w, label = WEIGHTS.get(k, (0.0, k))
        print(f"  {k:<14} {comps[k]:>8.4f} {w:>6.0%} {weighted.get(k, 0.0):>8.4f}   {label}")
    total = sum(weighted.get(k, 0.0) for k in ORDER)
    print(f"  {'TOTAL':<14} {'':>8} {'':>7} {total:>8.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=0, help="show top N leaderboard entries")
    ap.add_argument("--team", help="team_code to look up instead of my own")
    args = ap.parse_args()

    with client() as c:
        me = c.get(f"{BASE}/api/v2/me").json()
        team = args.team or me["team_code"]
        print(f"team={team}  class={me['class_id']}  members={len(me.get('members', []))}")

        subs = c.get(f"{BASE}/api/v2/me/submissions").json()
        if not args.team:
            print("\nsubmissions (newest first):")
            for s in subs:
                print(f"  {s['score']:>8.4f}  {s['status']:<10} {s['submitted_at']}  {s['submission_id']}")

        entry = c.get(f"{BASE}/api/v2/leaderboard/{VARIANT}/teams/{team}")
        if entry.status_code == 200:
            print("\n=== MY BREAKDOWN ===")
            render(entry.json())
        else:
            print(f"\nbreakdown {entry.status_code}: {entry.text[:200]}")

        if args.top:
            lb = c.get(f"{BASE}/api/v2/leaderboard/{VARIANT}").json()
            print(f"\n=== LEADERBOARD (generated {lb.get('generated_at')}, {len(lb.get('entries', []))} teams) ===")
            for e in lb.get("entries", [])[: args.top]:
                print(f"  {e['rank']:>3}  {e['score']:>8.4f}  {e['team_code']:<14} {e['display_name']}")


if __name__ == "__main__":
    sys.exit(main())
