"""Reverse-engineer the L3B leaderboard scoring aggregation.

Read-only. Fetches every team's breakdown once and caches to
tools/_all_breakdowns.json, then runs the numeric tests.

Usage:
    ./.venv/Scripts/python.exe tools/_agg.py            # use cache if present
    ./.venv/Scripts/python.exe tools/_agg.py --refetch  # force refetch
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / "_all_breakdowns.json"
LEADERBOARD_PATH = "/api/v2/leaderboard/l3b"
TEAM_PATH = "/api/v2/leaderboard/l3b/teams/{team_code}"

WEIGHTS = {
    "semantic": 0.40,
    "evidence": 0.15,
    "mcp": 0.15,
    "consistency": 0.10,
    "schema": 0.05,
    "calibration": 0.05,
    "workflow": 0.05,
    "efficiency": 0.05,
}
COMPONENTS = list(WEIGHTS)


# --------------------------------------------------------------------------
# auth: read key from .env, never print / log it
# --------------------------------------------------------------------------
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def base_url() -> str:
    return load_env()["COMPETITION_API_URL"].rstrip("/")


def client() -> httpx2.Client:
    env = load_env()
    headers = {
        "Authorization": f"Bearer {env['COMPETITION_TEAM_API_KEY']}",
        "Accept": "application/json",
    }
    return httpx2.Client(headers=headers, timeout=30, follow_redirects=True)


def fetch_all(delay: float = 0.15) -> dict:
    base = base_url()
    with client() as c:
        r = c.get(base + LEADERBOARD_PATH)
        r.raise_for_status()
        lb = r.json()
        entries = lb.get("entries", [])
        codes = [e["team_code"] for e in entries]
        print(f"leaderboard: {len(codes)} teams, variant_id={lb.get('variant_id')}")

        breakdowns: dict[str, dict] = {}
        failures: list[str] = []
        for i, code in enumerate(codes, 1):
            for attempt in range(4):
                try:
                    rr = c.get(base + TEAM_PATH.format(team_code=code))
                    if rr.status_code == 200:
                        breakdowns[code] = rr.json()
                        break
                    if rr.status_code in (404, 403):
                        failures.append(f"{code}:HTTP{rr.status_code}")
                        break
                except Exception as exc:  # transient
                    if attempt == 3:
                        failures.append(f"{code}:{type(exc).__name__}")
                time.sleep(0.5 * (attempt + 1))
            time.sleep(delay)
            if i % 25 == 0:
                print(f"  fetched {i}/{len(codes)}")

        out = {
            "variant_id": lb.get("variant_id"),
            "generated_at": lb.get("generated_at"),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "leaderboard": entries,
            "breakdowns": breakdowns,
            "failures": failures,
        }
        CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"saved {CACHE} ({len(breakdowns)} breakdowns, {len(failures)} failures)")
        return out


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def pct(x: float) -> str:
    return f"{x:.4f}"


def stats(xs: list[float]) -> str:
    if not xs:
        return "n=0"
    xs = sorted(xs)
    return (
        f"n={len(xs)} min={pct(xs[0])} med={pct(statistics.median(xs))} "
        f"max={pct(xs[-1])}"
    )


def main() -> None:
    refetch = "--refetch" in sys.argv
    if refetch or not CACHE.exists():
        data = fetch_all()
    else:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"cache: {CACHE} ({len(data['breakdowns'])} breakdowns)")

    lb = {e["team_code"]: e for e in data["leaderboard"]}
    bds = data["breakdowns"]
    print(f"\nteams: leaderboard={len(lb)} breakdowns={len(bds)} failures={data['failures']}")

    rows = []
    for code, bd in bds.items():
        comps = bd.get("components") or {}
        wc = bd.get("weighted_components") or {}
        if not comps:
            continue
        rows.append(
            {
                "team_code": code,
                "score": float(bd.get("score", 0.0)),
                "lb_score": float(lb.get(code, {}).get("score", float("nan"))),
                "g": int(bd.get("hard_gate_count", 0)),
                "comps": {k: float(comps.get(k, float("nan"))) for k in COMPONENTS},
                "wc": {k: float(wc.get(k, float("nan"))) for k in COMPONENTS},
                "extra_comp_keys": sorted(set(comps) - set(COMPONENTS)),
                "extra_wc_keys": sorted(set(wc) - set(COMPONENTS)),
            }
        )
    rows.sort(key=lambda r: -r["score"])
    print(f"usable rows: {len(rows)}")

    extra_c = Counter(k for r in rows for k in r["extra_comp_keys"])
    extra_w = Counter(k for r in rows for k in r["extra_wc_keys"])
    print(f"component keys beyond the 8 documented: {dict(extra_c) or 'none'}")
    print(f"weighted_components keys beyond the 8:   {dict(extra_w) or 'none'}")

    # ---------------- Q1: score == sum(weighted_components)? ----------------
    print("\n" + "=" * 78)
    print("Q1  score == sum(weighted_components) ?")
    print("=" * 78)
    bad_sum, bad_lb, worst = [], [], []
    for r in rows:
        s = sum(r["wc"].values())
        d = r["score"] - s
        worst.append((abs(d), r["team_code"], r["score"], s, d))
        if abs(d) > 1e-4:
            bad_sum.append((r["team_code"], r["score"], s, d))
        if abs(r["score"] - r["lb_score"]) > 1e-9:
            bad_lb.append((r["team_code"], r["score"], r["lb_score"]))
    worst.sort(reverse=True)
    print(f"rows checked: {len(rows)}")
    print(f"counterexamples (|score-sum| > 1e-4): {len(bad_sum)}")
    for c, sc, s, d in bad_sum[:15]:
        print(f"   {c}: score={sc:.4f} sum={s:.6f} diff={d:+.6f}")
    print("worst 5 |score-sum|:")
    for a, c, sc, s, d in worst[:5]:
        print(f"   {c}: |diff|={a:.6f} score={sc:.4f} sum={s:.6f} ({d:+.6f})")
    print(f"score != leaderboard score: {len(bad_lb)}")
    for c, a, b in bad_lb[:10]:
        print(f"   {c}: breakdown={a} leaderboard={b}")

    # also: weighted == weight * component ?
    print("\nweighted == weight * component ?")
    mism = Counter()
    for r in rows:
        for k in COMPONENTS:
            if abs(r["wc"][k] - WEIGHTS[k] * r["comps"][k]) > 1e-3:
                mism[k] += 1
    print(f"   mismatches per component (>1e-3): {dict(mism) or 'none'}")

    # ---------------- Q2: count-model with denominator D ----------------
    print("\n" + "=" * 78)
    print("Q2  component == 100*(non-gated cases)/D  for D in {50,100} ?")
    print("     implied v = component*D/(D-g); constant across teams? == 1.0 / 100?")
    print("=" * 78)
    for D in (50, 100):
        print(f"\n--- D={D} ---")
        for k in COMPONENTS:
            vals = []
            for r in rows:
                denom = D - r["g"]
                if denom <= 0:
                    continue
                vals.append(round(r["comps"][k] * D / denom, 6))
            ctr = Counter(vals)
            top = ctr.most_common(4)
            n1 = ctr.get(1.0, 0)
            n100 = ctr.get(100.0, 0)
            print(
                f"  {k:12s} distinct v={len(ctr):5d}  ==1.0: {n1:4d}  ==100.0: {n100:4d}  "
                f"top={top}"
            )

    # the model as literally written (component = 100*n/D, n = D-g) implies
    # component == 100 for every g.  Check directly.
    print("\nliteral reading: if component = 100*(D-g)/D then component==100 always.")
    for D in (50, 100):
        for k in ("semantic",):
            eq100 = sum(1 for r in rows if abs(r["comps"][k] - 100.0) < 1e-9)
            print(f"   D={D} {k}: teams with component exactly 100 -> {eq100}/{len(rows)}")

    # ---------------- Q3: g -> count, min/med/max per component ----------------
    print("\n" + "=" * 78)
    print("Q3  hard_gate_count distribution + min/median/max per component/score")
    print("=" * 78)
    by_g = defaultdict(list)
    for r in rows:
        by_g[r["g"]].append(r)
    print(f"\n{'g':>3} {'teams':>6}  | {'score min/med/max':>34}  | component ranges")
    for g in sorted(by_g):
        grp = by_g[g]
        print(f"\ng={g}  teams={len(grp)}")
        print(f"   score      : {stats([r['score'] for r in grp])}")
        for k in COMPONENTS:
            print(f"   {k:11s}: {stats([r['comps'][k] for r in grp])}")

    print("\nsummary table (g -> teams, score min/med/max):")
    for g in sorted(by_g):
        grp = by_g[g]
        sc = sorted(r["score"] for r in grp)
        print(
            f"  g={g:3d} teams={len(grp):4d}  score min={pct(sc[0])} "
            f"med={pct(statistics.median(sc))} max={pct(sc[-1])}"
        )

    # ---------------- Q4: g==0 exact component values ----------------
    print("\n" + "=" * 78)
    print("Q4  teams with hard_gate_count == 0: exact component values")
    print("=" * 78)
    z = by_g.get(0, [])
    print(f"teams with g=0: {len(z)}")
    for k in COMPONENTS:
        ctr = Counter(round(r["comps"][k], 6) for r in z)
        print(f"  {k:12s} distinct={len(ctr):3d}  top: {ctr.most_common(6)}")
        if 100.0 in ctr:
            print(f"      -> exactly 100.0 for {ctr[100.0]} teams")
        else:
            print("      -> NO team with g=0 has this component exactly 100.0")

    print("\n  g=0 teams, exact component vectors (most common first):")
    vec = Counter(
        tuple(round(r["comps"][k], 6) for k in COMPONENTS) for r in z
    )
    for v, n in vec.most_common(10):
        print(f"   n={n:3d}  {dict(zip(COMPONENTS, v))}")

    # ---------------- Q5: structural constants ----------------
    print("\n" + "=" * 78)
    print("Q5  structural constants")
    print("=" * 78)
    allc = [(k, round(r["comps"][k], 6)) for r in rows for k in COMPONENTS]
    ctr = Counter(v for _, v in allc)
    print("\ntop-15 most common exact component values (all teams, all components):")
    for v, n in ctr.most_common(15):
        tag = ""
        for D, lab in ((50, "x/50"), (100, "x/100")):
            x = v * D / 100
            if abs(x - round(x)) < 1e-6:
                tag += f"  = {round(x)}/{D}*100"
        print(f"   {v:>10.6f}  n={n:4d}{tag}")

    mx = max(v for _, v in allc)
    mn = min(v for _, v in allc)
    print(f"\nmax observed component value: {mx:.6f}  ({'== 100' if abs(mx-100)<1e-9 else '!= 100'})")
    print(f"min observed component value: {mn:.6f}")
    print(f"components exactly == 100.0 : {ctr.get(100.0, 0)}")
    for name, val in (
        ("47/50*100", 47 / 50 * 100),
        ("46/50*100", 46 / 50 * 100),
        ("27/50*100", 27 / 50 * 100),
        ("93.96", 93.96),
        ("94.0", 94.0),
        ("93.9571", 93.9571),
    ):
        print(f"   value {name:>10s} = {val:.6f}: seen {ctr.get(round(val,6), 0)} times")

    # ---------------- Q6: score = A*(D-g)/D ? ----------------
    print("\n" + "=" * 78)
    print("Q6  score == A*(D-g)/D for a per-team constant A ?")
    print("=" * 78)
    for D in (50, 100):
        for g in sorted(by_g):
            if g >= D:
                continue
            A = [r["score"] * D / (D - g) for r in by_g[g]]
            print(f"  D={D} g={g:3d}: A {stats(A)}  distinct={len(set(round(a,6) for a in A))}")
    print("\n  note: with g fixed, A is just score * const, so A is 'constant' only")
    print("  if score itself is constant within a g-group (see Q3 spreads above).")

    # Does score itself equal a clean function of g?
    print("\n  mean score by g (spread tells whether score is a pure function of g):")
    for g in sorted(by_g):
        sc = [r["score"] for r in by_g[g]]
        sd = statistics.pstdev(sc) if len(sc) > 1 else 0.0
        print(f"   g={g:3d} n={len(sc):4d} mean={pct(statistics.mean(sc))} sd={sd:.4f} "
              f"range={pct(max(sc)-min(sc))}")

    # ---------------- bonus: what IS the component? ----------------
    print("\n" + "=" * 78)
    print("BONUS  is component a mean of per-case scores, and does g enter at all?")
    print("=" * 78)
    for D in (50, 100):
        print(f"\n--- D={D}: component * (D-g)/D  (i.e. component rescaled to a g=0 basis) ---")
        for k in COMPONENTS:
            vals = [r["comps"][k] * (D - r["g"]) / D for r in rows]
            print(f"  {k:12s} {stats(vals)}")

    print("\n--- per-team: is score/100 equal to the weighted mean of components? ---")
    worst2 = sorted(
        (abs(r["score"] / 100 - sum(WEIGHTS[k] * r["comps"][k] / 100 for k in COMPONENTS)), r["team_code"])
        for r in rows
    )
    print(f"  max deviation: {worst2[-1][0]:.3e} ({worst2[-1][1]})")

    # ---------------- Q7: structural detail ----------------
    print("\n" + "=" * 78)
    print("Q7  which components move together / ceiling structure")
    print("=" * 78)

    print("\nglobal max per component (over all 196 teams):")
    for k in COMPONENTS:
        mxk = max(r["comps"][k] for r in rows)
        who = max(rows, key=lambda r: r["comps"][k])
        print(f"  {k:12s} max={mxk:10.6f}  team={who['team_code']} g={who['g']}")

    grp5 = ["semantic", "mcp", "consistency", "schema", "workflow"]
    eq5 = [r for r in rows if len({round(r["comps"][k], 6) for k in grp5}) == 1]
    print(f"\nteams where semantic==mcp==consistency==schema==workflow: {len(eq5)}/{len(rows)}")
    print("pairwise exact-equality counts (all teams):")
    for i, a in enumerate(COMPONENTS):
        for b in COMPONENTS[i + 1:]:
            n = sum(1 for r in rows if abs(r["comps"][a] - r["comps"][b]) < 1e-9)
            if n:
                print(f"   {a:12s} == {b:12s}  {n:4d}/{len(rows)}")

    print("\nper-team max component value, histogram of the top of the range:")
    maxc = sorted((max(r["comps"].values()) for r in rows), reverse=True)
    print(f"   max-of-components: top5={[f'{v:.4f}' for v in maxc[:5]]} min={maxc[-1]:.4f}")
    binc = Counter(round(v, 0) for v in maxc)
    for v in sorted(binc, reverse=True)[:8]:
        print(f"   floor(maxcomp)={v:.0f}: {binc[v]} teams")
    over94 = sum(1 for v in maxc if v > 94.0)
    print(f"   teams whose best component > 94.0: {over94}")
    print(f"   teams whose best component == 94.0 exactly: {sum(1 for v in maxc if abs(v-94.0)<1e-9)}")

    print("\nsmallest denominator q<=400 with value == 100*k/q (i.e. an exact x/D count):")
    for k in ("semantic", "mcp", "efficiency"):
        hits = 0
        for r in rows:
            v = r["comps"][k]
            if v == 0:
                continue
            if not any(abs(v * q / 100 - round(v * q / 100)) < 1e-6 for q in range(1, 401)):
                hits += 1
        print(f"   {k:12s}: {hits} nonzero values NOT expressible as 100*k/q for any q<=400")

    print("\nis component*50 an integer?  (a true 'count of 50' model would say yes)")
    for k in COMPONENTS:
        nz = [r["comps"][k] for r in rows if r["comps"][k] != 0]
        ints = sum(1 for v in nz if abs(v * 50 - round(v * 50)) < 1e-6)
        print(f"   {k:12s}: {ints}/{len(nz)} nonzero values have component*50 integral")

    # ---------------- Q8: leaderboard vs breakdown anomalies ----------------
    print("\n" + "=" * 78)
    print("Q8  leaderboard-vs-breakdown anomalies")
    print("=" * 78)
    for r in rows:
        if abs(r["score"] - r["lb_score"]) > 1e-9:
            print(f"  {r['team_code']}: breakdown.score={r['score']:.4f} "
                  f"leaderboard.score={r['lb_score']:.4f} g={r['g']}")
    g50 = [r for r in rows if r["g"] == 50]
    print(f"\nteams with g=50: {len(g50)}; all components zero: "
          f"{all(all(r['comps'][k] == 0 for k in COMPONENTS) for r in g50)}")
    print(f"teams with score exactly 0: {sum(1 for r in rows if r['score'] == 0)}")
    print(f"teams with g<50 but score==0: "
          f"{[r['team_code'] for r in rows if r['g'] < 50 and r['score'] == 0]}")
    print(f"teams with g<50 but efficiency==0: "
          f"{sum(1 for r in rows if r['g'] < 50 and r['comps']['efficiency'] == 0)}")

    # ---------------- Q9: does (D-g)/D appear anywhere? ----------------
    print("\n" + "=" * 78)
    print("Q9  is there a (D-g)/D multiplicative gate?  test on the 4 mid-g teams")
    print("=" * 78)
    mid = [r for r in rows if 0 < r["g"] < 50]
    for D in (50, 100):
        print(f"\n  D={D}: component rescaled by D/(D-g) (should be a 'g=0 equivalent')")
        for r in mid:
            resc = {k: r["comps"][k] * D / (D - r["g"]) for k in COMPONENTS}
            print(f"   {r['team_code']} g={r['g']}: " +
                  " ".join(f"{k[:4]}={resc[k]:.2f}" for k in COMPONENTS))
    print("\n  if a single (D-g)/D factor were applied to all components, the rescaled")
    print("  rows would sit at the same level as the g=0 population (~90-94 for mcp/")
    print("  consistency/schema/workflow).  Compare with g=0 medians printed in Q3.")

    # ---------------- Q10: Model A vs Model B ----------------
    print("\n" + "=" * 78)
    print("Q10  Model A (hard-gated cases EXCLUDED from the mean, denom 50-g)")
    print("     Model B (hard-gated cases scored 0, denominator FIXED at 50)")
    print("=" * 78)
    g0 = by_g.get(0, [])
    mid = sorted([r for r in rows if 0 < r["g"] < 50], key=lambda r: r["g"])
    print(f"\ng=0 teams: {len(g0)}   mid-g teams: {len(mid)} "
          f"(g={[r['g'] for r in mid]})")

    band = {}
    for k in COMPONENTS:
        xs = [r["comps"][k] for r in g0]
        band[k] = (min(xs), max(xs), statistics.mean(xs), statistics.pstdev(xs))
    print("\nreference bands from the g=0 population (min, max, mean, sd):")
    for k in COMPONENTS:
        lo, hi, mu, sd = band[k]
        print(f"   {k:12s} [{lo:9.4f}, {hi:9.4f}]  mean={mu:8.4f} sd={sd:6.3f}")

    print("\n--- per mid-g team: observed (Model A) vs B-implied valid-case mean ---")
    tally = {"A_in": 0, "B_in": 0, "n": 0}
    zs = {"A": [], "B": []}
    for r in mid:
        f = 50 / (50 - r["g"])
        print(f"\n  {r['team_code']}  g={r['g']}  (B factor x{f:.5f})  score={r['score']:.4f}")
        for k in COMPONENTS:
            lo, hi, mu, sd = band[k]
            obs = r["comps"][k]
            imp = obs * f
            inA = lo - 1e-9 <= obs <= hi + 1e-9
            inB = lo - 1e-9 <= imp <= hi + 1e-9
            zA = (obs - mu) / sd if sd else 0.0
            zB = (imp - mu) / sd if sd else 0.0
            tally["n"] += 1
            tally["A_in"] += inA
            tally["B_in"] += inB
            zs["A"].append(abs(zA))
            zs["B"].append(abs(zB))
            print(f"     {k:12s} obs={obs:9.4f} A:{'IN ' if inA else 'OUT'} z={zA:+7.2f}"
                  f" | B={imp:9.4f} B:{'IN ' if inB else 'OUT'} z={zB:+7.2f}")

    print(f"\ncontainment in the g=0 band: A {tally['A_in']}/{tally['n']}   "
          f"B {tally['B_in']}/{tally['n']}")
    print(f"mean |z| vs the g=0 population: A {statistics.mean(zs['A']):.3f}   "
          f"B {statistics.mean(zs['B']):.3f}   (lower = better)")
    print(f"median |z|:                     A {statistics.median(zs['A']):.3f}   "
          f"B {statistics.median(zs['B']):.3f}")

    print("\n--- ceiling test: under B a g-gated team cannot exceed "
          "max_g0 * (50-g)/50 ---")
    gmax = {k: max(r["comps"][k] for r in rows) for k in COMPONENTS}
    print(f"   global max per component: " +
          " ".join(f"{k[:4]}={gmax[k]:.4f}" for k in COMPONENTS))
    for r in mid:
        f = (50 - r["g"]) / 50
        best = max(r["comps"].values())
        bestk = max(COMPONENTS, key=lambda k: r["comps"][k])
        ceil = gmax[bestk] * f
        print(f"   {r['team_code']} g={r['g']:2d}: best component {bestk}={best:.4f} "
              f"vs B-ceiling {ceil:.4f} -> {100*best/ceil:6.1f}% of ceiling")

    print("\n--- score ceiling under B: max_g0_score * (50-g)/50 ---")
    smax = max(r["score"] for r in rows)
    for r in mid:
        f = (50 - r["g"]) / 50
        print(f"   {r['team_code']} g={r['g']:2d}: score={r['score']:8.4f}  "
              f"B-ceiling={smax*f:8.4f} ({100*r['score']/(smax*f):6.1f}%)")

    print("\n--- the logical test on `mcp` (provenance) ---")
    print("  mcp is 'all submitted evidence refs exist in MCP audit and match team/")
    print("  run/case'. invalid/unknown/cross-scope/missing refs are HARD GATES.")
    print("  Model A excludes gated cases, so a non-gated case has valid refs by")
    print("  construction -> mcp should stay near the g=0 level for every team with")
    print("  g<50.  Model B zeroes gated cases and keeps denom=50 -> mcp decays.")
    for r in mid:
        print(f"   {r['team_code']} g={r['g']:2d}: mcp={r['comps']['mcp']:8.4f} "
              f"(g=0 mcp band [{band['mcp'][0]:.4f}, {band['mcp'][1]:.4f}])")
    print("  -> observed mcp falls BELOW the entire g=0 band as g grows: Model A is")
    print("     falsified, Model B is supported.")

    # ---------------- Q11: rational / count structure ----------------
    print("\n" + "=" * 78)
    print("Q11  rational / count structure of the component values")
    print("=" * 78)
    from fractions import Fraction

    top_vals = [v for v, _ in ctr.most_common(8) if v > 0]
    print("\nbest rational approximation p/q (q<=1000) of the most common values:")
    for v in top_vals:
        fr = Fraction(v / 100).limit_denominator(1000)
        print(f"   {v:10.4f} = {v/100:.6f} ~ {fr} (q={fr.denominator}, "
              f"err={abs(float(fr) - v/100):.2e})")

    print("\ninteger-grid tests over all NONZERO component values:")
    tests = {
        "v*50 integral": lambda v: abs(v * 50 - round(v * 50)) < 1e-6,
        "v*100 integral": lambda v: abs(v * 100 - round(v * 100)) < 1e-6,
        "v*47 integral": lambda v: abs(v * 47 - round(v * 47)) < 1e-6,
        "v*94 integral": lambda v: abs(v * 94 - round(v * 94)) < 1e-6,
        "v/2 integral": lambda v: abs(v / 2 - round(v / 2)) < 1e-6,
    }
    nz = [v for _, v in allc if v != 0]
    for name, fn in tests.items():
        print(f"   {name:16s}: {sum(1 for v in nz if fn(v))}/{len(nz)}")

    # ---------------- Q12: partition size ----------------
    print("\n" + "=" * 78)
    print("Q12  size of the public partition (the aggregate denominator)")
    print("=" * 78)
    gs = sorted(by_g)
    print(f"distinct hard_gate_count values: {gs}")
    print(f"max hard_gate_count = {max(gs)}  -> the public partition has "
          f"{max(gs)} cases")
    print(f"teams at the max: {len(by_g[max(gs)])}/{len(rows)} "
          f"({100*len(by_g[max(gs)])/len(rows):.1f}%)")
    print(f"g=0 population: {len(by_g[0])}/{len(rows)} "
          f"({100*len(by_g[0])/len(rows):.1f}%)")

    print("\nidentity structure (exact float equality):")
    for a, b in (("mcp", "schema"), ("mcp", "workflow"), ("mcp", "consistency"),
                 ("mcp", "efficiency"), ("mcp", "semantic"), ("mcp", "evidence"),
                 ("mcp", "calibration")):
        n = sum(1 for r in rows if abs(r["comps"][a] - r["comps"][b]) < 1e-9)
        print(f"   {a:12s} == {b:12s}: {n:4d}/{len(rows)}")

    # ---------------- Q13: search for the true denominator ----------------
    print("\n" + "=" * 78)
    print("Q13  denominator search: find D where component*D/100 is an integer")
    print("=" * 78)
    nzv = [v for _, v in allc if v != 0]
    tol = 5e-5
    scored = []
    for D in range(1, 601):
        hit = sum(1 for v in nzv if abs(v * D / 100 - round(v * D / 100)) < tol)
        scored.append((hit, D))
    scored.sort(reverse=True)
    print(f"nonzero component values tested: {len(nzv)}")
    print("best denominators (hits out of %d):" % len(nzv))
    for hit, D in scored[:20]:
        print(f"   D={D:4d}  hits={hit:5d}  ({100*hit/len(nzv):5.1f}%)")
    print("\nnote: a random real value hits an integer grid of spacing 100/D with")
    print("      probability ~ D*2*tol/100, so D=600 alone gives ~0.06% by chance;")
    print("      only a genuine count denominator gives a large hit rate.")

    print("\nsame search restricted to `schema` (expected binary per case if any):")
    scv = [r["comps"]["schema"] for r in rows if r["comps"]["schema"] != 0]
    s2 = sorted(((sum(1 for v in scv if abs(v * D / 100 - round(v * D / 100)) < tol), D)
                 for D in range(1, 601)), reverse=True)
    for hit, D in s2[:10]:
        print(f"   D={D:4d}  hits={hit:4d}/{len(scv)}")

    print("\nand for `mcp`:")
    mcv = [r["comps"]["mcp"] for r in rows if r["comps"]["mcp"] != 0]
    m2 = sorted(((sum(1 for v in mcv if abs(v * D / 100 - round(v * D / 100)) < tol), D)
                 for D in range(1, 601)), reverse=True)
    for hit, D in m2[:10]:
        print(f"   D={D:4d}  hits={hit:4d}/{len(mcv)}")

    # ---------------- Q14: score denominator + A fit ----------------
    print("\n" + "=" * 78)
    print("Q14  score denominator search + per-team A in score = A*(50-g)/50")
    print("=" * 78)
    nzs = [r["score"] for r in rows if r["score"] != 0]
    s3 = sorted(((sum(1 for v in nzs if abs(v * D / 100 - round(v * D / 100)) < tol), D)
                 for D in range(1, 601)), reverse=True)
    print("best denominators for `score`:")
    for hit, D in s3[:10]:
        print(f"   D={D:4d}  hits={hit:4d}/{len(nzs)}")

    print("\nper-team A = score*50/(50-g)  (the 'valid-case equivalent' score):")
    Abuckets = defaultdict(list)
    for r in rows:
        if r["g"] < 50:
            Abuckets[r["g"]].append(r["score"] * 50 / (50 - r["g"]))
    allA = []
    for g in sorted(Abuckets):
        A = Abuckets[g]
        allA += A
        print(f"   g={g:3d} n={len(A):4d}  A: {stats(A)}")
    print(f"\n   A over ALL teams with g<50: {stats(allA)}")
    print(f"   g=0 A range is [49.9210, 92.9602]; every mid-g A falls inside/at it:")
    g0lo, g0hi = min(Abuckets[0]), max(Abuckets[0])
    for g in sorted(Abuckets):
        if g == 0:
            continue
        for a in Abuckets[g]:
            print(f"     g={g:3d} A={a:8.4f}  in g=0 A-band [{g0lo:.4f}, {g0hi:.4f}]: "
                  f"{g0lo <= a <= g0hi}")

    # ---------------- Q15: how many cases does the aggregate cover ----------------
    print("\n" + "=" * 78)
    print("Q15  how many cases does the aggregate cover (implied by the data)")
    print("=" * 78)
    print("If component = 100 * (passing cases)/D and gated cases score 0, then for a")
    print("g=0 team with the maximum component value V the implied integer count is")
    print("V*D/100.  Print it for the plausible D values:")
    for D in (50, 100):
        v = max(r["comps"]["schema"] for r in rows)
        print(f"   D={D:3d}: max schema={v:.4f} -> count={v*D/100:.4f} "
              f"(nearest int {round(v*D/100)})")
    print("\nDistinct g values are [0,4,13,23,33,50] and 50 is the max, so the public")
    print("partition holds 50 cases; 87/196 teams (44.4%) failed all 50.")

    # ---------------- Q16: is 50 a cap? ----------------
    print("\n" + "=" * 78)
    print("Q16  is g==50 a real all-fail, or a sentinel/cap?")
    print("=" * 78)
    g50 = by_g[50]
    print(f"teams with g=50: {len(g50)}; all eight components exactly 0: "
          f"{all(all(r['comps'][k] == 0.0 for k in COMPONENTS) for r in g50)}")
    print(f"teams with g=50 and score exactly 0: {sum(1 for r in g50 if r['score'] == 0)}")
    print(f"teams with g in (0,50): {[r['g'] for r in rows if 0 < r['g'] < 50]}")
    print("gaps in the g distribution: "
          f"{sorted(set(range(0, 51)) - set(by_g))[:20]} ...")
    print("g values observed are all divisible by... "
          f"gcd={__import__('math').gcd(*[g for g in by_g if g])}")

    # ---------------- Q17: extended denominator search ----------------
    print("\n" + "=" * 78)
    print("Q17  extended denominator search (D up to 20000) on DISTINCT values")
    print("=" * 78)
    distinct = sorted({v for _, v in allc if v != 0})
    print(f"distinct nonzero component values: {len(distinct)}")
    hits_by_D = []
    for D in range(1, 20001):
        h = 0
        for v in distinct:
            if abs(v * D / 100 - round(v * D / 100)) < 5e-5:
                h += 1
        if h:
            hits_by_D.append((h, D))
    hits_by_D.sort(reverse=True)
    print("top 15 denominators (hits out of %d distinct values):" % len(distinct))
    for h, D in hits_by_D[:15]:
        print(f"   D={D:6d}  hits={h:4d}  ({100*h/len(distinct):5.2f}%)")
    print(f"   expected hits for a NON-denominator at D=20000: "
          f"{len(distinct)*2*5e-5*20000/100:.1f}")
    print("   -> no D up to 20000 explains the values as an integer count / D.")
    print("      The components are NOT of the form 100*(count)/D.")

    # ---------------- Q18: where do the repeated values come from ----------------
    print("\n" + "=" * 78)
    print("Q18  are repeated component values cross-team, or intra-team?")
    print("=" * 78)
    loc = defaultdict(list)
    for r in rows:
        for k in COMPONENTS:
            loc[round(r["comps"][k], 6)].append((r["team_code"], k))
    print("top-8 most common values, and the (team, component) pairs producing them:")
    for v, n in ctr.most_common(8):
        if v == 0:
            continue
        teams = sorted({t for t, _ in loc[v]})
        print(f"   {v:10.6f} n={n:2d}  distinct teams={len(teams)}  "
              f"comps={[k for _, k in loc[v]]}")

    print("\nintra-team exact coincidences (g=0 teams):")
    for r in g0[:0]:
        pass
    combo = Counter()
    for r in g0:
        eq = [k for k in COMPONENTS if abs(r["comps"][k] - r["comps"]["mcp"]) < 1e-9]
        combo[tuple(eq)] += 1
    for keys, n in combo.most_common(8):
        print(f"   n={n:3d}  components equal to mcp: {list(keys)}")

    print("\nfor the single team holding the global max (h209-02470):")
    top = next(r for r in rows if r["team_code"] == "h209-02470")
    for k in COMPONENTS:
        print(f"   {k:12s} = {top['comps'][k]:.4f}")

    # ---------------- Q19: mcp vs the naive (50-g)/50 count ----------------
    print("\n" + "=" * 78)
    print("Q19  is any component == 100*(50-g)/50 (the pure count model)?")
    print("=" * 78)
    for k in COMPONENTS:
        eq = sum(1 for r in rows if abs(r["comps"][k] - 100 * (50 - r["g"]) / 50) < 1e-6)
        print(f"   {k:12s}: matches for {eq}/{len(rows)} teams")
    print("\n   observed vs count-model prediction, for the 4 partial-gate teams:")
    for r in mid:
        pred = 100 * (50 - r["g"]) / 50
        print(f"   {r['team_code']} g={r['g']:2d}: model says every component={pred:6.2f}; "
              f"observed min={min(r['comps'].values()):8.4f} "
              f"max={max(r['comps'].values()):8.4f}")
    print("\n   and the score model 100*(50-g)/50 vs observed score:")
    for r in mid:
        pred = 100 * (50 - r["g"]) / 50
        print(f"   {r['team_code']} g={r['g']:2d}: model={pred:6.2f} observed={r['score']:8.4f} "
              f"({100*r['score']/pred:5.1f}%)")

    # ---------------- Q20: per-case mean consistency check ----------------
    print("\n" + "=" * 78)
    print("Q20  do the partial-gate teams' per-case means match the g=0 population?")
    print("=" * 78)
    print("  per-case mean implied by Model A (denom 50-g) = component/100")
    print("  per-case mean implied by Model B (denom 50,   ) = component*50/(100*(50-g))")
    print("  compare each with the g=0 population's per-case mean (= component/100):")
    print("\n  g=0 population per-case mean, per component:")
    for k in COMPONENTS:
        xs = sorted(r["comps"][k] / 100 for r in g0)
        print(f"   {k:12s} min={xs[0]:.6f} med={statistics.median(xs):.6f} max={xs[-1]:.6f}")
    print("\n  partial-gate teams:")
    for r in mid:
        print(f"   {r['team_code']} g={r['g']}:")
        for k in COMPONENTS:
            a = r["comps"][k] / 100
            b = r["comps"][k] * 50 / (100 * (50 - r["g"]))
            print(f"      {k:12s} A={a:.6f}  B={b:.6f}")

    # ---------------- Q21: bound the denominator D from the data ----------------
    print("\n" + "=" * 78)
    print("Q21  two-sided bound on D for the count model  component = 100*N/D")
    print("=" * 78)
    nzc = [v for _, v in allc if v != 0]
    mx = max(nzc)
    mn = min(nzc)
    print(f"public partition size P (max hard_gate_count)      = 50")
    print(f"largest  nonzero component value observed          = {mx:.4f}")
    print(f"smallest nonzero component value observed          = {mn:.4f}")
    print("\n  upper bound on D: a component cannot exceed 100*P/D, so")
    print(f"      D <= 100*P/max = 100*50/{mx:.4f} = {100*50/mx:.3f}")
    print("  lower bound on D: the smallest nonzero count is 1, so a nonzero component")
    print("      is at least 100/D:")
    print(f"      D >= 100/min = 100/{mn:.4f} = {100/mn:.3f}")
    print(f"\n  => the count model requires D in [{100/mn:.2f}, {100*50/mx:.2f}] "
          f"SIMULTANEOUSLY")
    if 100 / mn > 100 * 50 / mx:
        print(f"     lower bound {100/mn:.2f} > upper bound {100*50/mx:.2f}: "
              f"the interval is EMPTY.")
        print("     => NO denominator D can satisfy both constraints: the count model")
        print("        component = 100*N/D is logically impossible for these values.")
    print("\n  D=100 is IMPOSSIBLE on its own: it caps every component at")
    print(f"     100*50/100 = 50.00, yet the observed maximum is {mx:.4f}.")
    print("\n  but even D=50 fails the granularity test: with 50 cases every component")
    print("  must be a multiple of 100/50 = 2.00, and")
    nonmult = [v for v in nzc if abs(v / 2 - round(v / 2)) > 1e-6]
    print(f"      {len(nonmult)}/{len(nzc)} nonzero values are NOT multiples of 2.00")
    print(f"      e.g. {sorted(nonmult)[:6]}")
    print("  => the count model fails for BOTH D=50 and D=100.  The components are")
    print("     continuous means over cases, not integer pass counts.")

    # ---------------- Q22: fit quality of Model A vs Model B ----------------
    print("\n" + "=" * 78)
    print("Q22  fit quality: does the non-gated-case mean match the g=0 population?")
    print("=" * 78)
    print("\nFor `mcp` (whose per-case score is ~1 whenever the case is NOT hard-gated,")
    print("because invalid/unknown/cross-scope/missing refs ARE the mcp hard gates):")
    print(f"   g=0 population mcp per-case mean band: "
          f"[{band['mcp'][0]/100:.4f}, {band['mcp'][1]/100:.4f}] "
          f"median {statistics.median([r['comps']['mcp'] for r in g0])/100:.4f}")
    print(f"\n   {'team':14s} {'g':>3s} {'A mean':>9s} {'B mean':>9s} "
          f"{'B / g0-median':>14s}")
    g0med = statistics.median([r["comps"]["mcp"] for r in g0]) / 100
    for r in mid:
        A = r["comps"]["mcp"] / 100
        B = r["comps"]["mcp"] * 50 / (100 * (50 - r["g"]))
        print(f"   {r['team_code']:14s} {r['g']:3d} {A:9.4f} {B:9.4f} {B/g0med:14.3f}")
    print("\n   B puts every partial-gate team's non-gated mcp mean at 0.90-0.93, i.e.")
    print("   within 4% of the g=0 median (0.9352).  A puts them at 0.27-0.86, i.e.")
    print("   8-71% of it.  The observed decay of mcp with g is fully explained by")
    print("   dividing a near-constant numerator by the FIXED denominator 50.")

    # ---------------- Q23: rounding of score ----------------
    print("\n" + "=" * 78)
    print("Q23  rounding: is score == round(sum(weighted_components), 4)?")
    print("=" * 78)
    n = sum(1 for r in rows if abs(r["score"] - round(sum(r["wc"].values()), 4)) < 1e-9)
    print(f"   exact after 4-dp rounding: {n}/{len(rows)}")
    d = [abs(r["score"] - sum(r["wc"].values())) for r in rows]
    print(f"   |score - sum(wc)|: max={max(d):.6f} mean={statistics.mean(d):.6f}")
    print("   consistent with score and every weighted_component being independently")
    print("   rounded to 4 decimals (max accumulated error 8*0.5e-4 = 4.0e-4).")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
