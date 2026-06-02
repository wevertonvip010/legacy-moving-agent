"""
agent/tools.py
Definicao e execucao de todas as ferramentas do agente Legacy Moving.
Cada ferramenta mapeia para um endpoint da API do ERP.
"""
import logging
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
                "description": "Registra uma avaria (dano a objeto do cliente) ocorrida em uma mudanca.",
                "input_schema": {
                              "type": "object",
                              "properties": {
                                                "os_id": {"type": "integer", "description": "ID da Ordem de Servico"},
                                                "tipo": {"type": "string", "description": "Tipo: arranhado|quebrado|molhado|amassado|perdido|outros"},
                                                "descricao": {"type": "string", "description": "Descricao detalhada da avaria"},
                                                "valor_estimado": {"type": "number", "description": "Valor estimado do dano em reais"}
                              },
                              "required": ["os_id", "tipo", "descricao"]
                }
      },
      {
                "name": "consultar_boxes_guarda_moveis",
                "description": "Verifica a situacao dos boxes do guarda-moveis: quais estao ocupados, livres, cliente, valor, data.",
                "input_schema": {
                              "type": "object",
                              "properties": {
                                                "status": {"type": "string", "description": "livre|ocupado|manutencao. Se vazio, retorna todos."}
                              },
                              "required": []
                }
      },
      {
                "name": "consultar_cliente",
                "description": "Busca informacoes completas de um cliente: dados, historico de OS, contratos.",
                "input_schema": {
                              "type": "object",
                              "properties": {
                                                "nome": {"type": "string", "description": "Nome ou parte do nome do cliente"}
                              },
                              "required": ["nome"]
                }
      },
      {
                "name": "consultar_programacao_semana",
                "description": "Consulta toda a programacao operacional da semana atual ou proxima.",
                "input_schema": {
                              "type": "object",
                              "properties": {
                                                "proxima_semana": {"type": "boolean", "description": "True para proxima semana, False para semana atual"}
                              },
                              "required": []
                }
      },
      {
                "name": "consultar_ranking_equipe",
                "description": "Consulta o ranking de funcionarios por pontos de gamificacao e quantidade de servicos.",
                "input_schema": {
                              "type": "object",
                              "properties": {
                                                "limite": {"type": "integer", "description": "Quantidade de funcionarios no ranking (padrao 10)"}
                              },
                              "required": []
                }
      }
]


# ── EXECUCAO DAS FERRAMENTAS ─────────────────────────────────────────────────

def execute_tool(tool_name: str, params: dict) -> dict:
      """Executa a ferramenta solicitada pelo Claude e retorna o resultado."""
      logger.info(f'Executando ferramenta: {tool_name}')

    handlers = {
              'consultar_os_do_dia': _consultar_os_do_dia,
              'consultar_os_por_cliente': _consultar_os_por_cliente,
              'criar_lead': _criar_lead,
              'consultar_leads': _consultar_leads,
              'registrar_despesa': _registrar_despesa,
              'consultar_resumo_financeiro': _consultar_resumo_financeiro,
              'consultar_estoque': _consultar_estoque,
              'consultar_equipe_disponivel': _consultar_equipe_disponivel,
              'registrar_avaria': _registrar_avaria,
              'consultar_boxes_guarda_moveis': _consultar_boxes_guarda_moveis,
              'consultar_cliente': _consultar_cliente,
              'consultar_programacao_semana': _consultar_programacao_semana,
              'consultar_ranking_equipe': _consultar_ranking_equipe,
    }

    handler = handlers.get(tool_name)
    if not handler:
              return {'erro': f'Ferramenta desconhecida: {tool_name}'}

    try:
              return handler(params)
except Exception as e:
          logger.error(f'Erro na ferramenta {tool_name}: {e}')
          return {'erro': str(e)}


def _consultar_os_do_dia(p):
      from datetime import date
      data = p.get('data') or date.today().isoformat()
      os_list = api.get('/api/os', params={'data': data, 'limit': 50})
      if isinstance(os_list, list):
                filtradas = [o for o in os_list if o.get('data_mudanca', '').startswith(data)]
                return {'data': data, 'total': len(filtradas), 'os': filtradas}
            return os_list

def _consultar_os_por_cliente(p):
      nome = p.get('nome_cliente', '')
    clientes = api.get('/api/clientes', params={'busca': nome})
    if isinstance(clientes, list) and clientes:
              cliente_id = clientes[0].get('id')
              os_list = api.get('/api/os', params={'cliente_id': cliente_id, 'limit': 20})
              return {'cliente': clientes[0].get('nome'), 'os': os_list}
          return {'mensagem': f'Cliente "{nome}" nao encontrado'}

def _criar_lead(p):
      return api.post('/api/leads', p)

def _consultar_leads(p):
      params = {}
    if p.get('status'):
              params['status'] = p['status']
          params['limit'] = p.get('limite', 10)
    return api.get('/api/leads', params=params)

def _registrar_despesa(p):
      from datetime import date
    p['data'] = date.today().isoformat()
    return api.post('/api/despesas', p)

def _consultar_resumo_financeiro(p):
      from datetime import date
    hoje = date.today()
    mes = p.get('mes', hoje.month)
    ano = p.get('ano', hoje.year)
    return api.get('/api/financeiro/resumo', params={'mes': mes, 'ano': ano})

def _consultar_estoque(p):
      params = {}
    if p.get('material'):
              params['busca'] = p['material']
          return api.get('/api/estoque', params=params)

def _consultar_equipe_disponivel(p):
      from datetime import date
    data = p.get('data') or date.today().isoformat()
    return api.get('/api/funcionarios', params={'disponivel': True, 'data': data})

def _registrar_avaria(p):
      from datetime import date
    p['data_mudanca'] = date.today().isoformat()
    os_info = api.get(f'/api/os/{p["os_id"]}')
    if isinstance(os_info, dict):
              p['cliente'] = os_info.get('cliente', '')
              p['os_numero'] = os_info.get('numero', '')
              p['equipe'] = os_info.get('equipe', '')
          return api.post('/api/avarias', p)

def _consultar_boxes_guarda_moveis(p):
      params = {}
    if p.get('status'):
              params['status'] = p['status']
          return api.get('/api/guarda-moveis', params=params)

def _consultar_cliente(p):
      nome = p.get('nome', '')
    clientes = api.get('/api/clientes', params={'busca': nome})
    if isinstance(clientes, list) and clientes:
              cliente = clientes[0]
              historico = api.get(f'/api/clientes/{cliente["id"]}/historico')
              return {'cliente': cliente, 'historico': historico}
          return {'mensagem': f'Cliente "{nome}" nao encontrado'}

def _consultar_programacao_semana(p):
      from datetime import date, timedelta
    hoje = date.today()
    if p.get('proxima_semana'):
              inicio = hoje + timedelta(days=(7 - hoje.weekday()))
else:
        inicio = hoje - timedelta(days=hoje.weekday())
      fim = inicio + timedelta(days=6)
    return api.get('/api/programacao', params={'data_inicio': inicio.isoformat(), 'data_fim': fim.isoformat()})

def _consultar_ranking_equipe(p):
      limite = p.get('limite', 10)
    return api.get('/api/funcionarios/ranking', params={'limit': limite})
