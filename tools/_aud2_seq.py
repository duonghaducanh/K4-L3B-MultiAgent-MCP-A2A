import json, sys
cid = sys.argv[1] if len(sys.argv) > 1 else "L3B_CASE_058"
evs = []
for l in open('traces/trace.jsonl', encoding='utf-8'):
    if l.strip():
        e = json.loads(l)
        if e['case_id'] == cid:
            evs.append(e)
print('=====', cid, 'n_events', len(evs))
for e in evs:
    print(f"   {e['event_type']:22s} {str(e.get('actor')):16s} tool={str(e.get('tool_name')):22s} dc={e.get('decision_code')}")
