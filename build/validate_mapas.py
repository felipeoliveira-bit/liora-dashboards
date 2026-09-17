#!/usr/bin/env python3
# validate_mapas.py — impede que uma edicao nos mapas APAGUE gente sem querer.
#
# POR QUE ISSO EXISTE (17/09/2026)
# Cadastrar vendedor e' `str.replace` em 13 pontos de 4 arquivos. Ao cadastrar o
# Ronaldo eu usei como ancora uma linha que TINHA MAIS ENTRADAS DEPOIS dela e
# terminei o texto novo com um comentario `#`. O resto da linha original — Tatiane
# Correia, Maria Lucia, Tais Santos, Antonio Mariano e Silvia Dias — foi parar
# DENTRO do comentario. Cinco vendedores de Salvador sumiram do SELLER_PRACA e
# iriam para "Outros" no proximo rebuild.
#
# `py_compile` passou. `node --check` passou. `validate_html` passou. Nada disso
# olha SEMANTICA: um mapa com 5 chaves a menos continua sendo Python/JS valido.
# Este script olha.
#
# COMO FUNCIONA
# Compara cada mapa do working tree com a versao de um commit de referencia (por
# padrao HEAD) e FALHA se alguma chave sumiu. Comentarios sao removidos antes de
# extrair as chaves - e' justamente a chave que virou comentario que se quer pegar.
#
# Remocao legitima (desligamento, troca de lideranca) se declara na linha de
# comando e vai para o log:
#   python3 build/validate_mapas.py --ok "mobile/index.html:LIDERES:Adroaldo Bonfim"
#
# Uso:
#   python3 build/validate_mapas.py                 # compara com HEAD
#   python3 build/validate_mapas.py --ref HEAD~3
# Saida: exit 0 se nada sumiu; exit 1 listando o que sumiu.

import re, sys, subprocess, argparse

MAPAS = [
    ('build/process_lideranca.py', 'PRACA_TITLE',  'py'),
    ('build/process_lideranca.py', 'EMAIL2NAME',   'py'),
    ('build/process_lideranca.py', 'ROSTER_ATIVO', 'py'),
    ('build/process_mobile.py',    'EMAIL_NOME',   'py'),
    ('build/process_mobile.py',    'SELLER_PRACA', 'py'),
    ('mobile/index.html',          'SELLER_PRACA', 'js'),
    ('mobile/index.html',          'METAS',        'js'),
    ('mobile/index.html',          'CREDENTIALS',  'js'),
    ('mobile/index.html',          'LIDERES',      'js'),
]
# Listas (nao mapas): conferidas por contagem de nomes.
LISTAS = [
    ('desktop/index.html', r"\{nome:\s*'([^']+)',\s*praca:", 'VENDEDORES (4 copias)'),
    ('desktop/index.html', r"\{n:\s*'([^']+)',\s*p:",        'ANT_ROSTER'),
]


def _bloco(src, var, kind):
    for abre in ([var + ' = {'] if kind == 'py' else
                 ['let ' + var + ' = {', 'const ' + var + ' = {', 'let ' + var + '={', 'const ' + var + '={']):
        i = src.find(abre)
        if i >= 0:
            j = src.find('\n}', i)
            return src[i:j if j > 0 else len(src)]
    return None


def chaves(src, var, kind):
    blk = _bloco(src, var, kind)
    if blk is None:
        return None
    if kind == 'py':
        blk = re.sub(r'#[^\n]*', '', blk)
    else:
        blk = re.sub(r'//[^\n]*', '', blk)
        blk = re.sub(r'/\*.*?\*/', '', blk, flags=re.S)
    return set(re.findall(r"'([^']+)'\s*:", blk))


def do_ref(ref, path):
    r = subprocess.run(['git', 'show', '%s:%s' % (ref, path)],
                       capture_output=True, text=True, encoding='utf-8')
    return r.stdout if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', default='HEAD')
    ap.add_argument('--ok', action='append', default=[],
                    help='remocao aprovada: "arquivo:MAPA:chave"')
    a = ap.parse_args()
    aprovadas = set(a.ok)
    problemas = []

    for path, var, kind in MAPAS:
        antes_src = do_ref(a.ref, path)
        if antes_src is None:
            print('?? %s nao existe em %s - pulando' % (path, a.ref)); continue
        try:
            agora_src = open(path, encoding='utf-8').read()
        except FileNotFoundError:
            print('?? %s nao existe no working tree - pulando' % path); continue
        antes, agora = chaves(antes_src, var, kind), chaves(agora_src, var, kind)
        if antes is None or agora is None:
            print('?? mapa %s nao encontrado em %s - pulando' % (var, path)); continue
        sumiram = {k for k in (antes - agora)
                   if '%s:%s:%s' % (path, var, k) not in aprovadas}
        ok_decl = (antes - agora) - sumiram
        status = 'XX' if sumiram else 'ok'
        print('%s %-28s %-14s %3d -> %3d  +%d%s' % (
            status, path, var, len(antes), len(agora), len(agora - antes),
            ('  (remocao aprovada: %s)' % sorted(ok_decl)) if ok_decl else ''))
        if sumiram:
            problemas.append((path, var, sorted(sumiram)))

    for path, pat, rotulo in LISTAS:
        antes_src = do_ref(a.ref, path)
        if antes_src is None: continue
        antes = set(re.findall(pat, antes_src))
        agora = set(re.findall(pat, open(path, encoding='utf-8').read()))
        sumiram = {k for k in (antes - agora)
                   if '%s:%s:%s' % (path, rotulo, k) not in aprovadas}
        print('%s %-28s %-14s %3d -> %3d  +%d' % (
            'XX' if sumiram else 'ok', path, rotulo, len(antes), len(agora), len(agora - antes)))
        if sumiram:
            problemas.append((path, rotulo, sorted(sumiram)))

    if problemas:
        print('\n>>> CHAVES SUMIRAM (provavelmente engolidas por um comentario):')
        for path, var, ks in problemas:
            print('    %s / %s: %s' % (path, var, ks))
        print('\nSe a remocao for proposital, declare:')
        for path, var, ks in problemas:
            for k in ks:
                print('    --ok "%s:%s:%s"' % (path, var, k))
        return 1
    print('\nOK: nenhum mapa perdeu chave.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
