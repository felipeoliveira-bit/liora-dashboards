#!/usr/bin/env python3
# slice_base_ci.py - fatia a base do card 818 nos 3 recortes (versao CI).
# Mesmas regras do slice_base.py homologado (validadas campo-a-campo 17/06):
#   filtro comum : internal_sales_classification == 'FS_Liora'
#   deals        : latest_risk_analysis_created_at no mes corrente (dedup deal_id)
#   propostas    : proposal_created_at no mes corrente (sem dedup)
#   aguardando   : WAITING_DOCUMENTS + nao perdido + assinatura >= 1o dia do mes anterior (dedup)
# Mes corrente em America/Sao_Paulo. Escreve em <work>/ com utf-8 (sem BOM).
# Uso: python3 slice_base_ci.py <base.csv> <work_dir>
import csv, re, os, sys, datetime
try:
    from zoneinfo import ZoneInfo
    TODAY = datetime.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
except Exception:
    TODAY = datetime.date.today()

# Deals duplicados a excluir de TODOS os recortes (mesmo cliente aberto p/
# vendedores diferentes). Mantemos so o deal original. Espelha automacao/slice_base.py.
EXCLUDE_DEALS = {
    # Carla Beserra/Bezerra: confirmado 25/06 que NAO era duplicata - 2 UCs
    # distintas do mesmo CPF. As duas contam (fora da lista de exclusao).
    #
    # Ruan Oliveira Leal (vend. Tiago Assis / 'Outras', Salvador, Coelba, 100d
    # parado, "Cliente que se perdeu no funil") - pedido Felipe 15/07: vai virar
    # perdido, tirar da lista ja. Remover quando a base marcar como lost.
    '638a08a6-845f-4eab-a290-24366dfc131e',
    # Mw Safaty Ltda (SP, COLLECTING INFORMATION) - vend. Raynara Silva (suporte,
    # nao deveria criar lead). Felipe 07/08: vai virar perdido, tirar do CRM ja.
    # Remover quando a base marcar como lost.
    '4b4d439b-88d0-4838-bbd4-48ef5c0b256e',
    # Maria Solange Tavares (Parnamirim/Cosern, WAITING_DOCUMENTS, 14d parado,
    # vend. Marcio Galvao) - obs de risco: fatura com energia injetada de outra
    # GD. Felipe 26/08: cliente ja foi dado perdido, tirar das pendencias ja.
    # Remover quando a base marcar como lost.
    '7675267f-d62e-4fad-877e-5701a52b4ca9',
}

MESES = {'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
         'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}

def ymd(s):
    s=(s or '').strip()
    if not s: return None
    m=re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return (int(m.group(1)),int(m.group(2)),int(m.group(3)))
    m=re.match(r'^([a-zçã]+)\s+(\d{1,2}),\s*(\d{4})', s.lower())
    if m and m.group(1) in MESES: return (int(m.group(3)),MESES[m.group(1)],int(m.group(2)))
    return None

def in_cur_month(s):
    t=ymd(s); return t is not None and t[0]==TODAY.year and t[1]==TODAY.month

PREV=(TODAY.year-1,12,1) if TODAY.month==1 else (TODAY.year,TODAY.month-1,1)

# Janela do HISTORICO por vendedor: 3 meses fechados + o mes corrente (aba
# "Historico" do desktop). Espelha automacao/slice_base.py.
HIST_MESES=4
def _mes_janela(n):
    y,m=TODAY.year,TODAY.month; out=[]
    for _ in range(n):
        out.append('%04d-%02d'%(y,m)); m-=1
        if m==0: y,m=y-1,12
    return set(out)
HIST_JANELA=_mes_janela(HIST_MESES)
def in_hist_window(s):
    t=ymd(s); return t is not None and ('%04d-%02d'%(t[0],t[1])) in HIST_JANELA
def sig_recent(s):
    t=ymd(s); return t is not None and t>=PREV

def load_risk_real(base_path):
    # Mapa deal_id -> (result, created) do risco REAL (liora_silver.risk_analysis),
    # exportado pelo mb_export.py como risk_real.csv na mesma pasta da base.
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)), 'risk_real.csv')
    if not os.path.isfile(p): return {}
    m={}
    with open(p, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            did=(r.get('deal_id') or '').strip()
            if did: m[did]=((r.get('real_result') or '').strip(), (r.get('real_created') or '').strip())
    return m


def load_appr_date(base_path):
    # Mapa deal_id -> data da APROVACAO NO RISCO (coluna appr_created do risk_real.csv;
    # ver RISK_SQL em mb_export.py). Vazio se o CSV nao tiver a coluna (export antigo)
    # - nesse caso nada muda e a data segue vindo da analise mais nova.
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)), 'risk_real.csv')
    if not os.path.isfile(p): return {}
    m={}
    with open(p, encoding='utf-8-sig') as fh:
        rd=csv.DictReader(fh)
        if 'appr_created' not in (rd.fieldnames or []): return {}
        for r in rd:
            did=(r.get('deal_id') or '').strip(); v=(r.get('appr_created') or '').strip()
            if did and v: m[did]=v
    return m


def load_credit_date(base_path):
    # Mapa deal_id -> data da APROVACAO DO CREDITO (coluna credit_appr do
    # risk_real.csv; ver RISK_SQL em mb_export.py). So vem preenchida para
    # Antecipa com credito 'approved'. Vazio se o CSV for de um export antigo
    # sem a coluna - nesse caso nada muda e a data segue a do risco.
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)), 'risk_real.csv')
    if not os.path.isfile(p): return {}
    m={}
    with open(p, encoding='utf-8-sig') as fh:
        rd=csv.DictReader(fh)
        if 'credit_appr' not in (rd.fieldnames or []): return {}
        for r in rd:
            did=(r.get('deal_id') or '').strip(); v=(r.get('credit_appr') or '').strip()
            if did and v: m[did]=v
    return m


# EXCECAO da trava de mes fechado (Felipe 02/09) - deal que DEVE migrar mesmo
# tendo sido contado no mes anterior. Cada entrada aqui e' um PAGAMENTO EM
# DUPLICIDADE consciente: a venda ja foi paga no mes fechado e vai contar de novo.
# Colocar so por decisao explicita do Felipe, com o motivo e o MWh.
CREDIT_DATE_FORCE = {
    # Traumasport 0,555 MWh (Bruno Borges, [FS] Liora Antecipa PJ) - risco em
    # 31/08 19:11, credito aprovado 01/09 06:45. Ja entrou nos aprovados de
    # agosto (build b37fd7f, semana S13) e foi pago: o Bruno fechou agosto com
    # 12,004 MWh, que e' o "12" da planilha de fechamento; sem este cliente
    # daria 11,449. Felipe 02/09 pediu para contar em setembro assim mesmo,
    # ciente da duplicidade, para o vendedor ver os 3 Antecipa juntos.
    '31d7d3d6-b51f-4af5-81b7-1cc6f325268e',
}


def apply_credit_date(base, cred):
    # DATA DA VENDA DO ANTECIPA = APROVACAO DO CREDITO (Felipe 02/09).
    # Inverte o criterio anterior (data da aprovacao no risco, 25/08): o que
    # carimba a venda agora e' o momento em que o CREDITO foi aprovado.
    #
    # TRAVA DE MES FECHADO - nao remover. Deal cuja aprovacao no risco caiu em
    # mes JA FECHADO E PAGO nao migra: ele ja foi contado e remunerado la, e
    # traze-lo para o mes corrente paga o vendedor 2x. Conferido em 02/09 no
    # build congelado de agosto (commit b37fd7f): Traumasport (Bruno, 0,555),
    # Renata Cristiane e Athos Mateus (Ederson, 0,481+0,371) entraram nos
    # aprovados de 31/08, semana S13, pagos em 01/09 - somam 1,407 MWh.
    # A trava vale nos DOIS sentidos: tambem nao empurramos a venda para TRAS
    # (credito em mes fechado, risco no corrente), senao ela some do pagamento.
    # So trocamos a data quando as DUAS pontas estao no mes corrente/aberto.
    if not cred: return 0
    n=0
    for r in base:
        v=cred.get((r.get('deal_id') or '').strip())
        if not v: continue
        cur=(r.get('latest_risk_analysis_created_at') or '').strip()
        if not cur: continue
        forcado = (r.get('deal_id') or '').strip() in CREDIT_DATE_FORCE
        if not forcado and not in_cur_month(cur): continue   # risco em mes fechado -> fica la
        if not in_cur_month(v):   continue   # credito em mes fechado -> nao volta
        if v[:10]==cur[:10]: continue
        r['latest_risk_analysis_created_at']=v; n+=1
    return n


def apply_appr_date(base, appr):
    # DATA DA VENDA = APROVACAO NO RISCO, NAO A DO CREDITO (Felipe 25/08).
    # O Antecipa gera uma SEGUNDA analise de risco APPROVED quando o credito e' pago,
    # dias depois do APPROVED_PENDING_CREDIT que ja aprovou a venda. Como o pipeline
    # carimba a venda por latest_risk_analysis_created_at, ela pulava para a semana do
    # PAGAMENTO e o vendedor era pago 2x pela mesma venda na campanha (Diogenes e Bruna
    # do Fabio: risco 22/08, pagamento 24/08 -> reapareciam na semana 24-30/08).
    # Aqui a data volta para o inicio da sequencia aprovadora. So anda para TRAS: se o
    # card ja tem data mais antiga, ela manda (preserva override/atribuicao existente).
    # O total do mes nao muda - so o dia/semana em que a venda cai.
    if not appr: return 0
    n=0
    for r in base:
        v=appr.get((r.get('deal_id') or '').strip())
        if not v: continue
        cur=(r.get('latest_risk_analysis_created_at') or '').strip()
        if cur and v[:10] < cur[:10]:
            r['latest_risk_analysis_created_at']=v; n+=1
    return n


# --- AUGMENTO FONTE-VIVA (funil sales_b_group) -------------------------------
# Funde os deals Field FRESCOS do funil ao vivo (mb_export -> sbg_field.csv) na
# base do card818, que atrasa umas horas (job de curadoria periodico). Corrige o
# "aprovado do dia sumindo" SEM forcar na mao: linha ja existente -> atualiza so
# os campos de estagio/risco (sbg e mais fresco); linha ausente -> anexa mapeando
# colunas + derivando as poucas que faltam. So mexe em Field; nunca remove linha.
_SBG_STAGE_FIELDS = ['deal_stage','deal_lost_at','deal_lost_reason','latest_risk_analysis_result',
                     'latest_risk_analysis_created_at','latest_contract_id','latest_contract_signature_signed_at']
def _sbg_idle(updated):
    try:
        d=datetime.date(int(updated[0:4]),int(updated[5:7]),int(updated[8:10]))
        return str(max(0,(TODAY-d).days))
    except Exception:
        return ''
# -----------------------------------------------------------------------------
# BRONZE GAP (Felipe 15/08) - rede de seguranca contra congelamento do dbt.
# O card818 e' a gold sales_management, que depende da silver
# distributed_generation_proposals. Em 15/08 essa silver parou de materializar e
# TODA proposta criada depois sumiu do card818 - inclusive aprovados do dia (e do
# sbg_field, que sai da mesma gold). O bronze_gap.csv (mb_export) traz esses deals
# direto do BRONZE; aqui eles viram linhas no formato do card818 e sao anexados a
# base ANTES do augmento/risco. Com o dbt em dia o recorte vem vazio e nada muda.
def _gap_consumption_group(v):
    try: x=float(v)
    except Exception: return ''
    if x<=0.5: return '1. <= 0.5 MWh'
    if x<=1.0: return '2. <= 1.0 MWh'
    if x<=5.0: return '3. <= 5.0 MWh'
    return '4. > 5.0 MWh'

def apply_bronze_gap(base, fields, base_path):
    # A classificacao de canal (internal_sales_classification/sales_team) e' logica do
    # dbt e nao existe no bronze. Em vez de reimplementar, aprendemos o de-para da
    # propria base: por (canal, organizacao) usamos a classificacao mais frequente ja
    # vista no card818. Canal desconhecido entra sem classificacao (fica fora do
    # FS_Liora) - conservador de proposito: na duvida nunca infla o resultado.
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)),'bronze_gap.csv')
    if not os.path.isfile(p): return 0
    from collections import Counter
    pair={}; only={}
    for r in base:
        ch=(r.get('sales_channel_name') or '').strip()
        if not ch: continue
        org=(r.get('sales_organization_name') or '').strip()
        val=((r.get('internal_sales_classification') or '').strip(),
             (r.get('sales_team') or '').strip())
        pair.setdefault((ch,org),Counter())[val]+=1
        only.setdefault(ch,Counter())[val]+=1
    have=set((r.get('deal_id') or '').strip() for r in base)
    with open(p, encoding='utf-8-sig') as fh:
        rows=list(csv.DictReader(fh))
    add=0
    for g in rows:
        did=(g.get('deal_id') or '').strip()
        if not did or did in have: continue
        row={f:'' for f in fields}
        for k,v in g.items():
            c='current_total_bill_cost (R$)' if k=='current_total_bill_cost' else k
            if c in row: row[c]=(v or '')
        ch=(g.get('sales_channel_name') or '').strip()
        org=(g.get('sales_organization_name') or '').strip()
        cnt=pair.get((ch,org)) or only.get(ch)
        if cnt:
            cls,team=cnt.most_common(1)[0][0]
            row['internal_sales_classification']=cls
            row['sales_team']=team
        cons=(g.get('current_consumption') or '').strip()
        if 'current_consumption_filled' in row and not row['current_consumption_filled']:
            row['current_consumption_filled']=cons
        if 'is_current_consumption_estimated' in row: row['is_current_consumption_estimated']='false'
        if 'consumption_group' in row: row['consumption_group']=_gap_consumption_group(cons)
        if 'ops_tt_status' in row and not row['ops_tt_status']: row['ops_tt_status']='N/A'
        if 'ops_tt_status_reason' in row and not row['ops_tt_status_reason']: row['ops_tt_status_reason']='N/A'
        base.append(row); have.add(did); add+=1
    return add
# -----------------------------------------------------------------------------

def augment_from_sbg(base, fields, base_path):
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)),'sbg_field.csv')
    if not os.path.isfile(p): return (0,0)
    with open(p, encoding='utf-8-sig') as fh:
        sbg=list(csv.DictReader(fh))
    by_id={}
    for r in base:
        did=(r.get('deal_id') or '').strip()
        if did: by_id[did]=r
    npatch=napp=0
    for s in sbg:
        did=(s.get('deal_id') or '').strip()
        if not did: continue
        ch=(s.get('sales_channel_name') or '').strip()
        cls='FS_Liora' if ch=='Field Sales Liora' else 'Outro'
        if did in by_id:
            r=by_id[did]
            for f in _SBG_STAGE_FIELDS:
                if f in r: r[f]=s.get(f,'') or ''
            if not (r.get('latest_risk_analysis_comments') or '').strip() and (s.get('latest_risk_analysis_comments') or '').strip():
                r['latest_risk_analysis_comments']=s['latest_risk_analysis_comments']
            npatch+=1
        else:
            row={f:'' for f in fields}
            direct=['deal_id','deal_stage','deal_lost_at','deal_lost_reason','deal_created_at',
                    'current_client_cnpj','current_client_cpf','current_client_name','current_client_state',
                    'current_client_city','client_phone_number','distributor_short_name','sales_channel_name',
                    'sales_organization_name','energy_retailer_name','sales_person_name','sales_person_email',
                    'proposal_id','proposal_created_at','product_name','latest_contract_id',
                    'latest_contract_signature_signed_at','latest_risk_analysis_result',
                    'latest_risk_analysis_created_at','latest_risk_analysis_comments','current_consumption',
                    'has_valid_bill_uploaded']
            for f in direct:
                if f in row: row[f]=s.get(f,'') or ''
            if 'current_total_bill_cost (R$)' in row: row['current_total_bill_cost (R$)']=s.get('current_total_bill_cost','') or ''
            if 'current_consumption_filled' in row: row['current_consumption_filled']=s.get('current_consumption','') or ''
            if 'internal_sales_classification' in row: row['internal_sales_classification']=cls
            if 'sales_team' in row: row['sales_team']='Field Sales'
            if 'accepted_proposal' in row: row['accepted_proposal']='true'
            if 'ops_tt_status' in row: row['ops_tt_status']='N/A'
            if 'idle_days' in row: row['idle_days']=_sbg_idle(s.get('deal_updated_at','') or '')
            base.append(row); by_id[did]=row; napp+=1
    return (npatch,napp)
# -----------------------------------------------------------------------------

def apply_risk_real(base, real):
    # Sobrescreve o resultado de risco do card818 pelo risco REAL (fonte de verdade).
    # DATA (Felipe 14/08): quando o override CORRIGE o resultado e a data real e' mais
    # recente que a do card, a data tambem anda - senao o aprovado de hoje fica
    # carimbado no dia da analise velha e sai do resultado do dia. Quando o resultado
    # NAO muda, a data do card manda (preserva atribuicao de mes/semana).
    # real_created vem em America/Sao_Paulo (ver RISK_SQL no mb_export.py).
    if not real: return 0
    n=0; nd=0
    for r in base:
        rr=real.get((r.get('deal_id') or '').strip())
        if not rr: continue
        res,created=rr
        if not res: continue
        card_dt=(r.get('latest_risk_analysis_created_at') or '').strip()
        changed = res != (r.get('latest_risk_analysis_result') or '').strip()
        if changed:
            r['latest_risk_analysis_result']=res; n+=1
        if not card_dt and created:
            r['latest_risk_analysis_created_at']=created
        elif changed and created and created[:10] > card_dt[:10]:
            r['latest_risk_analysis_created_at']=created; nd+=1
    if nd: print('risco real: %d deal(s) com DATA de aprovacao movida p/ a analise real' % nd)
    return n

# -----------------------------------------------------------------------------
# QUEM ASSINOU (Felipe 27/08) - `current_client_name` e' o TITULAR PARSEADO DA
# FATURA, nao quem assinou o contrato. Quando a UC esta no nome de um parente ou
# do antigo dono, o card mostra uma pessoa e o vendedor procura por outra
# (Helenita x MAURICIO JOSE BONFIM, Olimpio Filho, 25/08). O signatario vem de
# `contracts.contract_metadata.client_name` (SIGNER_SQL no mb_export.py).
# NAO trocamos o titular pelo signatario: o signatario e' DIGITADO pelo vendedor
# e quase sempre e' pior (typo, so o primeiro nome, apelido: 'Dr Marcelo',
# 'Rferraz', 'DOIS IRMAOS 71-A'). Gravamos na coluna `signer_name` SO quando e'
# outra PESSOA -> 0,6% da base (59 de 9.806 deals com contrato em ago/26).
# Espelha o apply_signer do automacao/slice_base.py: mexeu num, mexe no outro.
# -----------------------------------------------------------------------------
SIGNER_COL='signer_name'

def _sig_norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',(s or '')).encode('ascii','ignore').decode()
    s=re.sub(r'[^a-z0-9 ]+',' ',s.lower())
    return re.sub(r'\s+',' ',s).strip()

def mesma_pessoa(titular, signer):
    # True = mesmo nome escrito de outro jeito (typo, acento, abreviacao, so o
    # primeiro nome, apelido). False = pessoa de fato diferente.
    # Calibrado contra os 35 casos divergentes do Field em agosto/26 (35/35).
    from difflib import SequenceMatcher
    a,b=_sig_norm(titular),_sig_norm(signer)
    if not a or not b or a==b: return True
    sa,sb=a.replace(' ',''),b.replace(' ','')
    if sa.startswith(sb) or sb.startswith(sa): return True    # truncado / colado
    ta=[t for t in a.split() if len(t)>=2]
    tb=[t for t in b.split() if len(t)>=2]
    if not ta or not tb: return True
    Sa,Sb=set(ta),set(tb)
    if Sa<=Sb or Sb<=Sa: return True                          # subconjunto
    if ta[0] in Sb or tb[0] in Sa: return True                # primeiro nome bate
    if SequenceMatcher(None,sa,sb).ratio()>=0.82: return True # typo
    return False

def apply_signer(base, fields, base_path):
    if SIGNER_COL not in fields: fields.append(SIGNER_COL)
    for r in base: r[SIGNER_COL]=''
    p=os.path.join(os.path.dirname(os.path.abspath(base_path)), 'signer.csv')
    if not os.path.isfile(p): return 0
    sig={}
    with open(p, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            did=(r.get('deal_id') or '').strip(); nome=(r.get('signer_name') or '').strip()
            if did and nome: sig[did]=nome
    n=0
    for r in base:
        nome=sig.get((r.get('deal_id') or '').strip())
        if nome and not mesma_pessoa((r.get('current_client_name') or '').strip(), nome):
            r[SIGNER_COL]=nome; n+=1
    return n

def main():
    base_path=sys.argv[1]; work=sys.argv[2]
    os.makedirs(work, exist_ok=True)
    with open(base_path, encoding='utf-8-sig') as fh:
        rd=csv.DictReader(fh); fields=rd.fieldnames; base=list(rd)
    print('base:', os.path.basename(base_path), '|', len(base), 'linhas |', len(fields), 'cols')
    if EXCLUDE_DEALS:
        n0=len(base)
        base=[r for r in base if (r.get('deal_id') or '') not in EXCLUDE_DEALS]
        if len(base)!=n0:
            print('excluidos %d deal(s) duplicado(s): %s' % (n0-len(base), ', '.join(sorted(EXCLUDE_DEALS))))
    if len(base) < 2000:
        sys.exit('ABORT: base com %d linhas (<2000).' % len(base))
    for c in ('internal_sales_classification','deal_stage','latest_risk_analysis_created_at',
              'proposal_created_at','latest_contract_signature_signed_at','deal_lost_at','deal_id'):
        if c not in fields: sys.exit('ABORT: coluna ausente: '+c)
    if len(set(r['deal_stage'] for r in base)) <= 1:
        sys.exit('ABORT: base com um unico deal_stage.')
    ngap=apply_bronze_gap(base, fields, base_path)
    if ngap: print('bronze gap: %d deal(s) anexado(s) do bronze (gold atrasada)' % ngap)
    npatch,napp=augment_from_sbg(base, fields, base_path)
    if npatch or napp: print('augmento funil vivo: %d atualizado(s), %d anexado(s)' % (npatch,napp))
    ncorr=apply_risk_real(base, load_risk_real(base_path))
    if ncorr: print('risco real: %d deal(s) com resultado corrigido vs card818' % ncorr)
    nappr=apply_appr_date(base, load_appr_date(base_path))
    ncred=apply_credit_date(base, load_credit_date(base_path))
    print('data da aprovacao do CREDITO: %d deal(s) recarimbado(s) (trava de mes fechado ativa)' % ncred)
    nsig=apply_signer(base, fields, base_path)
    print('quem assinou: %d deal(s) assinado(s) por outra pessoa' % nsig)
    print('data da aprovacao no risco: %d deal(s) recarimbado(s) (Antecipa pago depois)' % nappr)
    fs=[r for r in base if r['internal_sales_classification']=='FS_Liora']
    # Operacao de campo: deals de Field Sales as vezes vem com classificacao
    # 'Outro' (tag errada). Para APROVADOS/analisados contamos pela operacao
    # (sales_team), nao so pela tag. Propostas/Aguardando seguem so FS_Liora.
    fs_field=[r for r in base if r['internal_sales_classification']=='FS_Liora' or (r.get('sales_team') or '').strip()=='Field Sales'
              or (r.get('sales_organization_name') or '').strip().upper()=='LIORA EVENTOS']  # Felipe 03/08: vendas LIORA EVENTOS (Joao Santos, vendedor Field mis-tagueado Inside) contam no resultado Field
    def dedup(rs):
        out=[]; seen=set()
        for r in rs:
            if r['deal_id'] in seen: continue
            seen.add(r['deal_id']); out.append(r)
        return out
    deals=dedup([r for r in fs_field if in_cur_month(r['latest_risk_analysis_created_at'])])
    prop =[r for r in fs if in_cur_month(r['proposal_created_at'])]
    agu  =dedup([r for r in fs if r['deal_stage']=='WAITING_DOCUMENTS'
                 and not (r['deal_lost_at'] or '').strip()
                 and sig_recent(r['latest_contract_signature_signed_at'])])
    # Recorte Antecipa (Inside Sales / produto de credito LIORA_ANTECIPA_PF|PJ):
    # todas as propostas do produto Antecipa geradas no mes corrente (sem dedup,
    # sem filtro FS_Liora). Alimenta a aba "Antecipa" do desktop.
    antecipa=[r for r in base
              if (r.get('product_name') or '').strip().upper().startswith('LIORA_ANTECIPA')
              and in_cur_month(r.get('proposal_created_at'))]
    # Recorte HISTORICO: propostas do FIELD (GD + Antecipa de campo) dos ultimos
    # HIST_MESES meses, coorte pela data da proposta. Aba "Historico" do desktop.
    historico=[r for r in fs_field if in_hist_window(r.get('proposal_created_at'))]

    if not deals or not prop or not agu:
        sys.exit('ABORT: recorte vazio (deals=%d prop=%d agu=%d).' % (len(deals),len(prop),len(agu)))
    def write(name, rs):
        p=os.path.join(work, name+'.csv')
        with open(p,'w',newline='',encoding='utf-8') as fh:
            w=csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rs)
    write('deals', deals); write('propostas_geradas', prop); write('aguardando_documentos', agu)
    if antecipa: write('antecipa_geradas', antecipa)
    if historico: write('historico_vendedor', historico)
    print('mes %04d-%02d | deals=%d propostas=%d aguardando=%d antecipa=%d historico=%d (%s)' % (TODAY.year,TODAY.month,len(deals),len(prop),len(agu),len(antecipa),len(historico),' '.join(sorted(HIST_JANELA))))

if __name__=='__main__':
    main()
