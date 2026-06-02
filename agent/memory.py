"""
agent/memory.py
Gerencia o historico de conversas por usuario (numero de WhatsApp).
Mantem contexto entre mensagens para conversas naturais.
"""
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(os.environ.get('MEMORY_DIR', '/tmp/agent_memory'))
MAX_HISTORY = 20  # Maximo de mensagens no historico
SESSION_TIMEOUT_HOURS = 2  # Resetar contexto apos 2h de inatividade


class ConversationMemory:
      """Armazena historico de conversa por numero de telefone em arquivos JSON."""

    def __init__(self):
              MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def _file_path(self, phone: str) -> Path:
              # Sanitizar numero de telefone para nome de arquivo seguro
              safe_phone = ''.join(c for c in phone if c.isdigit())
              return MEMORY_DIR / f'{safe_phone}.json'

    def get_history(self, phone: str) -> list:
              """Retorna o historico de mensagens do usuario."""
              path = self._file_path(phone)
              if not path.exists():
                            return []
                        try:
                                      data = json.loads(path.read_text())
                                      # Verificar timeout de sessao
                                      last_activity = data.get('last_activity')
                                      if last_activity:
                                                        last_dt = datetime.fromisoformat(last_activity)
                                                        if datetime.now() - last_dt > timedelta(hours=SESSION_TIMEOUT_HOURS):
                                                                              logger.info(f'[{phone}] Sessao expirada — resetando historico')
                                                                              self.clear_history(phone)
                                                                              return []
                                                                      return data.get('messages', [])
                        except Exception as e:
                                      logger.error(f'Erro ao ler historico de {phone}: {e}')
                                      return []

    def save_history(self, phone: str, messages: list):
              """Salva o historico de mensagens do usuario."""
        path = self._file_path(phone)
        # Manter apenas as ultimas MAX_HISTORY mensagens
        if len(messages) > MAX_HISTORY:
                      messages = messages[-MAX_HISTORY:]
                  try:
                                data = {
                                                  'phone': phone,
                                                  'messages': messages,
                                                  'last_activity': datetime.now().isoformat(),
                                                  'total_messages': len(messages)
                                }
                                path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
            logger.error(f'Erro ao salvar historico de {phone}: {e}')

    def clear_history(self, phone: str):
              """Limpa o historico de conversa do usuario."""
        path = self._file_path(phone)
        if path.exists():
                      path.unlink()
                      logger.info(f'[{phone}] Historico limpo')

    def get_stats(self) -> dict:
              """Retorna estatisticas de uso da memoria."""
        sessions = list(MEMORY_DIR.glob('*.json'))
        return {
                      'total_sessions': len(sessions),
                      'memory_dir': str(MEMORY_DIR)
        }
