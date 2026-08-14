#!/usr/bin/env python3
# ==========================================================================
# swap_data.py  —  swap CIRÚRGICO (Liora Central v48)
# Injeta os 3 arrays gerados pelo process.py dentro do HTML, trocando APENAS
# const rawData / const RAW / const HC_PROP e alinhando o BP_TODAY.
# Preserva TODOS os patches já aplicados no HTML.
#
# Princípio: nunca reconstruir o HTML do zero. Sempre partir do HTML de
# trabalho ATUAL (base_atual.html), que carrega todos os patches.
#
# Uso:  python3 swap_data.py base_atual.html liora_central_v48.html
# (defaults: SRC=base_atual.html  OUT=liora_central_v48.html)
# ==========================================================================
import json, io, re, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else 'base_atual.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'liora_central_v48.html'

def enc(s):  # ORDEM OBRIGATÓRIA: & -> &amp;  DEPOIS  " -> &quot;
    return s.replace('&', '&amp;').replace('"', '&quot;')
def dec(s):  # reverso: &quot; -> "  DEPOIS  &amp; -> &
    return s.replace('&quot;', '"').replace('&amp;', '&')

def find_array(decoded, var):
    """Localiza 'const VAR = [ ... ]' por contador de profundidade de colchetes
    (regex simples não funciona: há objetos aninhados e arrays dentro de arrays)."""
    i = decoded.find('const '+var+' = [')
    if i < 0: i = decoded.find('const '+var+'=[')
    if i < 0: return None
    start = decoded.find('[', i)
    depth=0; j=start; instr=False; esc=False; q=''
    while j < len(decoded):
        c = decoded[j]
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

def frame_bounds(html):
    out=[]
    for m in re.finditer(r'srcdoc="', html):
        s=m.end(); e=html.find('"></iframe>', s)
        if e!=-1: out.append((s,e))
    return out

payload = {
 'rawData': json.load(open('new_rawData.json')),
 'RAW':     json.load(open('new_RAW.json')),
 'HC_PROP': json.load(open('new_HC_PROP.json')),
 'ANTECIPA': json.load(open('new_ANTECIPA.json')),
 'ANT_FIELD': json.load(open('new_ANT_FIELD.json')),
 'MISSAO': json.load(open('new_MISSAO.json')),
 'MISSAO_ROSTER': json.load(open('new_MISSAO_ROSTER.json')),
}

report=[]
for var, data in payload.items():
    done=False
    for (s,e) in frame_bounds(h):
        raw_frame = h[s:e]
        if ('const '+var+' = [') not in raw_frame and ('const '+var+'=[') not in raw_frame:
            continue
        decoded = dec(raw_frame)
        pos = find_array(decoded, var)
        if not pos: continue
        a,b = pos
        old_enc = enc(decoded[a:b])
        cnt = raw_frame.count(old_enc)
        assert cnt == 1, f'[{var}] array codificado encontrado {cnt}x (esperava 1)'
        new_enc = enc(json.dumps(data, ensure_ascii=False, separators=(',',':')))
        h = h[:s] + raw_frame.replace(old_enc, new_enc, 1) + h[e:]
        report.append(f'{var}: {len(data)} itens injetados')
        done=True
        break
    assert done, f'[{var}] não encontrado em nenhum frame'

# ---- BP_TODAY = data máxima dos dados (alinha TODAS as ocorrências) -------
# CUIDADO: trocar SÓ "BP_TODAY = '...'". A curva de meta acumulada usa as
# mesmas datas como CHAVE de objeto — nunca fazer replace global da data.
maxd = max([x['date'] for x in payload['rawData'] if x['date']] +
           [r['date'] for r in payload['RAW'] if r['date']])
occ = set(re.findall(r"BP_TODAY = '(\d{4}-\d{2}-\d{2})'", h))
for d in occ:
    if d != maxd:
        h = h.replace(f"BP_TODAY = '{d}'", f"BP_TODAY = '{maxd}'")
        report.append(f"BP_TODAY {d} -> {maxd}")
if all(d == maxd for d in occ):
    report.append(f"BP_TODAY já em {maxd} (sem mudança)")

io.open(OUT,'w',encoding='utf-8').write(h)
print('SWAP OK:')
for r in report: print('  -', r)
