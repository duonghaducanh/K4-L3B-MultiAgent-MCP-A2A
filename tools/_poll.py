"""Poll our team's breakdown until the score changes; write UTF-8."""
from __future__ import annotations
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2
from student_agent.config import Settings

s = Settings.load(ROOT)
h = {"Authorization": f"Bearer {s.team_api_key}"}
ORDER = ["semantic","evidence","mcp","consistency","schema","calibration","workflow","efficiency"]
W = {"semantic":.40,"evidence":.15,"mcp":.15,"consistency":.10,"schema":.05,
     "calibration":.05,"workflow":.05,"efficiency":.05}
lines = []
with httpx2.Client(headers=h, timeout=60.0) as c:
    me = c.get(f"{s.competition_api_url}/api/v2/me").json()
    code = me["team_code"]
    lines.append(f"team={code}")
    prev = None
    for i in range(20):
        d = c.get(f"{s.competition_api_url}/api/v2/leaderboard/l3b/teams/{code}").json()
        sc = d.get("score")
        lines.append(f"[{i}] rank={d.get('rank')} score={sc} gates={d.get('hard_gate_count')} "
                     f"submitted={d.get('submitted_at')}")
        if sc is not None and sc != prev:
            comps = d.get("components", {})
            w = d.get("weighted_components", {})
            for k in ORDER:
                lines.append(f"    {k:12s} {comps.get(k,0):8.4f} x{W[k]:.2f} = {w.get(k,0):7.4f}")
            prev = sc
        time.sleep(15)
pathlib.Path(ROOT / "tools/_o_poll.txt").write_text("\n".join(lines), encoding="utf-8")
print("done")
