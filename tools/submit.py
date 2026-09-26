"""Package the current artifacts and upload them, then print the breakdown.

    ./.venv/Scripts/python.exe tools/submit.py [--note TEXT]

The API key is read from .env and never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx2  # noqa: E402

from score import BASE, ORDER, WEIGHTS, client, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="dist/submission.zip")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    env = load_env()
    zip_path = ROOT / args.zip
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    print(f"zip={zip_path.name} entries={len(names)}")
    print("  sample:", names[:3], "...", names[-2:])

    data = {
        "class_id": env.get("CLASS_ID", "H209"),
        "student_last5": env.get("STUDENT_LAST5", "02859"),
    }
    if args.note:
        data["note"] = args.note

    with client() as c:
        with zip_path.open("rb") as fh:
            files = {"file": (zip_path.name, fh, "application/zip")}
            r = c.post(f"{BASE}/api/v2/submissions", data=data, files=files)
        print("upload status:", r.status_code)
        print("upload body:", r.text[:600])
        if r.status_code >= 400:
            return
        me = c.get(f"{BASE}/api/v2/me").json()
        code = me["team_code"]
        d = c.get(f"{BASE}/api/v2/leaderboard/l3b/teams/{code}").json()
    print(f"\nrank {d.get('rank')}  {d.get('team_code')}  score={d.get('score')}  gates={d.get('hard_gate_count')}")
    comps = d.get("components", {})
    w = d.get("weighted_components", {})
    for k in ORDER:
        weight, label = WEIGHTS[k]
        print(f"  {k:12s} {comps.get(k, 0):8.4f}  x{weight:.2f} = {w.get(k, 0):7.4f}   {label}")


if __name__ == "__main__":
    main()
