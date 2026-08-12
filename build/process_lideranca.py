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
INJECT_DEALS = []  # virada agosto 03/08: limpo (inject de julho)
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
}
EMAIL2NAME = {  # email -> nome canônico do vendedor (resolve nomes variáveis do CRM)
 'silmara.gomes@lioraenergia.com.br':'Silmara Gomes',
 'briel.barbosa@lioraenergia.com.br':'Briel Barbosa','olimpio.filho@lioraenergia.com.br':'Olímpio Filho','fabio.rodrigues@lioraenergia.com.br':'Fábio Rodrigues',  # novos 10/08
 'luciana.campos@lioraenergia.com.br':'Luciana Campos',
 'nicola.popovic@lioraenergia.com.br':'Nicola Popovic',
 'nha.negocios@gmail.com':'Anderson Correia',
 'anderson.correia@lioraenergia.com.br':'Anderson Correia',
 'percy.hormazabal@lioraenergia.com.br':'Percy Hormazabal',
 'monica.silveira@lioraenergia.com.br':'Monica Silveira',
 'ana.ribeiro@lioraenergia.com.br':'Ana Ribeiro',
 'jose.lima@lioraenergia.com.br':'Rodrigo Lima',
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
 norm('MARIA FRAUZINA CAMILO'): ('Anderson Correia','spi','SPI'),  # aprovado 06/08 do Anderson; base trocou p/ Lucas 07/08 -> volta p/ Anderson (Felipe 07/08); remover qdo base corrigir
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
}
CONSUMPTION_OVERRIDE = {
 norm('FRANCISCO ALDECI DE QUEIROZ FERNANDES'): 5.86,  # base mostra 0.59 (Felipe 03/07)
 norm('GABRIEL LUCHIARI ALBERTO'): 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 norm('PERFECTA VIDROS E ALUMINIOS EIRELI'): 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 norm('CHEVROFOR COM PECAS E ACESSORIOS LTDA'): 1.21,  # base mostra 0.50 (Felipe 07/07)
 norm('MÁRCIO PEREIRA PINTO'): 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
 norm('DRAX CENTRO AUTOMOTIVO LTDA'): 4.311,
}
# LOST_IGNORE: ignora lost_at/lost_reason (falso 'nao aceito pela distribuidora') p/ estes clientes.
LOST_IGNORE = { norm('FRANCISCO ALDECI DE QUEIROZ FERNANDES'), norm('ANTÔNIO EDMILSON LEITE') }  # 2º: dup denied em BGC, forçado aprovado (Felipe 15/07)
# FORCE_APPROVED: deals que contam como aprovado por decisao manual (contrato assinado,
# aguardando BGC). Chave = deal_id. Remover quando a base refletir BGC APPROVED.
FORCE_APPROVED = {'cfb2500c-c323-4943-a7f8-e831a8f37b55': '2026-08-04',  # PP FERREIRA DE SALES COMER DE COSMETICOS - aprovado manual SOS 15:32 04/08 (Aurivando/CE); card818+risk_real ainda MANUAL; remover quando base refletir
                  '42d73385-cf0f-4a56-bdb6-0d81161087f2': '2026-08-11',  # MAIZA PEREIRA DA SILVA (Antecipa PF, Bruno Borges/CE) - aprovado manual (Felipe 11/08); base risco MANUAL/credito vazio; remover quando base refletir
                  'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': '2026-08-12'}  # ISMAEL RODRIGUES SILVA (Antecipa PF, Phillip Faria/Ribeirao SPI) - aprovado manual (Felipe 12/08); base risco MANUAL; remover quando base refletir
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

# ---- rawData (deals + aguardando, dedup por deal_id) ---------------------
def mk_deal(r):
    risk = (r['latest_risk_analysis_result'] or '').strip()
    if r['deal_stage']=='BGC_PARCEIRO': risk=''  # em validação Antecipa: não conta como aprovado
    credit = (r.get('latest_credit_analysis_result') or '').strip().lower()  # Antecipa
    credito_ok = (credit == 'approved')
    if credito_ok: risk='APPROVED'  # Felipe 06/08: crédito aprovado (Antecipa) conta como aprovado no Field
    if r['deal_id'] in FORCE_APPROVED: risk='APPROVED'  # aprovado manual
    # aprovado conta pela DATA DA ANÁLISE DE RISCO; sem risco (WAITING) usa criação
    d = pdate(r['latest_risk_analysis_created_at']) or pdate(r['deal_created_at'])
    if r['deal_id'] in FORCE_APPROVED and FORCE_APPROVED[r['deal_id']]: d = FORCE_APPROVED[r['deal_id']]  # data de aprovação manual
    forced = r['deal_id'] in FORCE_APPROVED
    out_stage = 'REQUEST_TITULARIDADE' if (forced and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']
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
      'produto': (r.get('product_name') or '').strip(),
      'credito_ok': credito_ok,  # Antecipa: análise de crédito aprovada (Felipe 06/08)
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
          'risk': ('APPROVED' if (_did in ANT_APPROVE or (r.get('latest_credit_analysis_result') or '').strip().lower()=='approved') else (r.get('latest_risk_analysis_result') or '').strip()),
          'credito': ('approved' if _did in ANT_APPROVE else (r.get('latest_credit_analysis_result') or '').strip()),
          'tipo': _ant_tipo(r.get('product_name')),
          'signed': bool((r.get('latest_contract_signature_signed_at') or '').strip()),
          'date': d or '',
        })
for _did, _rec in ANT_APPROVE.items():
    if _did not in _seen_ant:
        _r = dict(_rec); _r['risk'] = 'APPROVED'; _r.setdefault('credito','approved')
        ANTECIPA.append(_r)
ANTECIPA.sort(key=lambda x: x['date'], reverse=True)
io.open('new_ANTECIPA.json','w').write(json.dumps(ANTECIPA, ensure_ascii=False))
# ---- ANT_FIELD: propostas do FIELD do mes (GD FS_Liora + Antecipa Field) com flags
# sig(assinado)/apr(aprovado risco) p/ calcular a fatia do Antecipa nos KPIs da aba. ----
def _gd_apr(r):
    risk=(r.get('latest_risk_analysis_result') or '').strip()
    if (r.get('deal_stage') or '')=='BGC_PARCEIRO': risk=''
    if (r.get('latest_credit_analysis_result') or '').strip().lower()=='approved': risk='APPROVED'
    if (r.get('deal_id') or '').strip() in FORCE_APPROVED: risk='APPROVED'
    return risk=='APPROVED'
ANT_FIELD=[]
for r in prop:  # GD field (FS_Liora)
    _cli=(r.get('current_client_name') or '').strip(); _em=r.get('sales_person_email')
    _d=pdate(r.get('proposal_created_at')) or pdate(r.get('deal_created_at'))
    ANT_FIELD.append({'date':_d or '','praca':_ANT_PRACA_KEY.get(praca_of(_em,_cli),'Outras'),
                      's':seller_of(_em,_cli),
                      'sig':bool((r.get('latest_contract_signature_signed_at') or '').strip()),
                      'apr':_gd_apr(r)})
for _x in ANTECIPA:  # Antecipa Field (mesma definicao do numerador da aba)
    ANT_FIELD.append({'date':_x['date'],'praca':_x['praca'],'s':_x['s'],
                      'sig':bool(_x.get('signed')),'apr':(_x.get('risk')=='APPROVED')})
io.open('new_ANT_FIELD.json','w').write(json.dumps(ANT_FIELD, ensure_ascii=False))
print('ant_field:', len(ANT_FIELD))
print('antecipa:', len(ANTECIPA), '|', (os.path.basename(f_ant) if f_ant else 'sem arquivo'))

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
