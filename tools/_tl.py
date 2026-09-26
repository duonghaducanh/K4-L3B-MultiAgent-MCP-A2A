"""Timeline of the original run: look for a run-rotation boundary of size 23."""

from __future__ import annotations

import glob
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = sorted((os.path.getmtime(p), Path(p).stem) for p in glob.glob(str(ROOT / "outputs" / "*.json")))
print(f"{'idx':>4} {'local time':>10} {'case':>16}  gap_s")
prev = None
for i, (t, cid) in enumerate(rows, 1):
    gap = "" if prev is None else f"{t - prev:6.1f}"
    print(f"{i:>4} {time.strftime('%H:%M:%S', time.localtime(t)):>10} {cid:>16}  {gap}")
    prev = t

print("\n--- mtime -> case-number map (solve order) ---")
order = [cid[-3:] for _, cid in rows]
print(" ".join(order))
