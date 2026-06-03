"""
agent/user_context.py
Fase 4 -- Multi-usuario com contexto individual
Cada usuario tem seu proprio contexto: preferencias, historico de acoes,
estado da conversa, tema ativo e dados personalizados.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")
CONTEXT_FILE = Path(os.environ.get("USER_CONTEXT_FILE", "/tmp/user_contexts.json"))


def _now() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


# Preferencias padrao por role
DEFAULT_PREFERENCES = {
    "admin": {
        "resumo_diario": True,
        "alertas_financeiros": True,
        "alertas_operacionais": True,
        "alertas_estoque": True,
        "alertas_leads": True,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
    "supervisor": {
        "resumo_diario": True,
        "alertas_financeiros": False,
        "alertas_operacionais": True,
        "alertas_estoque": True,
        "alertas_leads": False,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
    "motorista": {
        "resumo_diario": False,
        "alertas_financeiros": False,
        "alertas_operacionais": True,
        "alertas_estoque": False,
        "alertas_leads": False,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
    "operacional": {
        "resumo_diario": False,
        "alertas_financeiros": False,
        "alertas_operacionais": True,
        "alertas_estoque": False,
        "alertas_leads": False,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
    "comercial": {
        "resumo_diario": False,
        "alertas_financeiros": False,
        "alertas_operacionais": False,
        "alertas_estoque": False,
        "alertas_leads": True,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
    "financeiro": {
        "resumo_diario": True,
        "alertas_financeiros": True,
        "alertas_operacionais": False,
        "alertas_estoque": False,
        "alertas_leads": False,
        "modo_verboso": False,
        "idioma": "pt-BR",
    },
}


class UserContextManager:
    """
    Gerencia o contexto individual de cada usuario.
    Armazena preferencias, estado atual da conversa,
    ultima acao, OS em foco, etc.
    """

    def __init__(self):
        self._contexts = self._load()

    def _load(self) -> dict:
        if CONTEXT_FILE.exists():
            try:
                return json.loads(CONTEXT_FILE.read_text())
            except Exception as e:
                logger.error(f"[UserContext] Erro ao carregar: {e}")
        return {}

    def _save(self):
        try:
            CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONTEXT_FILE.write_text(json.dumps(self._contexts, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"[UserContext] Erro ao salvar: {e}")

    def _get_or_create(self, phone: str, role: str = "operacional") -> dict:
        """Retorna ou cria o contexto de um usuario."""
        if phone not in self._contexts:
            prefs = DEFAULT_PREFERENCES.get(role, DEFAULT_PREFERENCES["operacional"]).copy()
            self._contexts[phone] = {
                "phone": phone,
                "role": role,
                "preferencias": prefs,
                "estado": {
                    "os_em_foco": None,        # OS que o usuario esta discutindo
                    "cliente_em_foco": None,   # Cliente em foco
                    "ultima_acao": None,        # Ultima ferramenta usada
                    "aguardando": None,         # Esperando confirmacao de algo
                },
                "historico_acoes": [],  # ultimas 20 acoes realizadas
                "criado_em": _now().isoformat(),
                "atualizado_em": _now().isoformat(),
            }
            self._save()
        return self._contexts[phone]

    # --- Preferencias ---

    def get_preferencias(self, phone: str, role: str = "operacional") -> dict:
        """Retorna as preferencias do usuario."""
        ctx = self._get_or_create(phone, role)
        return ctx.get("preferencias", {})

    def set_preferencia(self, phone: str, chave: str, valor: Any, role: str = "operacional") -> bool:
        """Define uma preferencia do usuario."""
        ctx = self._get_or_create(phone, role)
        ctx["preferencias"][chave] = valor
        ctx["atualizado_em"] = _now().isoformat()
        self._save()
        logger.info(f"[UserContext] {phone}: preferencia {chave}={valor}")
        return True

    def quer_notificacao(self, phone: str, tipo_alerta: str, role: str = "operacional") -> bool:
        """Verifica se o usuario quer receber um tipo especifico de notificacao."""
        prefs = self.get_preferencias(phone, role)
        return prefs.get(tipo_alerta, False)

    # --- Estado da conversa ---

    def get_estado(self, phone: str, role: str = "operacional") -> dict:
        """Retorna o estado atual da conversa do usuario."""
        ctx = self._get_or_create(phone, role)
        return ctx.get("estado", {})

    def set_os_em_foco(self, phone: str, os_id: Optional[int], role: str = "operacional"):
        """Define a OS que o usuario esta discutindo no momento."""
        ctx = self._get_or_create(phone, role)
        ctx["estado"]["os_em_foco"] = os_id
        ctx["atualizado_em"] = _now().isoformat()
        self._save()

    def set_cliente_em_foco(self, phone: str, cliente: Optional[str], role: str = "operacional"):
        """Define o cliente em foco na conversa."""
        ctx = self._get_or_create(phone, role)
        ctx["estado"]["cliente_em_foco"] = cliente
        ctx["atualizado_em"] = _now().isoformat()
        self._save()

    def set_aguardando(self, phone: str, descricao: Optional[str], role: str = "operacional"):
        """Marca que o agente esta aguardando confirmacao do usuario."""
        ctx = self._get_or_create(phone, role)
        ctx["estado"]["aguardando"] = descricao
        ctx["atualizado_em"] = _now().isoformat()
        self._save()

    def limpar_estado(self, phone: str, role: str = "operacional"):
        """Limpa o estado da conversa (apos conclusao ou timeout)."""
        ctx = self._get_or_create(phone, role)
        ctx["estado"] = {
            "os_em_foco": None,
            "cliente_em_foco": None,
            "ultima_acao": None,
            "aguardando": None,
        }
        ctx["atualizado_em"] = _now().isoformat()
        self._save()

    # --- Historico de acoes ---

    def registrar_acao(self, phone: str, acao: str, detalhes: dict = None, role: str = "operacional"):
        """Registra uma acao realizada pelo usuario (para contexto futuro)."""
        ctx = self._get_or_create(phone, role)
        historico = ctx.get("historico_acoes", [])

        entrada = {
            "acao": acao,
            "detalhes": detalhes or {},
            "ts": _now().isoformat(),
        }
        historico.append(entrada)

        # Manter apenas as 20 ultimas acoes
        ctx["historico_acoes"] = historico[-20:]
        ctx["estado"]["ultima_acao"] = acao
        ctx["atualizado_em"] = _now().isoformat()
        self._save()

    def get_historico_acoes(self, phone: str, limite: int = 10, role: str = "operacional") -> list:
        """Retorna o historico de acoes do usuario."""
        ctx = self._get_or_create(phone, role)
        historico = ctx.get("historico_acoes", [])
        return historico[-limite:]

    def get_ultima_acao(self, phone: str, role: str = "operacional") -> Optional[str]:
        """Retorna a ultima acao realizada pelo usuario."""
        ctx = self._get_or_create(phone, role)
        return ctx.get("estado", {}).get("ultima_acao")

    # --- Contexto resumido para o prompt ---

    def get_contexto_para_prompt(self, phone: str, role: str = "operacional") -> str:
        """
        Retorna um resumo do contexto do usuario para incluir no system prompt.
        Ajuda o Claude a ter continuidade entre conversas.
        """
        ctx = self._get_or_create(phone, role)
        estado = ctx.get("estado", {})
        historico = ctx.get("historico_acoes", [])

        partes = []

        if estado.get("os_em_foco"):
            partes.append(f"OS em foco: #{estado['os_em_foco']}")

        if estado.get("cliente_em_foco"):
            partes.append(f"Cliente em foco: {estado['cliente_em_foco']}")

        if estado.get("aguardando"):
            partes.append(f"Aguardando confirmacao: {estado['aguardando']}")

        if historico:
            ultimas = historico[-3:]
            acoes_str = ", ".join(h["acao"] for h in ultimas)
            partes.append(f"Ultimas acoes: {acoes_str}")

        if not partes:
            return ""

        return "Contexto do usuario:\n" + "\n".join(f"- {p}" for p in partes)

    # --- Listar todos os usuarios ---

    def listar_usuarios_com_contexto(self) -> list:
        """Lista todos os usuarios com seus contextos (para admin)."""
        resultado = []
        for phone, ctx in self._contexts.items():
            resultado.append({
                "phone": phone,
                "role": ctx.get("role", "?"),
                "ultima_acao": ctx.get("estado", {}).get("ultima_acao"),
                "atualizado_em": ctx.get("atualizado_em", ""),
                "total_acoes": len(ctx.get("historico_acoes", [])),
            })
        return resultado


# Instancia global
user_context_manager = UserContextManager()
