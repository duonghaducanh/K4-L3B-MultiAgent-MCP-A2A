import json, glob, collections
# For each case, compare opened_at against the 2 history purchase timestamps (from trace? no) -> use _learn1 + inputs
# We know for cached cases. Instead: use output 'data_conflicts' presence + issue to infer.
# Better: read inputs and the trace's tool_result_consumed cannot give timestamps. So use _learn1 for 9 cases + replay cache if any.
d = json.load(open("tools/_learn1.json", encoding="utf-8"))
print(f"{'case':14s} {'opened':10s} {'purch_A':10s} {'purch_B':10s} {'target_sel':10s} {'status_A':12s} {'status_B':12s}")
for cid in sorted(d.keys()):
    num = cid[-3:]
    inp = json.load(open(f"inputs/L3B_CASE_{num}.json", encoding="utf-8"))
    orders = d[cid]["get_customer_history"]["data"]["orders"]
    ts = sorted(o["order_purchase_timestamp"][:10] for o in orders)
    opened = inp["opened_at"][:10]
    # select
    sel = max([t for t in ts if t <= opened], default=None)
    st = {o["order_purchase_timestamp"][:10]: o["order_status"] for o in orders}
    print(f"{cid:14s} {opened:10s} {ts[0]:10s} {ts[1] if len(ts)>1 else '-':10s} {str(sel):10s} {st.get(ts[0],'?'):12s} {st.get(ts[-1],'?'):12s}")
