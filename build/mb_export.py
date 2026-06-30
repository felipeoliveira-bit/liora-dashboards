#!/usr/bin/env python3
# mb_export.py - puxa a base viva do Metabase pela API REST (sem o conector do app).
# Roda no GitHub Actions (sempre-ligado). Usa stdlib (urllib), sem dependencias.
#
# Env obrigatorias:
#   METABASE_URL      ex: https://metabase.suaempresa.com  (sem barra no fim)
#   METABASE_API_KEY  API key criada no Metabase (Settings > Authentication > API keys)
# Saida:
#   <out_dir>/base.csv            -> export do card 818 (base inteira ~16k linhas)
#   <out_dir>/docs_pendentes.csv  -> 4o recorte (opcional; nao derruba se falhar)
#
# Uso: python3 mb_export.py <out_dir>
import os, sys, json, urllib.request, urllib.error, urllib.parse

URL = (os.environ.get('METABASE_URL') or '').rstrip('/')
KEY = os.environ.get('METABASE_API_KEY') or ''
CARD_ID = 818
DATABASE_ID = 3
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'

DOCS_SQL = r"""
WITH waiting_deals AS (
  SELECT id AS deal_id FROM (
    SELECT id, stage, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.deals`
  ) WHERE rn=1 AND deleted_at IS NULL
    AND stage IN ('WAITING_DOCUMENTS','ME_WAITING_DOCUMENTS')
),
waiting_contracts AS (
  SELECT DISTINCT c.id AS contract_id
  FROM `liora_silver.contracts` c
  JOIN `liora_silver.distributed_generation_proposals` dgp
    ON dgp.id = c.distributed_generation_proposal_id
  JOIN waiting_deals w ON w.deal_id = dgp.deal_id
),
prereq AS (
  SELECT contract_id, tag, JSON_VALUE(prerequisite_data,'$.title') AS title FROM (
    SELECT id, contract_id, tag, prerequisite_data, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.contract_document_prerequisites`
  ) WHERE rn=1 AND deleted_at IS NULL
),
uploaded AS (
  SELECT DISTINCT contract_id, tag FROM `liora_silver.documents`
  WHERE deleted_at IS NULL AND url IS NOT NULL
)
SELECT
  wc.contract_id,
  COUNTIF(p.tag IS NOT NULL AND u.tag IS NULL) AS qtd_pendente,
  STRING_AGG(IF(p.tag IS NOT NULL AND u.tag IS NULL, p.title, NULL), ' | ' ORDER BY p.title) AS docs_pendentes
FROM waiting_contracts wc
LEFT JOIN prereq p ON p.contract_id = wc.contract_id
LEFT JOIN uploaded u ON u.contract_id=p.contract_id AND u.tag=p.tag
GROUP BY wc.contract_id
"""

UC_SQL = r"""
WITH deals_dedup AS (
  SELECT id AS deal_id FROM (
    SELECT id, deleted_at, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.deals`
  ) WHERE rn=1 AND deleted_at IS NULL
),
prop AS (
  SELECT deal_id, id AS proposal_id
  FROM `liora_silver.distributed_generation_proposals`
  WHERE deleted_at IS NULL
),
bills AS (
  SELECT distributed_generation_proposal_id AS proposal_id,
         current_client_instalation AS uc,
         ROW_NUMBER() OVER (PARTITION BY distributed_generation_proposal_id ORDER BY created_at DESC) rn
  FROM `liora_silver.original_electricity_bills`
  WHERE deleted_at IS NULL AND current_client_instalation IS NOT NULL
    AND TRIM(current_client_instalation) != ''
),
joined AS (
  SELECT d.deal_id, b.uc,
    ROW_NUMBER() OVER (PARTITION BY d.deal_id ORDER BY b.uc) rn2
  FROM deals_dedup d
  JOIN prop p ON p.deal_id = d.deal_id
  JOIN bills b ON b.proposal_id = p.proposal_id AND b.rn = 1
)
SELECT deal_id, uc FROM joined WHERE rn2 = 1
"""

def _req(path, data=None, form=False):
    url = URL + path
    headers = {'x-api-key': KEY}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.read()

def export_card_csv(card_id, dest):
    raw = _req('/api/card/%d/query/csv' % card_id)
    open(dest, 'wb').write(raw)
    n = max(0, raw.count(b'\n') - 1)
    return n

def export_sql_csv(db_id, sql, dest):
    q = {'database': db_id, 'type': 'native', 'native': {'query': sql}}
    raw = _req('/api/dataset/csv', data={'query': json.dumps(q)}, form=True)
    open(dest, 'wb').write(raw)
    n = max(0, raw.count(b'\n') - 1)
    return n

def main():
    if not URL or not KEY:
        print('ERRO: defina METABASE_URL e METABASE_API_KEY (secrets).', file=sys.stderr)
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, 'base.csv')
    try:
        n = export_card_csv(CARD_ID, base)
    except urllib.error.HTTPError as e:
        print('ERRO HTTP no export do card %d: %s %s\n%s'
              % (CARD_ID, e.code, e.reason, e.read()[:500].decode('utf-8','replace')), file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print('ERRO no export do card %d: %s' % (CARD_ID, e), file=sys.stderr)
        sys.exit(3)
    print('base.csv OK: %d linhas' % n)
    if n < 2000:
        print('ERRO: base com %d linhas (<2000) - export incompleto.' % n, file=sys.stderr)
        sys.exit(4)
    # docs_pendentes (opcional)
    try:
        d = export_sql_csv(DATABASE_ID, DOCS_SQL, os.path.join(OUT, 'docs_pendentes.csv'))
        print('docs_pendentes.csv OK: %d linhas' % d)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'docs_pendentes.csv'))
        except Exception: pass
        print('aviso: docs_pendentes falhou (segue sem ele): %s' % e, file=sys.stderr)
    # uc_por_deal (opcional) - nro de instalacao (UC) por deal, via conta de luz
    try:
        u = export_sql_csv(DATABASE_ID, UC_SQL, os.path.join(OUT, 'uc_por_deal.csv'))
        print('uc_por_deal.csv OK: %d linhas' % u)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'uc_por_deal.csv'))
        except Exception: pass
        print('aviso: uc_por_deal falhou (segue sem ele): %s' % e, file=sys.stderr)

if __name__ == '__main__':
    main()
