"""Where do we diverge from the policy answer key?"""
from __future__ import annotations
import json, pathlib
from collections import Counter
ROOT = pathlib.Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "tools/_policy.json").read_text(encoding="utf-8"))["data"]["rules"]
TOPICS = ("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
          "refund_pending","refund_failed","unsupported_claim","canceled_order_paid",
          "unavailable_order_paid","late_delivery_seller")
lines = []
def p(s): lines.append(str(s))

conf = Counter(); status = Counter(); action = Counter(); partytype = Counter()
mismatch = []; refundbad = []
for f in sorted((ROOT / "outputs").glob("*.json")):
    o = json.loads(f.read_text(encoding="utf-8"))
    n = int(f.stem.rsplit("_", 1)[1])
    topic = TOPICS[(n - 1) % 10]
    rule = policy[topic]
    a = o["assessment"]
    conf[a["confidence"]] += 1
    status[a["case_status"]] += 1
    for act in o["resolution_actions"]:
        action[act] += 1
    for rp in o["root_cause_analysis"]["responsible_parties"]:
        partytype[rp["party_type"]] += 1
    if a["case_status"] != rule["case_status"] or list(o["resolution_actions"]) != [rule["recommended_action"]]:
        mismatch.append((f.stem, topic, a["case_status"], rule["case_status"],
                         o["resolution_actions"], rule["recommended_action"]))
    refund = o["financial_resolution"]["recommended_refund_brl"]
    if rule["refund_brl"] == 0 and refund != 0:
        refundbad.append((f.stem, topic, refund))

p("confidence distribution: %s" % sorted(conf.items()))
p("case_status distribution: %s" % sorted(status.items()))
p("resolution_actions distribution: %s" % sorted(action.items()))
p("responsible party_type distribution: %s" % sorted(partytype.items()))
p("")
p("status/action mismatches vs policy: %d" % len(mismatch))
for m in mismatch[:40]:
    p("   %s topic=%-24s got=(%s,%s) want=(%s,%s)" % m)
p("")
p("nonzero refund on a no-refund topic: %d" % len(refundbad))
for r in refundbad[:20]:
    p("   %s %s refund=%s" % r)
pathlib.Path(ROOT / "tools/_o_diag.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
