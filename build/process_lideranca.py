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
INJECT_DEALS = []  # 25/08: Marli Merces (f8ba2c6d) e Chesser 2a UC (e607c712) ja estao na gold
                   # viva com risco APPROVED -> o inject virava DUPLICATA no desktop
                   # (deals + INJECT_DEALS nao deduplica). Removidos conforme o proprio
                   # comentario original ("remover quando card818 refletir").
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
 'olavocavalcanti@lioraenergia.com.br':'RN Interior','olavo.cavaldanti@lioraenergia.com.br':'RN Interior','francisco.oliveira@lioraenergia.com.br':'RN Interior','paulo.lima@lioraenergia.com.br':'Ribeirao',  # novos 24/08 (Olavo Cavalcanti - Mossoro/RN Interior; Paulo Lima - Ribeirao)
}
EMAIL2NAME = {  # email -> nome canônico do vendedor (resolve nomes variáveis do CRM)
 'silmara.gomes@lioraenergia.com.br':'Silmara Gomes',
 'briel.barbosa@lioraenergia.com.br':'Briel Barbosa','olimpio.filho@lioraenergia.com.br':'Olímpio Filho','fabio.rodrigues@lioraenergia.com.br':'Fábio Rodrigues',  # novos 10/08
 'karianine.sampaio@lioraenergia.com.br':'Karianine Sampaio',  # nova 18/08 (CRM manda 'karianine Sampaio' minusculo)
 'olavocavalcanti@lioraenergia.com.br':'Olavo Cavalcanti','olavo.cavaldanti@lioraenergia.com.br':'Olavo Cavalcanti','francisco.oliveira@lioraenergia.com.br':'Doni Oliveira','paulo.lima@lioraenergia.com.br':'Paulo Lima',  # novos 24/08 (Olavo Cavalcanti - Mossoro/RN Interior; Paulo Lima - Ribeirao)
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
# FORCE_DENIED: deals que NAO contam como aprovado por decisao manual, mesmo com risco
# APPROVED_PENDING_CREDIT / credito 'approved'. Nasceu da Dileuda (25/08): cliente
# desistiu, o Antecipa nunca foi pago (credit_stage parado em GATHERING_DEPOSIT_
# INFORMATION) e o credito_ok passava na frente do teste de perdido em 2 dos 4
# isAprovado() do desktop e no do mobile. Efeito: zera _apc/credito_ok, marca risco
# DENIED e MANTEM o stage real (BGC_PARCEIRO), entao o cliente cai como negado em
# todas as telas. Chave = deal_id.
FORCE_DENIED = {
  '77a56fa5-9c4e-476c-b71d-ac08534d6745',  # DILEUDA CORINGA DA FONSECA DA SILVA (Antecipa PF, Thiago Macillo/Natal RN, 0.49 MWh) - desistiu; perdido 13/08 na base; era FORCE_APPROVED e o Felipe liberou considerar reprovada (25/08)
}
FORCE_APPROVED = {
                  'b3caa8ce-9553-4bd6-ab3f-9559420cb24e': '2026-09-04',  # AMANDA MARCONDES (Antecipa PJ, Briel Barbosa/Campinas SPI, 1.921 MWh) - SCHEDULED_TITULARIDADE + contrato assinado 03/09; risco MANUAL sem carimbo. Aprovado manual a pedido do Felipe 04/09. ATENCAO: existe deal GD irmao 6943dfcb (LIORA_B_, mesma cliente, mesmos 1.921 MWh) em SIGNING CONTRACT - se aquele aprovar, vira DUPLO COMPUTO; remover um dos dois.
                  '1e11931c-3e99-48f4-a338-47d734012625': '2026-08-20',  # FRANCISCO DAS CHAGAS CUNHA SILVA / 33050196000188 (Antecipa PJ, Olimpio Filho/Ribeirao, 0.916 MWh) - reaprovado 20/08 (lag de ingestao). ATENCAO: o risco RE-REPROVOU o deal em 21/08 14:04 ('Reprovado na analise de risco', lost + BGC_PARCEIRO) e o risk_real confirma DENIED; Felipe 21/08 mandou MANTER como aprovado mesmo assim. Nao remover sem falar com ele.
                  'cfb2500c-c323-4943-a7f8-e831a8f37b55': '2026-08-04',  # PP FERREIRA DE SALES COMER DE COSMETICOS - aprovado manual SOS 15:32 04/08 (Aurivando/CE); card818+risk_real ainda MANUAL; remover quando base refletir
                  'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': '2026-08-12',  # ISMAEL RODRIGUES SILVA (Antecipa PF, Phillip Faria/Ribeirao SPI) - aprovado manual (Felipe 12/08); base risco MANUAL; remover quando base refletir
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
                  # Felipe 01/09 (00h30): 5 aprovacoes manuais do fechamento de agosto, todas carimbadas 31/08 a pedido dele.
                  'fe00362b-896b-40f7-86cc-7a24d444de58': '2026-08-31',  # MARIA LUISA DA SILVA DE ASSIS (Antecipa PF, Olimpio Filho/Ribeirao, 0.221 MWh) - risco DENIED 31/08 22:14 (fatura ilegivel, 3 devolutivas) + lost_at; Felipe mandou contar. NAO remover sem falar com ele.
                  '8ba12fdb-f575-4bff-a843-cd29175536b2': '2026-08-31',  # ROBERTO MACARIO JUNIOR (Antecipa PJ, Paulo Lima/Ribeirao, 11.274 MWh) - APPROVED_PENDING_CREDIT 26/08 mas credit_stage PAYMENT_REJECTED (apc_ok barra); remover quando o pagamento entrar
                  'c8815842-0a4e-4b24-8a65-405fa9c3fa90': '2026-08-31',  # ARTHUR BORGES VEIGA (Antecipa PJ, Paulo Lima/Ribeirao, 4.493 MWh) - APPROVED_PENDING_CREDIT 27/08 mas credit_stage CREDIT_ANALISYS_REJECTED (apc_ok barra); remover quando o credito entrar
                  '05e5601a-7865-4320-a523-b76169b41e91': '2026-08-31',  # MG E CB ALIMENTOS LTDA (GD LIORA_B_, Diego Faria/SPI Campinas, 5.236 MWh) - SCHEDULED_TITULARIDADE com risco ainda MANUAL; remover quando a base refletir
                  '6f69c433-a8d8-40f2-9b8a-6988f2c07e3e': '2026-08-31',  # FAB ALIMENTOS EIRELI (GD LIORA_B_, Diego Faria/SPI Campinas, 3.080 MWh) - SCHEDULED_TITULARIDADE com risco ainda MANUAL; remover quando a base refletir
                  }  # ALEXANDRE ZANETI ARANTES (Antecipa PJ, Karianine Sampaio/Ribeirao, 0.871 MWh) - risco APPROVED 20/08 01:14

# ---- DATA DA VENDA = APROVACAO NO RISCO (Felipe 25/08) --------------------
# O Antecipa gera uma SEGUNDA analise de risco APPROVED quando o CREDITO e' pago,
# dias depois do APPROVED_PENDING_CREDIT que ja aprovou a venda. Como a data vem de
# latest_risk_analysis_created_at (a analise mais nova), a venda pulava para a semana
# do PAGAMENTO e o vendedor era pago DE NOVO por um cliente ja pago na semana anterior
# (relato do Joao 25/08: Diogenes e Bruna do Fabio, risco 22/08, reapareceram em 24/08).
# Regra: vale o inicio da sequencia aprovadora (analise mais antiga a partir da qual
# todas aprovaram). Deal reprovado e reaprovado depois usa a reaprovacao.
#
# TRES CAMADAS, nesta ordem de forca (FORCE_APPROVED ganha de todas):
#  1. mapa abaixo - os 35 deals de agosto apurados na liora_silver.risk_analysis (25/08).
#     Pode ser esvaziado na virada do mes.
#  2. LEDGER (PREV_APROV, logo abaixo) - a data de uma venda ja publicada como aprovada
#     nunca anda para FRENTE. Cobre os casos novos sozinho, sem depender de export.
#  3. slice - coluna appr_created do risk_real.csv (RISK_SQL em build/mb_export.py),
#     que recarimba latest_risk_analysis_created_at. E' a camada exata; depende de a
#     query do export trazer a coluna nova.
RISK_APPR_DATE = {
 '309da0a1-7653-4c00-8cd5-49c6217f55a4': '2026-08-03',  # Clinica Ts Health LTDA (Bruno Borges, LIORA_B_ - GD, nao Antecipa) - risco 03/08 17:28, 2a analise 04/08 14:25
 '41e3cca5-5417-4a81-af4f-28bc8ee70c5d': '2026-08-05',  # DANIELE LUZ DE ALMEIDA (Luciana Sobral, ANTECIPA PF) - risco 05/08 18:13, credito pago 07/08 14:34
 'f0a1f2b4-0601-4c35-9ef4-92c2087f2202': '2026-08-05',  # THAIS DA SILVA DANIEL (Odirley Costa, ANTECIPA PF) - risco 05/08 13:16, credito pago 07/08 14:30
 '631969e6-b404-4a74-b6a8-9a258df0fa43': '2026-08-06',  # JURACI CARLOS DE FRANCA (Ederson Silva, ANTECIPA PF) - risco 06/08 14:20, credito pago 11/08 13:58
 '269e9609-8761-42a3-a979-f63b0ddb7886': '2026-08-06',  # KELY ROSA DA SILVA (Ederson Silva, ANTECIPA PF) - risco 06/08 14:59, credito pago 10/08 07:53
 'ac6472e0-eee1-4423-9a4b-662a6d0bc06c': '2026-08-06',  # LEANDRO GABRIEL DA SILVA DE CARVALHO (Ederson Silva, ANTECIPA PF) - risco 06/08 14:15, credito pago 12/08 14:32
 '22e0278a-2068-4f35-ace0-27eec743c332': '2026-08-06',  # LUZIANA RIBEIRO SALES (Ederson Silva, ANTECIPA PF) - risco 06/08 15:18, credito pago 19/08 09:33
 '54fa2b2a-7b2c-49f4-b98e-36bc523a6be3': '2026-08-08',  # Francisco Jairo Rodrigues (Neilon Nascimento, ANTECIPA PF) - risco 08/08 14:38, credito pago 11/08 13:53
 '83bf2289-52be-43e8-bd76-a1b8e9c9e734': '2026-08-10',  # DGN STORE & ESTACIONAMENTO (Percy Hormazabal, ANTECIPA PJ) - risco 10/08 19:00, credito pago 12/08 14:26
 '42d73385-cf0f-4a56-bdb6-0d81161087f2': '2026-08-11',  # Maiza pereira da Silva (Bruno Borges, ANTECIPA PF) - risco 11/08 12:10, credito pago 12/08 10:34
 'ceb1e43b-54f4-419a-8278-6b0b300300e1': '2026-08-12',  # ANTONIO MORENO (Ederson Silva, ANTECIPA PF) - risco 12/08 14:06, credito pago 20/08 19:09
 'e70a63ca-e4ee-4ad5-af68-433548b49305': '2026-08-12',  # MARINA DA SILVA (Ederson Silva, ANTECIPA PF) - risco 12/08 17:12, credito pago 14/08 14:06
 'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': '2026-08-12',  # ISMAEL RODRIGUES SILVA (Phillip Faria, ANTECIPA PF) - risco 12/08 15:42, credito pago 14/08 14:10
 '1d00bb47-a942-4407-8216-98df676b41e9': '2026-08-13',  # ALESSANDRA DELFINO (Phillip Faria, ANTECIPA PF) - risco 13/08 14:05, credito pago 14/08 20:02
 'b4e7eacc-8dc9-445e-9a37-d83cb3ecff80': '2026-08-13',  # DANILO FERREIRA DE LACERDA (Fabio Rodrigues, ANTECIPA PF) - risco 13/08 12:15, credito pago 14/08 19:58
 '7078748d-07a0-454d-a500-cfdb559b954f': '2026-08-14',  # MARIA DE LOURDES BRITO DA COSTA (Ederson Silva, ANTECIPA PF) - risco 14/08 16:58, credito pago 18/08 13:24
 'dabf7abd-1266-40b0-bb0b-6b593cfca457': '2026-08-15',  # MATEUS BERNARDINO DE MELO (Odirley Costa, ANTECIPA PF) - risco 15/08 11:04, credito pago 18/08 13:18
 '85ca8818-734b-4c32-bbb4-635d4d9493f2': '2026-08-17',  # Eliano Barbosa dos santos (Ederson Silva, ANTECIPA PF) - risco 17/08 13:16, credito pago 18/08 19:07
 '0b97aa9e-2def-45ec-ad98-034573f178a6': '2026-08-17',  # Jonas Emer Coquely (Olimpio Filho, ANTECIPA PJ) - risco 17/08 17:13, credito pago 18/08 19:12
 '25611c90-3b9b-4b2f-a42e-41d22dcebd7a': '2026-08-17',  # Thais Cristina Flosino (Olimpio Filho, ANTECIPA PJ) - risco 17/08 16:30, credito pago 24/08 12:26
 '2b4ac293-dd90-4926-b56f-f31d43f7ac8b': '2026-08-17',  # Acougue Polegatto Ltda (Joao Felipe, ANTECIPA PJ) - risco 17/08 13:40, credito pago 18/08 19:24
 '3f157076-50ad-4108-b71d-b70527a45887': '2026-08-18',  # Nelo Minghe Neto (2a UC) (Fabio Rodrigues, ANTECIPA PJ) - risco 18/08 17:40, credito pago 20/08 18:57
 'e6aae19f-6a23-4b53-9b72-7c5121d03a69': '2026-08-18',  # VICTOR HUGO GOULART DA SILVA (Olimpio Filho, ANTECIPA PF) - risco 18/08 18:08, credito pago 20/08 18:51
 '18a28a63-cd00-4bde-97e0-f04151fe5a2d': '2026-08-18',  # Nelo Minghe Neto (Fabio Rodrigues, ANTECIPA PJ) - risco 18/08 17:46, credito pago 20/08 00:47
 '67505be8-e7a4-496f-a8e3-a711909fa2fc': '2026-08-19',  # Alexandre Zaneti Arantes (Karianine Sampaio, ANTECIPA PJ) - risco 19/08 13:57, credito pago 20/08 01:14
 '2a50c11b-55c8-4f23-810f-438c71f90696': '2026-08-19',  # ROSEMEIRE DIAS DE ALMEIDA (Ettore Rossi, ANTECIPA PF) - risco 19/08 09:33, credito pago 20/08 00:23
 'b43f455a-0b07-455f-83b6-8558186432d2': '2026-08-19',  # DANIELA CAMPOS AMARAL (Ederson Silva, ANTECIPA PF) - risco 19/08 18:17, credito pago 24/08 12:08
 '77a74bf3-4cb4-427e-9548-8be61dac8f85': '2026-08-19',  # VALDENIA AMARO MARTINS (Odirley Costa, ANTECIPA PF) - risco 19/08 17:40, credito pago 20/08 18:47
 '0dadf9d4-4e2a-44aa-94f3-feb2236c0e15': '2026-08-20',  # DEIVID MARCIEL DA SILVA SAMPAIO (Karianine Sampaio, ANTECIPA PF) - risco 20/08 16:00, credito pago 24/08 11:38
 '5a3e3021-b5d2-482a-ac49-fd720f76beb0': '2026-08-20',  # MARCELO BRAZ DA SILVA (Ederson Silva, ANTECIPA PF) - risco 20/08 19:09, credito pago 24/08 11:30
 '81b409e1-1596-47f5-aaa8-1ea27d44c58a': '2026-08-20',  # Emile Raylane dos Santos silva (Tamires Costa, ANTECIPA PF) - risco 20/08 18:47, credito pago 24/08 11:50
 '4e4fdd43-0a52-4199-9a21-1ce4de5d06b5': '2026-08-20',  # JOSE PAULO APARECIDO CORREIA (Karianine Sampaio, ANTECIPA PF) - risco 20/08 16:55, credito pago 24/08 11:56
 '7a7e8fed-a442-42be-9d33-6e99c1a63e2b': '2026-08-21',  # VANESSA PAULA GOMES DA SILVA (Lucas Santos, ANTECIPA PF) - risco 21/08 13:20, credito pago 24/08 11:19
 '98d40580-78bd-4a62-b1d1-7bf346c549a0': '2026-08-22',  # Bruna Helena Nunes de lacerda (Fabio Rodrigues, ANTECIPA PJ) - risco 22/08 18:05, credito pago 24/08 22:03
 'ec28eba4-c245-4807-bcef-c4722c0197b9': '2026-08-22',  # DIOGENES DE FIGUEIREDO LIMA JUNIOR (Fabio Rodrigues, ANTECIPA PF) - risco 22/08 16:26, credito pago 24/08 21:57
}

# ---- LEDGER: venda aprovada nao muda de dia (Felipe 25/08) ---------------
# Le o rawData do mobile JA PUBLICADO (../mobile/index.html deste mesmo repo clonado)
# e guarda deal_id -> aprov_date. Se a venda ja estava aprovada num dia, esse dia manda:
# a reaprovacao de risco que o Antecipa gera no pagamento do credito nao muda mais a
# semana da venda. Como o rebuild publica a cada ~2h, a aprovacao original (APPROVED_
# PENDING_CREDIT) sempre e' capturada dias antes do pagamento. So anda para TRAS.
# Fail-safe: sem arquivo/sem match -> {} e nada muda. Escape hatch: FORCE_APPROVED.
def _load_prev_aprov():
    import os as _os, re as _re, json as _json, sys as _sys
    p = _os.environ.get('PREV_MOBILE') or _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), '..', 'mobile', 'index.html')
    try:
        t = open(p, encoding='utf-8').read()
        m = _re.search(r'const rawData\s*=\s*(\[.*?\]);', t, _re.S)
        if not m:
            return {}
        out = {}
        for r in _json.loads(m.group(1)):
            did = (r.get('deal_id') or '').strip()
            a = (r.get('aprov_date') or '').strip()
            if did and a:
                out[did] = a[:10]
        print('ledger de datas: %d aprovado(s) no publicado (%s)'
              % (len(out), _os.path.basename(p)))
        return out
    except Exception as _e:
        print('aviso ledger de datas:', _e, file=_sys.stderr)
        return {}
PREV_APROV = _load_prev_aprov()

def _mesma_semana_paga(a, b):
    # True se as duas datas caem no mesmo mes E na mesma semana de campanha.
    a = (a or '')[:10]; b = (b or '')[:10]
    if len(a) < 10 or len(b) < 10 or a[:7] != b[:7]:
        return False
    return semana(a) == semana(b)


def appr_date_of(deal_id, calc, aprovado=True):
    """Data de aprovacao final: mapa > ledger > calculada.

    O ledger (25/08) segura a data para TRAS. Excecao aberta em 02/09 para a regra
    da aprovacao do CREDITO (ver apply_credit_date no slice): a data PODE andar
    para frente quando o destino cai no MESMO mes e na MESMA semana ja publicada -
    ai o dia no card fica correto e o PAGAMENTO nao muda de semana. Se o passo
    cruzaria a fronteira da semana (ou do mes), o ledger continua mandando: venda
    ja paga numa semana nao migra para a seguinte.
    """
    fix = RISK_APPR_DATE.get(deal_id)
    d = fix or (calc or '')
    if aprovado:
        prev = PREV_APROV.get(deal_id) or ''
        if prev and (not d or prev < d):
            if not (d and _mesma_semana_paga(prev, d)):
                d = prev
    return d or ''

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
# Felipe 25/08 (final): a lista e' INVERTIDA de proposito. So estes motivos DESFAZEM a
# venda aprovada: o cliente desistiu, ou o credito foi reprovado. Todo o resto mantem o
# aprovado. 'UC Desligada' (16 clientes / 30,77 MWh em agosto) NAO e' reprovacao: e' o
# canal de Ops que nao consegue avancar com a titularidade porque a UC esta desligada -
# a venda foi aprovada no risco e continua valendo. Idem 'Telefone incorreto',
# 'Baixa Renda / NIS', 'placa solar'. Risco DENIED e credito negado ja caem nos testes
# proprios, sem depender do motivo da perda.
LOST_DESFAZ = {'cliente desistiu', 'reprovado na análise de crédito'}

def apc_ok(r):
    """True quando o risco e' APPROVED_PENDING_CREDIT e o credito NAO foi negado."""
    if (r.get('latest_risk_analysis_result') or '').strip() != 'APPROVED_PENDING_CREDIT':
        return False
    if (r.get('latest_credit_analysis_result') or '').strip().lower() in CREDIT_NEG:
        return False
    if (r.get('deal_credit_stage') or '').strip() in CREDIT_STAGE_NEG:
        return False
    return True

# ---- CALIBRACAO ANTECIPA: risco E credito (Felipe 01/09/2026) -------------
# Ate 31/08 bastava UMA das duas analises para o Antecipa contar como aprovado
# (credito 'approved' sozinho, ou risco APPROVED sozinho). Isso deixava passar
# tres casos errados, todos conferidos na gold antes da mudanca:
#   - SONIA REGINA SPACASSASSI (27/07) risco DENIED + credito approved -> contava
#   - Larissa Cecilia Sampaio (16/07) risco APPROVED + credito denied  -> contava
#   - LUIS CLAUDIO SANTOS MARQUES ME e JOAO DA SILVA (30/06) risco APPROVED
#     sem NENHUMA analise de credito -> contavam (15,82 MWh)
# Regra nova (decisao do Felipe 01/09, sem excecao para credito ausente):
#   Antecipa so e' aprovado quando risco in (APPROVED, APPROVED_PENDING_CREDIT)
#   E credito == 'approved'. Etapa de credito rejeitada/pagamento rejeitado
#   continua barrando (era o que o apc_ok ja fazia).
# NAO afeta GD: o gate so roda quando o produto e' ANTECIPA.
# A excecao continua sendo o FORCE_APPROVED manual, aplicado depois.
# Agosto/26 fecha igual nas duas regras: 74 deals / 69,385 MWh.
ANT_RISK_OK = {'APPROVED', 'APPROVED_PENDING_CREDIT'}
# UNICA excecao ao gate (Felipe 01/09): deal que JA MIGROU nao e' bloqueado. Venda
# entregue e' venda entregue, mesmo sem registro de analise de credito na base.
# Caso que motivou: LUIS CLAUDIO SANTOS MARQUES ME (Lucas Danielian, 30/06, 15,402
# MWh) - ACTIVE MEMBER + ops APROVADO + risco APPROVED, zero analise de credito.
ANT_MIGRADO_STAGES = {'ACTIVE_MEMBER', 'ACTIVE MEMBER', 'TITULARIDADE_ONGOING',
                      'TITULARIDADE ONGOING', 'REGISTERING_DG'}

def ant_migrado(r):
    """Deal que ja chegou na titularidade/migracao: o gate do Antecipa nao se aplica."""
    if (r.get('deal_stage') or '').strip().upper() in ANT_MIGRADO_STAGES:
        return True
    return 'aprovado' in (r.get('ops_tt_status') or '').strip().lower()

def is_antecipa(r):
    """Produto Antecipa (respeita o PRODUCT_OVERRIDE de venda registrada errado)."""
    _ov = PRODUCT_OVERRIDE.get((r.get('deal_id') or '').strip(), {})
    prod = _ov.get('produto') or (r.get('product_name') or '')
    return 'ANTECIPA' in prod.strip().upper()

def ant_ok(r, credito_ok=None):
    """Antecipa aprovado. Risco APPROVED exige credito 'approved'; APPROVED_PENDING_
    CREDIT conta a partir da aprovacao no RISCO (Felipe 03/09)."""
    _risk = (r.get('latest_risk_analysis_result') or '').strip()
    if _risk not in ANT_RISK_OK:
        return False
    # APPROVED_PENDING_CREDIT: conta ja na aprovacao do risco, sem esperar a analise
    # de credito (Felipe 03/09). Motivo: a venda que o risco aprova as 17h so
    # aparecia no dia seguinte, quando o credito era analisado. Credito NEGADO (ou
    # etapa de credito/pagamento rejeitada) continua barrando - e' o apc_ok.
    # Caso que delimita a regra: Rodrigo Henrique da Silva (Ederson, 0,245 MWh) -
    # risco APPROVED_PENDING_CREDIT 01/09 17:05, credito DENIED 02/09 10:35
    # (score 208, 'historico crescente de debitos') -> NAO conta.
    # Os 3 furos fechados em 01/09 seguem fechados: risco DENIED + credito approved
    # cai no ANT_RISK_OK; risco APPROVED sem nenhuma analise de credito continua
    # exigindo credito 'approved' logo abaixo.
    if _risk == 'APPROVED_PENDING_CREDIT':
        _ov = PRODUCT_OVERRIDE.get((r.get('deal_id') or '').strip(), {})
        if _ov.get('credito_ok') is False:
            return False
        return apc_ok(r)
    if credito_ok is None:
        credito_ok = (r.get('latest_credit_analysis_result') or '').strip().lower() == 'approved'
    if not credito_ok:
        return False
    if (r.get('deal_credit_stage') or '').strip() in CREDIT_STAGE_NEG:
        return False
    return True


# FORCE_NOTE: nota que aparece no card do cliente forcado (Felipe 01/09: "considerado
# no card, mas cliente reprovado e o motivo"). Prefixa o campo 'motivo' do rawData —
# o card do desktop e a aba de detalhe do mobile imprimem esse campo. Chave = deal_id.
FORCE_NOTE = {
  'b3caa8ce-9553-4bd6-ab3f-9559420cb24e': 'ℹ️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 04/09) — titularidade agendada e contrato assinado em 03/09; o risco ainda esta em analise MANUAL na base (carimbo 04/09 11:25), sem carimbo de aprovacao.',
  'fe00362b-896b-40f7-86cc-7a24d444de58': '⚠️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 01/09) — cliente REPROVADO na analise de risco em 31/08: faturas vencidas 29/07 e 26/08, e antes o analista devolveu 3x pedindo fatura legivel.',
  '8ba12fdb-f575-4bff-a843-cd29175536b2': '⚠️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 01/09) — Antecipa com PAGAMENTO REJEITADO na base; o risco aprovou pendente de credito em 26/08.',
  'c8815842-0a4e-4b24-8a65-405fa9c3fa90': '⚠️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 01/09) — ANALISE DE CREDITO REPROVADA na base; o risco aprovou pendente de credito em 27/08.',
  '05e5601a-7865-4320-a523-b76169b41e91': 'ℹ️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 01/09) — titularidade agendada, risco ainda sem carimbo (MANUAL) na base.',
  '6f69c433-a8d8-40f2-9b8a-6988f2c07e3e': 'ℹ️ CONSIDERADO APROVADO NO CARD (decisao do Felipe 01/09) — titularidade agendada, risco ainda sem carimbo (MANUAL) na base.',
}
def force_note(did, txt):
    """Prefixa a nota do aprovado manual no motivo, preservando o texto original."""
    n = FORCE_NOTE.get((did or '').strip())
    if not n: return txt
    t = (txt or '').strip()
    return (n + ' | ' + t) if t else n

# ---- rawData (deals + aguardando, dedup por deal_id) ---------------------
def mk_deal(r):
    risk = (r['latest_risk_analysis_result'] or '').strip()
    _apc = apc_ok(r)  # Felipe 18/08: risco aprovado pendente de crédito já conta
    if r['deal_stage']=='BGC_PARCEIRO' and not _apc: risk=''  # em validação Antecipa: não conta como aprovado
    credit = (r.get('latest_credit_analysis_result') or '').strip().lower()  # Antecipa
    _ov0 = PRODUCT_OVERRIDE.get((r.get('deal_id') or '').strip(), {})  # venda Antecipa registrada com produto errado
    credito_ok = _ov0.get('credito_ok', credit == 'approved')
    if r['deal_id'] in FORCE_DENIED: _apc=False; credito_ok=False  # reprovado manual (Felipe)
    # Felipe 01/09: Antecipa so conta com as DUAS analises aprovadas (ver ant_ok).
    _ant_bloq = (is_antecipa(r) and not ant_ok(r, credito_ok)
                 and not ant_migrado(r)  # migrado nunca e' bloqueado
                 and r['deal_id'] not in FORCE_APPROVED)
    if _ant_bloq:
        _apc = False; credito_ok = False
        if risk == 'APPROVED': risk = ''  # risco aprovado sem credito approved nao conta
    if _apc: risk='APPROVED'  # Felipe 18/08: APPROVED_PENDING_CREDIT = aprovado (falta só o pagamento)
    if credito_ok: risk='APPROVED'  # Felipe 06/08: crédito aprovado (Antecipa) conta como aprovado no Field
    if r['deal_id'] in FORCE_APPROVED: risk='APPROVED'  # aprovado manual
    if r['deal_id'] in FORCE_DENIED: risk='DENIED'  # reprovado manual (Felipe): ganha de tudo
    # aprovado conta pela DATA DA ANÁLISE DE RISCO; sem risco (WAITING) usa criação
    # a data da APROVACAO NO RISCO manda na analise mais nova (que no Antecipa e' a do
    # pagamento do credito) - ver RISK_APPR_DATE acima (Felipe 25/08)
    d = (appr_date_of(r['deal_id'], pdate(r['latest_risk_analysis_created_at']), risk == 'APPROVED')
         or pdate(r['deal_created_at']))
    if r['deal_id'] in FORCE_APPROVED and FORCE_APPROVED[r['deal_id']]: d = FORCE_APPROVED[r['deal_id']]  # data de aprovação manual
    forced = r['deal_id'] in FORCE_APPROVED
    # o isAprovado() do HTML descarta BGC_PARCEIRO ANTES de olhar o risco, entao o
    # aprovado-pendente-de-credito precisa sair do estagio de validacao (mesmo
    # tratamento que o FORCE_APPROVED ja fazia na mao para esses mesmos clientes).
    out_stage = 'REQUEST_TITULARIDADE' if ((forced or _apc) and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']
    _prod_ov = PRODUCT_OVERRIDE.get((r.get('deal_id') or '').strip(), {})  # venda Antecipa registrada com produto errado (Felipe 18/08)
    return {
      'c': r['current_client_name'],
      'sig': (r.get('signer_name') or '').strip(),  # quem assinou, so quando e' outra pessoa (Felipe 27/08)
      's': seller_of(r['sales_person_email'], r['current_client_name']),
      'op': op_of(r['sales_person_email'], r['current_client_name']),
      'risk': risk,
      'mwh': mwh_of(r['current_client_name'], r['current_consumption_filled'], r['deal_id']),
      'stage': out_stage,
      'status': r['ops_tt_status'] or 'N/A',
      'idle': int(fnum(r['idle_days'])),
      'city': r['current_client_city'],
      'produto': _prod_ov.get('produto', (r.get('product_name') or '').strip()),
      'credito_ok': (False if _ant_bloq else _prod_ov.get('credito_ok', credito_ok)),  # Antecipa: análise de crédito aprovada (Felipe 06/08)
      'ant_bloq': bool(_ant_bloq),  # Antecipa sem as DUAS análises aprovadas: nunca conta (Felipe 01/09)
      'apc': bool(_apc),  # aprovado no risco, pendente de crédito/pagamento (Felipe 18/08)
      'fapr': bool(forced),  # aprovado manual (FORCE_APPROVED) - alimenta a quebra do card
      'rapr': (r['latest_risk_analysis_result'] or '').strip()=='APPROVED',  # risco APPROVED na base (quebra do card)
      'credito': credit_pt(r.get('deal_credit_stage')),  # situação do Antecipa (PT)
      'semana': semana(d),
      'lost_at': ('' if (forced or norm(r['current_client_name']) in LOST_IGNORE) else (r['deal_lost_at'] or '')),
      'lost_reason': ('' if (forced or norm(r['current_client_name']) in LOST_IGNORE) else (r['deal_lost_reason'] or '')),
      'motivo': force_note(r.get('deal_id'), (('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else (r.get('latest_risk_analysis_comments') or '').strip())),
      'docs': DOCS.get((r.get('latest_contract_id') or '').strip(),''),
      'uc': UC.get(r['deal_id'],''),
      'date': d or '',
    }
# SO NO CRM MOBILE (Felipe 02/09): deal que o slice liberou via CREDIT_DATE_FORCE
# para o vendedor ver a venda, mas que NAO pode entrar no dash de lideres nem no
# fechamento - a venda ja foi contada e paga no mes anterior. Excecao consciente a
# regra "todo override vai nos dois dashboards" (Felipe 07/08): aqui a assimetria e'
# o objetivo, e' ela que evita o pagamento em duplicidade.
SO_MOBILE_DEALS = {
    # Traumasport 0,555 MWh (Bruno Borges, Antecipa PJ). Ja entrou nos aprovados de
    # agosto (build b37fd7f, semana S13): o Bruno fechou agosto com 12,004 MWh, o
    # "12" da planilha de fechamento; sem esse cliente daria 11,449.
    '31d7d3d6-b51f-4af5-81b7-1cc6f325268e',
}

seen = set(); rawData = []
for r in deals + agu:                 # aguardando entra como deals extras
    did = r['deal_id']
    if did in seen: continue           # dedup por deal_id (clientes multi-UC)
    if did in SO_MOBILE_DEALS: continue  # aparece so no CRM mobile - ver acima
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
      'sig': (r.get('signer_name') or '').strip(),
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
        _adate = FORCE_APPROVED.get(_did) or appr_date_of(_did, pdate(r.get('latest_risk_analysis_created_at'))) or (d or '')
        ANTECIPA.append({
          'c': _cli,
          'sig': (r.get('signer_name') or '').strip(),
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
          # Felipe 25/08: perdido nunca conta -> vira 'PERDIDO' (nunca 'APPROVED'), o que
          # tira o cliente do KPI Aprovadas da aba E da campanha (MISSAO filtra risk=='APPROVED').
          # ANT_APPROVE/FORCE_APPROVED continuam ganhando (decisao manual do Felipe).
          'risk': ('APPROVED' if (_did in ANT_APPROVE or _did in FORCE_APPROVED)
                   else ('PERDIDO' if ((r.get('deal_lost_at') or '').strip()
                                       and (r.get('deal_lost_reason') or '').strip().lower() in LOST_DESFAZ)
                   else ('APPROVED' if ant_ok(r)
                         else (r.get('latest_risk_analysis_result') or '').strip()))),  # Felipe 01/09: risco E crédito (era apc_ok OU crédito)
          'credito': ('approved' if _did in ANT_APPROVE else (r.get('latest_credit_analysis_result') or '').strip()),
          'tipo': _ant_tipo(r.get('product_name')),
          # obs = observacao da analise de risco (Felipe 21/08): da visibilidade
          # ao time do que travou o cliente (fatura vencida, baixa_renda, etc).
          'obs': force_note(_did, clean_obs(r.get('latest_risk_analysis_comments'))),
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

# ---- MISSAO: campanha "Semana do Antecipa" (24-31/08/2026) ----------------
# Alimenta a aba "Missao" do desktop (restrita a lideres/gestao). Recorte:
# cliente Antecipa do FIELD com analise APROVADA (risco ou credito) e data de
# aprovacao (adate) dentro da janela. A largada valeu de 13/08 (slide "A largada
# e hoje"), a vigencia oficial do material e 17-23/08 -> Felipe optou por 13/08.
MISSAO_INI, MISSAO_FIM = '2026-08-24', '2026-08-31'
MISSAO = [{'s':x['s'], 'praca':x['praca'], 'mwh':x['mwh'], 'c':x['c'], 'tipo':x.get('tipo',''),
           'sig':x.get('sig',''),
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
               'Adroaldo Bonfim','Kelma Rangel','Mirla Albuquerque','Caio Lannes','João Santos','Bruno Borges',
               'Bruno Andrade'}  # desligado 25/08 (Mirla assumiu RN Capital)
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
    # Felipe 25/08: perdido nunca conta (excecao: troca de titularidade). FORCE_APPROVED ganha.
    if (r.get('deal_id') or '').strip() not in FORCE_APPROVED and (r.get('deal_lost_at') or '').strip() \
       and (r.get('deal_lost_reason') or '').strip().lower() in LOST_DESFAZ:
        return False
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
    ANT_FIELD.append({'date':_d or '','adate':(appr_date_of((r.get('deal_id') or '').strip(), pdate(r.get('latest_risk_analysis_created_at'))) or (_d or '')),'praca':_ANT_PRACA_KEY.get(praca_of(_em,_cli),'Outras'),
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
 'olavocavalcanti@lioraenergia.com.br': ('consultor','2026-08-24'),
 'olavo.cavaldanti@lioraenergia.com.br': ('consultor','2026-08-24'),  # Mossoro / RN Interior
 'francisco.oliveira@lioraenergia.com.br': ('consultor','2026-08-31'),  # Doni Oliveira (Francisco/Mossoro - RN Interior) cadastrado 03/09, admissao 31/08
 'paulo.lima@lioraenergia.com.br': ('consultor','2026-08-24'),        # Ribeirao Preto SPI
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
