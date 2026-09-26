import json, httpx2, sys
env={}
for line in open(".env",encoding="utf-8"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["COMPETITION_TEAM_API_KEY"]; base=env["COMPETITION_API_URL"].rstrip("/")
h={"Authorization":f"Bearer {key}","Accept":"application/json"}
out=[]
with httpx2.Client(headers=h, timeout=30, follow_redirects=True) as c:
    lb=c.get(base+"/api/v2/leaderboard/l3b").json()
    entries=lb.get("entries",[])
    out.append(f"leaderboard entries: {len(entries)}")
    mine=[e for e in entries if abs(e.get("score",0)-45.9335)<0.01]
    out.append("my entry: "+json.dumps(mine, ensure_ascii=False))
    # try breakdown for a few
    for e in entries[:1]+mine[:1]:
        for path in [f"/api/l3b/leaderboard/{e['class_id']}/{e['team_code']}/breakdown",
                     f"/api/v2/leaderboard/l3b/teams/{e['team_code']}"]:
            try:
                r=c.get(base+path)
                out.append(f"GET {path} -> {r.status_code} {r.text[:900]}")
            except Exception as ex:
                out.append(f"GET {path} ERR {type(ex).__name__}")
open("tools/_bd.txt","w",encoding="utf-8").write("\n".join(out))
print("done")
