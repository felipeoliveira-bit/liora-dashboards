#!/usr/bin/env python3
# validate.py — node --check em cada bloco <script> dos 7 iframes + checa
# que não há aspas duplas literais dentro de nenhum srcdoc.
# Uso: python3 validate.py [liora_central_v48.html]
import re, subprocess, os, tempfile, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else 'liora_central_v48.html'
doc = open(PATH, encoding='utf-8').read()

# 1) aspas literais por srcdoc (deve ser 0 em todos)
bad = 0
for i, m in enumerate(re.finditer(r'srcdoc="', doc)):
    s = m.end(); e = doc.find('"></iframe>', s)
    n = doc[s:e].count('"')
    if n: bad += 1; print(f'  srcdoc {i}: {n} aspas literais!')
print('srcdocs com aspas literais:', bad, '(esperado 0)')

# 2) node --check em cada script de cada frame
frames = []
for m in re.finditer(r'srcdoc="', doc):
    s = m.end(); e = doc.find('"></iframe>', s)
    if e == -1: continue
    frames.append(doc[s:e].replace('&quot;', '"').replace('&amp;', '&'))

print(f'iframes encontrados: {len(frames)}')
allok = True
for fi, fdoc in enumerate(frames):
    for si, s in enumerate(re.findall(r'<script[^>]*>(.*?)</script>', fdoc, re.S)):
        if not s.strip(): continue
        tf = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8')
        tf.write(s); tf.close()
        r = subprocess.run(['node', '--check', tf.name], capture_output=True, text=True)
        if r.returncode != 0:
            allok = False
            print(f'  [iframe {fi} / script {si}] ERRO\n{r.stderr}')
        else:
            print(f'  [iframe {fi} / script {si}] OK ({len(s)} chars)')
        os.unlink(tf.name)

print('\nRESULTADO:', 'TODOS OK' if (allok and bad == 0) else 'HOUVE ERROS')
