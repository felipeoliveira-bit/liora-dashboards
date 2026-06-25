#!/usr/bin/env python3
# ==========================================================================
# check_drift.py  -  Compara o numero de APROVADOS publicado no dashboard
# (desktop/index.html, repo liora-dashboards) com a base VIVA do Metabase.
#
# Por que existe: o dashboard e um snapshot republicado a cada 2h. Entre um
# rebuild e outro, o Metabase continua aprovando deals, entao o numero
# publicado fica naturalmente um pouco abaixo do vivo. Este check quantifica
# esse atraso e ALERTA se passar da tolerancia (sinal de ciclo de rebuild
# travado / conector indisponivel / dado parado), em vez de descobrir so
# quando alguem repara que "nao bate".
#
# Uso:
#   python3 check_drift.py <base_card818.csv> [--tol N]
#   (base = export do card 818 pelo conector; o healthcheck gera antes de chamar)
# Saida: bloco legivel + linha final VERDICT=OK|DRIFT|ERRO para o agente ler.
# Exit code: 0 sempre (nunca derruba o healthcheck); o veredito vai no texto.
# ==========================================================================
import csv, re, os, sys, glob, json, subprocess, tempfile, shutil, datetime

try:
    from zoneinfo import ZoneInfo
    TODAY = datetime.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
except Exception:
    TODAY = datetime.date.today()

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
TOKENF = os.path.join(PROJ, '.gh-token')
REPO = 'github.com/felipeoliveira-bit/liora-dashboards.git'
TOL = 8  # tolerancia default de deals de atraso antes de alertar

MESES = {'janeiro':1,'fevereiro':2,'marco':3,'março':3,'abril':4,'maio':5,'junho':6,
         'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}

def ymd(s):
    s = (s or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^([a-zçã]+)\s+(\d{1,2}),\s*(\d{4})', s.lower())
    if m and m.group(1) in MESES: return (int(m.group(3)), MESES[m.group(1)], int(m.group(2)))
    return None

def in_cur_month(s):
    t = ymd(s); return t is not None and t[0] == TODAY.year and t[1] == TODAY.month

def live_aprovados(base_path):
    """Recorte 'Clientes Analisados' identico ao slice_base.py: FS_Liora,
    risco no mes corrente, dedup deal_id -> conta APPROVED nao perdido."""
    with open(base_path, encoding='utf-8-sig') as fh:
        base = list(csv.DictReader(fh))
    # mesma regra do slice: operacao de campo conta por sales_team, nao so pela tag.
    fs = [r for r in base if r.get('internal_sales_classification') == 'FS_Liora'
          or (r.get('sales_team') or '').strip() == 'Field Sales']
    seen = set(); appr = 0; analisados = 0
    for r in fs:
        if not in_cur_month(r.get('latest_risk_analysis_created_at')): continue
        if r['deal_id'] in seen: continue
        seen.add(r['deal_id']); analisados += 1
        if (r.get('latest_risk_analysis_result') or '') == 'APPROVED' \
           and not (r.get('deal_lost_at') or '').strip():
            appr += 1
    return appr, analisados, len(base)

def published_aprovados():
    """Extrai const rawData do desktop/index.html publicado e conta APPROVED
    nao perdido (mesma def do dashboard: risk APPROVED & sem lost_at)."""
    tok = open(TOKENF).read().strip()
    remote = "https://x-access-token:" + tok + "@" + REPO
    tmp = tempfile.mkdtemp(prefix='drift_')
    try:
        subprocess.run(['git', 'clone', '-q', '--depth', '1', remote, tmp],
                       check=True, capture_output=True, text=True)
        html = open(os.path.join(tmp, 'desktop', 'index.html'), encoding='utf-8').read()
        # rawData embutido no srcdoc do frame-funil, com aspas entitizadas
        m = re.search(r'const rawData =\s*(\[.*?\]);', html, re.S)
        if not m:
            return None, None, 'nao achei const rawData no HTML publicado'
        raw = m.group(1).replace('&quot;', '"').replace('&amp;', '&') \
                        .replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'")
        data = json.loads(raw)
        appr = sum(1 for x in data
                   if (x.get('risk') == 'APPROVED') and not (x.get('lost_at') or ''))
        return appr, len(data), None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    args = [a for a in sys.argv[1:]]
    tol = TOL
    if '--tol' in args:
        i = args.index('--tol'); tol = int(args[i+1]); del args[i:i+2]
    base_path = args[0] if args else None
    if not base_path or not os.path.isfile(base_path):
        cand = glob.glob('/sessions/*/mnt/Metabase/*.csv') \
             + glob.glob(os.path.join(os.path.dirname(PROJ), 'Metabase', '*.csv'))
        cand = [c for c in cand if not os.path.basename(c).startswith('docs_pendentes')]
        if not cand:
            print('VERDICT=ERRO sem export do card 818 para comparar'); return
        base_path = max(cand, key=os.path.getmtime)

    try:
        live, analis, nbase = live_aprovados(base_path)
    except Exception as e:
        print('VERDICT=ERRO falha lendo base viva: %s' % e); return
    try:
        pub, npub, err = published_aprovados()
    except Exception as e:
        pub, npub, err = None, None, str(e)

    print('base viva   :', os.path.basename(base_path), '(%d linhas)' % nbase)
    print('mes corrente:', '%04d-%02d' % (TODAY.year, TODAY.month))
    print('APROVADOS Metabase (vivo)   :', live, '   (analisados %d)' % analis)
    if pub is None:
        print('APROVADOS dashboard publicado: indisponivel (%s)' % err)
        print('VERDICT=ERRO nao comparei (sem numero publicado)'); return
    drift = live - pub
    print('APROVADOS dashboard publicado:', pub, '   (rawData %d itens)' % npub)
    print('DRIFT (vivo - publicado)    :', drift)
    if abs(drift) <= tol:
        print('VERDICT=OK diferenca %d dentro da tolerancia (%d)' % (drift, tol))
    else:
        print('VERDICT=DRIFT publicado %d vs vivo %d (dif %d > tol %d) -> rode rebuild (Run now)'
              % (pub, live, drift, tol))

if __name__ == '__main__':
    main()
