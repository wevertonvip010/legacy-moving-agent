"""
agent/tools.py
Definicao e execucao de todas as ferramentas do agente Legacy Moving.
Cada ferramenta mapeia para um endpoint da API do ERP.
Fase 2: Adicionadas ferramentas de agenda (Google Calendar) e notificacoes.
Fase 3: Drive inteligente + Analytics proativo.
Fase 4: Preferencias e contexto individual por usuario.
"""
import logging
from datetime import datetime
from integrations.legacy_api import LegacyAPI

logger = logging.getLogger(__name__)
api = LegacyAPI()

# ── DEFINICAO DAS FERRAMENTAS (formato Anthropic tool use) ─────────────────

TOOLS = [
{
"name": "consultar_os_do_dia",
"description": "Consulta as Ordens de Servico (mudancas) programadas para hoje ou uma data especifica. Use quando o usuario perguntar sobre a agenda do dia, mudancas de hoje, o que tem hoje, etc.",
"input_schema": {
"type": "object",
"properties": {
"data": {
"type": "string",
"description": "Data no formato YYYY-MM-DD. Se nao informada, usa hoje."
}
},
"required": []
}
},
{
"name": "consultar_os_por_cliente",
"description": "Busca todas as OS de um cliente pelo nome. Use quando o usuario mencionar o nome de um cliente e quiser ver suas mudancas.",
"input_schema": {
"type": "object",
"properties": {
"nome_cliente": {
"type": "string",
"description": "Nome ou parte do nome do cliente"
}
},
"required": ["nome_cliente"]
}
},
{
"name": "criar_lead",
"description": "Cria um novo lead (potencial cliente) no sistema. Use quando o usuario informar dados de um novo contato interessado em mudanca.",
"input_schema": {
"type": "object",
"properties": {
"nome": {"type": "string", "description": "Nome completo do lead"},
"telefone": {"type": "string", "description": "Telefone com DDD"},
"email": {"type": "string", "description": "Email (opcional)"},
"origem": {"type": "string", "description": "Como chegou: indicacao|instagram|google|organizer|direto"},
"tipo_servico": {"type": "string", "description": "Tipo: residencial|comercial|guarda_moveis|desmontagem"},
"cidade_origem": {"type": "string", "description": "Cidade de origem da mudanca"},
"cidade_destino": {"type": "string", "description": "Cidade de destino"},
"observacoes": {"type": "string", "description": "Observacoes adicionais"}
},
"required": ["nome", "telefone"]
}
},
{
"name": "consultar_leads",
"description": "Consulta leads no sistema. Pode filtrar por status ou buscar os mais recentes.",
"input_schema": {
"type": "object",
"properties": {
"status": {"type": "string", "description": "Status: novo|em_contato|orcamento_enviado|convertido|perdido"},
"limite": {"type": "integer", "description": "Quantidade de leads a retornar (padrao 10)"}
},
"required": []
}
},
{
"name": "registrar_despesa",
"description": "Registra uma despesa no financeiro da empresa. Use quando o usuario informar um gasto, pagamento ou custo.",
"input_schema": {
"type": "object",
"properties": {
"descricao": {"type": "string", "description": "Descricao da despesa"},
"valor": {"type": "number", "description": "Valor em reais"},
"categoria": {"type": "string", "description": "Categoria: combustivel|pedagio|alimentacao|materiais|equipe|manutencao|aluguel|outros"},
"os_id": {"type": "integer", "description": "ID da OS relacionada (opcional)"}
},
"required": ["descricao", "valor", "categoria"]
}
},
{
"name": "consultar_resumo_financeiro",
"description": "Consulta o resumo financeiro do mes atual: receitas, despesas e lucro.",
"input_schema": {
"type": "object",
"properties": {
"mes": {"type": "integer", "description": "Mes (1-12). Se nao informado, usa o mes atual."},
"ano": {"type": "integer", "description": "Ano. Se nao informado, usa o ano atual."}
},
"required": []
}
},
{
"name": "consultar_estoque",
"description": "Verifica o nivel de estoque dos materiais (caixas, plastico bolha, fita, etc.).",
"input_schema": {
"type": "object",
"properties": {
"material": {"type": "string", "description": "Nome ou parte do nome do material. Se vazio, retorna todos."}
},
"required": []
}
},
{
"name": "consultar_equipe_disponivel",
"description": "Verifica quais funcionarios estao disponiveis para uma data.",
"input_schema": {
"type": "object",
"properties": {
"data": {"type": "string", "description": "Data no formato YYYY-MM-DD. Se nao informada, usa hoje."}
},
"required": []
}
},
{
"name": "registrar_avaria",
"description": "Registra uma avaria (dano em item do cliente) durante uma mudanca. Pode incluir foto.",
"input_schema": {
"type": "object",
"properties": {
"os_id": {"type": "integer", "description": "ID da Ordem de Servico"},
"descricao": {"type": "string", "description": "Descricao detalhada da avaria"},
"item_danificado": {"type": "string", "description": "Nome do item danificado"},
"foto_url": {"type": "string", "description": "URL da foto (se houver)"}
},
"required": ["os_id", "descricao", "item_danificado"]
}
},
{
"name": "consultar_boxes_guarda_moveis",
"description": "Consulta os boxes do servico de guarda-moveis: ocupados, livres e seus conteudos.",
"input_schema": {
"type": "object",
"properties": {
"status": {"type": "string", "description": "Status: todos|ocupado|livre"}
},
"required": []
}
},
{
"name": "consultar_cliente",
"description": "Busca informacoes completas de um cliente pelo nome ou telefone.",
"input_schema": {
"type": "object",
"properties": {
"busca": {"type": "string", "description": "Nome ou telefone do cliente"}
},
"required": ["busca"]
}
},
{
"name": "consultar_programacao_semana",
"description": "Retorna a programacao completa da semana: todas as OS agendadas.",
"input_schema": {
"type": "object",
"properties": {},
"required": []
}
},
{
"name": "consultar_ranking_equipe",
"description": "Consulta o ranking de desempenho da equipe: mudancas realizadas, avaliacao, etc.",
"input_schema": {
"type": "object",
"properties": {
"periodo": {"type": "string", "description": "Periodo: mes_atual|semana|30_dias"}
},
"required": []
}
},
{
"name": "criar_tarefa",
"description": "Cria uma tarefa no sistema com prazo e responsavel. Use para to-dos, pendencias, follow-ups.",
"input_schema": {
"type": "object",
"properties": {
"titulo": {"type": "string", "description": "Titulo da tarefa"},
"descricao": {"type": "string", "description": "Descricao detalhada"},
"responsavel": {"type": "string", "description": "Nome do responsavel"},
"prazo": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
"prioridade": {"type": "string", "description": "Prioridade: baixa|media|alta|urgente"}
},
"required": ["titulo", "prazo"]
}
},
{
"name": "consultar_tarefas",
"description": "Lista tarefas do sistema. Pode filtrar por responsavel ou status.",
"input_schema": {
"type": "object",
"properties": {
"responsavel": {"type": "string", "description": "Nome do responsavel (opcional)"},
"status": {"type": "string", "description": "Status: pendente|em_andamento|concluida|vencida"},
"limite": {"type": "integer", "description": "Quantidade maxima (padrao 10)"}
},
"required": []
}
},
{
"name": "agenda_listar_eventos",
"description": "Lista eventos do Google Calendar. Use para ver compromissos, reunioes, mudancas agendadas no calendario.",
"input_schema": {
"type": "object",
"properties": {
"periodo": {"type": "string", "description": "Periodo: hoje|semana|proximo_mes. Padrao: hoje"},
"busca": {"type": "string", "description": "Texto para filtrar eventos (opcional)"}
},
"required": []
}
},
{
"name": "agenda_criar_evento",
"description": "Cria um evento no Google Calendar. Use para agendar reunioes, visitas, compromissos ou adicionar mudancas na agenda.",
"input_schema": {
"type": "object",
"properties": {
"titulo": {"type": "string", "description": "Titulo do evento"},
"data": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
"hora_inicio": {"type": "string", "description": "Hora de inicio no formato HH:MM"},
"hora_fim": {"type": "string", "description": "Hora de fim no formato HH:MM (opcional, padrao +1h)"},
"descricao": {"type": "string", "description": "Descricao ou notas do evento"},
"local": {"type": "string", "description": "Endereco ou local do evento"},
"lembrete_minutos": {"type": "integer", "description": "Minutos antes para lembrete (padrao: 30)"}
},
"required": ["titulo", "data", "hora_inicio"]
}
},
{
"name": "agenda_criar_evento_os",
"description": "Cria automaticamente um evento no Google Calendar para uma Ordem de Servico de mudanca.",
"input_schema": {
"type": "object",
"properties": {
"numero_os": {"type": "string", "description": "Numero da OS"},
"cliente": {"type": "string", "description": "Nome do cliente"},
"data": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
"hora": {"type": "string", "description": "Hora de inicio no formato HH:MM"},
"origem": {"type": "string", "description": "Endereco de origem"},
"destino": {"type": "string", "description": "Endereco de destino"},
"motorista": {"type": "string", "description": "Nome do motorista (opcional)"}
},
"required": ["numero_os", "cliente", "data", "hora", "origem", "destino"]
}
},
{
"name": "notificar_equipe",
"description": "Envia uma mensagem/notificacao para membros especificos da equipe via WhatsApp. Use para avisos urgentes, comunicados, etc.",
"input_schema": {
"type": "object",
"properties": {
"mensagem": {"type": "string", "description": "Texto da mensagem a enviar"},
"cargo": {"type": "string", "description": "Cargo alvo: todos|admin|supervisor|motorista|operacional|comercial|financeiro"},
"numeros": {"type": "array", "items": {"type": "string"}, "description": "Lista de numeros especificos (alternativa ao cargo)"}
},
"required": ["mensagem"]
}
},,
{
"name": "drive_salvar_arquivo",
"description": "Salva um arquivo (imagem, documento, comprovante) no Google Drive. Use quando o usuario enviar uma midia e quiser arquivar, ou quando quiser salvar um documento de uma OS.",
"input_schema": {
"type": "object",
"properties": {
"url": {"type": "string", "description": "URL do arquivo a salvar"},
"nome": {"type": "string", "description": "Nome do arquivo (ex: comprovante_os123.jpg)"},
"categoria": {"type": "string", "description": "Categoria: avarias|contratos|comprovantes|fotos_os|orcamentos|relatorios|outros"},
"descricao": {"type": "string", "description": "Descricao do arquivo"},
"os_id": {"type": "integer", "description": "ID da OS relacionada (opcional)"}
},
"required": ["url", "nome"]
}
},
{
"name": "drive_buscar_arquivos",
"description": "Busca arquivos salvos no Google Drive por descricao, categoria ou OS. Use quando o usuario perguntar por documentos, fotos ou arquivos de uma OS ou cliente.",
"input_schema": {
"type": "object",
"properties": {
"query": {"type": "string", "description": "Texto para buscar no nome ou descricao"},
"categoria": {"type": "string", "description": "Filtrar por categoria: avarias|contratos|comprovantes|fotos_os|orcamentos|relatorios|outros"},
"os_id": {"type": "integer", "description": "Filtrar por OS especifica"}
},
"required": []
}
},
{
"name": "drive_listar_arquivos_os",
"description": "Lista todos os arquivos (fotos, documentos) de uma OS especifica no Drive.",
"input_schema": {
"type": "object",
"properties": {
"os_id": {"type": "integer", "description": "ID da OS"}
},
"required": ["os_id"]
}
},
{
"name": "gerar_analise_proativa",
"description": "Gera um relatorio proativo com alertas e insights sobre financeiro, operacional, estoque e leads. Use quando o admin pedir uma analise geral ou diagnostico do negocio.",
"input_schema": {
"type": "object",
"properties": {
"modulo": {"type": "string", "description": "Modulo especifico: financeiro|operacional|estoque|leads|geral (padrao: geral)"}
},
"required": []
}
},
{
"name": "configurar_preferencias",
"description": "Configura as preferencias do usuario: quais notificacoes receber, modo verboso, etc. Use quando o usuario quiser personalizar o comportamento do agente.",
"input_schema": {
"type": "object",
"properties": {
"preferencia": {"type": "string", "description": "Nome da preferencia: resumo_diario|alertas_financeiros|alertas_operacionais|alertas_estoque|alertas_leads|modo_verboso"},
"valor": {"type": "boolean", "description": "true para ativar, false para desativar"}
},
"required": ["preferencia", "valor"]
}
},
{
"name": "consultar_meu_contexto",
"description": "Mostra o contexto atual do usuario: preferencias configuradas, ultima OS vista, historico de acoes recentes. Use quando o usuario perguntar sobre suas configuracoes.",
"input_schema": {
"type": "object",
"properties": {},
"required": []
}
}
]

# ── MAPEAMENTO CARGO → FERRAMENTAS PERMITIDAS ──────────────────────────────

TOOLS_POR_ROLE = {
"admin": [t["name"] for t in TOOLS],  # Admin tem tudo
"supervisor": [
"consultar_os_do_dia", "consultar_os_por_cliente", "consultar_programacao_semana",
"consultar_cliente", "consultar_equipe_disponivel", "consultar_ranking_equipe",
"registrar_despesa", "consultar_resumo_financeiro", "consultar_estoque",
"criar_lead", "consultar_leads", "registrar_avaria",
"consultar_boxes_guarda_moveis", "criar_tarefa", "consultar_tarefas",
"agenda_listar_eventos", "agenda_criar_evento", "agenda_criar_evento_os",
"notificar_equipe",
"drive_salvar_arquivo", "drive_buscar_arquivos", "drive_listar_arquivos_os",
"gerar_analise_proativa", "configurar_preferencias", "consultar_meu_contexto",
],
"motorista": [
"consultar_os_do_dia", "consultar_programacao_semana",
"registrar_despesa", "registrar_avaria",
"agenda_listar_eventos",
],
"operacional": [
"consultar_os_do_dia", "consultar_programacao_semana",
"consultar_estoque", "registrar_avaria",
"consultar_equipe_disponivel", "agenda_listar_eventos",
"consultar_boxes_guarda_moveis",
],
"comercial": [
"criar_lead", "consultar_leads", "consultar_cliente",
"consultar_os_por_cliente", "criar_tarefa", "consultar_tarefas",
"agenda_listar_eventos", "agenda_criar_evento",
],
"financeiro": [
"registrar_despesa", "consultar_resumo_financeiro",
"consultar_os_do_dia", "consultar_estoque",
"consultar_tarefas",
],
"bloqueado": [],
}


def get_tools_for_role(role: str) -> list:
    """Retorna a lista de ferramentas filtradas pelo cargo do usuario."""
    allowed = TOOLS_POR_ROLE.get(role, [])
    return [t for t in TOOLS if t["name"] in allowed]


# ── EXECUCAO DAS FERRAMENTAS ───────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict, user_context: dict = None) -> str:
    """Executa uma ferramenta e retorna o resultado como string."""
    handlers = {
        "consultar_os_do_dia": _consultar_os_do_dia,
        "consultar_os_por_cliente": _consultar_os_por_cliente,
        "criar_lead": _criar_lead,
        "consultar_leads": _consultar_leads,
        "registrar_despesa": _registrar_despesa,
        "consultar_resumo_financeiro": _consultar_resumo_financeiro,
        "consultar_estoque": _consultar_estoque,
        "consultar_equipe_disponivel": _consultar_equipe_disponivel,
        "registrar_avaria": _registrar_avaria,
        "consultar_boxes_guarda_moveis": _consultar_boxes_guarda_moveis,
        "consultar_cliente": _consultar_cliente,
        "consultar_programacao_semana": _consultar_programacao_semana,
        "consultar_ranking_equipe": _consultar_ranking_equipe,
        "criar_tarefa": _criar_tarefa,
        "consultar_tarefas": _consultar_tarefas,
        "agenda_listar_eventos": _agenda_listar_eventos,
        "agenda_criar_evento": _agenda_criar_evento,
        "agenda_criar_evento_os": _agenda_criar_evento_os,
        "notificar_equipe": _notificar_equipe,
        "drive_salvar_arquivo": _drive_salvar_arquivo,
        "drive_buscar_arquivos": _drive_buscar_arquivos,
        "drive_listar_arquivos_os": _drive_listar_arquivos_os,
        "gerar_analise_proativa": _gerar_analise_proativa,
        "configurar_preferencias": _configurar_preferencias,
        "consultar_meu_contexto": _consultar_meu_contexto,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return f"Ferramenta '{tool_name}' nao encontrada."

    try:
        return handler(tool_input, user_context or {})
    except Exception as e:
        logger.error(f"Erro ao executar {tool_name}: {e}")
        return f"Erro ao executar {tool_name}: {str(e)}"


# ── IMPLEMENTACOES ─────────────────────────────────────────────────────────

def _consultar_os_do_dia(inp: dict, ctx: dict) -> str:
    data = inp.get("data") or datetime.now().strftime("%Y-%m-%d")
    result = api.listar_ordens_servico(data=data)
    if not result:
        return f"Nenhuma OS encontrada para {data}."
    lines = [f"OS do dia {data}: {len(result)} mudanca(s)"]
    for os in result:
        lines.append(f"- OS#{os.get('numero','?')} | {os.get('cliente_nome','?')} | {os.get('status','?')} | {os.get('hora_inicio','?')}")
    return "
".join(lines)


def _consultar_os_por_cliente(inp: dict, ctx: dict) -> str:
    nome = inp["nome_cliente"]
    result = api.buscar_clientes(nome)
    clientes = result.get("clientes", []) if isinstance(result, dict) else result or []
    if not clientes:
        return f"Nenhum cliente encontrado com o nome '{nome}'."
    lines = []
    for c in clientes[:5]:
        os_list = api.listar_ordens_servico(cliente_id=c.get("id"))
        lines.append(f"Cliente: {c.get('nome')} — {len(os_list or [])} OS(s)")
    return "
".join(lines) or "Nenhuma OS encontrada."


def _criar_lead(inp: dict, ctx: dict) -> str:
    nome_responsavel = ctx.get("name", "Agente")
    payload = {**inp, "responsavel": nome_responsavel}
    result = api.criar_lead(payload)
    if result:
        return f"Lead criado com sucesso! ID: {result.get('id', '?')} | Cliente: {inp['nome']}"
    return "Erro ao criar lead."


def _consultar_leads(inp: dict, ctx: dict) -> str:
    result = api.listar_leads(
        status=inp.get("status"),
        limite=inp.get("limite", 10),
    )
    leads = result if isinstance(result, list) else result.get("leads", []) if result else []
    if not leads:
        return "Nenhum lead encontrado."
    lines = [f"Leads ({len(leads)}):"]
    for l in leads:
        lines.append(f"- {l.get('nome','?')} | {l.get('status','?')} | {l.get('telefone','?')}")
    return "
".join(lines)


def _registrar_despesa(inp: dict, ctx: dict) -> str:
    nome_responsavel = ctx.get("name", "Agente WhatsApp")
    payload = {**inp, "responsavel": nome_responsavel}
    result = api.criar_despesa(payload)
    if result:
        return f"Despesa registrada! ID: {result.get('id','?')} | R$ {inp['valor']:.2f} | {inp['descricao']}"
    return "Erro ao registrar despesa."


def _consultar_resumo_financeiro(inp: dict, ctx: dict) -> str:
    hoje = datetime.now()
    mes = inp.get("mes", hoje.month)
    ano = inp.get("ano", hoje.year)
    result = api.resumo_financeiro(mes=mes, ano=ano)
    if not result:
        return f"Sem dados financeiros para {mes:02d}/{ano}."
    return (
        f"Resumo {mes:02d}/{ano}:
"
        f"  Receitas: R$ {result.get('receitas', 0):,.2f}
"
        f"  Despesas: R$ {result.get('despesas', 0):,.2f}
"
        f"  Lucro: R$ {result.get('lucro', 0):,.2f}
"
        f"  OS realizadas: {result.get('os_concluidas', 0)}"
    )


def _consultar_estoque(inp: dict, ctx: dict) -> str:
    result = api.listar_estoque(busca=inp.get("material", ""))
    itens = result if isinstance(result, list) else []
    if not itens:
        return "Estoque vazio ou item nao encontrado."
    lines = ["Estoque:"]
    for item in itens:
        alerta = " ⚠️ BAIXO" if item.get("quantidade", 0) <= item.get("quantidade_minima", 0) else ""
        lines.append(f"- {item.get('nome','?')}: {item.get('quantidade','?')} {item.get('unidade','un')}{alerta}")
    return "
".join(lines)


def _consultar_equipe_disponivel(inp: dict, ctx: dict) -> str:
    data = inp.get("data") or datetime.now().strftime("%Y-%m-%d")
    result = api.listar_equipe(disponivel=True, data=data)
    equipe = result if isinstance(result, list) else []
    if not equipe:
        return f"Nenhum funcionario disponivel em {data}."
    lines = [f"Equipe disponivel ({data}):"]
    for m in equipe:
        lines.append(f"- {m.get('nome','?')} | {m.get('cargo','?')}")
    return "
".join(lines)


def _registrar_avaria(inp: dict, ctx: dict) -> str:
    os_id = inp["os_id"]
    os_info = api.get_ordem_servico(os_id)
    if not os_info:
        return f"OS #{os_id} nao encontrada."
    payload = {
        "os_id": os_id,
        "descricao": inp["descricao"],
        "item_danificado": inp["item_danificado"],
        "foto_url": inp.get("foto_url"),
        "responsavel": ctx.get("name", "Agente"),
    }
    result = api.registrar_avaria(payload)
    if result:
        return f"Avaria registrada! OS #{os_id} | Item: {inp['item_danificado']}"
    return "Erro ao registrar avaria."


def _consultar_boxes_guarda_moveis(inp: dict, ctx: dict) -> str:
    result = api.listar_boxes(status=inp.get("status", "todos"))
    boxes = result if isinstance(result, list) else []
    if not boxes:
        return "Nenhum box encontrado."
    ocupados = [b for b in boxes if b.get("status") == "ocupado"]
    livres = [b for b in boxes if b.get("status") == "livre"]
    lines = [f"Boxes: {len(boxes)} total | {len(ocupados)} ocupados | {len(livres)} livres"]
    for b in boxes[:10]:
        status = "🔴 Ocupado" if b.get("status") == "ocupado" else "🟢 Livre"
        lines.append(f"- Box {b.get('numero','?')}: {status} | {b.get('cliente','—')}")
    return "
".join(lines)


def _consultar_cliente(inp: dict, ctx: dict) -> str:
    result = api.buscar_clientes(inp["busca"])
    clientes = result.get("clientes", []) if isinstance(result, dict) else result or []
    if not clientes:
        return f"Nenhum cliente encontrado para '{inp['busca']}'."
    c = clientes[0]
    return (
        f"Cliente: {c.get('nome','?')}
"
        f"Telefone: {c.get('telefone','?')}
"
        f"Email: {c.get('email','?')}
"
        f"Total OS: {c.get('total_os', 0)}
"
        f"Ultima OS: {c.get('ultima_os', '—')}"
    )


def _consultar_programacao_semana(inp: dict, ctx: dict) -> str:
    from datetime import timedelta
    hoje = datetime.now().date()
    fim = hoje + timedelta(days=7)
    result = api.listar_ordens_servico(data_inicio=str(hoje), data_fim=str(fim))
    os_list = result if isinstance(result, list) else []
    if not os_list:
        return "Nenhuma OS programada para os proximos 7 dias."
    lines = [f"Programacao da semana ({len(os_list)} OS):"]
    for os in os_list:
        lines.append(f"- {os.get('data_inicio','?')} | OS#{os.get('numero','?')} | {os.get('cliente_nome','?')}")
    return "
".join(lines)


def _consultar_ranking_equipe(inp: dict, ctx: dict) -> str:
    result = api.ranking_equipe(periodo=inp.get("periodo", "mes_atual"))
    ranking = result if isinstance(result, list) else []
    if not ranking:
        return "Sem dados de ranking disponíveis."
    lines = ["Ranking da equipe:"]
    for i, m in enumerate(ranking[:10], 1):
        lines.append(f"{i}. {m.get('nome','?')} | {m.get('os_concluidas',0)} OS | ⭐ {m.get('avaliacao','—')}")
    return "
".join(lines)


def _criar_tarefa(inp: dict, ctx: dict) -> str:
    payload = {**inp, "criado_por": ctx.get("name", "Agente")}
    result = api.criar_tarefa(payload)
    if result:
        return f"Tarefa criada! ID: {result.get('id','?')} | {inp['titulo']} | Prazo: {inp['prazo']}"
    return "Erro ao criar tarefa."


def _consultar_tarefas(inp: dict, ctx: dict) -> str:
    result = api.listar_tarefas(
        responsavel=inp.get("responsavel"),
        status=inp.get("status"),
        limite=inp.get("limite", 10),
    )
    tarefas = result if isinstance(result, list) else []
    if not tarefas:
        return "Nenhuma tarefa encontrada."
    lines = [f"Tarefas ({len(tarefas)}):"]
    for t in tarefas:
        prazo = t.get("prazo", "?")[:10]
        lines.append(f"- [{t.get('status','?')}] {t.get('titulo','?')} | Prazo: {prazo} | {t.get('responsavel_nome','?')}")
    return "
".join(lines)


# ── FERRAMENTAS FASE 2: AGENDA E NOTIFICACOES ──────────────────────────────

def _agenda_listar_eventos(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_calendar import (
            listar_eventos_hoje, listar_eventos_semana,
            listar_eventos, formatar_agenda_whatsapp, is_available
        )
        if not is_available():
            return "Google Calendar nao configurado. Adicione GOOGLE_CREDENTIALS_JSON e GOOGLE_CALENDAR_ID no .env"

        periodo = inp.get("periodo", "hoje")
        busca = inp.get("busca", "")

        if periodo == "hoje":
            eventos = listar_eventos_hoje()
            titulo = "AGENDA DE HOJE"
        elif periodo == "semana":
            eventos = listar_eventos_semana()
            titulo = "AGENDA DA SEMANA"
        else:
            eventos = listar_eventos(busca=busca)
            titulo = "AGENDA"

        return formatar_agenda_whatsapp(eventos, titulo)
    except Exception as e:
        logger.error(f"Erro agenda_listar_eventos: {e}")
        return f"Erro ao consultar agenda: {e}"


def _agenda_criar_evento(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_calendar import criar_evento, is_available
        if not is_available():
            return "Google Calendar nao configurado."

        data_str = inp["data"]
        hora_str = inp["hora_inicio"]
        dt_inicio = datetime.fromisoformat(f"{data_str}T{hora_str}:00")

        hora_fim = inp.get("hora_fim")
        dt_fim = datetime.fromisoformat(f"{data_str}T{hora_fim}:00") if hora_fim else None

        result = criar_evento(
            titulo=inp["titulo"],
            inicio=dt_inicio,
            fim=dt_fim,
            descricao=inp.get("descricao", ""),
            local=inp.get("local", ""),
            lembrete_minutos=inp.get("lembrete_minutos", 30),
        )
        return f"Evento criado no calendario! ID: {result['id']}
{inp['titulo']} | {data_str} {hora_str}"
    except Exception as e:
        logger.error(f"Erro agenda_criar_evento: {e}")
        return f"Erro ao criar evento: {e}"


def _agenda_criar_evento_os(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_calendar import criar_lembrete_mudanca, is_available
        if not is_available():
            return "Google Calendar nao configurado."

        data_str = inp["data"]
        hora_str = inp["hora"]
        dt = datetime.fromisoformat(f"{data_str}T{hora_str}:00")

        result = criar_lembrete_mudanca(
            numero_os=inp["numero_os"],
            cliente=inp["cliente"],
            data_mudanca=dt,
            origem=inp["origem"],
            destino=inp["destino"],
            motorista=inp.get("motorista", ""),
        )
        return f"Evento de mudanca criado no calendario!
OS #{inp['numero_os']} | {inp['cliente']} | {data_str} {hora_str}"
    except Exception as e:
        logger.error(f"Erro agenda_criar_evento_os: {e}")
        return f"Erro ao criar evento OS: {e}"


def _notificar_equipe(inp: dict, ctx: dict) -> str:
    try:
        import integrations.evolution as evo
        from agent.profiles import ProfileManager

        mensagem = inp["mensagem"]
        cargo = inp.get("cargo", "")
        numeros_especificos = inp.get("numeros", [])

        pm = ProfileManager()

        if numeros_especificos:
            destinatarios = numeros_especificos
        elif cargo and cargo != "todos":
            destinatarios = pm.get_numbers_by_roles([cargo])
        else:
            # Envia para todos os cargos ativos exceto bloqueado
            destinatarios = pm.get_numbers_by_roles(
                ["admin", "supervisor", "motorista", "operacional", "comercial", "financeiro"]
            )

        enviados = 0
        for number in destinatarios:
            try:
                evo.send_text(number, mensagem)
                enviados += 1
            except Exception as e:
                logger.warning(f"Erro ao notificar {number[-4:]}: {e}")

        return f"Notificacao enviada para {enviados} membro(s) da equipe."
    except Exception as e:
        logger.error(f"Erro notificar_equipe: {e}")
        return f"Erro ao notificar equipe: {e}"


# ── FASE 3: GOOGLE DRIVE ─────────────────────────────────────────────────────

def _drive_salvar_arquivo(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_drive import upload_from_url, is_available
        if not is_available():
            return "Google Drive nao configurado."
        result = upload_from_url(
            url=inp["url"],
            filename=inp["nome"],
            categoria=inp.get("categoria", "outros"),
            descricao=inp.get("descricao", ""),
            os_id=inp.get("os_id"),
        )
        if "erro" in result:
            return f"Erro ao salvar arquivo: {result['erro']}"
        return f"Arquivo salvo no Drive!\nNome: {result['nome']}\nURL: {result['url']}"
    except Exception as e:
        logger.error(f"Erro drive_salvar_arquivo: {e}")
        return f"Erro ao salvar no Drive: {e}"


def _drive_buscar_arquivos(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_drive import buscar_arquivos, formatar_arquivos_whatsapp, is_available
        if not is_available():
            return "Google Drive nao configurado."
        arquivos = buscar_arquivos(
            query_texto=inp.get("query", ""),
            categoria=inp.get("categoria"),
            os_id=inp.get("os_id"),
        )
        return formatar_arquivos_whatsapp(arquivos, titulo="Arquivos encontrados")
    except Exception as e:
        logger.error(f"Erro drive_buscar_arquivos: {e}")
        return f"Erro ao buscar no Drive: {e}"


def _drive_listar_arquivos_os(inp: dict, ctx: dict) -> str:
    try:
        from integrations.google_drive import listar_arquivos_os, formatar_arquivos_whatsapp, is_available
        if not is_available():
            return "Google Drive nao configurado."
        arquivos = listar_arquivos_os(os_id=inp["os_id"])
        return formatar_arquivos_whatsapp(arquivos, titulo=f"Arquivos da OS #{inp['os_id']}")
    except Exception as e:
        logger.error(f"Erro drive_listar_arquivos_os: {e}")
        return f"Erro ao listar arquivos OS: {e}"


# ── FASE 3: ANALYTICS PROATIVO ───────────────────────────────────────────────

def _gerar_analise_proativa(inp: dict, ctx: dict) -> str:
    try:
        from agent.analytics import (
            gerar_relatorio_proativo,
            gerar_insight_financeiro_texto,
            analisar_operacional,
            analisar_estoque,
            analisar_leads,
        )
        modulo = inp.get("modulo", "geral")
        if modulo == "financeiro":
            return gerar_insight_financeiro_texto(api)
        elif modulo == "operacional":
            dados = analisar_operacional(api)
            if dados.get("erro"):
                return f"Erro: {dados['erro']}"
            alertas = dados.get("alertas", [])
            insights = dados.get("insights", [])
            linhas = ["*Analise Operacional*", ""]
            linhas += [f"[!] {a}" for a in alertas]
            linhas += [f"-> {i}" for i in insights]
            return "\n".join(linhas) if linhas else "_Sem dados operacionais._"
        elif modulo == "estoque":
            dados = analisar_estoque(api)
            alertas = dados.get("alertas", [])
            return "\n".join(alertas) if alertas else "_Estoque em nivel normal._"
        elif modulo == "leads":
            dados = analisar_leads(api)
            linhas = dados.get("alertas", []) + dados.get("insights", [])
            return "\n".join(linhas) if linhas else "_Sem alertas de leads._"
        else:
            return gerar_relatorio_proativo(api)
    except Exception as e:
        logger.error(f"Erro gerar_analise_proativa: {e}")
        return f"Erro ao gerar analise: {e}"


# ── FASE 4: PREFERENCIAS E CONTEXTO DO USUARIO ───────────────────────────────

def _configurar_preferencias(inp: dict, ctx: dict) -> str:
    try:
        from agent.user_context import user_context_manager
        phone = ctx.get("phone", "")
        role = ctx.get("role", "operacional")
        preferencia = inp["preferencia"]
        valor = inp["valor"]
        user_context_manager.set_preferencia(phone, preferencia, valor, role)
        status = "ativado" if valor else "desativado"
        labels = {
            "resumo_diario": "Resumo diario",
            "alertas_financeiros": "Alertas financeiros",
            "alertas_operacionais": "Alertas operacionais",
            "alertas_estoque": "Alertas de estoque",
            "alertas_leads": "Alertas de leads",
            "modo_verboso": "Modo verboso",
        }
        label = labels.get(preferencia, preferencia)
        return f"Preferencia atualizada: *{label}* {status}."
    except Exception as e:
        logger.error(f"Erro configurar_preferencias: {e}")
        return f"Erro ao configurar preferencias: {e}"


def _consultar_meu_contexto(inp: dict, ctx: dict) -> str:
    try:
        from agent.user_context import user_context_manager
        phone = ctx.get("phone", "")
        role = ctx.get("role", "operacional")
        prefs = user_context_manager.get_preferencias(phone, role)
        historico = user_context_manager.get_historico_acoes(phone, limite=5, role=role)
        estado = user_context_manager.get_estado(phone, role)

        linhas = ["*Seu Contexto Atual*", ""]

        linhas.append("*Preferencias:*")
        for k, v in prefs.items():
            status = "ativado" if v else "desativado"
            linhas.append(f"  - {k}: {status}")

        if estado.get("os_em_foco"):
            linhas.append(f"\nOS em foco: #{estado['os_em_foco']}")

        if historico:
            linhas.append("\n*Ultimas acoes:*")
            for h in historico:
                ts = h.get("ts", "")[:16].replace("T", " ")
                linhas.append(f"  - {h['acao']} ({ts})")

        return "\n".join(linhas)
    except Exception as e:
        logger.error(f"Erro consultar_meu_contexto: {e}")
        return f"Erro ao consultar contexto: {e}"
