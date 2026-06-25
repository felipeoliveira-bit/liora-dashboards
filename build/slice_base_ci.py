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
    # (vazio) Carla Beserra/Bezerra: confirmado 25/06 que NAO era duplicata -
    # 2 UCs distintas do mesmo CPF (faturas/consumo/contratos diferentes). As duas contam.
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
def sig_recent(s):
    t=ymd(s); return t is not None and t>=PREV

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
    fs=[r for r in base if r['internal_sales_classification']=='FS_Liora']
    # Operacao de campo: deals de Field Sales as vezes vem com classificacao
    # 'Outro' (tag errada). Para APROVADOS/analisados contamos pela operacao
    # (sales_team), nao so pela tag. Propostas/Aguardando seguem so FS_Liora.
    fs_field=[r for r in base if r['internal_sales_classification']=='FS_Liora' or (r.get('sales_team') or '').strip()=='Field Sales']
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
    if not deals or not prop or not agu:
        sys.exit('ABORT: recorte vazio (deals=%d prop=%d agu=%d).' % (len(deals),len(prop),len(agu)))
    def write(name, rs):
        p=os.path.join(work, name+'.csv')
        with open(p,'w',newline='',encoding='utf-8') as fh:
            w=csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rs)
    write('deals', deals); write('propostas_geradas', prop); write('aguardando_documentos', agu)
    print('mes %04d-%02d | deals=%d propostas=%d aguardando=%d' % (TODAY.year,TODAY.month,len(deals),len(prop),len(agu)))

if __name__=='__main__':
    main()
