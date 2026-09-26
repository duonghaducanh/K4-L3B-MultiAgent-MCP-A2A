import json, pathlib, urllib.request, collections, sys
URL="https://n7-competition.pages.dev/api/v2/leaderboard/l3b"
try:
    req=urllib.request.Request(URL, headers={"User-Agent":"curl/8"})
    raw=urllib.request.urlopen(req, timeout=30).read()
except Exception as e:
    print("ERR", e); sys.exit(1)
j=json.loads(raw)
def walk(o):
    if isinstance(o,dict):
        if "team_code" in o or "team_id" in o or "components" in o:
            yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o,list):
        for v in o: yield from walk(v)
rows=[r for r in walk(j)]
print("rows:", len(rows))
# find component keys
keys=collections.Counter()
for r in rows:
    comp=r.get("components") or r.get("breakdown") or {}
    if isinstance(comp,dict):
        for k in comp: keys[k]+=1
print("component keys:", dict(keys))
# maxima
mx=collections.defaultdict(lambda: -1)
arg={}
for r in rows:
    comp=r.get("components") or r.get("breakdown") or {}
    if not isinstance(comp,dict): continue
    for k,v in comp.items():
        if isinstance(v,(int,float)) and v>mx[k]:
            mx[k]=v; arg[k]=r.get("team_code") or r.get("team_id") or r.get("name")
for k in sorted(mx):
    print(f"  max {k:14s} = {mx[k]:.4f}  by {arg[k]}")
print()
print("sample row keys:", sorted(rows[0].keys())[:20] if rows else None)
