#!/usr/bin/env python3
# time_sheet.py — le a aba "Time" da planilha "Liora Energia - Leads" e devolve o
# quadro do time (praca / papel / meta) por e-mail.
#
# POR QUE ISSO EXISTE
# A planilha e' onde o Felipe cadastra quem entrou, mas ela NUNCA foi lida pelo
# build: os mapas PRACA_TITLE / EMAIL2NAME / SELLER_PRACA / CREDENTIALS eram todos
# na mao, em 13 pontos de 4 arquivos. Em 15/09 o Paulo Alexandre Jorge comecou a
# vender, ficou fora de todos eles, e as vendas cairam em "Outras" no mobile e no
# SPI no desktop (fallback por cidade). So apareceu porque o Felipe estranhou o
# numero do Caio. Com este modulo o build passa a saber quem entrou.
#
# CONTRATO DE SEGURANCA (nao mudar sem pensar):
#   1. O CODIGO GANHA SEMPRE. A planilha so preenche quem NAO esta nos mapas.
#      Os mapas guardam as excecoes (e-mail alternativo, nome que diverge da base,
#      Camila Couto oculta, Rodrigo Lima que trocou de e-mail...) e a planilha nao
#      tem como saber disso.
#   2. NUNCA REMOVE NINGUEM. A aba Time ainda lista gente desligada (Bruno Andrade
#      esta la ate hoje) e nao tem coluna de status. Quem sai continua saindo pela
#      planilha de HC, como sempre.
#   3. FALHA E' NO-OP. Sem chave, sem rede, sem permissao ou aba renomeada -> devolve
#      {} e o build segue exatamente como antes, so imprimindo o motivo.
#
# Uso:
#   from time_sheet import carregar_time
#   time = carregar_time()   # {email: {'praca','papel','meta','label'}}

import os, sys, json, subprocess

SHEET_ID = os.environ.get('TIME_SHEET_ID', '1DOh5kccHjT1eq4msXZaudv-y_865yz7KsMRb-EYrwjs')
ABA      = os.environ.get('TIME_SHEET_TAB', 'Time')
FAIXA    = ABA + '!A2:E'

# Coluna B (rotulo) -> praca canonica do codigo (a mesma string do PRACA_TITLE).
# ATENCAO: a coluna E da planilha NAO serve. Ela e' REGIONAL, nao praca:
#   'rn'  agrupa Natal + RN Interior      (2 pracas, 2 lideres, 2 metas)
#   'spi' agrupa Campinas SPI + Ribeirao  (idem)
# Foi exatamente essa confusao que mandou o Paulo Jorge pro SPI. Use SEMPRE o rotulo.
LABEL2PRACA = {
    'SALVADOR':              'Salvador',
    'FEIRA DE SANTANA':      'Feira',
    'NATAL - RN':            'Natal',
    'RN INTERIOR - MOSSORÓ': 'RN Interior',
    'RN INTERIOR - MOSSORO': 'RN Interior',
    'SPI - CPFL PAULISTA':   'SPI',
    'RIBEIRÃO PRETO - SPI':  'Ribeirao',
    'RIBEIRAO PRETO - SPI':  'Ribeirao',
    'FORTALEZA - CE (ENEL)': 'CE',
}

# Cargos que NAO entram no quadro de vendedores.
CARGOS_FORA = {'diretor'}


def log(m):
    print('[time] ' + m, flush=True)


def _bootstrap():
    try:
        import google.oauth2.service_account  # noqa
        import googleapiclient.discovery       # noqa
        return True
    except Exception:
        log('instalando dependencias (google-api-python-client, google-auth)...')
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                            'google-api-python-client', 'google-auth'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log('pip falhou: ' + (r.stderr or r.stdout)[-300:])
            return False
        # pip pode sair 0 sem instalar nada (runner offline). Confirme de verdade.
        try:
            import google.oauth2.service_account  # noqa
            import googleapiclient.discovery       # noqa
            return True
        except Exception as e:
            log('dependencias ainda ausentes apos o pip: %s' % str(e)[:120])
            return False


def _linhas():
    """Devolve a matriz crua da aba, ou None se nao der para ler."""
    key = os.environ.get('GDRIVE_SA_KEY', '').strip()
    if not key:
        log('GDRIVE_SA_KEY ausente - seguindo so com os mapas do codigo.')
        return None
    if not _bootstrap():
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    try:
        info = json.loads(key)
    except Exception:
        log('GDRIVE_SA_KEY nao e JSON valido - seguindo so com os mapas do codigo.')
        return None
    try:
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        svc = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        resp = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=FAIXA).execute()
        return resp.get('values', [])
    except Exception as e:
        msg = str(e)
        log('nao consegui ler a aba "%s": %s' % (ABA, msg[:200]))
        if '403' in msg or 'permission' in msg.lower():
            # client_email e' identificador publico do service account (a chave
            # privada continua no secret). Sem ele o Felipe nao sabe com quem
            # compartilhar a planilha.
            log('COMPARTILHE a planilha (leitor) com: %s' % info.get('client_email', '?'))
        return None


def carregar_time():
    # CONTRATO 3: falha e' no-op. Qualquer excecao aqui derrubaria o rebuild inteiro
    # por causa de uma planilha - nao vale a pena. Devolve {} e o build segue.
    try:
        return _carregar_time()
    except Exception as e:
        log('erro inesperado (%s) - seguindo so com os mapas do codigo.' % str(e)[:150])
        return {}


def _carregar_time():
    linhas = _linhas()
    if linhas is None:
        return {}
    time, sem_praca, fora = {}, [], []
    for row in linhas:
        row = list(row) + [''] * (5 - len(row))
        email = (row[0] or '').strip().lower()
        if '@' not in email:
            continue
        label = (row[1] or '').strip()
        cargo = (row[2] or '').strip().lower()
        meta  = (row[3] or '').strip()
        if cargo in CARGOS_FORA:
            fora.append(email)
            continue
        praca = LABEL2PRACA.get(label.upper())
        if not praca:
            sem_praca.append((email, label))
            continue
        try:
            meta = int(float(meta))
        except Exception:
            meta = None
        time[email] = {
            'praca': praca,
            'papel': 'lider' if cargo.startswith('lider') or cargo.startswith('líder') else 'consultor',
            'meta':  meta,
            'label': label,
        }
    log('aba "%s": %d pessoas (%d fora por cargo)' % (ABA, len(time), len(fora)))
    if sem_praca:
        log('!!! ROTULO DE PRACA DESCONHECIDO (adicione ao LABEL2PRACA): %s' % sem_praca)
    return time


def conferir(time, praca_title, roster_ativo, rotulo='desktop'):
    """Compara a planilha com os mapas do codigo e imprime o diff.

    NAO altera nada - so relata. Devolve (faltando, divergentes) para quem quiser
    agir. 'faltando' = na planilha e fora do PRACA_TITLE (= pessoa que vai cair em
    "Outras" na primeira venda). 'divergentes' = praca diferente nos dois lados.
    """
    faltando, divergentes = [], []
    for em, d in sorted(time.items()):
        atual = praca_title.get(em)
        if atual is None:
            faltando.append((em, d['praca'], d['papel']))
        elif atual != d['praca']:
            divergentes.append((em, atual, d['praca']))
    if faltando:
        log('!!! NA PLANILHA E FORA DOS MAPAS (%d): %s' % (len(faltando), faltando))
    if divergentes:
        log('!!! PRACA DIVERGENTE codigo x planilha (%d): %s' % (len(divergentes), divergentes))
    sem_roster = [em for em, _, _ in faltando if em not in roster_ativo]
    if sem_roster:
        log('    (destes, fora tambem do ROSTER_ATIVO: %s)' % sem_roster)
    if not faltando and not divergentes:
        log('planilha x %s: tudo batendo.' % rotulo)
    return faltando, divergentes


if __name__ == '__main__':
    t = carregar_time()
    print(json.dumps(t, ensure_ascii=False, indent=1, sort_keys=True))
