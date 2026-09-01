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

# ---- CALIBRACAO ANTECIPA: risco E credito (Felipe 01/09/2026) -------------
# Espelha o process_lideranca.py (os 2 dashboards tem de bater). Ate 31/08
# bastava UMA das duas analises; agora o Antecipa so conta como aprovado com
# risco in (APPROVED, APPROVED_PENDING_CREDIT) E credito == 'approved'.
# Sem excecao para credito ausente - a excecao e' o FORCE_APPROVED manual.
# NAO afeta GD: o gate so roda quando o produto e' ANTECIPA.
ANT_RISK_OK = {'APPROVED', 'APPROVED_PENDING_CREDIT'}
# UNICA excecao ao gate (Felipe 01/09): deal que JA MIGROU nao e' bloqueado.
# Caso: LUIS CLAUDIO SANTOS MARQUES ME (30/06, 15,402 MWh) - ACTIVE MEMBER +
# ops APROVADO + risco APPROVED, zero analise de credito na base.
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
    """True quando o Antecipa esta aprovado nas DUAS analises (risco + credito)."""
    if (r.get('latest_risk_analysis_result') or '').strip() not in ANT_RISK_OK:
        return False
    if credito_ok is None:
        credito_ok = (r.get('latest_credit_analysis_result') or '').strip().lower() == 'approved'
    if not credito_ok:
        return False
    if (r.get('deal_credit_stage') or '').strip() in CREDIT_STAGE_NEG:
        return False
    return True
CONSUMPTION_OVERRIDE = {  # cliente (upper/strip) -> MWh; temp ate base corrigir
 'FRANCISCO ALDECI DE QUEIROZ FERNANDES': 5.86,  # base mostra 0.59 (Felipe 03/07)
 'GABRIEL LUCHIARI ALBERTO': 0.567,  # base mostra 0.13; fatura R$526/615 SP CPFL (Felipe 08/07)
 'PERFECTA VIDROS E ALUMINIOS EIRELI': 0.89,  # base mostra 0.19 (Felipe 07/07, ajuste p/ 0,890)
 'CHEVROFOR COM PECAS E ACESSORIOS LTDA': 1.21,  # base mostra 0.50 (Felipe 07/07)
 'MÁRCIO PEREIRA PINTO': 5.866,  # aprovado manual, base mostra 1.3 (Felipe 10/07)
 'DRAX CENTRO AUTOMOTIVO LTDA': 4.311,
}
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

def appr_date_of(deal_id, calc, aprovado=True):
    """Data de aprovacao final: mapa > ledger > calculada. Nunca anda para frente."""
    fix = RISK_APPR_DATE.get(deal_id)
    d = fix or (calc or '')
    if aprovado:
        prev = PREV_APROV.get(deal_id) or ''
        if prev and (not d or prev < d):
            d = prev
    return d or ''

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

# FORCE_NOTE: nota que aparece no card do cliente forcado (Felipe 01/09: "considerado
# no card, mas cliente reprovado e o motivo"). Prefixa o campo 'motivo' do rawData —
# o card do desktop e a aba de detalhe do mobile imprimem esse campo. Chave = deal_id.
FORCE_NOTE = {
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
        _prod_ov = PRODUCT_OVERRIDE.get(did, {})  # venda Antecipa registrada com produto errado (Felipe 18/08)
        credito_ok = _prod_ov.get('credito_ok', _credit == 'approved')  # Felipe 06/08: crédito aprovado conta como aprovado
        # Alinha ao desktop (definição oficial isAprovado): conta como aprovado se risco
        # APPROVED, OU status "aprovado", OU stage REQUEST_TITULARIDADE (fallback p/ deal
        # que avançou sem risco APPROVED). Nunca conta DENIED nem BGC_PARCEIRO (validação
        # Antecipa, ainda não aprovado) — EXCETO quando o crédito do Antecipa já foi aprovado.
        _apc = apc_ok(r)  # Felipe 18/08: APPROVED_PENDING_CREDIT = aprovado (falta só o pagamento)
        if did in FORCE_DENIED: _apc=False; credito_ok=False; _risk='DENIED'  # reprovado manual (Felipe)
        # Felipe 01/09: Antecipa so conta com as DUAS analises aprovadas (ver ant_ok).
        _ant_bloq = is_antecipa(r) and not ant_ok(r, credito_ok) and not ant_migrado(r) and not forced
        if _ant_bloq: _apc=False; credito_ok=False
        _reached = (_risk=='APPROVED') or _apc or ('aprovado' in _status) or (r['deal_stage']=='REQUEST_TITULARIDADE')
        # Felipe 25/08: PERDIDO nunca conta como aprovado, em qualquer estagio. Antes o
        # credito_ok e o _apc passavam na frente do teste de perdido e cliente que
        # desistiu seguia contando (Dileuda 13/08, Edilaine 24/08). Excecao: 'troca de
        # titularidade' (perda tecnica) e a LOST_IGNORE. FORCE_APPROVED continua ganhando:
        # e' decisao manual explicita do Felipe.
        _lost = (bool((r['deal_lost_at'] or '').strip())
                 and (r.get('deal_lost_reason') or '').strip().lower() in LOST_DESFAZ
                 and (cli or '').strip().upper() not in LOST_IGNORE)
        approved = forced or (not _lost and not _ant_bloq and (credito_ok or _apc or (_reached and _risk!='DENIED' and r['deal_stage']!='BGC_PARCEIRO')))
        # data do risco: o mapa RISK_APPR_DATE (aprovacao no risco) manda na analise
        # mais nova, que no Antecipa e' a do pagamento do credito (Felipe 25/08)
        _rdt = pdate(appr_date_of(did, iso(pdate(r['latest_risk_analysis_created_at'])), approved))
        aprov = (iso(_rdt or pdate(r['deal_created_at'])) if approved else '')
        created = pdate(r['deal_created_at'])
        basis = (_rdt or created) if approved else created
        if forced and FORCE_APPROVED[did]:
            aprov = FORCE_APPROVED[did]; basis = pdate(FORCE_APPROVED[did])  # data de aprovação manual
        try: idle=int(float(r['idle_days'])) if r['idle_days'].strip()!='' else 0
        except: idle=0
        out.append({
            'c':cli,'sig':(r.get('signer_name') or '').strip(),'s':s,'mwh':CONSUMPTION_OVERRIDE_BY_ID.get(r['deal_id'], CONSUMPTION_OVERRIDE.get((cli or '').strip().upper(), pfloat(r['current_consumption_filled']))),
            'stage':('REQUEST_TITULARIDADE' if ((forced or _apc) and r['deal_stage'] in ('BGC_PARCEIRO','BACKGROUND_CHECKING')) else r['deal_stage']),'status':r['ops_tt_status'],'idle':idle,
            'city':r['current_client_city'],'state':r['current_client_state'],
            'dist':DIST_MAP.get(r['distributor_short_name'], r['distributor_short_name']),
            'produto':_prod_ov.get('produto', (r.get('product_name') or '').strip()),
            'credito_ok':(False if _ant_bloq else credito_ok),'ant_bloq':bool(_ant_bloq),'credito':credit_pt(r.get('deal_credit_stage')),'apc':bool(_apc),'fapr':bool(forced),'rapr':(_risk=='APPROVED'),
            'deal_id':did,'uc':uc_map.get(did,''),'tel':r['client_phone_number'],'cnpj':r['current_client_cnpj'],'cpf':r['current_client_cpf'],
            'fatura':pfloat(r['current_total_bill_cost (R$)']),'semana':semana(basis),
            'lost_at':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_at']),'lost_reason':('' if (forced or (cli or '').strip().upper() in LOST_IGNORE) else r['deal_lost_reason']),
            'motivo':force_note(r.get('deal_id'), (('CANCELADO — '+(r.get('deal_lost_reason') or '').strip()) if ((r.get('latest_risk_analysis_result') or '').strip()=='APPROVED' and (r.get('deal_lost_at') or '').strip() and r.get('deal_stage')=='BACKGROUND_CHECKING' and (r.get('deal_lost_reason') or '').strip().lower()!='troca de titularidade') else clean_obs(r.get('latest_risk_analysis_comments')))),
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
            'current_client_name':cli,'sig':(r.get('signer_name') or '').strip(),'current_client_state':r['current_client_state'],
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
