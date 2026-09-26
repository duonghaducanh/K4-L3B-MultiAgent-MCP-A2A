"""Identify our team row + fetch our own breakdown; no secrets printed."""
from __future__ import annotations
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2
from student_agent.config import Settings

s = Settings.load(ROOT)
h = {"Authorization": f"Bearer {s.team_api_key}"}
base = s.competition_api_url
out = []
with httpx2.Client(headers=h, timeout=60.0) as c:
    r = c.get(f"{base}/api/v2/leaderboard/l3b/teams/me")
    out.append("me status=%s" % r.status_code)
    out.append(r.text[:2000])
pathlib.Path(ROOT / "tools/_o_me.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
