"""
integrations/legacy_api.py
Cliente HTTP para a API REST do ERP Legacy Moving.
Todas as chamadas ao backend passam por esta classe.
"""
import os
import logging
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

LEGACY_API_URL = os.environ.get('LEGACY_API_URL', 'http://localhost:5000')
LEGACY_JWT_TOKEN = os.environ.get('LEGACY_JWT_TOKEN', '')


class LegacyAPI:
      """
          Cliente para a API do Legacy Moving ERP.

                  Configurar via variaveis de ambiente:
                      - LEGACY_API_URL: URL do backend (ex: https://legacy.railway.app)
                          - LEGACY_JWT_TOKEN: Token JWT de um usuario admin para autenticacao
                              """

    def __init__(self):
              self.base_url = LEGACY_API_URL.rstrip('/')
              self._token = LEGACY_JWT_TOKEN
              self._session = requests.Session()
              self._session.headers.update({
                  'Content-Type': 'application/json',
                  'Authorization': f'Bearer {self._token}'
              })

    def _url(self, path: str) -> str:
              return f'{self.base_url}{path}'

    def get(self, path: str, params: dict = None) -> dict | list:
              """Executa GET na API Legacy Moving."""
              try:
                            resp = self._session.get(self._url(path), params=params, timeout=10)
                            resp.raise_for_status()
                            return resp.json()
except requests.exceptions.ConnectionError:
            logger.error(f'Nao foi possivel conectar ao ERP: {self.base_url}')
            return {'erro': 'Sistema ERP indisponivel no momento. Tente novamente em instantes.'}
except requests.exceptions.Timeout:
            logger.error(f'Timeout ao chamar {path}')
            return {'erro': 'Sistema ERP demorou muito para responder.'}
except requests.exceptions.HTTPError as e:
            logger.error(f'Erro HTTP {e.response.status_code} em GET {path}')
            if e.response.status_code == 401:
                              return {'erro': 'Token de autenticacao invalido. Configure LEGACY_JWT_TOKEN.'}
                          if e.response.status_code == 404:
                                            return {'erro': f'Recurso nao encontrado: {path}'}
                                        return {'erro': f'Erro {e.response.status_code}: {e.response.text[:200]}'}
except Exception as e:
            logger.error(f'Erro inesperado em GET {path}: {e}')
            return {'erro': str(e)}

    def post(self, path: str, data: dict) -> dict:
              """Executa POST na API Legacy Moving."""
              try:
                            resp = self._session.post(self._url(path), json=data, timeout=10)
                            resp.raise_for_status()
                            return resp.json()
except requests.exceptions.ConnectionError:
            logger.error(f'Nao foi possivel conectar ao ERP: {self.base_url}')
            return {'erro': 'Sistema ERP indisponivel no momento.'}
except requests.exceptions.HTTPError as e:
            logger.error(f'Erro HTTP {e.response.status_code} em POST {path}: {e.response.text}')
            try:
                              return e.response.json()
except Exception:
                  return {'erro': f'Erro {e.response.status_code}: {e.response.text[:200]}'}
except Exception as e:
              logger.error(f'Erro inesperado em POST {path}: {e}')
              return {'erro': str(e)}

    def put(self, path: str, data: dict) -> dict:
              """Executa PUT na API Legacy Moving."""
              try:
                            resp = self._session.put(self._url(path), json=data, timeout=10)
                            resp.raise_for_status()
                            return resp.json()
except Exception as e:
            logger.error(f'Erro em PUT {path}: {e}')
            return {'erro': str(e)}

    def health_check(self) -> bool:
              """Verifica se a API esta funcionando."""
              try:
                            resp = self._session.get(self._url('/health'), timeout=5)
                            return resp.status_code == 200
except Exception:
            return False
