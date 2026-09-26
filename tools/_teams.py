import json, httpx2
env={}
for line in open(".env",encoding="utf-8"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["COMPETITION_TEAM_API_KEY"]; base=env["COMPETITION_API_URL"].rstrip("/")
h={"Authorization":f"Bearer {key}","Accept":"application/json"}
rows=[]
with httpx2.Client(headers=h, timeout=30, follow_redirects=True) as c:
    lb=c.get(base+"/api/v2/leaderboard/l3b").json()["entries"]
    for e in lb:
        try:
            r=c.get(base+f"/api/v2/leaderboard/l3b/teams/{e['team_code']}")
            d=r.json()
            rows.append((d.get("score"), d.get("hard_gate_count"), d.get("components",{}), d.get("team_code")))
        except Exception as ex:
            rows.append((e.get("score"), None, {"ERR":str(ex)}, e.get("team_code")))
rows.sort(key=lambda r: -(r[0] or 0))
out=[]
out.append(f"{'score':>8} {'gates':>5} | sem evi mcp con sch cal wf eff | team")
for s,g,c_,t in rows:
    if g is None: out.append(f"{s:8.2f}   ?  ERR {t}"); continue
    out.append(f"{s:8.2f} {g:5d} | {c_.get('semantic',0):.1f} {c_.get('evidence',0):.1f} {c_.get('mcp',0):.1f} {c_.get('consistency',0):.1f} {c_.get('schema',0):.1f} {c_.get('calibration',0):.1f} {c_.get('workflow',0):.1f} {c_.get('efficiency',0):.1f} | {t}")
open("tools/_teams.txt","w",encoding="utf-8").write("\n".join(out))
print("rows:", len(rows))
