import json, httpx2
env={}
for line in open(".env",encoding="utf-8"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["COMPETITION_TEAM_API_KEY"]; base=env["COMPETITION_API_URL"].rstrip("/")
h={"Authorization":f"Bearer {key}","Accept":"application/json"}
sid="sub_QdhpOPoypS5eF9n1saoa1GF-AnlmRbB4"
out=[]
with httpx2.Client(headers=h, timeout=30, follow_redirects=True) as c:
    for p in [f"/api/v2/submissions/{sid}", f"/api/submissions/{sid}",
              f"/api/v2/submissions/{sid}/report", f"/api/v2/submissions/{sid}/cases",
              f"/api/v2/submissions/{sid}/gates", "/api/v2/me/submissions?detail=1"]:
        try:
            r=c.get(base+p)
            out.append(f"--- GET {p} -> {r.status_code}\n{r.text[:2500]}\n")
        except Exception as e:
            out.append(f"--- GET {p} ERR {type(e).__name__}: {e}\n")
open("tools/_det.txt","w",encoding="utf-8").write("\n".join(out))
# grep bundle
try:
    txt=httpx2.get("https://n7-competition.pages.dev/assets/index-BBesytlK.js", timeout=40).text
    for kw in ["hard_gate","required_evidence","evidence_group","missing_required","case_budget","max_calls","call_budget"]:
        i=txt.find(kw)
        if i>=0:
            out.append(f"=== BUNDLE {kw} @ {i}\n{txt[max(0,i-300):i+400]}\n")
    open("tools/_det.txt","a",encoding="utf-8").write("\n".join(out[-8:]))
except Exception as e:
    print("bundle err", e)
print("done")
