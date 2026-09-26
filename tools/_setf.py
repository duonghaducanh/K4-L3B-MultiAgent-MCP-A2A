"""Profile every set/array-valued field for uniformity across the 100 outputs."""
from __future__ import annotations
import json, pathlib
from collections import Counter
ROOT = pathlib.Path(__file__).resolve().parents[1]
lines=[]; p=lines.append

def shape(v):
    if isinstance(v, list):
        return "list[%d]" % len(v)
    return type(v).__name__

fields = Counter()
profiles = {}
for f in sorted((ROOT/"outputs").glob("*.json")):
    o = json.loads(f.read_text(encoding="utf-8"))
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            if node and isinstance(node[0], dict):
                profiles.setdefault(path, Counter())[tuple(sorted(node[0]))] += 1
            else:
                profiles.setdefault(path, Counter())[json.dumps(node)] += 1
    walk(o, "")
for path in sorted(profiles):
    c = profiles[path]
    p("%-46s %2d variants" % (path, len(c)))
    for val, n in c.most_common(6):
        p("      x%-4d %s" % (n, str(val)[:110]))
pathlib.Path(ROOT/"tools/_o_setf.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
