import csv, json, datetime, re, glob

# ── Documentos pendentes (4o recorte) ─────────────────────
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
        import sys; print('aviso docs:',e,file=sys.stderr)
    return d

# ── Maps canônicos ──
EMAIL_NOME = {
 'silmara.gomes@lioraenergia.com.br':'Silmara Gomes',
 'luciana.campos@lioraenergia.com.br':'Luciana Campos',
 'nicola.popovic@lioraenergia.com.br':'Nicola Popovic',
 'nha.negocios@gmail.com':'Anderson Correia',
 'anderson.correia@lioraenergia.com.br':'Anderson Correia',
 'percy.hormazabal@lioraenergia.com.br':'Percy Hormazabal',
 'ana.ribeiro@lioraenergia.com.br':'Ana Ribeiro',
 'jose.lima@lioraenergia.com.br':'Rodrigo Lima',
 'jose.monteiro@lioraenergia.com.br':'Rodrigo Lima',  # e-mail novo (14/08)
 'daniel.junior@lioraenergia.com.br':'Daniel Junior',
 'joao.santos@lioraenergia.com.br':'João Santos',
 'mecenas.junior@lioraenergia.com.br':'Mecenas Junior',
 'daniel.magnus@lioraenergia.com.br':'Daniel Magnus',
 'thymacillo@hotmail.com':'Thiago Firmo',  # mesmo vendedor, e-mail alternativo
 'thiago.firmo@lioraenergia.com.br':'Thiago Firmo','silvia.dias@lioraenergia.com.br':'Silvia Dias',
 'kelma.rangel@lioraenergia.com.br':'Kelma Rangel','lucileide.carlos@lioraenergia.com.br':'Lucileide Carlos',
 'rosangela.mendes@lioraenergia.com.br':'Rosangela Mendes','tiago.freitas@lioraenergia.com.br':'Tiago Freitas','tamires.costa@lioraenergia.com.br':'Tamires Costa',
 'ryan.trindade@lioraenergia.com.br':'Ryan Trindade','alberto.nascimento@lioraenergia.com.br':'Alberto Nascimento','marcel.sousa@lioraenergia.com.br':'Marcel Sousa','jefferson.fideli@lioraenergia.com.br':'Jefferson Fideli','phillip.faria@lioraenergia.com.br':'Phillip Faria','bruno.borges@lioraenergia.com.br':'Bruno Borges',
 'neilon.nascimento@lioraenergia.com.br':'Neilon Nascimento','sabrina.tomazeti@lioraenergia.com.br':'Sabrina Tomazeti','odirley.costa@lioraenergia.com.br':'Odirley Costa',
 'nubia.andrade@lioraenergia.com.br':'Núbia Andrade','marcio.galvao@lioraenergia.com.br':'Marcio Galvão',
 'bruno.andrade@lioraenergia.com.br':'Bruno Andrade','rodrigo.ribeiro@lioraenergia.com.br':'Rodrigo Ribeiro',
 'adroaldo.bonfim@lioraenergia.com.br':'Adroaldo Bonfim','ettore.rossi@lioraenergia.com.br':'Ettore Rossi','tatiane.correia@lioraenergia.com.br':'Tatiane Correia',
 'maria.lucia@lioraenergia.com.br':'Maria Lúcia','tais.santos@lioraenergia.com.br':'Tais Santos',
 'antonio.mariano@lioraenergia.com.br':'Antonio Mariano','caio.lannes@lioraenergia.com.br':'Caio Lannes',
 'monica.silveira@lioraenergia.com.br':'Monica Silveira','franciele.felix@lioraenergia.com.br':'Franciele Felix',
 'ederson.silva@lioraenergia.com.br':'Ederson Silva','diego.faria@lioraenergia.com.br':'Diego Faria',
 'briel.barbosa@lioraenergia.com.br':'Briel Barbosa','olimpio.filho@lioraenergia.com.br':'Olímpio Filho','fabio.rodrigues@lioraenergia.com.br':'Fábio Rodrigues', # novos 10/08
 'felipe.oliveira@lioraenergia.com.br':'Felipe Oliveira',
 'mirla.albuquerque@lioraenergia.com.br':'Mirla Albuquerque',
 'lucas.santos@lioraenergia.com.br':'Lucas Santos',
 'ananias.neto@lioraenergia.com.br':'Ananias Neto','ananias.oliveira@lioraenergia.com.br':'Ananias Neto',
 'thiago.araujo@lioraenergia.com.br':'Thiago Araujo França','camila.couto@lioraenergia.com.br':'Camila Couto',
}
NAME_MAP = {  # fallback quando não há email reconhecido (nome cru -> canônico)
 'antonio carlos':'Antonio Mariano','bruno rodrigues':'Bruno Andrade','ananias oliveira':'Ananias Neto',
}
SELLER_PRACA = {  # canônico -> label praça
 'Silmara Gomes':'CE',
 'Luciana Campos':'Salvador',
 'Nicola Popovic':'SPI',
 'Anderson Correia':'SPI',
 'Percy Hormazabal':'SPI',
 'Ana Ribeiro':'SPI',
 'Rodrigo Lima':'SPI',
 'Daniel Junior':'SPI',
 'João Santos':'Ribeirão Preto SPI',
 'Mirla Albuquerque':'RN Interior',
 'Lucas Santos':'RN Interior',
 'Jefferson Fideli':'RN Interior',
 'Phillip Faria':'Ribeirão Preto SPI',
 'Marcel Sousa':'Feira de Santana',
 'Mecenas Junior':'Natal',
 'Daniel Magnus':'Natal',
 'Thiago Firmo':'Natal',
 'Adroaldo Bonfim':'Salvador','Ettore Rossi':'Salvador','Tatiane Correia':'Salvador','Maria Lúcia':'Salvador','Tais Santos':'Salvador','Antonio Mariano':'Salvador','Silvia Dias':'Salvador',
 'Kelma Rangel':'Feira de Santana','Lucileide Carlos':'Feira de Santana','Rosangela Mendes':'Feira de Santana','Tiago Freitas':'Feira de Santana','Ryan Trindade':'Feira de Santana','Alberto Nascimento':'Feira de Santana','Tamires Costa':'Feira de Santana',
 'Bruno Andrade':'Natal','Marcio Galvão':'Natal','Rodrigo Ribeiro':'Natal','Ananias Neto':'Natal','Thiago Araujo França':'Natal','Camila Couto':'Feira de Santana',
 'Caio Lannes':'SPI','Monica Silveira':'SPI','Franciele Felix':'SPI','Ederson Silva':'SPI','Diego Faria':'SPI',
 'Bruno Borges':'CE','Neilon Nascimento':'CE','Sabrina Tomazeti':'CE','Odirley Costa':'CE','Núbia Andrade':'CE',
 'Briel Barbosa':'SPI','Olímpio Filho':'Ribeirão Preto SPI','Fábio Rodrigues':'Ribeirão Preto SPI',  # novos 10/08
 'Felipe Oliveira':'Outros',
}
DIST_MAP = {'NEOENERGIA COELBA':'Coelba','NEOENERGIA COSERN':'Cosern','CPFL PAULISTA':'CPFL','ENEL CE':'Enel'}
# Antecipa / credito (Felipe 06/08): crédito aprovado conta como aprovado no Field;
# deal_credit_stage traduzido p/ português p/ dar contexto da situação do cliente.
CREDIT_STAGE_PT = {
 'GATHERING_DEPOSIT_INFORMATION':'COLETANDO_INFORMAÇÕES_DE_DEPÓSITO',
 'PAYMENT_SUCCEDED':'PAGAMENTO_REALIZADO',
 'CREDIT_ANALISYS_REJECTED':'ANÁLISE_DE_CRÉDITO_REJEITADA',
 'WAITING_CLIENT_CONFIRMATION':'AGUARDANDO_CONFIRMAÇÃO_DO_CLIENTE',
 'WAITING_CLIENT_RESPONSE':'AGUARDANDO_RESPOSTA_DO_CLIENTE',
 'WAITING_PAYMENT_APPROVAL':'AGUARDANDO_APROVAÇÃO_DE_PAGAMENTO',
 'DISPATCH_RECOVERY_COMMS':'ENVIO_DE_COMUNICADOS_DE_RECUPERAÇÃO',
 'PAYMENT_REJECTED':'PAGAMENTO_REJEITADO',
 'PENDING':'PENDENTE',
}
def credit_pt(s):
    s=(s or '').strip()
    return CREDIT_STAGE_PT.get(s, s)
CLIENT_OVERRIDE = {  # cliente (upper/strip) -> (seller canônico, praça label)
 'NIVALDO GESTEIRA DE OLIVEIRA':('Maria Lúcia','Salvador'),
 'MANOEL ROQUE DA SILVA JUNIOR':('Lucileide Carlos','Feira de Santana'),
 'CARLA NUNCIA BESERRA':('Marcio Galvão','Natal'),  # 2a UC da Carla (mesma CPF) - é do Marcio, não do Ederson (Felipe 26/06)
 'MARIA SOARES RODRIGUES':('Rodrigo Ribeiro','Natal'),  # deal do Bruno -> Rodrigo (Felipe 03/07); base ainda nao atualizou
 'VALDEMARINA ALVES NABUCO':('Ettore Rossi','Salvador'),  # deal caiu no Adroaldo -> e do Rossi (Felipe 25/07)
 'NICHOLAS PIETRO RODRIGUES REGINALDO':('Lucas Santos','RN Interior'),  # dono -> Lucas (Felipe 27/07)
 'NATANAEL SILVA DOS SANTOS':('Lucas Santos','RN Interior'),  # dono -> Lucas (Felipe 27/07)
 'MARIA FRAUZINA CAMILO':('Anderson Correia','SPI'),
 'ANA JULIA DA CONCEIÇÃO FREIRE':('Ettore Rossi','Salvador'),  # venda do Rossi lancada na Silvia (Salvador); base ja corrigida mas o card818 ainda mostra Silvia (Felipe 14/08); remover qdo refletir  # aprovado 06/08 do Anderson; base trocou p/ Lucas 07/08 -> volta p/ Anderson (Felipe 07/08); remover qdo base corrigir
}
CONSUMPTION_OVERRIDE_BY_ID = {  # deal_id -> MWh; export do card818 congelou (mostra 0.632; base viva=1.636); remover qdo CI destravar
 '35f26046-9c78-4c2b-a7fe-04f7e7564c38': 1.636,  # Mw Safety Ltda / Joao Santos (Felipe 07/08)
 'a8216055-6fa2-491f-a651-0d70ad461f08': 0.632,  # a8216055 fatura R$47,90; Felipe mantem 0.632 (07/08)
 'd7f9bcce-7145-4bf3-b043-0c12b461bf97': 0.561,  # PAULO HENRIQUE GHIOTTI DA SILVA / Olimpio Filho (Ribeirao) - aprovado 17/08; card818 em cache manda 0.0, gold viva = 0.561 (Felipe 17/08); remover quando a base refletir
}
CONSUMPTION_OVERRIDE = {  # cliente (upper/strip) -> MWh; temp ate base corrigir
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES': 5.86,  # base mostra 0.59 (Felipe 03/07)
 'GABRIEL LUCHIARI ALBERTO': 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 'PERFECTA VIDROS E ALUMINIOS EIRELI': 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 'CHEVROFOR COM PECAS E ACESSORIOS LTDA': 1.21,  # base mostra 0.50 (Felipe 07/07)
 'MÁRCIO PEREIRA PINTO': 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
 'DRAX CENTRO AUTOMOTIVO LTDA': 4.311,
}
FORCE_APPROVED = {'cfb2500c-c323-4943-a7f8-e831a8f37b55': '2026-08-04',  # PP FERREIRA DE SALES COMER DE COSMETICOS - aprovado manual SOS 15:32 04/08 (Aurivando/CE); card818+risk_real ainda MANUAL; remover quando base refletir
                  'f9cf93c9-5348-4586-acdb-5a2b1dd49f60': '2026-08-12',  # ISMAEL RODRIGUES SILVA (Antecipa PF, Phillip Faria/Ribeirao SPI) - aprovado manual (Felipe 12/08); base risco MANUAL; remover quando base refletir
                  '77a56fa5-9c4e-476c-b71d-ac08534d6745': '2026-08-13',  # DILEUDA CORINGA DA FONSECA DA SILVA (Antecipa PF, Thiago Macillo/Natal RN) - aprovado manual (Felipe 13/08); risco APPROVED_PENDING_CREDIT + credito PENDING; remover quando base refletir
                  'b4e7eacc-8dc9-445e-9a37-d83cb3ecff80': '2026-08-13',  # DANILO FERREIRA DE LACERDA (Antecipa PF, Fabio Rodrigues/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; aprovado manual (Felipe 13/08); remover quando base refletir
                  '1d00bb47-a942-4407-8216-98df676b41e9': '2026-08-13',
                  '0b97aa9e-2def-45ec-ad98-034573f178a6': '2026-08-17',
                  '25611c90-3b9b-4b2f-a42e-41d22dcebd7a': '2026-08-17'}  # THAIS CRISTINA FLOSINO (Antecipa PJ, Joao Santos/Ribeirao) - risco APPROVED_PENDING_CREDIT + CREDITO APPROVED na gold, mas o card818 veio em cache com MANUAL/sem credito (Felipe 17/08); remover quando a base refletir  # JONAS EMER COQUELY / 62018400000181 (Antecipa PJ, Joao Santos/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT (Pix) + sem analise de credito; aprovado manual (Felipe 17/08); remover quando base refletir  # ALESSANDRA DELFINO (Antecipa PF, Phillip Faria/Ribeirao) - BGC_PARCEIRO risco APPROVED_PENDING_CREDIT + credito PENDING; aprovado manual (Felipe 13/08); remover quando base refletir
LOST_IGNORE = {  # ignora lost_at/lost_reason (falso 'nao aceito pela distribuidora')
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES',  # reprovado e erro; ignorar (Felipe 03/07)
 'ANTÔNIO EDMILSON LEITE',  # dup denied em BGC, forçado aprovado (Felipe 15/07)
}
# INJECT_DEALS: deals ausentes da base viva, adicionados manualmente (Felipe).
INJECT_DEALS = [
    {'deal_id': 'f8ba2c6d-df9c-4292-8f36-ef504a6b4305', 'deal_stage': 'REQUEST_TITULARIDADE', 'deal_lost_at': '', 'deal_lost_reason': '', 'rd_station_crm_id': '', 'deal_created_at': '2026-08-13T16:36:17', 'current_client_cnpj': '', 'current_client_cpf': '67308910504', 'current_client_name': 'MARLI MERCES DOS SANTOS LISBOA', 'client_phone_number': '+5571982531504', 'current_client_state': 'BA', 'current_client_city': 'LAURO DE FREITAS', 'distributor_short_name': 'NEOENERGIA COELBA', 'origin_campaign': '', 'origin_source': 'whatsapp-bot', 'internal_sales_classification': 'FS_Liora', 'sales_team': 'Field Sales', 'sales_organization_name': 'Liora', 'sales_channel_name': 'Field Sales Liora', 'sales_person_name': 'ETTORE ROSSI NETO', 'sales_person_email': 'ettore.rossi@lioraenergia.com.br', 'current_total_bill_cost (R$)': '275.82', 'rd_bill_cost (R$)': '275.0', 'under_minimal_flag': '0', 'rd_distributor': 'NEOENERGIA COELBA', 'current_consumption': '0.187', 'is_current_consumption_estimated': 'false', 'current_consumption_filled': '0.187', 'consumption_group': '1. <= 0.5 MWh', 'proposal_id': 'e72306d5-f7d8-4be3-8a3d-5157bf33c6ec', 'proposal_created_at': '2026-08-13T16:36:17', 'accepted_proposal': 'true', 'product_name': 'LIORA_F_', 'energy_retailer_name': 'Liora Energia', 'has_valid_bill_uploaded': 'true', 'bill_id': '', 'latest_contract_id': 'c964ff7a-31e3-4965-938b-e748505a8ad2', 'latest_contract_created_at': '2026-08-13T16:38:46', 'latest_contract_signature_signed_at': '2026-08-13T16:40:05', 'latest_risk_analysis_result': 'APPROVED', 'latest_risk_analysis_created_at': '2026-08-13T16:41:53', 'latest_risk_analysis_comments': '', 'idle_days': '0', 'idle_days_group': '1. <= 1 dia', 'cancelation_date': '', 'ops_tt_status': 'APROVADO', 'ops_tt_status_reason': 'APROVADO', 'credit_product': '0', 'deal_credit_stage': '', 'latest_credit_analysis_result': ''},  # MARLI MERCES DOS SANTOS LISBOA (Ettore Rossi/Salvador, LIORA_F_ Coelba) - aprovada risco 16:41 13/08 mas ausente do card818 (curado atrasa); inject manual (Felipe 13/08); remover quando card818 refletir
    {'deal_id': 'e607c712-93ed-43f2-9d77-dd257c009238', 'deal_stage': 'REQUEST_TITULARIDADE', 'deal_lost_at': '', 'deal_lost_reason': '', 'rd_station_crm_id': '', 'deal_created_at': '2026-08-14T12:40:27.471653', 'current_client_cnpj': '', 'current_client_cpf': '21835932886', 'current_client_name': 'CHESSER WILLIAM MASSARO', 'client_phone_number': '+5516992650332', 'current_client_state': 'SP', 'current_client_city': 'RIBEIRÃO PRETO', 'distributor_short_name': 'CPFL PAULISTA', 'origin_campaign': '', 'origin_source': 'whatsapp-bot', 'internal_sales_classification': 'FS_Liora', 'sales_team': 'Field Sales', 'sales_organization_name': 'Liora', 'sales_channel_name': 'Field Sales Liora', 'sales_person_name': 'Fabio Rodrigues ', 'sales_person_email': 'fabio.rodrigues@lioraenergia.com.br', 'current_total_bill_cost (R$)': '1826.79', 'rd_bill_cost (R$)': '2000.0', 'under_minimal_flag': '0', 'rd_distributor': 'CPFL PAULISTA', 'current_consumption': '1.81', 'is_current_consumption_estimated': 'false', 'current_consumption_filled': '1.81', 'consumption_group': '3. <= 5.0 MWh', 'proposal_id': '2abf98c2-da0a-4e78-897b-1a36542fe4b5', 'proposal_created_at': '2026-08-14T12:40:27.983546', 'accepted_proposal': 'true', 'product_name': 'LIORA_F_', 'energy_retailer_name': 'Liora Energia', 'has_valid_bill_uploaded': 'true', 'bill_id': 'e833c8c3-2035-4bb5-9759-2af80784b6ba', 'latest_contract_id': '1216232c-8f1c-4027-a4bf-cb90590ba89e', 'latest_contract_created_at': '2026-08-14T11:47:10.905748', 'latest_contract_signature_signed_at': '2026-08-14T11:53:57.00', 'latest_risk_analysis_result': 'APPROVED', 'latest_risk_analysis_created_at': '2026-08-14T19:22:59.422879', 'latest_risk_analysis_comments': '', 'idle_days': '0', 'idle_days_group': '1. <= 1 dia', 'cancelation_date': '', 'ops_tt_status': 'N/A', 'ops_tt_status_reason': 'N/A', 'credit_product': '0', 'deal_credit_stage': '', 'latest_credit_analysis_result': ''},  # CHESSER WILLIAM MASSARO 2a UC (UC 601093603514, Fabio Rodrigues/Ribeirao, LIORA_F_ CPFL) - risco APPROVED 19:22 14/08 mas ausente do card818 (curado atrasa); inject manual (Felipe 14/08); remover quando card818 refletir
]
INJECT_UC = {}
MES={'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
DOW=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
ANCHOR = datetime.date(2026,6,1)  # S0 = semana que contém o 1º do mês (junho/2026)
ANCHOR_MON = ANCHOR - datetime.timedelta(days=ANCHOR.weekday())

def pdate(s):
    s=(s or '').strip()
    if not s: return None
    if re.match(r'\d{4}-\d{2}-\d{2}',s): return datetime.date.fromisoformat(s[:10])
    m=re.match(r'([a-zç]+)\s+(\d+),\s*(\d{4})',s.lower())
    if m: return datetime.date(int(m.group(3)),MES[m.group(1)],int(m.group(2)))
    return None
def iso(d): return d.isoformat() if d else ''
def pfloat(s):
    s=(s or '').strip().replace(',','')
    if s=='' : return 0.0
    try: return float(s)
    except: return 0.0
def canon_seller(email, raw_name):
    e=(email or '').strip().lower()
    if e in EMAIL_NOME: return EMAIL_NOME[e]
    n=re.sub(r'\s+',' ',(raw_name or '')).strip()
    return NAME_MAP.get(n.lower(), n)
def semana(basis_date):
    if not basis_date: return ''
    mon = basis_date - datetime.timedelta(days=basis_date.weekday())
    idx = (mon - ANCHOR_MON).days // 7
    return f"S{idx}"

def load_uc(path):
    m={}
    if not path: return m
    try:
        with open(path,newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                did=(r.get('deal_id') or '').strip(); uc=(r.get('uc') or '').strip()
                if did and uc: m[did]=uc
    except Exception as e:
        print('aviso: uc nao carregado:', e)
    return m

def build_rawData(deals_path, ag_path, prop_path=None, docs_map=None, uc_map=None):
    docs_map = docs_map or {}
    uc_map = uc_map or {}
    def rows(p):
        with open(p,newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
    out=[]; seen=set()
    def emit(r):
        did=r['deal_id']
        if did in seen: return
        seen.add(did)
        cli=r['current_client_name'].strip()
        s=canon_seller(r['sales_person_email'], r['sales_person_name'])
        ov=CLIENT_OVERRIDE.get((cli or '').strip().upper())
        if ov: s=ov[0]
        forced = did in FORCE_APPROVED
        _risk = (r['latest_risk_analysis_result'] or '').strip()
        _status = (r.get('ops_tt_status') or '').lower()
        _credit = (r.get('latest_credit_analysis_result') or '').strip().lower()  # Antecipa
        credito_ok = (_credit == 'approved')  # Felipe 06/08: crédito aprovado conta como aprovado
        # Alinha ao desktop (definição oficial isAprovado): conta como aprovado se risco
        # APPROVED, OU status "aprovado", OU stage REQUEST_TITULARIDADE (fallback p/ deal
        # que avançou sem risco APPROVED). Nunca conta DENIED nem BGC_PARCEIRO (validação
        # Antecipa, ainda não aprovado) — EXCETO quando o crédito do Antecipa já foi aprovado.
        _reached = (_risk=='APPROVED') or ('aprovado' in _status) or (r['deal_stage']=='REQUEST_TITULARIDADE')
        approved = forced or credito_ok or (_reached and _risk!='DENIED' and r['deal_stage']!='BGC_PARCEIRO')
        aprov = (iso(pdate(r['latest_risk_analysis_created_at']) or pdate(r['deal_created_at'])) if approved else '')
        created = pdate(r['deal_created_at'])
        basis = (pdate(r['latest_risk_analysis_created_at']) or created) if approved else created
        if forced and FORCE_APPROVED[did]:
            aprov = FORCE_APPROVED[did]; basis = pdate(FORCE_APPROVED[did])  # data de aprovação manual
        try: idle=int(float(r['idle_days'])) if r['idle_days'].strip()!='' else 0
        except: idle=0
        out.append({
            'c':cli,'s':s,'mwh':CONSUMPTION_OVERRIDE_BY_ID.get(r['deal_id'], CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled']))),
            'stage':('REQUEST_TITULARIDADE' if (forced and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']),'status':r['ops_tt_status'],'idle':idle,
            'city':r['current_client_city'],'state':r['current_client_state'],
            'dist':DIST_MAP.get(r['distributor_short_name'], r['distributor_short_name']),
            'produto':(r.get('product_name') or '').strip(),
            'credito_ok':credito_ok,'credito':credit_pt(r.get('deal_credit_stage')),
            'deal_id':did,'uc':uc_map.get(did,''),'tel':r['client_phone_number'],'cnpj':r['current_client_cnpj'],'cpf':r['current_client_cpf'],
            'fatura':pfloat(r['current_total_bill_cost (R$)']),'semana':semana(basis),
            'lost_at':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_at']),'lost_reason':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_reason']),
            'motivo':(('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else (r.get('latest_risk_analysis_comments') or '').strip()),
            'date':iso(created),'aprov_date':aprov,
            'docs':docs_map.get((r.get('latest_contract_id') or '').strip(),''),
        })
    for r in rows(deals_path): emit(r)
    for r in INJECT_DEALS:
        uc_map.setdefault(r['deal_id'], INJECT_UC.get(r['deal_id'],''))
        emit(r)
    for r in rows(ag_path):    emit(r)
    if prop_path:                       # injeta aprovados manuais ausentes dos recortes
        for r in rows(prop_path):
            if r['deal_id'] in FORCE_APPROVED and r['deal_id'] not in seen: emit(r)
    return out

def build_RAW_PROP(prop_path):
    with open(prop_path,newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    out=[]
    for r in rows:
        d=pdate(r['proposal_created_at']) or pdate(r['deal_created_at'])
        cli=r['current_client_name'].strip()
        seller=canon_seller(r['sales_person_email'], r['sales_person_name'])
        praca=SELLER_PRACA.get(seller,'Outros')
        ov=CLIENT_OVERRIDE.get((cli or '').strip().upper())
        if ov: seller, praca = ov[0], ov[1]
        out.append({
            'date':iso(d),'week':(d.isocalendar()[1] if d else 0),'month':(d.month if d else 0),
            'dayofweek':(DOW[d.weekday()] if d else ''),
            'sales_person_name':r['sales_person_name'],'seller':seller,
            'bill_cost':pfloat(r['current_total_bill_cost (R$)']),
            'consumption_mwh':CONSUMPTION_OVERRIDE_BY_ID.get(r['deal_id'], CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled']))),
            'current_client_name':cli,'current_client_state':r['current_client_state'],
            'deal_stage':r['deal_stage'],'accepted_proposal':(str(r['accepted_proposal']).strip().lower()=='true'),
            'praca':praca,
        })
    return out

if __name__=='__main__':
    import sys
    d,a,p = sys.argv[1],sys.argv[2],sys.argv[3]
    docs_path = sys.argv[4] if len(sys.argv)>4 else None
    docs_map = load_docs(docs_path)
    import os as _os
    uc_map = load_uc(_os.environ.get('UC_CSV'))
    print('uc carregados:', len(uc_map))
    rd=build_rawData(d,a,p,docs_map,uc_map); rp=build_RAW_PROP(p)
    print('docs pendentes carregados:', len(docs_map))
    json.dump(rd,open('new_rawData.json','w'),ensure_ascii=False)
    json.dump(rp,open('new_RAW_PROP.json','w'),ensure_ascii=False)
    print('rawData',len(rd),'RAW_PROP',len(rp))
