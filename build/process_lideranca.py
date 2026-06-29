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

deals = rows(f_deals)
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
 'mecenas.junior@lioraenergia.com.br':'Natal',
 'adroaldo.bonfim@lioraenergia.com.br':'Salvador','ananias.neto@lioraenergia.com.br':'Natal',
 'antonio.mariano@lioraenergia.com.br':'Salvador','bruno.andrade@lioraenergia.com.br':'Natal',
 'bruno.borges@lioraenergia.com.br':'CE','caio.lannes@lioraenergia.com.br':'SPI',
 'diego.faria@lioraenergia.com.br':'SPI','ederson.silva@lioraenergia.com.br':'SPI',
 'ettore.rossi@lioraenergia.com.br':'Salvador','felipe.oliveira@lioraenergia.com.br':'Outras',
 'franciele.felix@lioraenergia.com.br':'SPI','kelma.rangel@lioraenergia.com.br':'Feira de Santana',
 'lucileide.carlos@lioraenergia.com.br':'Feira de Santana','marcio.galvao@lioraenergia.com.br':'Natal',
 'maria.lucia@lioraenergia.com.br':'Salvador','neilon.nascimento@lioraenergia.com.br':'CE',
 'nubia.andrade@lioraenergia.com.br':'Outras','odirley.costa@lioraenergia.com.br':'Outras',
 'rodrigo.ribeiro@lioraenergia.com.br':'Natal','rosangela.mendes@lioraenergia.com.br':'Feira de Santana',
 'ryan.trindade@lioraenergia.com.br':'Feira de Santana','tais.santos@lioraenergia.com.br':'Salvador',
 'tiago.freitas@lioraenergia.com.br':'Feira de Santana','thiago.araujo@lioraenergia.com.br':'Natal',
}
EMAIL2NAME = {  # email -> nome canônico do vendedor (resolve nomes variáveis do CRM)
 'silmara.gomes@lioraenergia.com.br':'Silmara Gomes',
 'luciana.campos@lioraenergia.com.br':'Luciana Campos',
 'nicola.popovic@lioraenergia.com.br':'Nicola Popovic',
 'nha.negocios@gmail.com':'Anderson Correia',
 'mecenas.junior@lioraenergia.com.br':'Mecenas Junior',
 'adroaldo.bonfim@lioraenergia.com.br':'Adroaldo Bonfim','ananias.neto@lioraenergia.com.br':'Ananias Neto',
 'antonio.mariano@lioraenergia.com.br':'Antonio Mariano','bruno.andrade@lioraenergia.com.br':'Bruno Andrade',
 'bruno.borges@lioraenergia.com.br':'Bruno Borges','caio.lannes@lioraenergia.com.br':'Caio Lannes',
 'diego.faria@lioraenergia.com.br':'Diego Faria','ederson.silva@lioraenergia.com.br':'Ederson Silva',
 'ettore.rossi@lioraenergia.com.br':'Ettore Rossi','felipe.oliveira@lioraenergia.com.br':'Felipe Oliveira',
 'franciele.felix@lioraenergia.com.br':'Franciele Felix','kelma.rangel@lioraenergia.com.br':'Kelma Rangel',
 'lucileide.carlos@lioraenergia.com.br':'Lucileide Carlos','marcio.galvao@lioraenergia.com.br':'Marcio Galvão',
 'maria.lucia@lioraenergia.com.br':'Maria Lúcia','neilon.nascimento@lioraenergia.com.br':'Neilon Nascimento',
 'nubia.andrade@lioraenergia.com.br':'Nubia  Andrade','odirley.costa@lioraenergia.com.br':'Odirley Costa',
 'rodrigo.ribeiro@lioraenergia.com.br':'Rodrigo Ribeiro','rosangela.mendes@lioraenergia.com.br':'Rosangela Mendes',
 'ryan.trindade@lioraenergia.com.br':'Ryan Trindade','tais.santos@lioraenergia.com.br':'Tais Santos',
 'tiago.freitas@lioraenergia.com.br':'Tiago Freitas','thiago.araujo@lioraenergia.com.br':'Thiago Araujo França',
}
TITLE2OP = {'Salvador':'salvador','Feira de Santana':'feira','Natal':'natal','SPI':'spi','CE':'ce','Outras':'outras'}

def norm(s): return re.sub(r'\s+',' ',(s or '').strip()).upper()
# CLIENT_OVERRIDE: força vendedor/praça enquanto o suporte não corrige na origem
CLIENT_OVERRIDE = {
 norm('NIVALDO GESTEIRA DE OLIVEIRA'): ('Maria Lúcia','salvador','Salvador'),
 norm('MANOEL ROQUE DA SILVA JUNIOR'): ('Lucileide Carlos','feira','Feira de Santana'),
 norm('CARLA NUNCIA BESERRA'): ('Marcio Galvão','natal','Natal'),  # 2a UC da Carla - é do Marcio (Felipe 26/06)
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

# ---- rawData (deals + aguardando, dedup por deal_id) ---------------------
def mk_deal(r):
    risk = (r['latest_risk_analysis_result'] or '').strip()
    # aprovado conta pela DATA DA ANÁLISE DE RISCO; sem risco (WAITING) usa criação
    d = pdate(r['latest_risk_analysis_created_at']) or pdate(r['deal_created_at'])
    return {
      'c': r['current_client_name'],
      's': seller_of(r['sales_person_email'], r['current_client_name']),
      'op': op_of(r['sales_person_email'], r['current_client_name']),
      'risk': risk,
      'mwh': fnum(r['current_consumption_filled']),
      'stage': r['deal_stage'],
      'status': r['ops_tt_status'] or 'N/A',
      'idle': int(fnum(r['idle_days'])),
      'city': r['current_client_city'],
      'semana': semana(d),
      'lost_at': r['deal_lost_at'] or '',
      'lost_reason': r['deal_lost_reason'] or '',
      'motivo': (('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else (r.get('latest_risk_analysis_comments') or '').strip()),
      'docs': DOCS.get((r.get('latest_contract_id') or '').strip(),''),
      'date': d or '',
    }
seen = set(); rawData = []
for r in deals + agu:                 # aguardando entra como deals extras
    did = r['deal_id']
    if did in seen: continue           # dedup por deal_id (clientes multi-UC)
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
      'consumption_mwh': fnum(r['current_consumption_filled']),
      'current_client_name': r['current_client_name'],
      'current_client_state': r['current_client_state'],
      'deal_stage': r['deal_stage'],
      'accepted_proposal': (r['accepted_proposal'] or '').strip().lower() == 'true',
      'praca': praca_of(r['sales_person_email'], r['current_client_name']),
      'det': {
        'CNPJ': r['current_client_cnpj'], 'CPF': r['current_client_cpf'],
        'Telefone': r['client_phone_number'], 'Cidade': r['current_client_city'],
        'Distribuidora': r['distributor_short_name'], 'Campanha': r['origin_campaign'],
        'Origem': r['origin_source'], 'Classificação': r['internal_sales_classification'],
        'Time': r['sales_team'], 'Canal': r['sales_channel_name'],
        'E-mail vendedor': r['sales_person_email'], 'Proposta ID': r['proposal_id'],
      },
    })

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
