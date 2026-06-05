"""
agent/user_context.py — Legacy Moving Agent

Fase 4 — Multi-usuário com contexto individual.
Cada usuário tem seu próprio contexto: preferências, histórico de ações,
estado da conversa, OS em foco, etc.

Persistência: SQLite via utils/database.py (com fallback em arquivo JSON).
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")
CONTEXT_FILE = Path(os.environ.get("USER_CONTEXT_FILE", "/tmp/user_contexts.json"))
MAX_ACOES = int(os.getenv("MAX_ACOES_HISTORICO", "50"))


def _now() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat()


# Preferências padrão por role
DEFAULT_PREFERENCES = {
    "admin":      {"resumo_diario": True,  "alertas_financeiros": True,  "alertas_operacionais": True,  "alertas_estoque": True,  "alertas_leads": True,  "modo_verboso": False},
    "supervisor": {"resumo_diario": True,  "alertas_financeiros": False, "alertas_operacionais": True,  "alertas_estoque": True,  "alertas_leads": False, "modo_verboso": False},
    "motorista":  {"resumo_diario": False, "alertas_financeiros": False, "alertas_operacionais": True,  "alertas_estoque": False, "alertas_leads": False, "modo_verboso": False},
    "operacional":{"resumo_diario": False, "alertas_financeiros": False, "alertas_operacionais": True,  "alertas_estoque": False, "alertas_leads": False, "modo_verboso": False},
    "comercial":  {"resumo_diario": False, "alertas_financeiros": False, "alertas_operacionais": False, "alertas_estoque": False, "alertas_leads": True,  "modo_verboso": False},
    "financeiro": {"resumo_diario": True,  "alertas_financeiros": True,  "alertas_operacionais": False, "alertas_estoque": False, "alertas_leads": False, "modo_verboso": False},
}


class UserContextManager:
    """
    Gerencia o contexto individual de cada usuário.
    Usa banco SQLite com fallback para arquivo JSON em /tmp.
    """

    def __init__(self):
        self._use_db = self._check_db()
        if not self._use_db:
            self._contexts = self._file_load()
        else:
            self._contexts = {}

    def _check_db(self) -> bool:
        try:
            from utils.database import get_session, UserContextDB
            with get_session() as s:
                s.query(UserContextDB).first()
            return True
        except Exception as e:
            logger.warning("[UserContext] Banco não disponível: %s", e)
            return False

    # ── CRUD ──

    def _get_or_create(self, phone: str, role: str = "operacional") -> dict:
        """Retorna ou cria o contexto de um usuário."""
        ctx = self._backend_get(phone)
        if ctx:
            return ctx
        prefs = DEFAULT_PREFERENCES.get(role, DEFAULT_PREFERENCES["operacional"]).copy()
        ctx = {
            "phone": phone,
            "role": role,
            "preferencias": prefs,
            "estado": {"os_em_foco": None, "cliente_em_foco": None, "aguardando": None},
            "historico_acoes": [],
            "avaria_pendente": None,
            "criado_em": _now(),
        }
        self._backend_save(phone, ctx)
        return ctx

    def _backend_get(self, phone: str) -> dict | None:
        if self._use_db:
            try:
                from utils.database import get_session, UserContextDB
                with get_session() as s:
                    row = s.get(UserContextDB, phone)
                    if row:
                        return {
                            "phone": row.phone,
                            "role": row.role,
                            "preferencias": json.loads(row.preferences_json or "{}"),
                            "historico_acoes": json.loads(row.actions_json or "[]"),
                        }
                return None
            except Exception as e:
                logger.error("[UserContext] Erro DB get: %s", e)
        return self._contexts.get(phone)

    def _backend_save(self, phone: str, ctx: dict):
        if self._use_db:
            try:
                from utils.database import get_session, UserContextDB
                with get_session() as s:
                    row = s.get(UserContextDB, phone)
                    if row:
                        row.role = ctx.get("role", "operacional")
                        row.preferences_json = json.dumps(ctx.get("preferencias", {}), ensure_ascii=False)
                        row.actions_json = json.dumps(ctx.get("historico_acoes", []), ensure_ascii=False)
                    else:
                        row = UserContextDB(
                            phone=phone,
                            role=ctx.get("role", "operacional"),
                            preferences_json=json.dumps(ctx.get("preferencias", {}), ensure_ascii=False),
                            actions_json=json.dumps(ctx.get("historico_acoes", []), ensure_ascii=False),
                        )
                        s.add(row)
                    s.commit()
                return
            except Exception as e:
                logger.error("[UserContext] Erro DB save: %s", e)
        # fallback
        self._contexts[phone] = ctx
        self._file_save()

    # ── API pública ──

    def get_preferencias(self, phone: str) -> dict:
        ctx = self._get_or_create(phone)
        return ctx.get("preferencias", {})

    def update_preferences(self, phone: str, updates: dict):
        """Atualiza preferências ou qualquer campo livre do contexto."""
        ctx = self._get_or_create(phone)
        if "preferencias" not in ctx:
            ctx["preferencias"] = {}
        # Campos especiais (estado de avaria pendente, etc.) vão direto no ctx
        for k, v in updates.items():
            if k in ("avaria_pendente", "estado", "os_em_foco"):
                ctx[k] = v
            else:
                ctx["preferencias"][k] = v
        self._backend_save(phone, ctx)

    def quer_notificacao(self, phone: str, tipo: str) -> bool:
        prefs = self.get_preferencias(phone)
        return prefs.get(f"alertas_{tipo}", False)

    def registrar_acao(self, phone: str, acao: str, detalhes: dict = None):
        """Registra uma ação no histórico do usuário."""
        ctx = self._get_or_create(phone)
        hist = ctx.get("historico_acoes", [])
        hist.append({
            "acao": acao,
            "timestamp": _now(),
            "detalhes": detalhes or {}
        })
        if len(hist) > MAX_ACOES:
            hist = hist[-MAX_ACOES:]
        ctx["historico_acoes"] = hist
        self._backend_save(phone, ctx)

    def get_ultima_acao(self, phone: str) -> dict | None:
        ctx = self._backend_get(phone)
        if not ctx:
            return None
        hist = ctx.get("historico_acoes", [])
        return hist[-1] if hist else None

    def get_contexto_para_prompt(self, phone: str, role: str = "") -> str:
        """Retorna string com contexto do usuário para injetar no system prompt."""
        ctx = self._backend_get(phone)
        if not ctx:
            return ""
        prefs = ctx.get("preferencias", {})
        ultima = self.get_ultima_acao(phone)
        linhas = ["[CONTEXTO DO USUÁRIO]"]
        if prefs.get("modo_verboso"):
            linhas.append("- Prefere respostas detalhadas")
        if ultima:
            linhas.append(f"- Última ação: {ultima.get('acao')} em {ultima.get('timestamp', '')[:16]}")
        # Avaria pendente aguardando número da OS
        av_pend = ctx.get("avaria_pendente") or prefs.get("avaria_pendente")
        if av_pend and av_pend.get("aguardando_os"):
            linhas.append(f"- ⚠️ AVARIA PENDENTE: foto recebida, aguardando número da OS")
            linhas.append(f"  message_id: {av_pend.get('message_id', '')}")
            linhas.append(f"  item: {av_pend.get('descricao', '')}")
            linhas.append("  Se o usuário informar um número de OS, registre a avaria imediatamente.")
        return "\n".join(linhas) if len(linhas) > 1 else ""

    def get_context(self, phone: str) -> dict:
        return self._get_or_create(phone)

    # ── Fallback arquivo ──

    def _file_load(self) -> dict:
        if CONTEXT_FILE.exists():
            try:
                return json.loads(CONTEXT_FILE.read_text())
            except Exception as e:
                logger.error("[UserContext] Erro arquivo load: %s", e)
        return {}

    def _file_save(self):
        try:
            CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONTEXT_FILE.write_text(json.dumps(self._contexts, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error("[UserContext] Erro arquivo save: %s", e)


# Instância global
user_context_manager = UserContextManager()
