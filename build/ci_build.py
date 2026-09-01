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
STAMP_TS = TS  # sobrescrito pelo data_ts real (watermark) apos o export; cai no relogio se faltar

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
    t = re.sub(r'(<span id="mb-ts">)[^<]*(</span>)', r'\g<1>'+STAMP_TS+r'\g<2>', t)
    t = re.sub(r"const MB_UPDATED = '[^']*';", "const MB_UPDATED = '"+STAMP_TS+"';", t)
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

# min-bytes: guard anti-truncamento. No inicio do mes (dia<=5) os recortes de
# "mes corrente" despencam e o HTML encolhe legitimamente -> afrouxa pra nao travar
# o job. O resto (script balanceado, </html>, node --check, marcadores) ainda protege.
def _min_bytes(path):
    if not os.path.isfile(path):
        return 0
    base = os.path.getsize(path)
    factor = 0.06 if NOW.day <= 5 else 0.9
    return int(base * factor)

# 0) limpa work
shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK)

# 1) export Metabase (card 818 + docs_pendentes)
run(['python3', os.path.join(BUILD,'mb_export.py'), WORK])

# carimbo do header = horario REAL da ultima atualizacao da base (data_ts.txt do mb_export;
# fonte: watermark do pipeline). Se ausente, mantem STAMP_TS = TS (relogio do build).
_dtf = os.path.join(WORK, 'data_ts.txt')
try:
    if os.path.isfile(_dtf):
        _v = open(_dtf, encoding='utf-8').read().strip()
        if _v:
            STAMP_TS = _v
except Exception:
    pass
print('carimbo (data real) ->', STAMP_TS)

# 2) slice nos 3 recortes
run(['python3', os.path.join(BUILD,'slice_base_ci.py'), os.path.join(WORK,'base.csv'), WORK])

# 3) DESKTOP: process_lideranca (UP_DIR=WORK) -> swap -> validate -> stamp
run(['python3', os.path.join(BUILD,'process_lideranca.py')], cwd=WORK, env={'UP_DIR': WORK})
run(['python3', os.path.join(BUILD,'swap_data_lideranca.py'), DESK, os.path.join(WORK,'out_desktop.html')], cwd=WORK)
vd = run(['python3', os.path.join(BUILD,'validate_lideranca.py'), os.path.join(WORK,'out_desktop.html')], cwd=WORK)
if 'HOUVE ERROS' in vd: sys.exit('VALIDATE desktop reportou erros.')
stamp(os.path.join(WORK,'out_desktop.html'))
_minb = _min_bytes(DESK)
run(['python3', os.path.join(BUILD,'validate_html.py'), os.path.join(WORK,'out_desktop.html'), '--kind','desktop','--min-bytes',str(_minb)])
shutil.copy(os.path.join(WORK,'out_desktop.html'), DESK)
print('   desktop carimbado ->', STAMP_TS)

# 4) MOBILE: process_mobile -> swap_mobile -> validate -> stamp
docs = os.path.join(WORK,'docs_pendentes.csv')
margs = [os.path.join(WORK,'deals.csv'), os.path.join(WORK,'aguardando_documentos.csv'), os.path.join(WORK,'propostas_geradas.csv')]
if os.path.isfile(docs): margs.append(docs)
run(['python3', os.path.join(BUILD,'process_mobile.py')]+margs, cwd=WORK, env={'UC_CSV': os.path.join(WORK,'uc_por_deal.csv')})
# 4a) FOTOS: puxa a pasta do Drive (service account) e injeta no template mobile
#     ANTES do swap. Fail-safe: sem key/erro sai 0 e preserva as fotos atuais.
run(['python3', os.path.join(BUILD,'photos_drive_sync.py'), MOB])
run(['python3', os.path.join(BUILD,'swap_mobile.py'), MOB, os.path.join(WORK,'out_mobile.html')], cwd=WORK)
node_check_scripts(os.path.join(WORK,'out_mobile.html'), 'mobile')
stamp(os.path.join(WORK,'out_mobile.html'))
_minb = _min_bytes(MOB)
run(['python3', os.path.join(BUILD,'validate_html.py'), os.path.join(WORK,'out_mobile.html'), '--kind','mobile','--min-bytes',str(_minb)])
shutil.copy(os.path.join(WORK,'out_mobile.html'), MOB)
print('   mobile carimbado ->', STAMP_TS)

print('BUILD OK @ %s (data %s)' % (TS, STAMP_TS))
_dp=DESK; _dh=open(_dp,encoding='utf-8').read(); _dh=_dh.replace("const pct = metaToDate>0 ? Math.min((mwh/metaToDate)*100, 100) : 0;","const pct = metaMes>0 ? (mwh/metaMes)*100 : 0;"); open(_dp,'w',encoding='utf-8').write(_dh); print('patch op-card aplicado')
_mp=MOB; _mh=open(_mp,encoding='utf-8').read(); _mh=_mh.replace(">ver comprovante ", ">ver comprovante (UC ${escapeHtml(String(p.uc||''))}) "); open(_mp,'w',encoding='utf-8').write(_mh); print('patch comprovante-uc aplicado')
_gp=MOB; _gh=open(_gp,encoding='utf-8').read(); _gh=_gh.replace("const url = String(p.comprovante || '').trim();","let url = String(p.comprovante || '').trim(); if(url.indexOf('1TAfY8Wcnkhr6sMVYGHN8qexYLEjBXJc2')>=0) url='';"); open(_gp,'w',encoding='utf-8').write(_gh); print('patch trava-recibo aplicado')
