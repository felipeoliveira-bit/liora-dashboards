#!/usr/bin/env python3
# swap_mobile.py — injeta rawData e RAW_PROP no HTML mobile (script normal, sem srcdoc)
# e alinha PROP_TODAY a data maxima. Uso: python3 swap_mobile.py base.html out.html
import json, io, re, sys
SRC, OUT = sys.argv[1], sys.argv[2]
def find_array(s, var):
    i = s.find('const '+var+' = [')
    if i < 0: i = s.find('const '+var+'=[')
    if i < 0: return None
    start = s.find('[', i); depth=0; j=start; instr=False; esc=False; q=''
    while j < len(s):
        c=s[j]
        if instr:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==q: instr=False
        else:
            if c=='"' or c=="'": instr=True; q=c
            elif c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: return (start, j+1)
        j+=1
    return None
h = io.open(SRC, encoding='utf-8').read()
payload = {'rawData': json.load(open('new_rawData.json')),
           'RAW_PROP': json.load(open('new_RAW_PROP.json'))}
report=[]
for var, data in payload.items():
    pos = find_array(h, var)
    assert pos, f'[{var}] nao encontrado'
    a,b = pos
    new = json.dumps(data, ensure_ascii=False, separators=(',',':'))
    h = h[:a] + new + h[b:]
    report.append(f'{var}: {len(data)} itens injetados')
maxd = max([x['date'] for x in payload['rawData'] if x.get('date')] +
           [r['date'] for r in payload['RAW_PROP'] if r.get('date')])
occ = set(re.findall(r"PROP_TODAY = '(\d{4}-\d{2}-\d{2})'", h))
for d in occ:
    if d != maxd:
        h = h.replace(f"PROP_TODAY = '{d}'", f"PROP_TODAY = '{maxd}'"); report.append(f"PROP_TODAY {d} -> {maxd}")
if all(d==maxd for d in occ): report.append(f"PROP_TODAY ja em {maxd}")
io.open(OUT,'w',encoding='utf-8').write(h)
print('SWAP MOBILE OK:'); [print('  -',r) for r in report]
