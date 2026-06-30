#!/usr/bin/env python3
# ci_build.py - orquestrador do rebuild no GitHub Actions (CWD = raiz do repo).
# export (Metabase API) -> slice -> process+swap desktop -> process+swap mobile
# -> valida -> carimba "Metabase atualizado HH:MM - DD/MM" -> grava nos index.html.
# O commit/push fica a cargo do workflow. Sai !=0 em erro (falha o job).
import os, sys, re, glob, shutil, subprocess, tempfile, datetime
try:
    from zoneinfo import ZoneInfo
    NOW = datetime.datetime.now(ZoneInfo('America/Sao_Paulo'))
except Exception:
    NOW = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
TS = NOW.strftime('%H:%M - %d/%m')

ROOT = os.getcwd()
BUILD = os.path.join(ROOT, 'build')
WORK = os.path.join(BUILD, '_work')
DESK = os.path.join(ROOT, 'desktop', 'index.html')
MOB  = os.path.join(ROOT, 'mobile', 'index.html')

def run(cmd, cwd=None, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit('ERRO em %s\n%s' % (' '.join(cmd), r.stderr))
    return r.stdout

def stamp(path):
    t = open(path, encoding='utf-8').read()
    t = re.sub(r'(<span id="mb-ts">)[^<]*(</span>)', r'\g<1>'+TS+r'\g<2>', t)
    t = re.sub(r"const MB_UPDATED = '[^']*';", "const MB_UPDATED = '"+TS+"';", t)
    open(path,'w',encoding='utf-8').write(t)

def node_check_scripts(html_path, label):
    html = open(html_path, encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    for i, s in enumerate(scripts):
        if not s.strip(): continue
        tf = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8')
        tf.write(s); tf.close()
        rc = subprocess.run(['node','--check',tf.name], capture_output=True, text=True)
        os.unlink(tf.name)
        if rc.returncode != 0:
            sys.exit('VALIDATE %s falhou (script %d):\n%s' % (label, i, rc.stderr))
    print('%s validado (node --check OK).' % label)

# 0) limpa work
shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK)

# 1) export Metabase (card 818 + docs_pendentes)
run(['python3', os.path.join(BUILD,'mb_export.py'), WORK])

# 2) slice nos 3 recortes
run(['python3', os.path.join(BUILD,'slice_base_ci.py'), os.path.join(WORK,'base.csv'), WORK])

# 3) DESKTOP: process_lideranca (UP_DIR=WORK) -> swap -> validate -> stamp
run(['python3', os.path.join(BUILD,'process_lideranca.py')], cwd=WORK, env={'UP_DIR': WORK})
run(['python3', os.path.join(BUILD,'swap_data_lideranca.py'), DESK, os.path.join(WORK,'out_desktop.html')], cwd=WORK)
vd = run(['python3', os.path.join(BUILD,'validate_lideranca.py'), os.path.join(WORK,'out_desktop.html')], cwd=WORK)
if 'HOUVE ERROS' in vd: sys.exit('VALIDATE desktop reportou erros.')
stamp(os.path.join(WORK,'out_desktop.html'))
_minb = int(os.path.getsize(DESK)*0.9) if os.path.isfile(DESK) else 0
run(['python3', os.path.join(BUILD,'validate_html.py'), os.path.join(WORK,'out_desktop.html'), '--kind','desktop','--min-bytes',str(_minb)])
shutil.copy(os.path.join(WORK,'out_desktop.html'), DESK)
print('   desktop carimbado ->', TS)

# 4) MOBILE: process_mobile -> swap_mobile -> validate -> stamp
docs = os.path.join(WORK,'docs_pendentes.csv')
margs = [os.path.join(WORK,'deals.csv'), os.path.join(WORK,'aguardando_documentos.csv'), os.path.join(WORK,'propostas_geradas.csv')]
if os.path.isfile(docs): margs.append(docs)
run(['python3', os.path.join(BUILD,'process_mobile.py')]+margs, cwd=WORK, env={'UC_CSV': os.path.join(WORK,'uc_por_deal.csv')})
run(['python3', os.path.join(BUILD,'swap_mobile.py'), MOB, os.path.join(WORK,'out_mobile.html')], cwd=WORK)
node_check_scripts(os.path.join(WORK,'out_mobile.html'), 'mobile')
stamp(os.path.join(WORK,'out_mobile.html'))
_minb = int(os.path.getsize(MOB)*0.9) if os.path.isfile(MOB) else 0
run(['python3', os.path.join(BUILD,'validate_html.py'), os.path.join(WORK,'out_mobile.html'), '--kind','mobile','--min-bytes',str(_minb)])
shutil.copy(os.path.join(WORK,'out_mobile.html'), MOB)
print('   mobile carimbado ->', TS)

print('BUILD OK @ %s' % TS)
