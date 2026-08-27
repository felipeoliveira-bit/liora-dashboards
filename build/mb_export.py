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
import os, sys, json, csv, io, urllib.request, urllib.error, urllib.parse
import time, uuid

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
),
-- DATA DA APROVACAO NO RISCO (Felipe 25/08) --------------------------------
-- O Antecipa gera uma SEGUNDA analise de risco (APPROVED) quando o credito e'
-- pago, dias depois da aprovacao de verdade (APPROVED_PENDING_CREDIT). Se a
-- venda for carimbada pela analise MAIS NOVA ela pula para a semana do
-- pagamento e o vendedor e' pago 2x pela mesma venda. `appr_created` devolve o
-- INICIO da sequencia aprovadora atual: a analise mais antiga a partir da qual
-- todas as seguintes aprovaram (APPROVED ou APPROVED_PENDING_CREDIT). Se o deal
-- foi reprovado e reaprovado depois, vale a reaprovacao (nao a aprovacao velha).
hist AS (
  SELECT co.deal_id, r.created_at,
         ROW_NUMBER() OVER (PARTITION BY co.deal_id ORDER BY r.created_at DESC) rn,
         CASE WHEN r.result IN ('APPROVED','APPROVED_PENDING_CREDIT') THEN 0 ELSE 1 END AS nao_aprov
  FROM `liora_silver.risk_analysis` r JOIN contr co ON co.contract_id = r.contract_id
),
corte AS (
  SELECT deal_id, MIN(CASE WHEN nao_aprov = 1 THEN rn END) AS rn_nao_aprov
  FROM hist GROUP BY deal_id
),
appr AS (
  SELECT h.deal_id, MIN(h.created_at) AS appr_created
  FROM hist h LEFT JOIN corte c ON c.deal_id = h.deal_id
  WHERE h.nao_aprov = 0 AND (c.rn_nao_aprov IS NULL OR h.rn < c.rn_nao_aprov)
  GROUP BY h.deal_id
)
SELECT b.deal_id, b.result AS real_result,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', b.created_at, 'America/Sao_Paulo') AS real_created,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%S', a.appr_created, 'America/Sao_Paulo') AS appr_created
FROM best b LEFT JOIN appr a ON a.deal_id = b.deal_id
WHERE b.rn = 1
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
# QUEM ASSINOU (Felipe 27/08): `current_client_name` do card818 e' o TITULAR
# PARSEADO DA FATURA. Quando a UC esta no nome de um parente/antigo dono, o card
# mostra uma pessoa e o vendedor procura por outra (Helenita x MAURICIO JOSE
# BONFIM, 25/08). O nome de quem assinou o contrato vive no contract_metadata.
# O slice grava so' quando e' outra PESSOA (ver mesma_pessoa no slice_base_ci.py).
SIGNER_SQL = r"""
WITH ct AS (
  SELECT distributed_generation_proposal_id AS pid,
         JSON_VALUE(contract_metadata,'$.client_name') AS signer_name
  FROM (
    SELECT distributed_generation_proposal_id, contract_metadata, created_at, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY distributed_generation_proposal_id ORDER BY created_at DESC) rn
    FROM `liora_bronze.contracts`) WHERE rn=1 AND deleted_at IS NULL),
dgp AS (
  SELECT id, deal_id FROM (
    SELECT id, deal_id, deleted_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ingested_at DESC) rn
    FROM `liora_bronze.distributed_generation_proposals`) WHERE rn=1 AND deleted_at IS NULL)
SELECT dgp.deal_id, ANY_VALUE(ct.signer_name) AS signer_name
FROM ct JOIN dgp ON dgp.id = ct.pid
WHERE ct.signer_name IS NOT NULL AND TRIM(ct.signer_name) != ''
GROUP BY dgp.deal_id
"""

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
# GOLD AO VIVO (Felipe 17/08/2026): o export do CARD 818 vem do CACHE do Metabase e
# pode atrasar horas - dois exports com 1h30 de diferenca voltaram byte a byte iguais
# enquanto um SELECT direto na MESMA tabela ja trazia propostas/aprovacoes novas (no dia
# 17/08 sumiram 21 das 65 propostas Antecipa geradas e 1 aprovado). Este recorte le a
# gold direto por SQL (nao passa pelo cache) e e' MESCLADO no base.csv logo apos o card.
# Os dois nomes de coluna com " (R$)" nao sao aceitos como alias no BigQuery, por isso
# saem como *_rs e o merge renomeia de volta para o cabecalho que o slice espera.
GOLD_LIVE_SQL = r"""
SELECT
  deal_id, deal_stage,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', deal_lost_at) AS deal_lost_at,
  deal_lost_reason, CAST(rd_station_crm_id AS STRING) AS rd_station_crm_id,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', deal_created_at) AS deal_created_at,
  current_client_cnpj, current_client_cpf, current_client_name, client_phone_number,
  current_client_state, current_client_city, distributor_short_name,
  origin_campaign, origin_source, internal_sales_classification, sales_team,
  sales_organization_name, sales_channel_name, sales_person_name, sales_person_email,
  CAST(current_total_bill_cost AS STRING) AS current_total_bill_cost_rs,
  CAST(rd_bill_cost AS STRING) AS rd_bill_cost_rs,
  CAST(under_minimal_flag AS STRING) AS under_minimal_flag,
  rd_distributor,
  CAST(current_consumption AS STRING) AS current_consumption,
  CAST(is_current_consumption_estimated AS STRING) AS is_current_consumption_estimated,
  CAST(current_consumption_filled AS STRING) AS current_consumption_filled,
  consumption_group, proposal_id,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', proposal_created_at) AS proposal_created_at,
  CAST(accepted_proposal AS STRING) AS accepted_proposal,
  product_name, energy_retailer_name,
  CAST(has_valid_bill_uploaded AS STRING) AS has_valid_bill_uploaded,
  bill_id, latest_contract_id,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', latest_contract_created_at) AS latest_contract_created_at,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', latest_contract_signature_signed_at) AS latest_contract_signature_signed_at,
  latest_risk_analysis_result,
  FORMAT_DATETIME('%Y-%m-%dT%H:%M:%S', latest_risk_analysis_created_at) AS latest_risk_analysis_created_at,
  latest_risk_analysis_comments,
  CAST(idle_days AS STRING) AS idle_days,
  idle_days_group,
  CAST(cancelation_date AS STRING) AS cancelation_date,
  ops_tt_status, ops_tt_status_reason,
  CAST(credit_product AS STRING) AS credit_product,
  deal_credit_stage, latest_credit_analysis_result
FROM `liora_gold.sales_management`
"""
GOLD_RENAME = {'current_total_bill_cost_rs': 'current_total_bill_cost (R$)',
               'rd_bill_cost_rs': 'rd_bill_cost (R$)'}

def _read_csv(path):
    raw = open(path, 'rb').read().replace(b'\x00', b'')
    r = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    return r.fieldnames, list(r)

def merge_gold_live(base_path, live_path):
    """Mescla a gold ao vivo no base.csv. Atualiza o que mudou, acrescenta o que
    faltava e PRESERVA linhas que so existem no card (fail-safe: nunca encolhe).
    Devolve (atualizadas, acrescentadas) ou levanta excecao (o chamador segue com o card)."""
    bf, base = _read_csv(base_path)
    lf, live = _read_csv(live_path)
    lf2 = [GOLD_RENAME.get(c, c) for c in lf]
    if bf != lf2:
        raise RuntimeError('colunas divergem card x gold (so no card: %s | so na gold: %s)'
                           % ([c for c in bf if c not in lf2], [c for c in lf2 if c not in bf]))
    for r in live:
        for k, v in GOLD_RENAME.items():
            if k in r:
                r[v] = r.pop(k)
    idx = {(r['deal_id'], r['proposal_id']): r for r in base}
    upd = add = 0
    for r in live:
        k = (r['deal_id'], r['proposal_id'])
        if k in idx:
            if idx[k] != r:
                upd += 1
            idx[k].update(r)
        else:
            base.append(r); idx[k] = r; add += 1
    with open(base_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=bf); w.writeheader(); w.writerows(base)
    return upd, add

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

def bust(sql):
    # QUEBRA-CACHE (Felipe 20/08): o Metabase cacheia resultado de query nativa pelo
    # hash do SQL. Sem isto o recorte volta IDENTICO ao da rodada anterior e as
    # analises de risco da ultima hora chegam como MANUAL -> aprovado do dia SOME
    # da tela (incidente 20/08: 8 aprovados de Field entre 15:24 e 17:02 sumiram).
    # Um comentario com timestamp+uuid muda o hash sem mudar UMA coluna do resultado.
    return '-- nocache %s %s\n%s' % (time.strftime('%Y%m%dT%H%M%S'), uuid.uuid4().hex[:8], sql)

def export_sql_csv(db_id, sql, dest):
    q = {'database': db_id, 'type': 'native', 'native': {'query': bust(sql)}}
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
    # gold ao vivo mesclada no base.csv (contorna o cache do card 818) - OPCIONAL:
    # se falhar, segue com o card puro (comportamento antigo).
    gold_p = os.path.join(OUT, 'gold_live.csv')
    try:
        g = export_sql_csv(DATABASE_ID, GOLD_LIVE_SQL, gold_p)
        print('gold_live.csv OK: %d linhas' % g)
        if g < 2000:
            raise RuntimeError('gold com %d linhas (<2000) - suspeita de export incompleto' % g)
        upd, add = merge_gold_live(base, gold_p)
        print('gold viva mesclada no base.csv: %d atualizada(s), %d acrescentada(s)' % (upd, add))
    except Exception as e:
        print('aviso: merge da gold viva falhou (segue so com o card 818): %s' % e, file=sys.stderr)
    finally:
        try: os.remove(gold_p)
        except Exception: pass
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
        # AVISO DE FRESCOR (Felipe 20/08): se a analise de risco mais nova do recorte
        # for de mais de 90 min atras, provavelmente veio de cache (ou o pipeline
        # travou) e os aprovados da ultima hora vao sumir da tela. Nao derruba o
        # build - so grita no log p/ dar nome ao problema na hora de conferir.
        try:
            _mx = ''
            with open(os.path.join(OUT, 'risk_real.csv'), encoding='utf-8-sig') as _fh:
                for _r in csv.DictReader(_fh):
                    _c = (_r.get('real_created') or '').strip()
                    if _c > _mx: _mx = _c
            print('risk_real: analise mais nova = %s' % (_mx or '?'))
            if _mx:
                _age = (time.time() - time.mktime(time.strptime(_mx[:19], '%Y-%m-%dT%H:%M:%S'))) / 60.0
                if _age > 90:
                    print('AVISO risk_real: analise mais nova tem %d min - suspeita de CACHE do Metabase; aprovado do dia pode sumir.' % _age, file=sys.stderr)
        except Exception as _e:
            print('aviso: nao consegui medir o frescor do risk_real: %s' % _e, file=sys.stderr)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'risk_real.csv'))
        except Exception: pass
        print('aviso: risk_real falhou (segue sem ele): %s' % e, file=sys.stderr)
    # quem assinou o contrato (opcional) - nome do signatario por deal, p/ o card
    # mostrar "assinou: X" quando o titular da fatura e' outra pessoa (Felipe 27/08).
    try:
        sg = export_sql_csv(DATABASE_ID, SIGNER_SQL, os.path.join(OUT, 'signer.csv'))
        print('signer.csv OK: %d linhas' % sg)
    except Exception as e:
        try: os.remove(os.path.join(OUT, 'signer.csv'))
        except Exception: pass
        print('aviso: signer falhou (cards seguem so com o titular): %s' % e, file=sys.stderr)
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
        q = {'database': DATABASE_ID, 'type': 'native', 'native': {'query': bust(DATA_TS_SQL)}}
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
