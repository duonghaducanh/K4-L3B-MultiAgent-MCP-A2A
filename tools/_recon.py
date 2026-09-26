"""Recon: exact breakdown, quota, top teams, gap decomposition."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx2  # noqa: E402

from score import BASE, ORDER, WEIGHTS, load_env  # noqa: E402


def main() -> None:
    env = load_env()
    h = {"Authorization": f"Bearer {env['COMPETITION_TEAM_API_KEY']}", "Accept": "application/json"}
    with httpx2.Client(headers=h, timeout=30.0, follow_redirects=True) as c:
        me = c.get(f"{BASE}/api/v2/me").json()
        code = me["team_code"]
        comps = c.get(f"{BASE}/api/v2/competitions").json()
        print("competitions:", json.dumps(comps, ensure_ascii=False))

        mine = c.get(f"{BASE}/api/v2/leaderboard/l3b/teams/{code}").json()
        print("\nMY ENTRY:", json.dumps(mine, ensure_ascii=False))

        lb = c.get(f"{BASE}/api/v2/leaderboard/l3b").json()
        entries = lb["entries"]
        print(f"\nleaderboard n={len(entries)}")
        for e in entries[:6]:
            d = c.get(f"{BASE}/api/v2/leaderboard/l3b/teams/{e['team_code']}").json()
            print(f"\n#{d['rank']} {d['team_code']} score={d['score']} g={d['hard_gate_count']}")
            print("   " + " ".join(f"{k}={d['components'][k]:.4f}" for k in ORDER))

        # gap decomposition vs the best observed per component
        best = {k: 0.0 for k in ORDER}
        for e in entries:
            d = c.get(f"{BASE}/api/v2/leaderboard/l3b/teams/{e['team_code']}").json()
            for k in ORDER:
                best[k] = max(best[k], d["components"][k])
        print("\nBEST OBSERVED per component:", {k: round(v, 4) for k, v in best.items()})
        print("implied ceiling score:", round(sum(WEIGHTS[k] * best[k] for k in ORDER), 4))
        print("\nGAP (points available):")
        tot = 0.0
        for k in ORDER:
            g = (best[k] - mine["components"][k]) * WEIGHTS[k]
            tot += g
            print(f"  {k:12s} {mine['components'][k]:8.4f} -> {best[k]:8.4f}  +{g:.4f}")
        print(f"  TOTAL POTENTIAL +{tot:.4f}")


if __name__ == "__main__":
    main()
