"""Audit 2 - lattice analysis of leaderboard component values.

Goal: infer the granularity of the per-case score that produces these
component values, so we can tell how many cases are "bad" for us.

Usage: python tools/_aud2_lattice.py
"""
from __future__ import annotations

import json
from fractions import Fraction
from math import gcd
from pathlib import Path

CACHE = Path("tools/_all_bd2.json")


def frac_lattice(values, max_den=200000):
    """Find smallest D such that every value*D is (nearly) an integer."""
    for D in range(1, max_den + 1):
        ok = True
        for v in values:
            x = v * D
            if abs(x - round(x)) > 1e-6 * max(1.0, abs(x)):
                ok = False
                break
        if ok:
            return D
    return None


def main():
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    comp = {}
    for tc, e in d.items():
        c = e.get("components") or {}
        for k, v in c.items():
            if v is not None:
                comp.setdefault(k, set()).add(round(float(v), 6))

    for k in ("mcp", "schema", "workflow", "consistency", "semantic", "calibration"):
        vals = sorted(comp.get(k, set()))
        # pairwise diffs -> gcd of diffs is the lattice spacing
        base = vals[0]
        diffs = [round(v - base, 6) for v in vals[1:]]
        # express as integers of 1e-6 and gcd
        ints = [round(x * 1_000_000) for x in diffs if x > 0]
        g = 0
        for i in ints:
            g = gcd(g, i)
        spacing = g / 1_000_000
        print(f"{k:12s} distinct={len(vals):<4} max={vals[-1]:<9} min={vals[0]:<9} "
              f"lattice_spacing~{spacing:.6f}  (1/spacing={1/spacing if spacing else 0:.1f})")

    print()
    mcp = sorted(comp["mcp"])
    top = mcp[-1]
    print(f"max mcp = {top}  100-max = {100-top:.4f}")
    for D in (100, 200, 500, 1000, 2000, 5000):
        print(f"  max*D/100 with D={D}: {top*D/100:.6f}  (near int? "
              f"{abs(top*D/100-round(top*D/100))<1e-3})")

    ours = 93.7687
    print(f"\nours={ours}  loss vs max = {top-ours:.4f}")
    print(f"ratio loss/max_loss = {(top-ours)/(100-top):.4f}")
    # if loss = c * n_bad with small n
    for n in range(1, 21):
        print(f"   n_bad={n:<3} per-case loss={(top-ours)/n:.5f}", end="")
        print(f"   (max_loss/n={ (100-top)/n:.5f})")

    print("\n-- all distinct mcp values --")
    print(mcp)


if __name__ == "__main__":
    main()
