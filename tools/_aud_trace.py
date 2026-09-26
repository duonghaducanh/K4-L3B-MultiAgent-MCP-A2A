import json, glob
from collections import defaultdict, Counter

OUT = open('tools/_aud_trace.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

lines=[json.loads(l) for l in open('traces/trace.jsonl',encoding='utf-8')]
p('total events:', len(lines))
p('event types:', Counter(e['event_type'] for e in lines))
bycase=defaultdict(list)
for e in lines: bycase[e['case_id']].append(e)
p('cases:', len(bycase))

# policy refs per case
p('\n--- policy_decided refs per case ---')
polrefs={}
for cid in sorted(bycase):
    for e in bycase[cid]:
        if e['event_type']=='policy_decided':
            polrefs[cid]=tuple(e.get('evidence_refs') or [])
for cid in sorted(polrefs):
    p(cid, polrefs[cid], 'decision=%s'%[e.get('decision_code') for e in bycase[cid] if e['event_type']=='policy_decided'])

p('\n--- per-case tool refs ---')
for cid in sorted(bycase):
    tools=defaultdict(list)
    for e in bycase[cid]:
        if e['event_type']=='tool_result_consumed':
            tools[e['tool_name']].extend(e['evidence_refs'])
    p(cid, {t:tools[t] for t in tools})

p('\n--- case_finalized count ---')
p(Counter(e['case_id'] for e in lines if e['event_type']=='case_finalized'))
OUT.close()
print('done')
