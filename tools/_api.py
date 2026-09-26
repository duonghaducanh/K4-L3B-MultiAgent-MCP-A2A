import json, httpx2
env={}
for line in open(".env",encoding="utf-8"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["COMPETITION_TEAM_API_KEY"]; base=env["COMPETITION_API_URL"].rstrip("/")
h={"Authorization":f"Bearer {key}","Accept":"application/json"}
paths=["/api/v2/me/submissions","/api/v2/submissions","/api/v2/competitions","/api/v2/runs",
       "/api/l3b/submissions","/api/l3b/leaderboard","/api/v2/leaderboard/l3b"]
with httpx2.Client(headers=h, timeout=25, follow_redirects=True) as c:
    for p in paths:
        try:
            r=c.get(base+p)
            body=r.text
            if len(body)>1500: body=body[:1500]+"…"
            print(f"--- GET {p} -> {r.status_code}\n{body}\n")
        except Exception as e:
            print(f"--- GET {p} ERR {type(e).__name__}: {e}\n")
