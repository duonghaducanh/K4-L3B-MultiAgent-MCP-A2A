import json, sys
from collections import defaultdict

CASE = sys.argv[1] if len(sys.argv)>1 else 'L3B_CASE_012'
ev=defaultdict(list)
for line in open('traces/trace.jsonl',encoding='utf-8'):
    line=line.strip()
    if not line: continue
    try: e=json.loads(line)
    except: continue
    s=json.dumps(e)
    if CASE in s:
        ev[e.get('event_type','?')].append(e)

OUT=open('tools/_aud_case.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
p('=== trace events for %s ===' % CASE)
for k,v in ev.items(): p('  %-28s %d' % (k,len(v)))
p('')
for k,v in ev.items():
    for e in v:
        p('--- %s' % k)
        p(json.dumps(e, ensure_ascii=False)[:2500])
        p('')
OUT.close()
print('done', {k:len(v) for k,v in ev.items()})
