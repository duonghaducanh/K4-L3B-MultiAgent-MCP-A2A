import json, pathlib
ROOT=pathlib.Path('.')
out=[]
for n in ['001','012','039','071','098']:
    d=json.loads((ROOT/f'inputs/L3B_CASE_{n}.json').read_text(encoding='utf-8'))
    out.append('===== '+n)
    out.append(json.dumps(d,indent=1,ensure_ascii=False))
    out.append('')
(ROOT/'tools/_o_in.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
