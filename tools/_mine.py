"""Mine the full leaderboard for teams whose component vectors are informative.

Focus: who achieves the max on each component, and what does their full vector
look like?  Also cluster teams by their (mcp, consistency, schema, workflow)
signature to spot shared code lineages.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx2  # noqa: E402

from score import BASE, ORDER, load_env  # noqa: E402

CACHE = Path(__file__).resolve().parent / "_all_bd2.json"


def main() -> None:
    if CACHE.exists():
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        env = load_env()
        h = {"Authorization": f"Bearer {env['COMPETITION_TEAM_API_KEY']}", "Accept": "application/json"}
        with httpx2.Client(headers=h, timeout=30.0, follow_redirects=True) as c:
            lb = c.get(f"{BASE}/api/v2/leaderboard/l3b").json()
            out = {}
            for e in lb["entries"]:
                code = e["team_code"]
                try:
                    d = c.get(f"{BASE}/api/v2/leaderboard/l3b/teams/{code}")
                    if d.status_code == 200:
                        out[code] = d.json()
                except Exception:  # noqa: BLE001
                    pass
        data = out
        CACHE.write_text(json.dumps(data), encoding="utf-8")

    rows = list(data.values())
    print(f"teams={len(rows)}")

    # --- max per component, and that team's full vector ---
    for k in ORDER:
        best = max(rows, key=lambda r: r["components"].get(k, -1))
        v = best["components"]
        print(f"\nMAX {k:12s} = {v[k]:9.4f}  team={best['team_code']} g={best['hard_gate_count']} score={best['score']}")
        print("    " + " ".join(f"{x}={v[x]:.4f}" for x in ORDER))

    # --- efficiency distribution ---
    eff = sorted((r["components"]["efficiency"], r["team_code"], r["score"]) for r in rows)
    print("\nEFFICIENCY distribution (deciles):")
    n = len(eff)
    for i in range(0, 10):
        lo = eff[i * n // 10]
        print(f"  p{i*10:>2}: {lo[0]:8.4f} {lo[1]} score={lo[2]}")

    print("\nEFFICIENCY histogram by 10-point bins:")
    bins = Counter(int(r["components"]["efficiency"] // 10) * 10 for r in rows)
    for b in sorted(bins):
        print(f"  [{b:>3},{b+10:>3}): {bins[b]:4d}")

    # --- teams with high efficiency AND high score ---
    print("\nTOP by efficiency (with score):")
    for e, code, sc in eff[::-1][:12]:
        r = data[code]
        print(f"  {code:14s} eff={e:8.4f} score={sc:8.4f} g={r['hard_gate_count']} " +
              " ".join(f"{k[:4]}={r['components'][k]:.2f}" for k in ORDER if k != "efficiency"))

    # --- identity structure ---
    print("\nidentity groups (exact equality among components):")
    groups = Counter()
    for r in rows:
        v = r["components"]
        key = tuple(sorted(k for k in ORDER if abs(v[k] - v["mcp"]) < 1e-9))
        groups[key] += 1
    for key, cnt in groups.most_common(10):
        print(f"  n={cnt:4d}  equal-to-mcp: {list(key)}")

    # --- what is the max value overall ---
    allv = [r["components"][k] for r in rows for k in ORDER]
    print(f"\nmax component value overall = {max(allv):.6f}")
    print(f"top-12 distinct largest values: {sorted({round(v,4) for v in allv}, reverse=True)[:12]}")

    # --- teams whose evidence is the max: look for a pattern ---
    print("\nEVIDENCE top-10:")
    for r in sorted(rows, key=lambda r: -r["components"]["evidence"])[:10]:
        v = r["components"]
        print(f"  {r['team_code']:14s} ev={v['evidence']:8.4f} score={r['score']:8.4f} " +
              " ".join(f"{k[:4]}={v[k]:.3f}" for k in ORDER))

    # --- our team's neighbours: same saturated value ---
    mine = data.get("h209-02859")
    if mine:
        mv = mine["components"]
        print(f"\nMINE {json.dumps(mv, ensure_ascii=False)}")
        same = [r for r in rows if abs(r["components"]["mcp"] - mv["mcp"]) < 1e-9]
        print(f"teams sharing our mcp value {mv['mcp']}: {len(same)}")
        for r in sorted(same, key=lambda r: -r["components"]["efficiency"])[:12]:
            v = r["components"]
            print(f"  {r['team_code']:14s} score={r['score']:8.4f} " +
                  " ".join(f"{k[:4]}={v[k]:.3f}" for k in ORDER))


if __name__ == "__main__":
    main()
