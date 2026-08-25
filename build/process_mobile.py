import csv, json, datetime, re, glob

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
 'karianine.sampaio@lioraenergia.com.br':'Karianine Sampaio', # nova 18/08
 'olavocavalcanti@lioraenergia.com.br':'Olavo Cavalcanti','olavo.cavaldanti@lioraenergia.com.br':'Olavo Cavalcanti','paulo.lima@lioraenergia.com.br':'Paulo Lima',  # novos 24/08 (Olavo Cavalcanti - Mossoro/RN Interior; Paulo Lima - Ribeirao)
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
 'Briel Barbosa':'SPI','Olímpio Filho':'Ribeirão Preto SPI','Fábio Rodrigues':'Ribeirão Preto SPI',
 'Karianine Sampaio':'Ribeirão Preto SPI',  # novos 10/08
 'Olavo Cavalcanti':'RN Interior',
 'Paulo Lima':'Ribeirão Preto SPI',  # novos 24/08 (Olavo Cavalcanti - Mossoro/RN Interior; Paulo Lima - Ribeirao)
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
 'CHECKING_DEPOSIT_METHOD':'VERIFICANDO_FORMA_DE_PAGAMENTO',
}
def credit_pt(s):
    s=(s or '').strip()
    return CREDIT_STAGE_PT.get(s, s)

# ---- APPROVED_PENDING_CREDIT conta como aprovado (Felipe 18/08) -----------
# Espelha o process_lideranca.py (os 2 dashboards tem de bater): o risco
# APPROVED_PENDING_CREDIT JA E' aprovacao de risco - falta so o pagamento do
# Antecipa. Pix nao gera analise de credito, entao esses clientes ficavam de fora
# e precisavam de FORCE_APPROVED na mao. Excecao: credito NEGADO/REJEITADO.
CREDIT_NEG = {'denied', 'rejected', 'refused'}
CREDIT_STAGE_NEG = {'CREDIT_ANALISYS_REJECTED', 'PAYMENT_REJECTED'}
def apc_ok(r):
    if (r.get('latest_risk_analysis_result') or '').strip() != 'APPROVED_PENDING_CREDIT':
        return False
    if (r.get('latest_credit_analysis_result') or '').strip().lower() in CREDIT_NEG:
        return False
    if (r.get('deal_credit_stage') or '').strip() in CREDIT_STAGE_NEG:
        return False
    return True
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
# PRODUCT_OVERRIDE: deal_id -> produto/credito_ok. Venda feita como Antecipa mas registrada
# no CRM com outro produto (ex.: LIORA_F_). Sem isso o deal nao passa no isAntecipaDeal()
# (credito_ok && /ANTECIPA/) e perde o bonus 1,5x da Campanha da Semana. Remover quando o CRM corrigir.
PRODUCT_OVERRIDE = {
 '02f320f6-e275-449f-b385-aaec0dfcc541': {'produto':'LIORA_ANTECIPA_PJ','credito_ok':True},  # MARCELO OLIVEIRA VENERANDO (Odirley/CE, CNPJ 15329657000174, 2.62 MWh, aprovado 17/08) - vendido como Antecipa, base traz LIORA_F_ (Felipe 18/08)
}
CONSUMPTION_OVERRIDE = {  # cliente (upper/strip) -> MWh; temp ate base corrigir
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES': 5.86,  # base mostra 0.59 (Felipe 03/07)
 'GABRIEL LUCHIARI ALBERTO': 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 'PERFECTA VIDROS E ALUMINIOS EIRELI': 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 'CHEVROFOR COM PECAS E ACESSORIOS LTDA': 1.21,  # base mostra 0.50 (Felipe 07/07)
 'MÁRCIO PEREIRA PINTO': 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
 'DRAX CENTRO AUTOMOTIVO LTDA': 4.311,
}
FORCE_APPROVED = {
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

# ---- DATA DA VENDA = APROVACAO NO RISCO (Felipe 25/08) --------------------
# O Antecipa gera uma SEGUNDA analise de risco APPROVED quando o CREDITO e' pago,
# dias depois do APPROVED_PENDING_CREDIT que ja aprovou a venda. Como a data vem de
# latest_risk_analysis_created_at (a analise mais nova), a venda pulava para a semana
# do PAGAMENTO e o vendedor era pago DE NOVO por um cliente ja pago na semana anterior
# (relato do Joao 25/08: Diogenes e Bruna do Fabio, risco 22/08, reapareceram em 24/08).
# A regra definitiva esta no slice: RISK_SQL (build/mb_export.py) devolve appr_created =
# inicio da sequencia aprovadora, e o slice recarimba latest_risk_analysis_created_at.
# Este mapa e' o CINTO DE SEGURANCA: vale enquanto o export nao trouxer a coluna nova.
# Deals ja aprovados - so corrige a DATA (nao forca aprovacao). Pode sair quando o log
# do slice mostrar 'data da aprovacao no risco: N deal(s) recarimbado(s)'.
RISK_APPR_DATE = {
 'b43f455a-0b07-455f-83b6-8558186432d2': '2026-08-19',  # DANIELA CAMPOS AMARAL (Antecipa PF, Ederson Silva/SPI) - risco APC 19/08 18:17, pagamento 24/08 12:08
 '0dadf9d4-4e2a-44aa-94f3-feb2236c0e15': '2026-08-20',  # DEIVID MARCIEL DA SILVA SAMPAIO (Antecipa PF, Karianine/Ribeirao) - risco APC 20/08 16:00, pagamento 24/08 11:38
 '4e4fdd43-0a52-4199-9a21-1ce4de5d06b5': '2026-08-20',  # JOSE PAULO APARECIDO CORREIA (Antecipa PF, Karianine/Ribeirao) - risco APC 20/08 16:55, pagamento 24/08 11:56
 '81b409e1-1596-47f5-aaa8-1ea27d44c58a': '2026-08-20',  # EMILE RAYLANE DOS SANTOS SILVA (Antecipa PF, Tamires Costa) - risco APC 20/08 18:47, pagamento 24/08 11:50
 '5a3e3021-b5d2-482a-ac49-fd720f76beb0': '2026-08-20',  # MARCELO BRAZ DA SILVA (Antecipa PF, Ederson Silva/SPI) - risco APC 20/08 19:09, pagamento 24/08 11:30
 '7a7e8fed-a442-42be-9d33-6e99c1a63e2b': '2026-08-21',  # VANESSA PAULA GOMES DA SILVA (Antecipa PF, Lucas Santos) - risco APC 21/08 13:20, pagamento 24/08 11:19
 'ec28eba4-c245-4807-bcef-c4722c0197b9': '2026-08-22',  # DIOGENES DE FIGUEIREDO LIMA JUNIOR (Antecipa PF, Fabio Rodrigues/Ribeirao) - risco APC 22/08 16:26, pagamento 24/08 21:57
 '98d40580-78bd-4a62-b1d1-7bf346c549a0': '2026-08-22',  # BRUNA HELENA NUNES DE LACERDA (Antecipa PJ, Fabio Rodrigues/Ribeirao) - risco APC 22/08 18:05, pagamento 24/08 22:03
}
# Felipe 25/08 (final): a lista e' INVERTIDA de proposito. So estes motivos DESFAZEM a
# venda aprovada: o cliente desistiu, ou o credito foi reprovado. Todo o resto mantem o
# aprovado. 'UC Desligada' (16 clientes / 30,77 MWh em agosto) NAO e' reprovacao: e' o
# canal de Ops que nao consegue avancar com a titularidade porque a UC esta desligada -
# a venda foi aprovada no risco e continua valendo. Idem 'Telefone incorreto',
# 'Baixa Renda / NIS', 'placa solar'. Risco DENIED e credito negado ja caem nos testes
# proprios, sem depender do motivo da perda.
LOST_DESFAZ = {'cliente desistiu', 'reprovado na análise de crédito'}

LOST_IGNORE = {  # ignora lost_at/lost_reason (falso 'nao aceito pela distribuidora')
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES',  # reprovado e erro; ignorar (Felipe 03/07)
 'ANTÔNIO EDMILSON LEITE',  # dup denied em BGC, forçado aprovado (Felipe 15/07)
}
# INJECT_DEALS: deals ausentes da base viva, adicionados manualmente (Felipe).
INJECT_DEALS = []  # 25/08: Marli Merces (f8ba2c6d) e Chesser 2a UC (e607c712) ja estao na gold
                   # viva com risco APPROVED -> o inject virava DUPLICATA no desktop
                   # (deals + INJECT_DEALS nao deduplica). Removidos conforme o proprio
                   # comentario original ("remover quando card818 refletir").
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
        _prod_ov = PRODUCT_OVERRIDE.get(did, {})  # venda Antecipa registrada com produto errado (Felipe 18/08)
        # Alinha ao desktop (definição oficial isAprovado): conta como aprovado se risco
        # APPROVED, OU status "aprovado", OU stage REQUEST_TITULARIDADE (fallback p/ deal
        # que avançou sem risco APPROVED). Nunca conta DENIED nem BGC_PARCEIRO (validação
        # Antecipa, ainda não aprovado) — EXCETO quando o crédito do Antecipa já foi aprovado.
        _apc = apc_ok(r)  # Felipe 18/08: APPROVED_PENDING_CREDIT = aprovado (falta só o pagamento)
        _reached = (_risk=='APPROVED') or _apc or ('aprovado' in _status) or (r['deal_stage']=='REQUEST_TITULARIDADE')
        # Felipe 25/08: PERDIDO nunca conta como aprovado, em qualquer estagio. Antes o
        # credito_ok e o _apc passavam na frente do teste de perdido e cliente que
        # desistiu seguia contando (Dileuda 13/08, Edilaine 24/08). Excecao: 'troca de
        # titularidade' (perda tecnica) e a LOST_IGNORE. FORCE_APPROVED continua ganhando:
        # e' decisao manual explicita do Felipe.
        _lost = (bool((r['deal_lost_at'] or '').strip())
                 and (r.get('deal_lost_reason') or '').strip().lower() in LOST_DESFAZ
                 and (cli or '').strip().upper() not in LOST_IGNORE)
        approved = forced or (not _lost and (credito_ok or _apc or (_reached and _risk!='DENIED' and r['deal_stage']!='BGC_PARCEIRO')))
        # data do risco: o mapa RISK_APPR_DATE (aprovacao no risco) manda na analise
        # mais nova, que no Antecipa e' a do pagamento do credito (Felipe 25/08)
        _rdt = pdate(RISK_APPR_DATE.get(did)) or pdate(r['latest_risk_analysis_created_at'])
        aprov = (iso(_rdt or pdate(r['deal_created_at'])) if approved else '')
        created = pdate(r['deal_created_at'])
        basis = (_rdt or created) if approved else created
        if forced and FORCE_APPROVED[did]:
            aprov = FORCE_APPROVED[did]; basis = pdate(FORCE_APPROVED[did])  # data de aprovação manual
        try: idle=int(float(r['idle_days'])) if r['idle_days'].strip()!='' else 0
        except: idle=0
        out.append({
            'c':cli,'s':s,'mwh':CONSUMPTION_OVERRIDE_BY_ID.get(r['deal_id'], CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled']))),
            'stage':('REQUEST_TITULARIDADE' if ((forced or _apc) and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']),'status':r['ops_tt_status'],'idle':idle,
            'city':r['current_client_city'],'state':r['current_client_state'],
            'dist':DIST_MAP.get(r['distributor_short_name'], r['distributor_short_name']),
            'produto':_prod_ov.get('produto', (r.get('product_name') or '').strip()),
            'credito_ok':_prod_ov.get('credito_ok', credito_ok),'credito':credit_pt(r.get('deal_credit_stage')),'apc':bool(_apc),'fapr':bool(forced),'rapr':(_risk=='APPROVED'),
            'deal_id':did,'uc':uc_map.get(did,''),'tel':r['client_phone_number'],'cnpj':r['current_client_cnpj'],'cpf':r['current_client_cpf'],
            'fatura':pfloat(r['current_total_bill_cost (R$)']),'semana':semana(basis),
            'lost_at':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_at']),'lost_reason':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_reason']),
            'motivo':(('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else clean_obs(r.get('latest_risk_analysis_comments'))),
            'date':iso(created),'aprov_date':aprov,
            'docs':docs_map.get((r.get('latest_contract_id') or '').strip(),''),
            'cid':(r.get('latest_contract_id') or '').strip(),   # cruza c/ a planilha de pagamentos do Antecipa (action pagAntecipa)
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
