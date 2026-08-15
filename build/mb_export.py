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

RISK_SQL = r"""
WITH contr AS (
  SELECT c.id AS contract_id, dgp.deal_id
  FROM `liora_silver.contracts` c
  JOIN `liora_silver.distributed_generation_proposals` dgp
    ON dgp.id = c.distributed_generation_proposal_id
  WHERE c.deleted_at IS NULL
),
ra AS (
  SELECT contract_id, result, created_at,
         ROW_NUMBER() OVER (PARTITION BY contract_id ORDER BY created_at DESC) rn
  FROM `liora_silver.risk_analysis`
),
best AS (
  SELECT co.deal_id, r.result, r.created_at,
         ROW_NUMBER() OVER (PARTITION BY co.deal_id ORDER BY r.created_at DESC) rn
  FROM ra r JOIN contr co ON co.contract_id = r.contract_id WHERE r.rn = 1
)
SELECT deal_id, result AS real_result,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', created_at, 'America/Sao_Paulo') AS real_created
FROM best WHERE rn = 1
"""

SBG_SQL = r"""
SELECT
  deal_id, deal_stage, deal_lost_reason,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(deal_lost_at),'America/Sao_Paulo')) AS deal_lost_at,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(deal_created_at),'America/Sao_Paulo')) AS deal_created_at,
  current_client_cnpj, current_client_cpf, current_client_name,
  current_client_state, current_client_city, client_phone_number,
  distributor_short_name, sales_channel_name, sales_organization_name, energy_retailer_name,
  TRIM(CONCAT(COALESCE(sales_person_first_name,''), ' ', COALESCE(sales_person_last_name,''))) AS sales_person_name,
  sales_person_email,
  current_total_bill_cost, current_consumption,
  proposal_id, product_name,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(proposal_created_at),'America/Sao_Paulo')) AS proposal_created_at,
  latest_contract_id,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(latest_contract_signature_signed_at),'America/Sao_Paulo')) AS latest_contract_signature_signed_at,
  latest_risk_analysis_result, latest_risk_analysis_comments,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(latest_risk_analysis_created_at),'America/Sao_Paulo')) AS latest_risk_analysis_created_at,
  CAST(has_valid_bill_uploaded AS STRING) AS has_valid_bill_uploaded,
  funnel_stage_index,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', DATETIME(TIMESTAMP(deal_updated_at),'America/Sao_Paulo')) AS deal_updated_at
FROM `liora_gold.sales_b_group`
WHERE (sales_channel_name LIKE 'Field Sales%' OR sales_channel_name LIKE '[FS]%')
  AND ( DATE(DATETIME(TIMESTAMP(proposal_created_at),'America/Sao_Paulo')) >= DATE_TRUNC(CURRENT_DATE('America/Sao_Paulo'), MONTH)
     OR DATE(DATETIME(TIMESTAMP(latest_risk_analysis_created_at),'America/Sao_Paulo')) >= DATE_TRUNC(CURRENT_DATE('America/Sao_Paulo'), MONTH) )
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

# REDE DE SEGURANCA (Felipe 15/08): o card818 e' a gold sales_management, que depende
# da silver distributed_generation_proposals. Quando o dbt congela essa silver (aconteceu
# em 15/08: ultima proposta 14/08 18:48 UTC), TODA proposta criada depois some do card818
# - inclusive aprovados do dia. Este recorte traz, direto do BRONZE, os deals que ainda
# nao chegaram na gold. Com o dbt em dia ele volta vazio, entao pode ficar sempre ligado.
BRONZE_GAP_SQL = r"""
WITH cutoff AS (
  SELECT TIMESTAMP(MAX(created_at)) t FROM `liora_silver.distributed_generation_proposals`
),
bdgp AS (
  SELECT id, deal_id, created_at, product_id FROM (
    SELECT id, deal_id, created_at, product_id, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.distributed_generation_proposals`
  ) WHERE rn=1 AND deleted_at IS NULL
),
gap AS (
  SELECT b.* FROM bdgp b, cutoff
  LEFT JOIN `liora_gold.sales_management` g ON g.deal_id = b.deal_id
  WHERE g.deal_id IS NULL AND b.created_at > cutoff.t
),
bd AS (SELECT id, stage, lost_at, lost_reason, created_at, rd_station_crm_id,
              sales_person_id, sales_channel_id, sales_organization_bundle_id,
              credit_stage, deal_metadata FROM (
    SELECT id, stage, lost_at, lost_reason, created_at, rd_station_crm_id,
           sales_person_id, sales_channel_id, sales_organization_bundle_id,
           credit_stage, deal_metadata, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.deals`) WHERE rn=1 AND deleted_at IS NULL),
ppl AS (SELECT id, TRIM(CONCAT(IFNULL(first_name,''),' ',IFNULL(last_name,''))) nome, email FROM (
    SELECT id, first_name, last_name, email, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.people`) WHERE rn=1),
sc AS (SELECT id, name, sales_organization_id FROM (
    SELECT id, name, sales_organization_id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.sales_channels`) WHERE rn=1),
so AS (SELECT id, name FROM (
    SELECT id, name, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.sales_organizations`) WHERE rn=1),
sob AS (SELECT id, sales_organization_id FROM (
    SELECT id, sales_organization_id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.sales_organization_bundles`) WHERE rn=1),
prod AS (SELECT id, name FROM (
    SELECT id, name, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.distributed_generation_products`) WHERE rn=1),
bill AS (SELECT * FROM (
    SELECT id, distributed_generation_proposal_id, distributor_id, bill_metadata,
           current_client_cnpj, current_client_cpf, current_client_name,
           current_client_city, current_client_state, client_contact_phone, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY distributed_generation_proposal_id ORDER BY created_at DESC) rn
    FROM `liora_bronze.original_electricity_bills`) WHERE rn=1 AND deleted_at IS NULL),
dist AS (SELECT id, short_name FROM (
    SELECT id, short_name, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.distributors`) WHERE rn=1),
ct AS (SELECT * FROM (
    SELECT id, distributed_generation_proposal_id, created_at, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY distributed_generation_proposal_id ORDER BY created_at DESC) rn
    FROM `liora_bronze.contracts`) WHERE rn=1 AND deleted_at IS NULL),
sig AS (SELECT contract_id, MAX(signed_at) signed_at FROM `liora_bronze.contract_signatures`
        WHERE deleted_at IS NULL GROUP BY contract_id),
ra AS (SELECT * FROM (
    SELECT contract_id, result, created_at, comments,
           ROW_NUMBER() OVER (PARTITION BY contract_id ORDER BY created_at DESC) rn
    FROM `liora_bronze.risk_analysis`) WHERE rn=1),
ca AS (SELECT * FROM (
    SELECT cpf, result, created_at,
           ROW_NUMBER() OVER (PARTITION BY cpf ORDER BY created_at DESC) rn
    FROM `liora_bronze.credit_analyses` WHERE deleted_at IS NULL AND cpf IS NOT NULL) WHERE rn=1)
SELECT
  d.id AS deal_id, d.stage AS deal_stage,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', d.lost_at) AS deal_lost_at,
  d.lost_reason AS deal_lost_reason,
  d.rd_station_crm_id,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', d.created_at, 'America/Sao_Paulo') AS deal_created_at,
  bl.current_client_cnpj, bl.current_client_cpf, bl.current_client_name,
  bl.client_contact_phone AS client_phone_number,
  bl.current_client_state, bl.current_client_city,
  di.short_name AS distributor_short_name,
  so.name AS sales_organization_name, sc.name AS sales_channel_name,
  sp.nome AS sales_person_name, sp.email AS sales_person_email,
  CAST(JSON_VALUE(bl.bill_metadata,'$.current_total_bill_cost') AS STRING) AS current_total_bill_cost,
  CAST(JSON_VALUE(bl.bill_metadata,'$.current_consumption') AS STRING) AS current_consumption,
  g.id AS proposal_id,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', g.created_at, 'America/Sao_Paulo') AS proposal_created_at,
  IF(d.stage IN ('LEAD','PROPOSAL','WAITING COVERAGE','PROPOSAL GENERATED','COLLECTING INFORMATION'),'false','true') AS accepted_proposal,
  pr.name AS product_name,
  bl.id AS bill_id,
  c.id AS latest_contract_id,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', c.created_at, 'America/Sao_Paulo') AS latest_contract_created_at,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', s.signed_at, 'America/Sao_Paulo') AS latest_contract_signature_signed_at,
  r.result AS latest_risk_analysis_result,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', r.created_at, 'America/Sao_Paulo') AS latest_risk_analysis_created_at,
  r.comments AS latest_risk_analysis_comments,
  IF(JSON_VALUE(d.deal_metadata,'$.is_energy_as_credit')='true','1','0') AS credit_product,
  d.credit_stage AS deal_credit_stage,
  cr.result AS latest_credit_analysis_result
FROM gap g
JOIN bd d ON d.id = g.deal_id
LEFT JOIN ppl sp ON sp.id = d.sales_person_id
LEFT JOIN sc ON sc.id = d.sales_channel_id
LEFT JOIN sob ON sob.id = d.sales_organization_bundle_id
LEFT JOIN so ON so.id = IFNULL(sob.sales_organization_id, sc.sales_organization_id)
LEFT JOIN prod pr ON pr.id = g.product_id
LEFT JOIN bill bl ON bl.distributed_generation_proposal_id = g.id
LEFT JOIN dist di ON di.id = bl.distributor_id
LEFT JOIN ct c ON c.distributed_generation_proposal_id = g.id
LEFT JOIN sig s ON s.contract_id = c.id
LEFT JOIN ra r ON r.contract_id = c.id
LEFT JOIN ca cr ON cr.cpf = bl.current_client_cpf
ORDER BY proposal_created_at
"""

# horario REAL da ultima atualizacao da base = ultimo sucesso do pipeline de ingestao
# (mesma fonte do card "Ultima deal gerado do Datalake" no Metabase da Liora).
DATA_TS_SQL = r"""
SELECT FORMAT_DATETIME('%H:%M - %d/%m', DATETIME(MAX(updated_at), 'America/Sao_Paulo')) AS ts
FROM `liora-server-production.liora_bronze._ingestion_watermarks`
WHERE source_system = 'cloudsql_liora_db'
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
    # risco REAL (ultimo por deal, fonte liora_silver.risk_analysis) - corrige o
    # atraso/vazio do campo latest_risk_analysis_result do card818 (opcional).
    try:
        rr = export_sql_csv(DATABASE_ID, RISK_SQL, os.path.join(OUT, 'risk_real.csv'))
        print('risk_real.csv OK: %d linhas' % rr)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'risk_real.csv'))
        except Exception: pass
        print('aviso: risk_real falhou (segue sem ele): %s' % e, file=sys.stderr)
    # bronze_gap (opcional) - deals que ainda nao chegaram na gold (dbt atrasado).
    try:
        bg = export_sql_csv(DATABASE_ID, BRONZE_GAP_SQL, os.path.join(OUT, 'bronze_gap.csv'))
        print('bronze_gap.csv OK: %d linhas' % bg)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'bronze_gap.csv'))
        except Exception: pass
        print('aviso: bronze_gap falhou (segue sem ele): %s' % e, file=sys.stderr)
    # funil ao vivo (sales_b_group) - deals Field do mes p/ o augmento no slice.
    # Fonte FRESCA (continua) que corrige o atraso do card818 (curadoria periodica).
    try:
        sb = export_sql_csv(DATABASE_ID, SBG_SQL, os.path.join(OUT, 'sbg_field.csv'))
        print('sbg_field.csv OK: %d linhas' % sb)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'sbg_field.csv'))
        except Exception: pass
        print('aviso: sbg_field falhou (segue sem augmento): %s' % e, file=sys.stderr)
    # data_ts: HH:MM - DD/MM real da ultima atualizacao da base (watermark do pipeline).
    # Grava data_ts.txt (valor unico). Se falhar, o build cai no relogio do proprio build.
    try:
        q = {'database': DATABASE_ID, 'type': 'native', 'native': {'query': DATA_TS_SQL}}
        raw = _req('/api/dataset/csv', data={'query': json.dumps(q)}, form=True)
        lines = raw.decode('utf-8', 'replace').splitlines()
        val = lines[1].strip().strip('"') if len(lines) > 1 else ''
        if val:
            open(os.path.join(OUT, 'data_ts.txt'), 'w', encoding='utf-8').write(val)
            print('data_ts.txt OK: %s' % val)
    except Exception as e:
        print('aviso: data_ts falhou (usa relogio do build): %s' % e, file=sys.stderr)

if __name__ == '__main__':
    main()
