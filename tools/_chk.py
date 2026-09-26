import json, os
# 1. does the cached learn file contain get_policy?
d = json.load(open("tools/_learn1.json", encoding="utf-8"))
print("cached cases:", list(d.keys()))
print("tools per case:", {k: sorted(v.keys()) for k, v in list(d.items())[:2]})
# 2. case 010 output responsible parties
o = json.load(open("outputs/L3B_CASE_010.json", encoding="utf-8"))
print("\nCASE 010 output:", o["assessment"]["primary_issue"])
print("  responsible:", json.dumps(o["root_cause_analysis"]["responsible_parties"], ensure_ascii=False))
print("  affected sellers:", o["affected_entities"]["seller_ids"])
print("  refund lines:", json.dumps(o["financial_resolution"]["refund_lines"], ensure_ascii=False))
o2 = json.load(open("outputs/L3B_CASE_009.json", encoding="utf-8"))
print("\nCASE 009 output:", o2["assessment"]["primary_issue"])
print("  responsible:", json.dumps(o2["root_cause_analysis"]["responsible_parties"], ensure_ascii=False))
print("  affected sellers:", o2["affected_entities"]["seller_ids"])
