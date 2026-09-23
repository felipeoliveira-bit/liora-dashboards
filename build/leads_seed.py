#!/usr/bin/env python3
# ==========================================================================
# leads_seed.py - snapshot dos leads para o dash de lideres (Felipe 23/09)
#
# POR QUE ISSO EXISTE
# O dash de lideres buscava os leads AO VIVO no Apps Script toda vez que
# abria. O Apps Script tem janelas de indisponibilidade (medido em 23/09:
# 6 chamadas seguidas em 404, ~18s cada, com os doPost aparecendo
# "Concluido" na aba Execucoes - o script roda, a resposta nao chega).
# Quando isso acontece a aba Tarefas fica presa em "Sincronizando..." e o
# lider nao ve nada. O mobile sofre menos porque faz UMA chamada com escopo;
# o desktop nao tem login, entao precisa da lista inteira (~2,8 MB).
#
# Aqui o CI busca a lista uma vez por ciclo (a cada ~2h) e grava
# desktop/leads.json. O Netlify serve esse arquivo pelo CDN e a tela abre
# instantanea, sem depender do Apps Script. O Apps Script continua sendo a
# fonte para o botao "Atualizar" e para a gravacao (o vendedor salvando visita).
#
# CONTRATO DE SEGURANCA:
#   1. NUNCA derruba o build. Qualquer falha -> exit 0 e o snapshot anterior
#      continua no ar (dado de 2h atras e' melhor que tela vazia).
#   2. NUNCA sobrescreve um snapshot bom por um truncado: se vier menos de
#      MIN_LEADS, recusa. Ja vimos a API devolver 200 com corpo parcial.
#   3. Grava por arquivo temporario + replace, para nao deixar um json pela
#      metade se o processo morrer no meio.
#
# Uso:  python3 leads_seed.py [caminho/leads.json]
# ==========================================================================
import json, io, os, sys, time, tempfile, urllib.request, urllib.error

URL = os.environ.get(
    'LEADS_API_URL',
    'https://script.google.com/macros/s/AKfycbyk_rqDKe49ZOCtLJkXYNvITqF5wQBjs5Uu1-9-U5HadPsP_tyzulBaCpyeuLpaqokL1w/exec')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join('desktop', 'leads.json')
TENTATIVAS = int(os.environ.get('LEADS_SEED_TRIES', '5'))
MIN_LEADS = int(os.environ.get('LEADS_SEED_MIN', '500'))


def log(m):
    print('[leads] ' + m, flush=True)


def buscar():
    corpo = json.dumps({'action': 'list'}).encode('utf-8')
    req = urllib.request.Request(
        URL, data=corpo,
        headers={'Content-Type': 'text/plain;charset=utf-8'})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = r.read().decode('utf-8', 'replace')
    if txt.lstrip().startswith('<'):
        raise ValueError('veio HTML (pagina de erro do Apps Script), nao JSON')
    d = json.loads(txt)
    if not isinstance(d, dict) or not isinstance(d.get('leads'), list):
        raise ValueError('JSON sem a chave leads')
    return d


def anterior():
    try:
        with io.open(OUT, encoding='utf-8') as f:
            return len(json.load(f).get('leads') or [])
    except Exception:
        return 0


def main():
    antes = anterior()
    for i in range(1, TENTATIVAS + 1):
        try:
            d = buscar()
            n = len(d['leads'])
            if n < MIN_LEADS:
                raise ValueError('so %d leads (minimo %d) - resposta parcial, recusando'
                                 % (n, MIN_LEADS))
            os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT) or '.', suffix='.tmp')
            with io.open(fd, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
            os.replace(tmp, OUT)
            log('snapshot OK: %d leads -> %s (antes: %d)' % (n, OUT, antes))
            return 0
        except Exception as e:
            log('tentativa %d/%d falhou: %s' % (i, TENTATIVAS, str(e)[:170]))
            if i < TENTATIVAS:
                time.sleep(4 * i)
    if antes:
        log('nao consegui atualizar - MANTENDO o snapshot anterior (%d leads).' % antes)
    else:
        log('nao consegui atualizar e nao existe snapshot anterior. '
            'A tela cai no fetch ao vivo, como antes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
