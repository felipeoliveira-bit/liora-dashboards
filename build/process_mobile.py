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
 'ana.ribeiro@lioraenergia.com.br':'Ana Ribeiro',
 'joao.santos@lioraenergia.com.br':'João Santos',
 'mecenas.junior@lioraenergia.com.br':'Mecenas Junior',
 'daniel.magnus@lioraenergia.com.br':'Daniel Magnus',
 'kelma.rangel@lioraenergia.com.br':'Kelma Rangel','lucileide.carlos@lioraenergia.com.br':'Lucileide Carlos',
 'rosangela.mendes@lioraenergia.com.br':'Rosangela Mendes','tiago.freitas@lioraenergia.com.br':'Tiago Freitas',
 'ryan.trindade@lioraenergia.com.br':'Ryan Trindade','bruno.borges@lioraenergia.com.br':'Bruno Borges',
 'neilon.nascimento@lioraenergia.com.br':'Neilon Nascimento','sabrina.tomazeti@lioraenergia.com.br':'Sabrina Tomazeti','odirley.costa@lioraenergia.com.br':'Odirley Costa',
 'nubia.andrade@lioraenergia.com.br':'Núbia Andrade','marcio.galvao@lioraenergia.com.br':'Marcio Galvão',
 'bruno.andrade@lioraenergia.com.br':'Bruno Andrade','rodrigo.ribeiro@lioraenergia.com.br':'Rodrigo Ribeiro',
 'adroaldo.bonfim@lioraenergia.com.br':'Adroaldo Bonfim','ettore.rossi@lioraenergia.com.br':'Ettore Rossi','tatiane.correia@lioraenergia.com.br':'Tatiane Correia',
 'maria.lucia@lioraenergia.com.br':'Maria Lúcia','tais.santos@lioraenergia.com.br':'Tais Santos',
 'antonio.mariano@lioraenergia.com.br':'Antonio Mariano','caio.lannes@lioraenergia.com.br':'Caio Lannes',
 'monica.silveira@lioraenergia.com.br':'Monica Silveira','franciele.felix@lioraenergia.com.br':'Franciele Felix',
 'ederson.silva@lioraenergia.com.br':'Ederson Silva','diego.faria@lioraenergia.com.br':'Diego Faria',
 'felipe.oliveira@lioraenergia.com.br':'Felipe Oliveira',
 'mirla.albuquerque@lioraenergia.com.br':'Mirla Albuquerque',
 'ananias.neto@lioraenergia.com.br':'Ananias Neto','ananias.oliveira@lioraenergia.com.br':'Ananias Neto',
 'thiago.araujo@lioraenergia.com.br':'Thiago Araujo França',
}
NAME_MAP = {  # fallback quando não há email reconhecido (nome cru -> canônico)
 'antonio carlos':'Antonio Mariano','bruno rodrigues':'Bruno Andrade','ananias oliveira':'Ananias Neto',
}
SELLER_PRACA = {  # canônico -> label praça
 'Silmara Gomes':'CE',
 'Luciana Campos':'Salvador',
 'Nicola Popovic':'SPI',
 'Anderson Correia':'SPI',
 'Ana Ribeiro':'SPI',
 'João Santos':'Ribeirão Preto SPI',
 'Mirla Albuquerque':'RN Interior',
 'Mecenas Junior':'Natal',
 'Daniel Magnus':'Natal',
 'Adroaldo Bonfim':'Salvador','Ettore Rossi':'Salvador','Tatiane Correia':'Salvador','Maria Lúcia':'Salvador','Tais Santos':'Salvador','Antonio Mariano':'Salvador',
 'Kelma Rangel':'Feira de Santana','Lucileide Carlos':'Feira de Santana','Rosangela Mendes':'Feira de Santana','Tiago Freitas':'Feira de Santana','Ryan Trindade':'Feira de Santana',
 'Bruno Andrade':'Natal','Marcio Galvão':'Natal','Rodrigo Ribeiro':'Natal','Ananias Neto':'Natal','Thiago Araujo França':'Natal',
 'Caio Lannes':'SPI','Monica Silveira':'SPI','Franciele Felix':'SPI','Ederson Silva':'SPI','Diego Faria':'SPI',
 'Bruno Borges':'CE','Neilon Nascimento':'CE','Sabrina Tomazeti':'CE','Odirley Costa':'CE','Núbia Andrade':'CE',
 'Felipe Oliveira':'Outros',
}
DIST_MAP = {'NEOENERGIA COELBA':'Coelba','NEOENERGIA COSERN':'Cosern','CPFL PAULISTA':'CPFL','ENEL CE':'Enel'}
CLIENT_OVERRIDE = {  # cliente (upper/strip) -> (seller canônico, praça label)
 'NIVALDO GESTEIRA DE OLIVEIRA':('Maria Lúcia','Salvador'),
 'MANOEL ROQUE DA SILVA JUNIOR':('Lucileide Carlos','Feira de Santana'),
 'CARLA NUNCIA BESERRA':('Marcio Galvão','Natal'),  # 2a UC da Carla (mesma CPF) - é do Marcio, não do Ederson (Felipe 26/06)
 'MARIA SOARES RODRIGUES':('Rodrigo Ribeiro','Natal'),  # deal do Bruno -> Rodrigo (Felipe 03/07); base ainda nao atualizou
}
CONSUMPTION_OVERRIDE = {  # cliente (upper/strip) -> MWh; temp ate base corrigir
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES': 5.86,  # base mostra 0.59 (Felipe 03/07)
 'GABRIEL LUCHIARI ALBERTO': 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 'PERFECTA VIDROS E ALUMINIOS EIRELI': 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 'CHEVROFOR COM PECAS E ACESSORIOS LTDA': 1.21,  # base mostra 0.50 (Felipe 07/07)
 'MÁRCIO PEREIRA PINTO': 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
}
FORCE_APPROVED = {  # deal_id -> nota; contam como aprovado por decisao manual (pre-BGC)
 'b61609e9-835a-4ed2-896d-2de4fd55c4f9': '2026-07-15',  # Stefanny Karoline Martins - aprovado manual, Mirla/RN Interior (Felipe 16/07)
 '9ccf72c4-32d9-406f-b2c1-a533f486c8d1': '2026-07-14',  # Antonio Edmilson Leite - dup denied em BGC (Felipe 15/07)
 'a4a2cc08-a77e-4549-8306-ef13db2a3a95': '2026-07-10',  # Marcio Pereira pinto / Nicola Popovic (Felipe 10/07)
 '35ad764a-c6f8-4039-9bcc-9706c960c1a5': '2026-07-16',  # Larissa Cecilia Sampaio Tavares / Ederson Silva - risco APPROVED 16/07 pos-perdido em BGC_PARCEIRO (Felipe 17/07)
}
LOST_IGNORE = {  # ignora lost_at/lost_reason (falso 'nao aceito pela distribuidora')
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES',  # reprovado e erro; ignorar (Felipe 03/07)
 'ANTÔNIO EDMILSON LEITE',  # dup denied em BGC, forçado aprovado (Felipe 15/07)
}
# INJECT_DEALS: deals ausentes da base viva, adicionados manualmente (Felipe).
INJECT_DEALS = [
 {
 'deal_id':'b61609e9-835a-4ed2-896d-2de4fd55c4f9','deal_stage':'BACKGROUND_CHECKING','deal_lost_at':'','deal_lost_reason':'',
 'rd_station_crm_id':'','deal_created_at':'2026-07-15T00:00:00','current_client_cnpj':'','current_client_cpf':'',
 'current_client_name':'STEFANNY KAROLINE MARTINS DE S. MARTINS','client_phone_number':'',
 'current_client_state':'RN','current_client_city':'MOSSORÓ','distributor_short_name':'NEOENERGIA COSERN',
 'origin_campaign':'','origin_source':'','internal_sales_classification':'Direto','sales_team':'Field Sales',
 'sales_organization_name':'Liora','sales_channel_name':'','sales_person_name':'Mirla Albuquerque',
 'sales_person_email':'mirla.albuquerque@lioraenergia.com.br','current_total_bill_cost (R$)':'586.33',
 'rd_bill_cost (R$)':'586.33','under_minimal_flag':'0','rd_distributor':'NEOENERGIA COSERN',
 'current_consumption':'0.543','is_current_consumption_estimated':'false','current_consumption_filled':'0.543',
 'consumption_group':'2. <= 1.0 MWh','proposal_id':'','proposal_created_at':'','accepted_proposal':'true',
 'product_name':'','energy_retailer_name':'Liora Energia','has_valid_bill_uploaded':'false','bill_id':'',
 'latest_contract_id':'','latest_contract_created_at':'','latest_contract_signature_signed_at':'',
 'latest_risk_analysis_result':'','latest_risk_analysis_created_at':'2026-07-15T00:00:00',
 'latest_risk_analysis_comments':'','idle_days':'0','idle_days_group':'','cancelation_date':'',
 'ops_tt_status':'','ops_tt_status_reason':'','credit_product':'0',
},
]
INJECT_UC = {'b61609e9-835a-4ed2-896d-2de4fd55c4f9':'5039298'}
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
        # Alinha ao desktop (definição oficial isAprovado): conta como aprovado se risco
        # APPROVED, OU status "aprovado", OU stage REQUEST_TITULARIDADE (fallback p/ deal
        # que avançou sem risco APPROVED). Nunca conta DENIED nem BGC_PARCEIRO (validação
        # Antecipa, ainda não aprovado).
        _reached = (_risk=='APPROVED') or ('aprovado' in _status) or (r['deal_stage']=='REQUEST_TITULARIDADE')
        approved = forced or (_reached and _risk!='DENIED' and r['deal_stage']!='BGC_PARCEIRO')
        aprov = (iso(pdate(r['latest_risk_analysis_created_at']) or pdate(r['deal_created_at'])) if approved else '')
        created = pdate(r['deal_created_at'])
        basis = (pdate(r['latest_risk_analysis_created_at']) or created) if approved else created
        if forced and FORCE_APPROVED[did]:
            aprov = FORCE_APPROVED[did]; basis = pdate(FORCE_APPROVED[did])  # data de aprovação manual
        try: idle=int(float(r['idle_days'])) if r['idle_days'].strip()!='' else 0
        except: idle=0
        out.append({
            'c':cli,'s':s,'mwh':CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled'])),
            'stage':('REQUEST_TITULARIDADE' if (forced and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']),'status':r['ops_tt_status'],'idle':idle,
            'city':r['current_client_city'],'state':r['current_client_state'],
            'dist':DIST_MAP.get(r['distributor_short_name'], r['distributor_short_name']),
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
            'consumption_mwh':CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled'])),
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
