"""
utils/logger.py
Logger estruturado para o agente Legacy Moving
Formata logs com contexto (número, cargo, ação)
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import Optional


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # "text" ou "json"


def setup_logging() -> None:
    """Configura o logging global da aplicação."""
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    if LOG_FORMAT == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Silencia loggers muito verbosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class JsonFormatter(logging.Formatter):
    """Formata logs como JSON estruturado (ideal para Railway/Cloud)."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Adiciona campos extras se presentes
        for key in ("number", "role", "action", "os_id", "expense_id"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)
        return json.dumps(log_obj, ensure_ascii=False)


class AgentLogger:
    """Logger contextual para o agente — inclui número e cargo automaticamente."""

    def __init__(self, name: str = "agent"):
        self._logger = logging.getLogger(name)
        self._context: dict = {}

    def set_context(self, number: str, role: str, name: str = "") -> None:
        """Define o contexto atual (usuário ativo)."""
        self._context = {
            "number": number[-4:],  # Apenas últimos 4 dígitos por privacidade
            "role": role,
            "name": name,
        }

    def clear_context(self) -> None:
        """Limpa o contexto."""
        self._context = {}

    def _log(self, level: str, message: str, **kwargs) -> None:
        extra = {**self._context, **kwargs}
        ctx_str = " ".join(f"{k}={v}" for k, v in extra.items() if v)
        full_msg = f"{message} | {ctx_str}" if ctx_str else message
        getattr(self._logger, level)(full_msg)

    def info(self, message: str, **kwargs) -> None:
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log("error", message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        self._log("debug", message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        self._log("critical", message, **kwargs)

    # ─── Eventos específicos do agente ───

    def msg_received(self, number: str, role: str, msg_type: str, preview: str = "") -> None:
        """Log de mensagem recebida."""
        self.info(
            f"[MSG_IN] tipo={msg_type} preview={preview[:50]!r}",
            number=number[-4:],
            role=role,
        )

    def msg_sent(self, number: str, chars: int) -> None:
        """Log de mensagem enviada."""
        self.info(f"[MSG_OUT] chars={chars}", number=number[-4:])

    def tool_called(self, tool_name: str, args: dict) -> None:
        """Log de ferramenta chamada pelo agente."""
        safe_args = {k: v for k, v in args.items() if "senha" not in k.lower()}
        self.info(f"[TOOL] {tool_name} args={safe_args}")

    def tool_result(self, tool_name: str, success: bool, details: str = "") -> None:
        """Log de resultado de ferramenta."""
        status = "OK" if success else "FAIL"
        self.info(f"[TOOL_RESULT] {tool_name} status={status} {details}")

    def user_blocked(self, number: str) -> None:
        """Log de acesso negado."""
        self.warning(f"[ACCESS_DENIED] number=...{number[-4:]}")

    def vision_analyzed(self, media_type: str, success: bool) -> None:
        """Log de análise de imagem."""
        status = "OK" if success else "FAIL"
        self.info(f"[VISION] type={media_type} status={status}")

    def audio_transcribed(self, duration_s: float, success: bool) -> None:
        """Log de transcrição de áudio."""
        status = "OK" if success else "FAIL"
        self.info(f"[AUDIO] duration={duration_s:.1f}s status={status}")


# Instância global para uso em toda a aplicação
agent_logger = AgentLogger("legacy.agent")


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger padrão para o módulo especificado."""
    return logging.getLogger(name)
