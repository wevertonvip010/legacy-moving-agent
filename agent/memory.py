"""
agent/memory.py — Legacy Moving Agent

Gerencia o histórico de conversas por usuário (número de WhatsApp).
Usa SQLite via utils/database.py para persistência entre deploys.
Mantém fallback para arquivos JSON se o banco falhar.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Configurações
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "20"))
SESSION_TIMEOUT_HOURS = int(os.environ.get("SESSION_TIMEOUT_HOURS", "2"))

# Diretório de fallback (caso banco falhe)
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/tmp/agent_memory"))


class ConversationMemory:
    """
    Armazena histórico de conversa por número de telefone.
    Usa banco de dados SQLite (persistente entre deploys).
    Fallback automático para arquivos JSON em /tmp.
    """

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._use_db = self._check_db()

    def _check_db(self) -> bool:
        """Verifica se o banco de dados está disponível."""
        try:
            from utils.database import db_get_history
            db_get_history("test_connection")
            return True
        except Exception as e:
            logger.warning("[Memory] Banco não disponível, usando arquivos: %s", e)
            return False

    def get_history(self, phone: str) -> list:
        """Retorna o histórico de mensagens do usuário."""
        if self._use_db:
            try:
                from utils.database import db_get_history
                return db_get_history(phone)
            except Exception as e:
                logger.error("[Memory] Erro DB get_history: %s", e)
        return self._file_get_history(phone)

    def save_history(self, phone: str, messages: list):
        """Salva o histórico de mensagens do usuário."""
        if self._use_db:
            try:
                from utils.database import db_save_history
                db_save_history(phone, messages)
                return
            except Exception as e:
                logger.error("[Memory] Erro DB save_history: %s", e)
        self._file_save_history(phone, messages)

    def clear_history(self, phone: str):
        """Limpa o histórico de conversa do usuário."""
        if self._use_db:
            try:
                from utils.database import db_clear_history
                db_clear_history(phone)
            except Exception:
                pass
        path = self._file_path(phone)
        if path.exists():
            path.unlink()
        logger.info("[%s] Histórico limpo", phone)

    # ── Fallback em arquivo ──

    def _file_path(self, phone: str) -> Path:
        safe_phone = "".join(c for c in phone if c.isdigit())
        return MEMORY_DIR / f"{safe_phone}.json"

    def _file_get_history(self, phone: str) -> list:
        path = self._file_path(phone)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            last_activity = data.get("last_activity")
            if last_activity:
                last_dt = datetime.fromisoformat(last_activity)
                if datetime.now() - last_dt > timedelta(hours=SESSION_TIMEOUT_HOURS):
                    self.clear_history(phone)
                    return []
            return data.get("messages", [])
        except Exception as e:
            logger.error("[Memory] Erro arquivo get_history %s: %s", phone, e)
            return []

    def _file_save_history(self, phone: str, messages: list):
        if len(messages) > MAX_HISTORY:
            messages = messages[-MAX_HISTORY:]
        path = self._file_path(phone)
        try:
            data = {
                "phone": phone,
                "messages": messages,
                "last_activity": datetime.now().isoformat(),
                "total_messages": len(messages)
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error("[Memory] Erro arquivo save_history %s: %s", phone, e)

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso da memória."""
        return {
            "backend": "database" if self._use_db else "arquivo_tmp",
            "sessions_arquivo": len(list(MEMORY_DIR.glob("*.json"))),
        }
