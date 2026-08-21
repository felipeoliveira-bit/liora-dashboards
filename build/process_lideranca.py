#!/usr/bin/env python3
# ==========================================================================
# process.py  —  Liora Central v48 (desktop)
# Lê os 3 CSVs do Metabase e gera os 3 arrays embutidos no HTML:
#   new_rawData.json  (funil / deals)   -> const rawData  no frame-funil
#   new_RAW.json      (propostas)        -> const RAW      no frame-propostas
#   new_HC_PROP.json  (HC por proposta)  -> const HC_PROP  no frame-pessoas
#
# Validado campo a campo contra a base embutida de 16/06/2026 (gabarito).
# Uso:  python3 process.py
# Coloque os 3 CSVs em /mnt/user-data/uploads/ (qualquer sufixo no nome).
# ==========================================================================
import csv, json, re, io, datetime, sys, glob, os

# ── Observacao da analise de risco (Felipe 21/08) ───────────────────────────
# latest_risk_analysis_comments explica por que o Antecipa travou ("1 fatura
# vencida", "baixa_renda", "instalacao desligada"...), mas vem colado num
# payload PIX EMV gigante ("00020126980014br.gov.bcb.pix0136...") que polui a
# tela. Aqui tiramos o payload e recuperamos de dentro dele a referencia da
# fatura (Conta Ref MES/AA Vencimento DD/MM/AA), que e' a parte util.
_OBS_PIX = re.compile(r'0002\d{2}\S{20,}.*$', re.S)   # payload vem sempre no fim: corta dali pro fim
_OBS_REF = re.compile(r'Conta Ref ([A-Z]{3}/\d{2}) Vencimento (\d{2}/\d{2}/\d{2})')
def clean_obs(t, limit=200):
    raw = (t or '').replace('\r', ' ')
    if not raw.strip(): return ''
    t = _OBS_PIX.sub(' ', raw)
    t = re.sub(r'(?i),?\s*pix\s*:?\s*$', '', re.sub(r'\s+', ' ', t).strip())
    t = t.strip(' ,;.|-\u00b7')
    refs = _OBS_REF.findall(raw)
    if refs and 'Ref' not in t:
        t = (t + ' \u00b7 ' + ', '.join('ref ' + a + ' venc ' + b for a, b in refs[:3])).strip(' \u00b7')
    return t[:limit].strip()

# ── Documentos pendentes (4o recorte) ──
def short_doc(t):
    t=(t or '').strip(); low=t.lower(); rep='representante' in low
    if 'frente do documento' in low: return 'RG/CNH repr. (frente)' if rep else 'RG/CNH (frente)'
    if 'verso do documento' in low:  return 'RG/CNH repr. (verso)'  if rep else 'RG/CNH (verso)'
    if 'selfie segurando' in low:    return 'Selfie c/ documento'
    if 'selfie' in low:              return 'Selfie'
    if 'conta de luz' in low:        return 'Conta de luz'
    if 'contrato de aluguel' in low: return 'Contrato de aluguel'
    if 'contrato social' in low:     return 'Contrato social'
    if 'rela\u00e7\u00e3o com o im\u00f3vel' in low: return 'Rela\u00e7\u00e3o com o im\u00f3vel'
    if 'ata condominial' in low:     return 'Ata do condom\u00ednio'
    if 'procura\u00e7\u00e3o' in low and 'cnpj' in low: return 'Procura\u00e7\u00e3o (garantidor)'
    if 'procura\u00e7\u00e3o' in low: return 'Procura\u00e7\u00e3o'
    if 'documento gen\u00e9rico' in low: return 'Documento'
    if 'outros' in low:              return 'Outros'
    return t

def load_docs(path):
    d={}
    if not path:
        return d
    try:
        with open(path,encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh):
                cid=(r.get('contract_id') or '').strip()
                if not cid: continue
                raw=(r.get('docs_pendentes') or '').strip()
                if raw:
                    seen=set(); out=[]
                    for part in raw.split(' | '):
                        lbl=short_doc(part)
                        if lbl and lbl not in seen: seen.add(lbl); out.append(lbl)
                    d[cid]=', '.join(out)
                else:
                    d[cid]='__OK__'
    except Exception as e:
        print('aviso docs:',e,file=sys.stderr)
    return d

import os as _os
UP = _os.environ.get('UP_DIR', '.')

def find_csv(*patterns):
    for pat in patterns:
        hits = sorted(glob.glob(os.path.join(UP, pat)))
        if hits:
            return hits[-1]            # pega o mais recente (maior sufixo)
    raise FileNotFoundError('CSV não encontrado: ' + ' | '.join(patterns))

def rows(path):
    with open(path, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))

f_deals = find_csv('deals*.csv')
f_agu   = find_csv('aguardando_documentos*.csv', 'aguardando*.csv')
f_prop  = find_csv('propostas_geradas*.csv', 'propostas*.csv')
f_docs  = (sorted(glob.glob(os.path.join(UP,'docs_pendentes*.csv'))) or [None])[-1]
print('deals   :', os.path.basename(f_deals))
print('aguardando:', os.path.basename(f_agu))
print('propostas:', os.path.basename(f_prop))
DOCS = load_docs(f_docs); print('docs pendentes:', len(DOCS), '|', os.path.basename(f_docs) if f_docs else 'sem arquivo')
f_uc = (sorted(glob.glob(os.path.join(UP,'uc_por_deal*.csv'))) or [None])[-1]
f_ant = (sorted(glob.glob(os.path.join(UP,'antecipa_geradas*.csv'))) or [None])[-1]
def _load_uc(p):
    m={}
    if not p: return m
    try:
        for r in rows(p):
            did=(r.get('deal_id') or '').strip(); uc=(r.get('uc') or '').strip()
            if did and uc: m[did]=uc
    except Exception as e: print('aviso uc:', e)
    return m
UC = _load_uc(f_uc); print('uc por deal:', len(UC), '|', os.path.basename(f_uc) if f_uc else 'sem arquivo')

deals = rows(f_deals)
# INJECT_DEALS: deals ausentes da base viva, adicionados manualmente (Felipe).
# Remover quando a base do Metabase passar a refletir o cliente.
INJECT_DEALS = [
    {'deal_id': 'f8ba2c6d-df9c-4292-8f36-ef504a6b4305', 'deal_stage': 'REQUEST_TITULARIDADE', 'deal_lost_at': '', 'deal_lost_reason': '', 'rd_station_crm_id': '', 'deal_created_at': '2026-08-13T16:36:17', 'current_client_cnpj': '', 'current_client_cpf': '67308910504', 'current_client_name': 'MARLI MERCES DOS SANTOS LISBOA', 'client_phone_number': '+5571982531504', 'current_client_state': 'BA', 'current_client_city': 'LAURO DE FREITAS', 'distributor_short_name': 'NEOENERGIA COELBA', 'origin_campaign': '', 'origin_source': 'whatsapp-bot', 'internal_sales_classification': 'FS_Liora', 'sales_team': 'Field Sales', 'sales_organization_name': 'Liora', 'sales_channel_name': 'Field Sales Liora', 'sales_person_name': 'ETTORE ROSSI NETO', 'sales_person_email': 'ettore.rossi@lioraenergia.com.br', 'current_total_bill_cost (R$)': '275.82', 'rd_bill_cost (R$)': '275.0', 'under_minimal_flag': '0', 'rd_distributor': 'NEOENERGIA COELBA', 'current_consumption': '0.187', 'is_current_consumption_estimated': 'false', 'current_consumption_filled': '0.187', 'consumption_group': '1. <= 0.5 MWh', 'proposal_id': 'e72306d5-f7d8-4be3-8a3d-5157bf33c6ec', 'proposal_created_at': '2026-08-13T16:36:17', 'accepted_proposal': 'true', 'product_name': 'LIORA_F_', 'energy_retailer_name': 'Liora Energia', 'has_valid_bill_uploaded': 'true', 'bill_id': '', 'latest_contract_id': 'c964ff7a-31e3-4965-938b-e748505a8ad2', 'latest_contract_created_at': '2026-08-13T16:38:46', 'latest_contract_signature_signed_at': '2026-08-13T16:40:05', 'latest_risk_analysis_result': 'APPROVED', 'latest_risk_analysis_created_at': '2026-08-13T16:41:53', 'latest_risk_analysis_comments': '', 'idle_days': '0', 'idle_days_group': '1. <= 1 dia', 'cancelation_date': '', 'ops_tt_status': 'APROVADO', 'ops_tt_status_reason': 'APROVADO', 'credit_product': '0', 'deal_credit_stage': '', 'latest_credit_analysis_result': ''},  # MARLI MERCES DOS SANTOS LISBOA (Ettore Rossi/Salvador, LIORA_F_ Coelba) - aprovada risco 16:41 13/08 mas ausente do card818 (curado atrasa); inject manual (Felipe 13/08); remover quando card818 refletir
    {'deal_id': 'e607c712-93ed-43f2-9d77-dd257c009238', 'deal_stage': 'REQUEST_TITULARIDADE', 'deal_lost_at': '', 'deal_lost_reason': '', 'rd_station_crm_id': '', 'deal_created_at': '2026-08-14T12:40:27.471653', 'current_client_cnpj': '', 'current_client_cpf': '21835932886', 'current_client_name': 'CHESSER WILLIAM MASSARO', 'client_phone_number': '+5516992650332', 'current_client_state': 'SP', 'current_client_city': 'RIBEIRÃO PRETO', 'distributor_short_name': 'CPFL PAULISTA', 'origin_campaign': '', 'origin_source': 'whatsapp-bot', 'internal_sales_classification': 'FS_Liora', 'sales_team': 'Field Sales', 'sales_organization_name': 'Liora', 'sales_channel_name': 'Field Sales Liora', 'sales_person_name': 'Fabio Rodrigues ', 'sales_person_email': 'fabio.rodrigues@lioraenergia.com.br', 'current_total_bill_cost (R$)': '1826.79', 'rd_bill_cost (R$)': '2000.0', 'under_minimal_flag': '0', 'rd_distributor': 'CPFL PAULISTA', 'current_consumption': '1.81', 'is_current_consumption_estimated': 'false', 'current_consumption_filled': '1.81', 'consumption_group': '3. <= 5.0 MWh', 'proposal_id': '2abf98c2-da0a-4e78-897b-1a36542fe4b5', 'proposal_created_at': '2026-08-14T12:40:27.983546', 'accepted_proposal': 'true', 'product_name': 'LIORA_F_', 'energy_retailer_name': 'Liora Energia', 'has_valid_bill_uploaded': 'true', 'bill_id': 'e833c8c3-2035-4bb5-9759-2af80784b6ba', 'latest_contract_id': '1216232c-8f1c-4027-a4bf-cb90590ba89e', 'latest_contract_created_at': '2026-08-14T11:47:10.905748', 'latest_contract_signature_signed_at': '2026-08-14T11:53:57.00', 'latest_risk_analysis_result': 'APPROVED', 'latest_risk_analysis_created_at': '2026-08-14T19:22:59.422879', 'latest_risk_analysis_comments': '', 'idle_days': '0', 'idle_days_group': '1. <= 1 dia', 'cancelation_date': '', 'ops_tt_status': 'N/A', 'ops_tt_status_reason': 'N/A', 'credit_product': '0', 'deal_credit_stage': '', 'latest_credit_analysis_result': ''},  # CHESSER WILLIAM MASSARO 2a UC (UC 601093603514, Fabio Rodrigues/Ribeirao, LIORA_F_ CPFL) - risco APPROVED 19:22 14/08 mas ausente do card818 (curado atrasa); inject manual (Felipe 14/08); remover quando card818 refletir
]
deals = deals + INJECT_DEALS
UC['b61609e9-835a-4ed2-896d-2de4fd55c4f9'] = '5039298'  # Stefanny Karoline (instalacao da fatura)
agu   = rows(f_agu)
prop  = rows(f_prop)

# ---- GUARD de estágio único (regra manual) -------------------------------
stages = set(r['deal_stage'] for r in deals)
if len(stages) <= 1:
    sys.exit('!!! ABORT: deals.csv tem um único deal_stage (%s) — recorte provavelmente incompleto.' % stages)

# ---- helpers -------------------------------------------------------------
MESES = {'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
         'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
def pdate(s):
    """Aceita ISO (2026-06-03T...) e texto pt-BR (junho 6, 2026, 11:00)."""
    s = (s or '').strip()
    if not s: return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return s[:10]
    m = re.match(r'^([a-zçã]+)\s+(\d{1,2}),\s*(\d{4})', s.lower())
    if m and m.group(1) in MESES:
        return '%04d-%02d-%02d' % (int(m.group(3)), MESES[m.group(1)], int(m.group(2)))
    return None

def fnum(s):
    """Parse numérico US ('3,069.97' -> 3069.97). NUNCA dividir por 1000."""
    s = (s or '').strip().replace(',', '')
    if not s: return 0.0
    try: return float(s)
    except: return 0.0

def semana(dstr):
    if not dstr: return ''
    day = int(dstr[8:10])
    return 'S' + str((day - 1)//7 + 1)          # S1..S5 = semana do mês

DOW = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

# ---- Mapas canônicos (referência = EMAIL) --------------------------------
PRACA_TITLE = {  # email -> praça (Title) usada no RAW
 'silmara.gomes@lioraenergia.com.br':'CE',
 'luciana.campos@lioraenergia.com.br':'Salvador',
 'nicola.popovic@lioraenergia.com.br':'SPI',
 'nha.negocios@gmail.com':'SPI',
 'anderson.correia@lioraenergia.com.br':'SPI',
 'percy.hormazabal@lioraenergia.com.br':'SPI',
 'monica.silveira@lioraenergia.com.br':'SPI',
 'ana.ribeiro@lioraenergia.com.br':'SPI',
 'jose.lima@lioraenergia.com.br':'SPI',
 'jose.monteiro@lioraenergia.com.br':'SPI',  # Rodrigo Lima trocou de e-mail 14/08 (o antigo jose.lima virou jose.lima1 = outra pessoa)
 'daniel.junior@lioraenergia.com.br':'SPI',
 'joao.santos@lioraenergia.com.br':'Ribeirao',
 'mirla.albuquerque@lioraenergia.com.br':'RN Interior',
 'lucas.santos@lioraenergia.com.br':'RN Interior',
 'mecenas.junior@lioraenergia.com.br':'Natal',
 'daniel.magnus@lioraenergia.com.br':'Natal',
 'thymacillo@hotmail.com':'Natal',  # Thiago Firmo (e-mail alternativo no CRM)
 'thiago.firmo@lioraenergia.com.br':'Natal','silvia.dias@lioraenergia.com.br':'Salvador',
 'adroaldo.bonfim@lioraenergia.com.br':'Salvador','ananias.neto@lioraenergia.com.br':'Natal',
 'antonio.mariano@lioraenergia.com.br':'Salvador','bruno.andrade@lioraenergia.com.br':'Natal',
 'bruno.borges@lioraenergia.com.br':'CE','caio.lannes@lioraenergia.com.br':'SPI',
 'diego.faria@lioraenergia.com.br':'SPI','ederson.silva@lioraenergia.com.br':'SPI',
 'ettore.rossi@lioraenergia.com.br':'Salvador','tatiane.correia@lioraenergia.com.br':'Salvador','felipe.oliveira@lioraenergia.com.br':'Outras',
 'franciele.felix@lioraenergia.com.br':'SPI','kelma.rangel@lioraenergia.com.br':'Feira',
 'lucileide.carlos@lioraenergia.com.br':'Feira','marcio.galvao@lioraenergia.com.br':'Natal',
 'maria.lucia@lioraenergia.com.br':'Salvador','neilon.nascimento@lioraenergia.com.br':'CE','sabrina.tomazeti@lioraenergia.com.br':'CE',
 'nubia.andrade@lioraenergia.com.br':'CE','odirley.costa@lioraenergia.com.br':'CE',  # Felipe 07/08: sao CE (alinha ao CRM); antes 'Outras'
 'rodrigo.ribeiro@lioraenergia.com.br':'Natal','rosangela.mendes@lioraenergia.com.br':'Feira',
 'ryan.trindade@lioraenergia.com.br':'Feira','alberto.nascimento@lioraenergia.com.br':'Feira','marcel.sousa@lioraenergia.com.br':'Feira','jefferson.fideli@lioraenergia.com.br':'RN Interior','phillip.faria@lioraenergia.com.br':'Ribeirao','tais.santos@lioraenergia.com.br':'Salvador',
 'tiago.freitas@lioraenergia.com.br':'Feira','tamires.costa@lioraenergia.com.br':'Feira','thiago.araujo@lioraenergia.com.br':'Natal','camila.couto@lioraenergia.com.br':'Feira',
 'briel.barbosa@lioraenergia.com.br':'SPI','olimpio.filho@lioraenergia.com.br':'Ribeirao','fabio.rodrigues@lioraenergia.com.br':'Ribeirao',  # novos 10/08
 'karianine.sampaio@lioraenergia.com.br':'Ribeirao',  # nova 18/08 (Pradopolis/SP, time Ribeirao - Felipe 18/08)
}
EMAIL2NAME = {  # email -> nome canônico do vendedor (resolve nomes variáveis do CRM)
 'silmara.gomes@lioraenergia.com.br':'Silmara Gomes',
 'briel.barbosa@lioraenergia.com.br':'Briel Barbosa','olimpio.filho@lioraenergia.com.br':'Olímpio Filho','fabio.rodrigues@lioraenergia.com.br':'Fábio Rodrigues',  # novos 10/08
 'karianine.sampaio@lioraenergia.com.br':'Karianine Sampaio',  # nova 18/08 (CRM manda 'karianine Sampaio' minusculo)
 'luciana.campos@lioraenergia.com.br':'Luciana Campos',
 'nicola.popovic@lioraenergia.com.br':'Nicola Popovic',
 'nha.negocios@gmail.com':'Anderson Correia',
 'anderson.correia@lioraenergia.com.br':'Anderson Correia',
 'percy.hormazabal@lioraenergia.com.br':'Percy Hormazabal',
 'monica.silveira@lioraenergia.com.br':'Monica Silveira',
 'ana.ribeiro@lioraenergia.com.br':'Ana Ribeiro',
 'jose.lima@lioraenergia.com.br':'Rodrigo Lima',
 'jose.monteiro@lioraenergia.com.br':'Rodrigo Lima',  # e-mail novo (14/08); o antigo fica pelos deals ja criados
 'daniel.junior@lioraenergia.com.br':'Daniel Junior',
 'joao.santos@lioraenergia.com.br':'João Santos',
 'mirla.albuquerque@lioraenergia.com.br':'Mirla Albuquerque',
 'lucas.santos@lioraenergia.com.br':'Lucas Santos',
 'mecenas.junior@lioraenergia.com.br':'Mecenas Junior',
 'daniel.magnus@lioraenergia.com.br':'Daniel Magnus',
 'thymacillo@hotmail.com':'Thiago Firmo',  # mesmo vendedor, e-mail alternativo
 'thiago.firmo@lioraenergia.com.br':'Thiago Firmo','silvia.dias@lioraenergia.com.br':'Silvia Dias',
 'adroaldo.bonfim@lioraenergia.com.br':'Adroaldo Bonfim','ananias.neto@lioraenergia.com.br':'Ananias Neto',
 'antonio.mariano@lioraenergia.com.br':'Antonio Mariano','bruno.andrade@lioraenergia.com.br':'Bruno Andrade',
 'bruno.borges@lioraenergia.com.br':'Bruno Borges','caio.lannes@lioraenergia.com.br':'Caio Lannes',
 'diego.faria@lioraenergia.com.br':'Diego Faria','ederson.silva@lioraenergia.com.br':'Ederson Silva',
 'ettore.rossi@lioraenergia.com.br':'Ettore Rossi','tatiane.correia@lioraenergia.com.br':'Tatiane Correia','felipe.oliveira@lioraenergia.com.br':'Felipe Oliveira',
 'franciele.felix@lioraenergia.com.br':'Franciele Felix','kelma.rangel@lioraenergia.com.br':'Kelma Rangel',
 'lucileide.carlos@lioraenergia.com.br':'Lucileide Carlos','marcio.galvao@lioraenergia.com.br':'Marcio Galvão',
 'maria.lucia@lioraenergia.com.br':'Maria Lúcia','neilon.nascimento@lioraenergia.com.br':'Neilon Nascimento','sabrina.tomazeti@lioraenergia.com.br':'Sabrina Tomazeti',
 'nubia.andrade@lioraenergia.com.br':'Nubia  Andrade','odirley.costa@lioraenergia.com.br':'Odirley Costa',
 'rodrigo.ribeiro@lioraenergia.com.br':'Rodrigo Ribeiro','rosangela.mendes@lioraenergia.com.br':'Rosangela Mendes',
 'ryan.trindade@lioraenergia.com.br':'Ryan Trindade','alberto.nascimento@lioraenergia.com.br':'Alberto Nascimento','marcel.sousa@lioraenergia.com.br':'Marcel Sousa','jefferson.fideli@lioraenergia.com.br':'Jefferson Fideli','phillip.faria@lioraenergia.com.br':'Phillip Faria','tais.santos@lioraenergia.com.br':'Tais Santos',
 'tiago.freitas@lioraenergia.com.br':'Tiago Freitas','tamires.costa@lioraenergia.com.br':'Tamires Costa','thiago.araujo@lioraenergia.com.br':'Thiago Araujo França','camila.couto@lioraenergia.com.br':'Camila Couto',
}
TITLE2OP = {'Salvador':'salvador','Feira':'feira','Natal':'natal','RN Interior':'rninterior','SPI':'spi','Ribeirao':'ribeirao','CE':'ce','Outras':'outras'}

def norm(s): return re.sub(r'\s+',' ',(s or '').strip()).upper()
# CLIENT_OVERRIDE: força vendedor/praça enquanto o suporte não corrige na origem
CLIENT_OVERRIDE = {
 norm('NIVALDO GESTEIRA DE OLIVEIRA'): ('Maria Lúcia','salvador','Salvador'),
 norm('MANOEL ROQUE DA SILVA JUNIOR'): ('Lucileide Carlos','feira','Feira'),
 norm('CARLA NUNCIA BESERRA'): ('Marcio Galvão','natal','Natal'),  # 2a UC da Carla - é do Marcio (Felipe 26/06)
 norm('MARIA SOARES RODRIGUES'): ('Rodrigo Ribeiro','natal','Natal'),  # deal do Bruno -> Rodrigo (Felipe 03/07)
 norm('VALDEMARINA ALVES NABUCO'): ('Ettore Rossi','salvador','Salvador'),  # deal caiu no Adroaldo -> e do Rossi (Felipe 25/07)
 norm('NICHOLAS PIETRO RODRIGUES REGINALDO'): ('Lucas Santos','rninterior','RN Interior'),  # dono -> Lucas (Felipe 27/07)
 norm('NATANAEL SILVA DOS SANTOS'): ('Lucas Santos','rninterior','RN Interior'),  # dono -> Lucas (Felipe 27/07)
 norm('MARIA FRAUZINA CAMILO'): ('Anderson Correia','spi','SPI'),
 norm('ANA JULIA DA CONCEIÇÃO FREIRE'): ('Ettore Rossi','salvador','Salvador'),  # venda do Rossi lancada na Silvia (Salvador); base ja corrigida mas o card818 ainda mostra Silvia (Felipe 14/08); remover qdo refletir  # aprovado 06/08 do Anderson; base trocou p/ Lucas 07/08 -> volta p/ Anderson (Felipe 07/08); remover qdo base corrigir
}

unknown = set()
def seller_of(email, client):
    ov = CLIENT_OVERRIDE.get(norm(client))
    if ov: return ov[0]
    em = (email or '').strip().lower()
    if em and em not in EMAIL2NAME: unknown.add(em)
    return EMAIL2NAME.get(em, (email or '').strip())
def op_of(email, client):
    ov = CLIENT_OVERRIDE.get(norm(client))
    if ov: return ov[1]
    em = (email or '').strip().lower()
    return TITLE2OP.get(PRACA_TITLE.get(em, 'Outras'), 'outras')
def praca_of(email, client):
    ov = CLIENT_OVERRIDE.get(norm(client))
    if ov: return ov[2]
    em = (email or '').strip().lower()
    return PRACA_TITLE.get(em, 'Outras')

# CONSUMPTION_OVERRIDE: corrige MWh na fonte enquanto a base nao atualiza (temp).
CONSUMPTION_OVERRIDE_BY_ID = {  # deal_id -> MWh; ganha do override por nome. card818 congelado (0.632) e nome 'MW SAFETY LTDA' forca 0.632 em todas as UCs; este id e' 1.636 (Felipe 07/08); remover qdo CI destravar
 '35f26046-9c78-4c2b-a7fe-04f7e7564c38': 1.636,  # Mw Safety Ltda / Joao Santos (Ribeirao)
 'a8216055-6fa2-491f-a651-0d70ad461f08': 0.632,  # a8216055 fatura R$47,90; Felipe mantem 0.632 (07/08)
 'd7f9bcce-7145-4bf3-b043-0c12b461bf97': 0.561,  # PAULO HENRIQUE GHIOTTI DA SILVA / Olimpio Filho (Ribeirao) - aprovado 17/08; card818 em cache manda 0.0, gold viva = 0.561 (Felipe 17/08); remover quando a base refletir
}
CONSUMPTION_OVERRIDE = {
 norm('FRANCISCO ALDECI DE QUEIROZ FERNANDES'): 5.86,  # base mostra 0.59 (Felipe 03/07)
 norm('GABRIEL LUCHIARI ALBERTO'): 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 norm('PERFECTA VIDROS E ALUMINIOS EIRELI'): 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 norm('CHEVROFOR COM PECAS E ACESSORIOS LTDA'): 1.21,  # base mostra 0.50 (Felipe 07/07)
 norm('MÁRCIO PEREIRA PINTO'): 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
 norm('DRAX CENTRO AUTOMOTIVO LTDA'): 4.311,
}
# PRODUCT_OVERRIDE: deal_id -> produto/credito_ok. Espelha o mesmo dict do process_mobile.py
# (os 2 dashboards tem de bater). Venda feita como Antecipa e registrada com outro produto.
PRODUCT_OVERRIDE = {
 '02f320f6-e275-449f-b385-aaec0dfcc541': {'produto':'LIORA_ANTECIPA_PJ','credito_ok':True},  # MARCELO OLIVEIRA VENERANDO (Odirley/CE, 2.62 MWh, aprovado 17/08) - vendido como Antecipa, base traz LIORA_F_ (Felipe 18/08)
}
# LOST_IGNORE: ignora lost_at/lost_reason (falso 'nao aceito pela distribuidora') p/ estes clientes.
LOST_IGNORE = { norm('FRANCISCO ALDECI DE QUEIROZ FERNANDES'), norm('ANTÔNIO EDMILSON LEITE') }  # 2º: dup denied em BGC, forçado aprovado (Felipe 15/07)
# FORCE_APPROVED: deals que contam como aprovado por decisao manual (contrato assinado,
# aguardando BGC). Chave = deal_id. Remover quando a base refletir BGC APPROVED.
FORCE_APPROVED = {'dabf7abd-1266-40b0-bb0b-6b593cfca457': '2026-08-18',  # MATEUS BERNARDINO DE MELO (Antecipa PF, Odirley Costa/CE, 2.616 MWh) - risco APROVADO na gold viva em 18/08 13:18 (card818 em cache ainda mostra a analise antiga de 15/08 APPROVED_PENDING_CREDIT, que jogava ele p/ fora da janela 17-23/08 e matava o 1,5x); credito ja em PAYMENT_SUCCEDED. Felipe 18/08: contar com 1,5x. Remover quando o card818 refletir.
                  '1e11931c-3e99-48f4-a338-47d734012625': '2026-08-20',  # FRANCISCO DAS CHAGAS CUNHA SILVA / 33050196000188 (Antecipa PJ, Olimpio Filho/Ribeirao, 0.916 MWh) - reaprovado 20/08 (lag de ingestao). ATENCAO: o risco RE-REPROVOU o deal em 21/08 14:04 ('Reprovado na analise de risco', lost + BGC_PARCEIRO) e o risk_real confirma DENIED; Felipe 21/08 mandou MANTER como aprovado mesmo assim. Nao remover sem falar com ele.
                  'cfb2500c-c323-4943-a7f8-e831a8f37b55': '2026-08-04',  # PP FERREIRA DE SALES COMER DE COSMETICOS - aprovado manual SOS 15:32 04/08 (Aurivando/CE); card818+risk_real ainda MANUAL; remover quando base refletir
                  'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': '2026-08-12',  # ISMAEL RODRIGUES SILVA (Antecipa PF, Phillip Faria/Ribeirao SPI) - aprovado manual (Felipe 12/08); base risco MANUAL; remover quando base refletir
                  '77a56fa5-9c4e-476c-b71d-ac08534d6745': '2026-08-13',  # DILEUDA CORINGA DA FONSECA DA SILVA (Antecipa PF, Thiago Macillo/Natal RN) - aprovado manual (Felipe 13/08); risco APPROVED_PENDING_CREDIT + credito PENDING; remover quando base refletir
                  'b4e7eacc-8dc9-445e-9a37-d83cb3ecff80': '2026-08-13',  # DANILO FERREIRA DE LACERDA (Antecipa PF, Fabio Rodrigues/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; aprovado manual (Felipe 13/08); remover quando base refletir
                  '1d00bb47-a942-4407-8216-98df676b41e9': '2026-08-13',
                  '0b97aa9e-2def-45ec-ad98-034573f178a6': '2026-08-17',
                  '25611c90-3b9b-4b2f-a42e-41d22dcebd7a': '2026-08-17',  # THAIS CRISTINA FLOSINO (Antecipa PJ, Joao Santos/Ribeirao) - risco APPROVED_PENDING_CREDIT + CREDITO APPROVED na gold, mas o card818 veio em cache com MANUAL/sem credito (Felipe 17/08); remover quando a base refletir  # JONAS EMER COQUELY / 62018400000181 (Antecipa PJ, Joao Santos/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT (Pix) + sem analise de credito; aprovado manual (Felipe 17/08); remover quando base refletir  # ALESSANDRA DELFINO (Antecipa PF, Phillip Faria/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; aprovado manual (Felipe 13/08); remover quando base refletir
                  # Felipe 20/08: Antecipa aprovado na MADRUGADA de 20/08 (pagamento fechou de noite,
                  # risco saiu entre 00:23 e 01:14) conta no dia 19/08, dia em que a venda foi trabalhada.
                  # Data manual so p/ o dia; os 3 estao APPROVED de verdade na base (nao e' aprovacao forcada).
                  '2a50c11b-55c8-4f23-810f-438c71f90696': '2026-08-19',  # ROSEMEIRE DIAS DE ALMEIDA (Antecipa PF, Ettore Rossi/Salvador, 1.29 MWh) - risco APPROVED 20/08 00:23
                  '18a28a63-cd00-4bde-97e0-f04151fe5a2d': '2026-08-19',  # NELO MINGHE NETO (Antecipa PJ, Fabio Rodrigues/Ribeirao, 0.905 MWh) - risco APPROVED 20/08 00:47
                  '67505be8-e7a4-496f-a8e3-a711909fa2fc': '2026-08-19',  # ALEXANDRE ZANETI ARANTES (Antecipa PJ, Karianine Sampaio/Ribeirao, 0.871 MWh) - risco APPROVED 20/08 01:14
                  }  # ALEXANDRE ZANETI ARANTES (Antecipa PJ, Karianine Sampaio/Ribeirao, 0.871 MWh) - risco APPROVED 20/08 01:14
def mwh_of(client, raw, did=None):
    if did is not None:
        ovid = CONSUMPTION_OVERRIDE_BY_ID.get(did)
        if ovid is not None: return ovid
    ov = CONSUMPTION_OVERRIDE.get(norm(client))
    return ov if ov is not None else fnum(raw)

# ---- Antecipa / credito (Felipe 06/08) -----------------------------------
# Cliente do Antecipa com analise de CREDITO aprovada conta como aprovado no
# resultado de Field (mesmo em BGC_PARCEIRO / risco APPROVED_PENDING_CREDIT).
# deal_credit_stage traduzido p/ portugues p/ dar contexto da situacao.
CREDIT_STAGE_PT = {
 'GATHERING_DEPOSIT_INFORMATION': 'COLETANDO_INFORMAÇÕES_DE_DEPÓSITO',
 'PAYMENT_SUCCEDED': 'PAGAMENTO_REALIZADO',
 'CREDIT_ANALISYS_REJECTED': 'ANÁLISE_DE_CRÉDITO_REJEITADA',
 'WAITING_CLIENT_CONFIRMATION': 'AGUARDANDO_CONFIRMAÇÃO_DO_CLIENTE',
 'WAITING_CLIENT_RESPONSE': 'AGUARDANDO_RESPOSTA_DO_CLIENTE',
 'WAITING_PAYMENT_APPROVAL': 'AGUARDANDO_APROVAÇÃO_DE_PAGAMENTO',
 'DISPATCH_RECOVERY_COMMS': 'ENVIO_DE_COMUNICADOS_DE_RECUPERAÇÃO',
 'PAYMENT_REJECTED': 'PAGAMENTO_REJEITADO',
 'PENDING': 'PENDENTE',
}
def credit_pt(s):
    s = (s or '').strip()
    return CREDIT_STAGE_PT.get(s, s)

# ---- APPROVED_PENDING_CREDIT conta como aprovado (Felipe 18/08) -----------
# Regra nova: APPROVED_PENDING_CREDIT JA E' aprovacao de risco - o "pending credit"
# e' so a etapa de pagamento do Antecipa. Antes so contava se o credito saisse
# 'approved', o que deixava de fora todo Antecipa pago via PIX (que nunca gera
# analise de credito: Jonas Emer 17/08, Nelo Minghe 18/08) e obrigava a um
# FORCE_APPROVED manual por cliente. UNICA excecao: credito NEGADO/REJEITADO.
CREDIT_NEG = {'denied', 'rejected', 'refused'}
CREDIT_STAGE_NEG = {'CREDIT_ANALISYS_REJECTED', 'PAYMENT_REJECTED'}
def apc_ok(r):
    """True quando o risco e' APPROVED_PENDING_CREDIT e o credito NAO foi negado."""
    if (r.get('latest_risk_analysis_result') or '').strip() != 'APPROVED_PENDING_CREDIT':
        return False
    if (r.get('latest_credit_analysis_result') or '').strip().lower() in CREDIT_NEG:
        return False
    if (r.get('deal_credit_stage') or '').strip() in CREDIT_STAGE_NEG:
        return False
    return True

# ---- rawData (deals + aguardando, dedup por deal_id) ---------------------
def mk_deal(r):
    risk = (r['latest_risk_analysis_result'] or '').strip()
    _apc = apc_ok(r)  # Felipe 18/08: risco aprovado pendente de crédito já conta
    if r['deal_stage']=='BGC_PARCEIRO' and not _apc: risk=''  # em validação Antecipa: não conta como aprovado
    credit = (r.get('latest_credit_analysis_result') or '').strip().lower()  # Antecipa
    credito_ok = (credit == 'approved')
    if _apc: risk='APPROVED'  # Felipe 18/08: APPROVED_PENDING_CREDIT = aprovado (falta só o pagamento)
    if credito_ok: risk='APPROVED'  # Felipe 06/08: crédito aprovado (Antecipa) conta como aprovado no Field
    if r['deal_id'] in FORCE_APPROVED: risk='APPROVED'  # aprovado manual
    # aprovado conta pela DATA DA ANÁLISE DE RISCO; sem risco (WAITING) usa criação
    d = pdate(r['latest_risk_analysis_created_at']) or pdate(r['deal_created_at'])
    if r['deal_id'] in FORCE_APPROVED and FORCE_APPROVED[r['deal_id']]: d = FORCE_APPROVED[r['deal_id']]  # data de aprovação manual
    forced = r['deal_id'] in FORCE_APPROVED
    # o isAprovado() do HTML descarta BGC_PARCEIRO ANTES de olhar o risco, entao o
    # aprovado-pendente-de-credito precisa sair do estagio de validacao (mesmo
    # tratamento que o FORCE_APPROVED ja fazia na mao para esses mesmos clientes).
    out_stage = 'REQUEST_TITULARIDADE' if ((forced or _apc) and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']
    _prod_ov = PRODUCT_OVERRIDE.get((r.get('deal_id') or '').strip(), {})  # venda Antecipa registrada com produto errado (Felipe 18/08)
    return {
      'c': r['current_client_name'],
      's': seller_of(r['sales_person_email'], r['current_client_name']),
      'op': op_of(r['sales_person_email'], r['current_client_name']),
      'risk': risk,
      'mwh': mwh_of(r['current_client_name'], r['current_consumption_filled'], r['deal_id']),
      'stage': out_stage,
      'status': r['ops_tt_status'] or 'N/A',
      'idle': int(fnum(r['idle_days'])),
      'city': r['current_client_city'],
      'produto': _prod_ov.get('produto', (r.get('product_name') or '').strip()),
      'credito_ok': _prod_ov.get('credito_ok', credito_ok),  # Antecipa: análise de crédito aprovada (Felipe 06/08)
      'apc': bool(_apc),  # aprovado no risco, pendente de crédito/pagamento (Felipe 18/08)
      'fapr': bool(forced),  # aprovado manual (FORCE_APPROVED) - alimenta a quebra do card
      'rapr': (r['latest_risk_analysis_result'] or '').strip()=='APPROVED',  # risco APPROVED na base (quebra do card)
      'credito': credit_pt(r.get('deal_credit_stage')),  # situação do Antecipa (PT)
      'semana': semana(d),
      'lost_at': ('' if (forced or norm(r['current_client_name']) in LOST_IGNORE) else (r['deal_lost_at'] or '')),
      'lost_reason': ('' if (forced or norm(r['current_client_name']) in LOST_IGNORE) else (r['deal_lost_reason'] or '')),
      'motivo': (('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else (r.get('latest_risk_analysis_comments') or '').strip()),
      'docs': DOCS.get((r.get('latest_contract_id') or '').strip(),''),
      'uc': UC.get(r['deal_id'],''),
      'date': d or '',
    }
seen = set(); rawData = []
for r in deals + agu:                 # aguardando entra como deals extras
    did = r['deal_id']
    if did in seen: continue           # dedup por deal_id (clientes multi-UC)
    seen.add(did)
    rawData.append(mk_deal(r))
for r in prop:                        # injeta aprovados manuais ausentes dos recortes
    did = r['deal_id']
    if did in FORCE_APPROVED and did not in seen:
        seen.add(did)
        rawData.append(mk_deal(r))
rawData.sort(key=lambda x: (x['date'], -x['mwh']), reverse=True)

# ---- RAW (propostas — todas do mês corrente, sem dedup) ------------------
RAW = []
for r in prop:
    d = pdate(r['proposal_created_at'])
    dt = datetime.date(int(d[:4]), int(d[5:7]), int(d[8:10])) if d else None
    RAW.append({
      'date': d or '',
      'week': dt.isocalendar()[1] if dt else 0,      # semana ISO
      'month': dt.month if dt else 0,
      'dayofweek': DOW[dt.weekday()] if dt else '',   # nome em inglês
      'sales_person_name': r['sales_person_name'],
      'seller': seller_of(r['sales_person_email'], r['current_client_name']),
      'bill_cost': round(fnum(r['current_total_bill_cost (R$)']), 2),  # R$ CRU (sem /1000!)
      'consumption_mwh': mwh_of(r['current_client_name'], r['current_consumption_filled'], r['deal_id']),
      'current_client_name': r['current_client_name'],
      'current_client_state': r['current_client_state'],
      'deal_stage': r['deal_stage'],
      'accepted_proposal': (r['accepted_proposal'] or '').strip().lower() == 'true',
      'praca': praca_of(r['sales_person_email'], r['current_client_name']),
      'uc': UC.get(r['deal_id'],''),
      'produto': (r.get('product_name') or '').strip(),
      'det': {
        'CNPJ': r['current_client_cnpj'], 'CPF': r['current_client_cpf'],
        'Telefone': r['client_phone_number'], 'Cidade': r['current_client_city'],
        'Distribuidora': r['distributor_short_name'], 'Campanha': r['origin_campaign'],
        'Origem': r['origin_source'], 'Classificação': r['internal_sales_classification'],
        'Time': r['sales_team'], 'Canal': r['sales_channel_name'],
        'E-mail vendedor': r['sales_person_email'], 'Proposta ID': r['proposal_id'],
      },
    })

# ---- ANTECIPA (propostas do produto de credito Antecipa, mes corrente) ---
# Recorte proprio (Inside Sales / Retool), independente do FS_Liora. Alimenta a
# aba "Antecipa" do desktop: total, aceites, funil por estagio, distribuidora/UF
# e lista de clientes. Os agregados sao calculados no proprio frame (JS).
ANT_DIST = {
 'NEOENERGIA COELBA':'Coelba','NEOENERGIA COSERN':'Cosern','ENEL CE':'Enel CE',
 'CPFL PAULISTA':'CPFL','COPEL-DIS':'Copel','EQUATORIAL CEA':'Equatorial CEA',
 'ENEL RJ':'Enel RJ','NEOENERGIA ELEKTRO':'Elektro','Amazonas Energia':'Amazonas',
 'EQUATORIAL GO':'Equatorial GO','ENEL SP':'Enel SP','LIGHT':'Light',
}
def _ant_tipo(prod):
    p=(prod or '').strip().upper()
    if p.endswith('PJ'): return 'PJ'
    if p.endswith('PF'): return 'PF'
    return '-'
# Chave de praca no formato usado pelos frames (badge/pilulas): 'RN Interior'->'RNInterior'
_ANT_PRACA_KEY = {'Salvador':'Salvador','Feira':'Feira','Natal':'Natal','RN Interior':'RNInterior',
                  'SPI':'SPI','Ribeirao':'Ribeirao','CE':'CE','Outras':'Outras'}
# ANT_APPROVE: aprovacoes manuais da aba Antecipa (Felipe). Forca risk=APPROVED p/ o deal
# (por deal_id) e injeta o registro se o card818 ainda nao o trouxe (o augmento do funil
# vivo traz com risco MANUAL). Remover quando a base refletir a aprovacao.
ANT_APPROVE = {
 'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': {  # ISMAEL RODRIGUES SILVA - Phillip Faria/Ribeirao SPI - Antecipa PF - aprovado manual (Felipe 12/08)
   'c':'ISMAEL RODRIGUES SILVA','s':'Phillip Faria','praca':'Ribeirao','city':'SERTAOZINHO','uf':'SP',
   'dist':'CPFL','bill':460.09,'mwh':0.206,'stage':'BGC_PENDING_BILLS','acc':True,
   'tipo':'PF','signed':True,'date':'2026-08-12',
 },
 '77a56fa5-9c4e-476c-b71d-ac08534d6745': {  # DILEUDA CORINGA DA FONSECA DA SILVA - Thiago Macillo/Natal RN - Antecipa PF - aprovado manual (Felipe 13/08); risco APPROVED_PENDING_CREDIT + credito PENDING; remover quando base refletir
   'c':'DILEUDA CORINGA DA FONSECA DA SILVA','s':'Thiago Macillo','praca':'Natal','city':'NATAL','uf':'RN',
   'dist':'Cosern','bill':758.16,'mwh':0.49,'stage':'BGC_PARCEIRO','acc':True,
   'tipo':'PF','signed':True,'date':'2026-08-12',
 },
 'b4e7eacc-8dc9-445e-9a37-d83cb3ecff80': {  # DANILO FERREIRA DE LACERDA - Fabio Rodrigues/Ribeirao - Antecipa PF - aprovado manual (Felipe 13/08); BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; remover quando base refletir
   'c':'DANILO FERREIRA DE LACERDA','s':'Fabio Rodrigues','praca':'Ribeirao','city':'RIBEIRAO PRETO','uf':'SP',
   'dist':'CPFL','bill':470.11,'mwh':0.45,'stage':'BGC_PARCEIRO','acc':True,
   'tipo':'PF','signed':True,'date':'2026-08-13',
 },
 '1d00bb47-a942-4407-8216-98df676b41e9': {  # ALESSANDRA DELFINO - Phillip Faria/Ribeirao - Antecipa PF - aprovado manual (Felipe 13/08); BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; remover quando base refletir
   'c':'ALESSANDRA DELFINO','s':'Phillip Faria','praca':'Ribeirao','city':'RIBEIRAO PRETO','uf':'SP',
   'dist':'CPFL','bill':204.9,'mwh':0.207,'stage':'BGC_PARCEIRO','acc':True,
   'tipo':'PF','signed':True,'date':'2026-08-13',
 },
 '0b97aa9e-2def-45ec-ad98-034573f178a6': {  # JONAS EMER COQUELY - Joao Santos/Ribeirao - Antecipa PJ - aprovado manual (Felipe 17/08); BGC_PARCEIRO risco APPROVED_PENDING_CREDIT (Pix) + sem analise de credito; remover quando base refletir
   'c':'Jonas Emer Coquely','s':'João Santos','praca':'Ribeirao','city':'RIBEIRÃO PRETO','uf':'SP',
   'dist':'CPFL','bill':758.15,'mwh':2.38,'stage':'BGC_PARCEIRO','acc':True,
   'tipo':'PJ','signed':True,'date':'2026-08-15',
 },
 '25611c90-3b9b-4b2f-a42e-41d22dcebd7a': {  # THAIS CRISTINA FLOSINO - Joao Santos/Ribeirao - Antecipa PJ - credito approved na gold; card818 em cache (Felipe 17/08); remover quando a base refletir
   'c':'Thaís Cristina Flosino','s':'João Santos','praca':'Ribeirao','city':'RIBEIRÃO PRETO','uf':'SP',
   'dist':'CPFL','bill':459.95,'mwh':0.429,'stage':'BGC_PARCEIRO','acc':True,
   'tipo':'PJ','signed':True,'date':'2026-08-12',
 },
 '02f320f6-e275-449f-b385-aaec0dfcc541': {  # MARCELO OLIVEIRA VENERANDO - Odirley Costa/CE - vendido como Antecipa PJ mas o CRM registrou LIORA_F_ (fora do recorte Antecipa); injecao manual (Felipe 18/08); remover quando o CRM corrigir o produto
   'c':'MARCELO OLIVEIRA VENERANDO','s':'Odirley Costa','praca':'CE','city':'PACATUBA','uf':'CE',
   'dist':'Enel CE','bill':313.39,'mwh':2.62,'stage':'REQUEST_TITULARIDADE','acc':True,
   'tipo':'PJ','signed':True,'date':'2026-08-13','adate':'2026-08-17',
 },
}
_seen_ant = set()
ANTECIPA = []
if f_ant:
    for r in rows(f_ant):
        # SO Field Sales (Felipe 10/08): a aba Antecipa passa a mostrar apenas as
        # propostas do time de campo; ignora Inside Sales / Performance / Retool.
        _team = (r.get('sales_team') or '').strip()
        _chan = (r.get('sales_channel_name') or '').strip().upper()
        if _team != 'Field Sales' and not _chan.startswith('[FS]'):
            continue
        d = pdate(r.get('proposal_created_at')) or pdate(r.get('deal_created_at'))
        dist_raw = (r.get('distributor_short_name') or '').strip()
        _cli = (r.get('current_client_name') or '').strip()
        _em = r.get('sales_person_email')
        _did = (r.get('deal_id') or '').strip()
        _seen_ant.add(_did)
        # adate = data da APROVACAO (analise de risco). Usada p/ contar aprovados
        # pela data em que foram aprovados dentro do filtro (Felipe 12/08), nao pela geracao.
        # FORCE_APPROVED/ANT_APPROVE guardam a data da aprovacao MANUAL (Felipe): ela ganha
        # do risco da base, senao o deal forcado entra na aba com a data errada (Missao/aprovados por data).
        _adate = FORCE_APPROVED.get(_did) or pdate(r.get('latest_risk_analysis_created_at')) or (d or '')
        ANTECIPA.append({
          'c': _cli,
          's': seller_of(_em, _cli),
          'praca': _ANT_PRACA_KEY.get(praca_of(_em, _cli), 'Outras'),
          'city': (r.get('current_client_city') or '').strip(),
          'uf': (r.get('current_client_state') or '').strip(),
          'dist': ANT_DIST.get(dist_raw, dist_raw.title() if dist_raw else '-'),
          'bill': round(fnum(r.get('current_total_bill_cost (R$)')), 2),
          'mwh': round(fnum(r.get('current_consumption_filled')), 3),
          'stage': (r.get('deal_stage') or '').strip(),
          'acc': (r.get('accepted_proposal') or '').strip().lower()=='true',
          # Felipe 12/08: a aba Antecipa passa a honrar credito aprovado (mesma regra 06/08 do resto):
          # credito=='approved' conta como APPROVED aqui tambem (antes so risco APPROVED contava, e
          # deals com credito approved + risco APPROVED_PENDING_CREDIT sumiam da aba). Ver memoria antecipa.
          'risk': ('APPROVED' if (_did in ANT_APPROVE or apc_ok(r) or (r.get('latest_credit_analysis_result') or '').strip().lower()=='approved') else (r.get('latest_risk_analysis_result') or '').strip()),  # apc_ok: Felipe 18/08
          'credito': ('approved' if _did in ANT_APPROVE else (r.get('latest_credit_analysis_result') or '').strip()),
          'tipo': _ant_tipo(r.get('product_name')),
          # obs = observacao da analise de risco (Felipe 21/08): da visibilidade
          # ao time do que travou o cliente (fatura vencida, baixa_renda, etc).
          'obs': clean_obs(r.get('latest_risk_analysis_comments')),
          'signed': bool((r.get('latest_contract_signature_signed_at') or '').strip()),
          'date': d or '',
          'adate': _adate,
        })
for _did, _rec in ANT_APPROVE.items():
    if _did not in _seen_ant:
        _r = dict(_rec); _r['risk'] = 'APPROVED'; _r.setdefault('credito','approved')
        _r['adate'] = FORCE_APPROVED.get(_did) or _r.get('adate') or _r.get('date','')
        ANTECIPA.append(_r)
ANTECIPA.sort(key=lambda x: x['date'], reverse=True)
io.open('new_ANTECIPA.json','w').write(json.dumps(ANTECIPA, ensure_ascii=False))

# ---- MISSAO: campanha "Semana do Antecipa" (13-23/08/2026) ----------------
# Alimenta a aba "Missao" do desktop (restrita a lideres/gestao). Recorte:
# cliente Antecipa do FIELD com analise APROVADA (risco ou credito) e data de
# aprovacao (adate) dentro da janela. A largada valeu de 13/08 (slide "A largada
# e hoje"), a vigencia oficial do material e 17-23/08 -> Felipe optou por 13/08.
MISSAO_INI, MISSAO_FIM = '2026-08-13', '2026-08-23'
MISSAO = [{'s':x['s'], 'praca':x['praca'], 'mwh':x['mwh'], 'c':x['c'], 'tipo':x.get('tipo',''),
           'adate':(x.get('adate') or x.get('date') or '')}
          for x in ANTECIPA
          if x.get('risk')=='APPROVED' and MISSAO_INI <= (x.get('adate') or x.get('date') or '') <= MISSAO_FIM]
MISSAO.sort(key=lambda x: (x['adate'], -x['mwh']), reverse=True)
io.open('new_MISSAO.json','w').write(json.dumps(MISSAO, ensure_ascii=False))
# Roster = quadro de vendedores por praca. O pre-requisito da campanha e' 1 venda
# de Antecipa POR VENDEDOR, entao a aba precisa da lista completa (nao so de quem
# ja vendeu). Fora: gestao e vendedores ocultos (alinhado ao OCULTOS_TIME do mobile).
MISSAO_FORA = {'Felipe Oliveira','Ana Ribeiro','Raynara Silva','Camila Couto',
               'Ananias Neto','Rosangela Mendes','Franciele Felix','Ryan Trindade','Antonio Mariano',
               'Thiago Araujo França',  # espelha OCULTOS_TIME + EX_TIME do mobile (os 2 dashboards tem de bater)
               # Felipe 14/08: LIDER nao entra no pre-requisito (nao precisa vender 1 Antecipa);
               # o que ele vender continua somando no MWh do time.
               'Adroaldo Bonfim','Kelma Rangel','Bruno Andrade','Mirla Albuquerque','Caio Lannes','João Santos','Bruno Borges'}
_ros = set()
for _em, _pr in PRACA_TITLE.items():
    if _pr == 'Outras': continue
    _nm = EMAIL2NAME.get(_em)
    if not _nm or _nm in MISSAO_FORA: continue
    _ros.add((_ANT_PRACA_KEY.get(_pr, 'Outras'), _nm))
MISSAO_ROSTER = [[a,b] for a,b in sorted(_ros)]
io.open('new_MISSAO_ROSTER.json','w').write(json.dumps(MISSAO_ROSTER, ensure_ascii=False))
print('missao:', len(MISSAO), 'aprovados |', len(MISSAO_ROSTER), 'vendedores no roster')
# ---- ANT_FIELD: propostas do FIELD do mes (GD FS_Liora + Antecipa Field) com flags
# sig(assinado)/apr(aprovado risco) p/ calcular a fatia do Antecipa nos KPIs da aba. ----
def _gd_apr(r):
    risk=(r.get('latest_risk_analysis_result') or '').strip()
    _apc=apc_ok(r)  # Felipe 18/08
    if (r.get('deal_stage') or '')=='BGC_PARCEIRO' and not _apc: risk=''
    if _apc: risk='APPROVED'
    if (r.get('latest_credit_analysis_result') or '').strip().lower()=='approved': risk='APPROVED'
    if (r.get('deal_id') or '').strip() in FORCE_APPROVED: risk='APPROVED'
    return risk=='APPROVED'
ANT_FIELD=[]
for r in prop:  # GD field (FS_Liora)
    _cli=(r.get('current_client_name') or '').strip(); _em=r.get('sales_person_email')
    _d=pdate(r.get('proposal_created_at')) or pdate(r.get('deal_created_at'))
    ANT_FIELD.append({'date':_d or '','adate':(pdate(r.get('latest_risk_analysis_created_at')) or (_d or '')),'praca':_ANT_PRACA_KEY.get(praca_of(_em,_cli),'Outras'),
                      's':seller_of(_em,_cli),
                      'sig':bool((r.get('latest_contract_signature_signed_at') or '').strip()),
                      'apr':_gd_apr(r)})
for _x in ANTECIPA:  # Antecipa Field (mesma definicao do numerador da aba)
    ANT_FIELD.append({'date':_x['date'],'adate':_x.get('adate',_x['date']),'praca':_x['praca'],'s':_x['s'],
                      'sig':bool(_x.get('signed')),'apr':(_x.get('risk')=='APPROVED')})
io.open('new_ANT_FIELD.json','w').write(json.dumps(ANT_FIELD, ensure_ascii=False))
print('ant_field:', len(ANT_FIELD))
print('antecipa:', len(ANTECIPA), '|', (os.path.basename(f_ant) if f_ant else 'sem arquivo'))

# ---- ROSTER do time (planilha de HC do Field, aba principal) -------------
# https://docs.google.com/spreadsheets/d/1Xrq4e1B3cjla9xA-ypHCP_H-fLxrT2H5crS2UwthIAw/
# email -> (cargo, hiring_date). SO quem esta ATIVO aqui aparece na aba
# "Historico" (Felipe 14/08: mostrar so os ativos). Quem sai da operacao some da
# aba no rebuild seguinte. ATUALIZAR quando entrar/sair gente (mesmo ritual dos
# mapas PRACA_TITLE/EMAIL2NAME). 'managment' TRUE (Felipe, Lucas Ferrara) fica de fora.
ROSTER_ATIVO = {
 'kelma.rangel@lioraenergia.com.br': ('lider','2025-09-01'),
 'lucileide.carlos@lioraenergia.com.br': ('consultor','2025-10-06'),
 'ettore.rossi@lioraenergia.com.br': ('consultor','2025-11-05'),
 'adroaldo.bonfim@lioraenergia.com.br': ('lider','2025-12-02'),
 'maria.lucia@lioraenergia.com.br': ('consultor','2026-01-08'),
 'marcio.galvao@lioraenergia.com.br': ('consultor','2026-02-02'),
 'caio.lannes@lioraenergia.com.br': ('lider','2026-02-25'),
 'tais.santos@lioraenergia.com.br': ('consultor','2026-03-16'),
 'bruno.andrade@lioraenergia.com.br': ('lider','2026-04-09'),
 'monica.silveira@lioraenergia.com.br': ('consultor','2026-04-15'),
 'tiago.freitas@lioraenergia.com.br': ('consultor','2026-04-15'),
 'bruno.borges@lioraenergia.com.br': ('lider','2026-04-15'),
 'ederson.silva@lioraenergia.com.br': ('consultor','2026-05-27'),
 'diego.faria@lioraenergia.com.br': ('consultor','2026-06-01'),
 'neilon.nascimento@lioraenergia.com.br': ('consultor','2026-06-01'),
 'rodrigo.ribeiro@lioraenergia.com.br': ('consultor','2026-06-01'),
 'odirley.costa@lioraenergia.com.br': ('consultor','2026-06-15'),
 'nubia.andrade@lioraenergia.com.br': ('consultor','2026-06-15'),
 'mecenas.junior@lioraenergia.com.br': ('consultor','2026-06-24'),
 'luciana.campos@lioraenergia.com.br': ('consultor','2026-06-25'),
 'nicola.popovic@lioraenergia.com.br': ('consultor','2026-06-29'),
 'joao.santos@lioraenergia.com.br': ('lider','2026-07-01'),
 'sabrina.tomazeti@lioraenergia.com.br': ('consultor','2026-07-06'),
 'tatiane.correia@lioraenergia.com.br': ('consultor','2026-07-13'),
 'daniel.magnus@lioraenergia.com.br': ('consultor','2026-07-13'),
 'anderson.correia@lioraenergia.com.br': ('consultor','2026-07-13'),
 'nha.negocios@gmail.com': ('consultor','2026-07-13'),  # e-mail alternativo do Anderson
 'mirla.albuquerque@lioraenergia.com.br': ('lider','2026-07-13'),
 'lucas.santos@lioraenergia.com.br': ('consultor','2026-07-23'),
 'silvia.dias@lioraenergia.com.br': ('consultor','2026-07-23'),
 'thiago.firmo@lioraenergia.com.br': ('consultor','2026-07-23'),
 'thymacillo@hotmail.com': ('consultor','2026-07-23'),  # e-mail alternativo do Thiago Firmo
 'alberto.nascimento@lioraenergia.com.br': ('consultor','2026-07-28'),
 'jefferson.fideli@lioraenergia.com.br': ('consultor','2026-08-03'),
 'marcel.sousa@lioraenergia.com.br': ('consultor','2026-08-03'),
 'phillip.faria@lioraenergia.com.br': ('consultor','2026-08-03'),
 'jose.monteiro@lioraenergia.com.br': ('consultor','2026-08-05'),  # Rodrigo Lima (corp_email da planilha)
 'jose.lima@lioraenergia.com.br': ('consultor','2026-08-05'),      # Rodrigo Lima (e-mail usado no CRM/dashboard)
 'daniel.junior@lioraenergia.com.br': ('consultor','2026-08-05'),
 'percy.hormazabal@lioraenergia.com.br': ('consultor','2026-08-06'),
 'tamires.costa@lioraenergia.com.br': ('consultor','2026-08-06'),
 'briel.barbosa@lioraenergia.com.br': ('consultor','2026-08-10'),
 'olimpio.filho@lioraenergia.com.br': ('consultor','2026-08-10'),
 'karianine.sampaio@lioraenergia.com.br': ('consultor','2026-08-18'),
 'fabio.rodrigues@lioraenergia.com.br': ('consultor','2026-08-10'),
}

# ---- HIST: historico de performance por vendedor (aba "Historico") -------
# Fonte: recorte historico_vendedor*.csv (3 meses fechados + mes corrente).
# COORTE PELA DATA DA PROPOSTA: todas as etapas seguem a proposta gerada no mes,
# e' o que faz as conversoes fecharem entre as linhas (Anexo A do Frame de
# Feedback do Field). Propostas contam por linha (igual a aba Propostas);
# gerados/assinados/aprovados contam por deal unico dentro do mes.
f_hist = (sorted(glob.glob(os.path.join(UP,'historico_vendedor*.csv'))) or [None])[-1]

def _hist_aprovado(x):
    # Espelho EXATO do isAprovado do HTML (nao alterar sem alterar o JS).
    if x.get('credito_ok'): return True
    if x['stage'] == 'BGC_PARCEIRO': return False
    if x['lost_at'] and x['stage'] == 'BACKGROUND_CHECKING' \
       and (x['lost_reason'] or '').strip().lower() != 'troca de titularidade': return False
    if x['risk'] == 'DENIED': return False
    if x['risk'] == 'APPROVED': return True
    if 'aprovado' in (x['status'] or '').lower(): return True
    if x['stage'] == 'REQUEST_TITULARIDADE': return True
    return False

HIST = []
_fora = set()
_unk_snap = set(unknown)  # mk_deal() no historico ve ex-vendedores: nao alerta por eles
if f_hist:
    _agg = {}; _seen_hd = set()
    for r in rows(f_hist):
        _d = pdate(r.get('proposal_created_at'))
        if not _d: continue
        _cli = (r.get('current_client_name') or '').strip(); _em = r.get('sales_person_email')
        # ex-vendedores aparecem no historico (meses passados) e nao estao nos mapas:
        # usa o nome do CRM como fallback SEM sujar o alerta de e-mail desconhecido.
        _e = (_em or '').strip().lower()
        _ros = ROSTER_ATIVO.get(_e)
        if not _ros or _ros[0] == 'lider':
            _fora.add(_e or '(sem email)')
            continue          # so os ATIVOS e NAO-LIDERES entram na aba (Felipe 14/08)
        _s = (CLIENT_OVERRIDE.get(norm(_cli)) or [None])[0] or EMAIL2NAME.get(_e) \
             or (r.get('sales_person_name') or _e or '?').strip()
        _pr = _ANT_PRACA_KEY.get(praca_of(_em, _cli), 'Outras')
        _k = (_s, _pr, _d[:7])
        _a = _agg.setdefault(_k, {'s':_s,'praca':_pr,'m':_d[:7],'p':0,'g':0,'a':0,'ap':0,'mwh':0.0,
                                  'pa':0,'ga':0,'aa':0,'apa':0,'mwha':0.0,
                                  'lid':(_ros[0]=='lider'), 'hire':_ros[1]})
        _ant = (r.get('product_name') or '').strip().upper().startswith('LIORA_ANTECIPA')
        _a['p'] += 1
        if _ant: _a['pa'] += 1
        _did = (r.get('deal_id') or '').strip()
        if _did:
            if (_k, _did) in _seen_hd: continue
            _seen_hd.add((_k, _did))
        _x = mk_deal(r)
        if (r.get('latest_contract_created_at') or '').strip():
            _a['g'] += 1
            if _ant: _a['ga'] += 1
        if (r.get('latest_contract_signature_signed_at') or '').strip():
            _a['a'] += 1
            if _ant: _a['aa'] += 1
        if _hist_aprovado(_x):
            _a['ap'] += 1; _a['mwh'] += _x['mwh']
            if _ant:
                _a['apa'] += 1; _a['mwha'] += _x['mwh']
    for _v in _agg.values():
        _v['mwh'] = round(_v['mwh'], 3); _v['mwha'] = round(_v['mwha'], 3)
    HIST = sorted(_agg.values(), key=lambda z: (z['praca'], z['s'], z['m']))
unknown.clear(); unknown.update(_unk_snap)
if _fora:
    print('historico: fora da aba (inativo ou lider):', ', '.join(sorted(_fora)))
io.open('new_HIST.json','w').write(json.dumps(HIST, ensure_ascii=False))
print('historico:', len(HIST), 'linhas vendedor x mes |',
      (os.path.basename(f_hist) if f_hist else 'sem arquivo'))

# ---- HC_PROP = [[date, seller]] (1:1 com RAW) ----------------------------
HC_PROP = [[r['date'], r['seller']] for r in RAW]

if unknown:
    print('!!! EMAILS DESCONHECIDOS (adicione aos mapas):', unknown, file=sys.stderr)

io.open('new_rawData.json','w').write(json.dumps(rawData, ensure_ascii=False))
io.open('new_RAW.json','w').write(json.dumps(RAW, ensure_ascii=False))
io.open('new_HC_PROP.json','w').write(json.dumps(HC_PROP, ensure_ascii=False))

# ---- relatório de sanidade ----------------------------------------------
from collections import Counter
print('\nrawData:', len(rawData), '| RAW:', len(RAW), '| HC_PROP:', len(HC_PROP))
print('emails desconhecidos:', unknown or 'nenhum')
print('rawData stage:', dict(Counter(x['stage'] for x in rawData)))
print('rawData op   :', dict(Counter(x['op'] for x in rawData)))
print('rawData risk :', dict(Counter(x['risk'] for x in rawData)))
apr = Counter()
for x in rawData:
    if x['risk'] == 'APPROVED' and not x['lost_at']:
        apr[x['op']] += x['mwh']
print('APROVADO MWh por praça:', {k: round(v,2) for k,v in apr.items()})
print('RAW praca:', dict(Counter(r['praca'] for r in RAW)))
print('Baleias (bill_cost>2000):', sum(1 for r in RAW if r['bill_cost'] > 2000))
print('data máxima:', max([x['date'] for x in rawData if x['date']] + [r['date'] for r in RAW if r['date']]))
