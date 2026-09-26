"""Fetch the live leaderboard top-30 and locate our team."""
from __future__ import annotations
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2
from student_agent.config import Settings

s = Settings.load(ROOT)
h = {"Authorization": f"Bearer {s.team_api_key}"}
out = []
with httpx2.Client(headers=h, timeout=60.0) as c:
    r = c.get(f"{s.competition_api_url}/api/v2/leaderboard/l3b")
    out.append("status=%s" % r.status_code)
    try:
        d = r.json()
    except Exception:
        out.append(r.text[:1000]); d = None
    if d is not None:
        rows = d if isinstance(d, list) else (d.get("entries") or d.get("leaderboard") or d.get("rows") or [])
        out.append("n=%d" % len(rows))
        out.append("top 20:")
        for row in rows[:20]:
            out.append("  %s" % json.dumps(row, ensure_ascii=False))
        out.append("--- our key submissions ---")
        # try identify by class/name
        for row in rows:
            nm = str(row.get("display_name", ""))
            if "F4" in nm or "K4L3B" in nm:
                out.append("  %s" % json.dumps(row, ensure_ascii=False))
pathlib.Path(ROOT / "tools/_o_lb.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
