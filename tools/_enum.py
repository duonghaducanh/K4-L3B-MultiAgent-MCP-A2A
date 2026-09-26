"""Extract every enum/const/required constraint from the output schemas and test our outputs."""
from __future__ import annotations
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
S = ROOT / "contracts/schemas"
lines=[]; p=lines.append

defs = {}
for name in ("l3a-output-v2.schema.json","l3b-output-v2.schema.json"):
    s = json.loads((S/name).read_text(encoding="utf-8"))
    for k, v in (s.get("$defs") or {}).items():
        defs.setdefault(k, v)

# print every enum found anywhere
def walk(node, path, out):
    if isinstance(node, dict):
        if "enum" in node:
            out.append((path, node["enum"]))
        if "const" in node:
            out.append((path, [node["const"]]))
        for k, v in node.items():
            walk(v, f"{path}/{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]", out)

enums=[]
walk(defs, "$defs", enums)
seen=set()
for path, vals in enums:
    key=(path.rsplit("/",1)[0], tuple(map(str,vals)))
    if key in seen: continue
    seen.add(key)
    p("%-58s %s" % (path, vals))
pathlib.Path(ROOT/"tools/_o_enum.txt").write_text("\n".join(lines),encoding="utf-8")
print("ok", len(lines))
