#!/usr/bin/env python3
# validate_html.py — guarda estrutural anti-quebra de um HTML construido.
# Uso: python3 validate_html.py <arquivo.html> [--kind mobile|desktop] [--min-bytes N]
# Sai !=0 (e imprime "FALHOU: ...") se o arquivo estiver quebrado. Sai 0 e imprime "OK" se passar.
# Pega exatamente o bug que derrubou o CRM: <script> sem </script> / arquivo truncado.
import sys, re, subprocess, tempfile, os
from html import unescape

def fail(msg):
    print("VALIDATE FALHOU:", msg)
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        fail("uso: validate_html.py <arquivo> [--kind mobile|desktop] [--min-bytes N]")
    path = sys.argv[1]
    kind = 'mobile'
    min_bytes = 0
    a = sys.argv[2:]
    for i,tok in enumerate(a):
        if tok == '--kind' and i+1 < len(a): kind = a[i+1]
        if tok == '--min-bytes' and i+1 < len(a): min_bytes = int(a[i+1])

    if not os.path.isfile(path):
        fail(f"arquivo nao existe: {path}")
    html = open(path, encoding='utf-8').read()
    size = len(html.encode('utf-8'))

    # 1) tamanho minimo (anti-truncamento por baseline)
    if min_bytes and size < min_bytes:
        fail(f"arquivo pequeno demais ({size} bytes < minimo {min_bytes}) — provavel truncamento")

    # 2) tags de script balanceadas
    opens  = len(re.findall(r'<script(\s|>)', html))
    closes = len(re.findall(r'</script\s*>', html))
    if opens == 0:
        fail("nenhuma tag <script> encontrada")
    if opens != closes:
        fail(f"<script> abertos ({opens}) != </script> fechados ({closes}) — script NAO fechado / arquivo truncado")

    # 3) termina em </html> (nao cortado no meio)
    if not html.rstrip().endswith('</html>'):
        fail("arquivo nao termina em </html> — provavel truncamento")

    # 4) pelo menos 1 bloco de script inline NAO vazio, e cada um valido no node --check
    blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    nonempty = [b for b in blocks if b.strip()]
    if not nonempty:
        fail("zero blocos de script inline com conteudo (regex nao casou) — NAO trate como OK")
    for i, s in enumerate(nonempty):
        # desktop e srcdoc-based: o JS dentro do iframe vem HTML-escapado
        # (&amp;&amp; = &&, &quot; = aspas). O navegador desconverte ao renderizar,
        # entao aqui desconvertemos antes do node --check pra nao dar falso positivo.
        src = unescape(s) if kind == 'desktop' else s
        tf = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8')
        tf.write(src); tf.close()
        rc = subprocess.run(['node','--check',tf.name], capture_output=True, text=True)
        os.unlink(tf.name)
        if rc.returncode != 0:
            fail(f"node --check reprovou o bloco {i}: {rc.stderr.strip()[:300]}")

    # 5) marcadores obrigatorios (globais que precisam existir pra app renderizar)
    required = ['const rawData', 'const RAW_PROP']
    if kind == 'mobile':
        required += ['CAMP_CFG']
    miss = [m for m in required if m not in html]
    if miss:
        fail(f"marcadores ausentes: {miss}")

    print(f"VALIDATE OK [{kind}]: {size} bytes, {opens} <script>/{closes} </script>, {len(nonempty)} bloco(s) node-check OK, termina em </html>, marcadores {required} presentes")
    sys.exit(0)

if __name__ == '__main__':
    main()
