"""
integrations/legacy_api.py
Cliente HTTP para a API REST do ERP Legacy Moving.
Todas as chamadas ao backend passam por esta classe.
Versao 2: metodos completos para todas as funcionalidades do agente.
"""
import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

LEGACY_API_URL = os.environ.get("LEGACY_API_URL", "http://localhost:5000")
LEGACY_JWT_TOKEN = os.environ.get("LEGACY_JWT_TOKEN", "")


class LegacyAPI:
    """
    Cliente para a API do Legacy Moving ERP.
    Configurar via variaveis de ambiente:
      LEGACY_API_URL   : URL do backend
      LEGACY_JWT_TOKEN : Token JWT admin
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        # Aceita parâmetros opcionais; usa env vars como fallback
        self.base_url = (base_url or LEGACY_API_URL).rstrip("/")
        self._token = api_key or LEGACY_JWT_TOKEN
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        })

    # ─────────────────────────────────────────────────────────────
    # HTTP BASE
    # ─────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get(self, path: str, params: dict = None) -> dict:
        try:
            resp = self._session.get(self._url(path), params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            logger.error(f"ERP indisponivel: {self.base_url}")
            return {"erro": "Sistema ERP indisponivel no momento."}
        except requests.exceptions.Timeout:
            return {"erro": "Sistema ERP demorou muito para responder."}
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP {e.response.status_code} em GET {path}")
            if e.response.status_code == 401:
                return {"erro": "Token invalido. Configure LEGACY_JWT_TOKEN."}
            if e.response.status_code == 404:
                return {"erro": f"Recurso nao encontrado: {path}"}
            return {"erro": f"Erro {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            logger.error(f"Erro inesperado GET {path}: {e}")
            return {"erro": str(e)}

    def post(self, path: str, data: dict) -> dict:
        try:
            resp = self._session.post(self._url(path), json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"erro": "Sistema ERP indisponivel no momento."}
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP {e.response.status_code} em POST {path}")
            try:
                return e.response.json()
            except Exception:
                return {"erro": f"Erro {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            logger.error(f"Erro inesperado POST {path}: {e}")
            return {"erro": str(e)}

    def put(self, path: str, data: dict) -> dict:
        try:
            resp = self._session.put(self._url(path), json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Erro PUT {path}: {e}")
            return {"erro": str(e)}

    def delete(self, path: str) -> dict:
        try:
            resp = self._session.delete(self._url(path), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Erro DELETE {path}: {e}")
            return {"erro": str(e)}

    def health_check(self) -> bool:
        try:
            resp = self._session.get(self._url("/health"), timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────
    # ORDENS DE SERVICO
    # ─────────────────────────────────────────────────────────────

    def listar_ordens_servico(self, data: str = None, data_inicio: str = None,
                               data_fim: str = None, status: str = None,
                               cliente_id: int = None, limite: int = 20) -> list:
        params = {}
        if data: params["data"] = data
        if data_inicio: params["data_inicio"] = data_inicio
        if data_fim: params["data_fim"] = data_fim
        if status: params["status"] = status
        if cliente_id: params["cliente_id"] = cliente_id
        params["limite"] = limite
        resultado = self.get("/api/ordens-servico", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def obter_ordem_servico(self, os_id: int) -> dict:
        return self.get(f"/api/ordens-servico/{os_id}")

    def criar_ordem_servico(self, dados: dict) -> dict:
        return self.post("/api/ordens-servico", dados)

    def atualizar_ordem_servico(self, os_id: int, dados: dict) -> dict:
        return self.put(f"/api/ordens-servico/{os_id}", dados)

    def buscar_os_por_cliente(self, nome_cliente: str) -> list:
        resultado = self.get("/api/ordens-servico", {"cliente_nome": nome_cliente})
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # CLIENTES E LEADS
    # ─────────────────────────────────────────────────────────────

    def buscar_cliente(self, nome: str = None, telefone: str = None) -> list:
        params = {}
        if nome: params["nome"] = nome
        if telefone: params["telefone"] = telefone
        resultado = self.get("/api/clientes", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def criar_lead(self, dados: dict) -> dict:
        return self.post("/api/leads", dados)

    def listar_leads(self, status: str = None, limite: int = 10) -> list:
        params = {"limite": limite}
        if status: params["status"] = status
        resultado = self.get("/api/leads", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def atualizar_lead(self, lead_id: int, dados: dict) -> dict:
        return self.put(f"/api/leads/{lead_id}", dados)

    # ─────────────────────────────────────────────────────────────
    # FINANCEIRO
    # ─────────────────────────────────────────────────────────────

    def registrar_despesa(self, dados: dict) -> dict:
        return self.post("/api/financeiro/despesas", dados)

    def registrar_receita(self, dados: dict) -> dict:
        return self.post("/api/financeiro/receitas", dados)

    def obter_resumo_financeiro(self, mes: int = None, ano: int = None) -> dict:
        agora = datetime.now()
        params = {
            "mes": mes or agora.month,
            "ano": ano or agora.year,
        }
        return self.get("/api/financeiro/resumo", params)

    def listar_despesas(self, mes: int = None, ano: int = None,
                        categoria: str = None, limite: int = 20) -> list:
        agora = datetime.now()
        params = {
            "mes": mes or agora.month,
            "ano": ano or agora.year,
            "limite": limite,
        }
        if categoria: params["categoria"] = categoria
        resultado = self.get("/api/financeiro/despesas", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # ESTOQUE
    # ─────────────────────────────────────────────────────────────

    def listar_estoque(self, material: str = None) -> list:
        params = {}
        if material: params["nome"] = material
        resultado = self.get("/api/estoque", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def atualizar_estoque(self, item_id: int, quantidade: int) -> dict:
        return self.put(f"/api/estoque/{item_id}", {"quantidade": quantidade})

    # ─────────────────────────────────────────────────────────────
    # EQUIPE
    # ─────────────────────────────────────────────────────────────

    def listar_equipe_disponivel(self, data: str = None) -> list:
        params = {}
        if data: params["data"] = data
        resultado = self.get("/api/equipe/disponibilidade", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def listar_equipe(self, role: str = None, disponivel: bool = None,
                      data: str = None) -> list:
        """
        Lista membros da equipe com filtros opcionais.
        Alias flexível para listar_equipe_disponivel com suporte a role e disponivel.
        
        Args:
            role: Cargo/função (ex: "motorista", "operacional")
            disponivel: Se True, filtra apenas disponíveis
            data: Data para verificar disponibilidade (padrão: hoje)
        """
        params = {}
        if role: params["role"] = role
        if disponivel is not None: params["disponivel"] = disponivel
        if data: params["data"] = data
        return self.get("/api/equipe", params)

    def obter_funcionario(self, funcionario_id: int) -> dict:
        return self.get(f"/api/funcionarios/{funcionario_id}")

    def listar_funcionarios(self, cargo: str = None, ativo: bool = True) -> list:
        params = {"ativo": ativo}
        if cargo: params["cargo"] = cargo
        resultado = self.get("/api/funcionarios", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def obter_ranking_equipe(self, periodo: str = "mes") -> list:
        resultado = self.get("/api/equipe/ranking", {"periodo": periodo})
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # AVARIAS
    # ─────────────────────────────────────────────────────────────

    def registrar_avaria(self, dados: dict) -> dict:
        return self.post("/api/avarias", dados)

    def adicionar_observacao_os(self, numero_os: str, observacao: str,
                                tipo: str = "GERAL") -> dict:
        """
        Adiciona uma observação a uma OS existente.
        Usado pelo DamageRegistry para registrar avarias no ERP.
        
        Args:
            numero_os: Número da Ordem de Serviço
            observacao: Texto da observação
            tipo: Tipo da observação (ex: "AVARIA", "GERAL")
        """
        return self.post(f"/api/ordens-servico/{numero_os}/observacoes", {
            "texto": observacao,
            "tipo": tipo,
        })

    def listar_avarias(self, os_id: int = None, limite: int = 10) -> list:
        params = {"limite": limite}
        if os_id: params["os_id"] = os_id
        resultado = self.get("/api/avarias", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # GUARDA-MOVEIS / BOXES
    # ─────────────────────────────────────────────────────────────

    def consultar_boxes_guarda_moveis(self, status: str = None) -> list:
        params = {}
        if status: params["status"] = status
        resultado = self.get("/api/guarda-moveis/boxes", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # TAREFAS
    # ─────────────────────────────────────────────────────────────

    def criar_tarefa(self, dados: dict) -> dict:
        return self.post("/api/tarefas", dados)

    def listar_tarefas(self, status: str = None, responsavel_id: int = None,
                       limite: int = 10) -> list:
        params = {"limite": limite}
        if status: params["status"] = status
        if responsavel_id: params["responsavel_id"] = responsavel_id
        resultado = self.get("/api/tarefas", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def atualizar_tarefa(self, tarefa_id: int, dados: dict) -> dict:
        return self.put(f"/api/tarefas/{tarefa_id}", dados)

    # ─────────────────────────────────────────────────────────────
    # PROGRAMACAO / AGENDA OPERACIONAL
    # ─────────────────────────────────────────────────────────────

    def obter_programacao_semana(self, data_inicio: str = None) -> list:
        params = {}
        if data_inicio: params["data_inicio"] = data_inicio
        resultado = self.get("/api/programacao/semana", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    def obter_programacao_dia(self, data: str = None) -> list:
        params = {}
        if data: params["data"] = data
        resultado = self.get("/api/programacao/dia", params)
        return resultado if isinstance(resultado, list) else resultado.get("items", [])

    # ─────────────────────────────────────────────────────────────
    # DASHBOARD / METRICAS
    # ─────────────────────────────────────────────────────────────

    def obter_dashboard(self) -> dict:
        """Retorna metricas consolidadas para o dashboard."""
        return self.get("/api/dashboard")

    def obter_kpis(self, periodo: str = "mes") -> dict:
        """Retorna KPIs do negocio: NPS, taxa conversao, ocupacao equipe."""
        return self.get("/api/kpis", {"periodo": periodo})


# Instância global — inicializada em main.py
legacy_api: LegacyAPI = None
