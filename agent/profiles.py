"""
agent/profiles.py
Gerencia perfis de usuarios por numero de WhatsApp.
Define quem e cada pessoa, seu cargo e o que pode ver/fazer.

ROLES DISPONIVEIS:
  admin       - Ve e faz tudo (dono / gerente)
    supervisor  - Ve tudo, registra qualquer despesa/OS
      motorista   - Registra proprias despesas, ve propria agenda
        operacional - Registra ocorrencias/avarias, ve OS do dia
          comercial   - Registra leads, ve leads e clientes
            financeiro  - Ve financeiro, registra despesas
            """
import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

PROFILES_FILE = Path(os.environ.get('PROFILES_FILE', '/tmp/agent_profiles.json'))

# Perfil padrao para numeros nao cadastrados
DEFAULT_ROLE = os.environ.get('DEFAULT_ROLE', 'bloqueado')  # bloqueado | operacional


# ── DEFINICAO DE PERMISSOES POR ROLE ─────────────────────────────────────────

ROLE_PERMISSIONS = {
      'admin': {
                'label': 'Administrador',
                'emoji': '👑',
                'pode_ver': ['*'],  # tudo
                'pode_fazer': ['*'],  # tudo
                'saudacao': f'Ola, Admin da {COMPANY_NAME}! Estou pronto. Contato: {COMPANY_EMAIL}'
      },
      'supervisor': {
                'label': 'Supervisor',
                'emoji': '🔧',
                'pode_ver': ['os', 'programacao', 'equipe', 'estoque', 'financeiro', 'avarias', 'leads', 'clientes'],
                'pode_fazer': ['registrar_despesa', 'registrar_avaria', 'consultar_os', 'consultar_equipe', 'consultar_estoque'],
                'saudacao': 'Ola, Supervisor! Posso te ajudar com OS, equipe, estoque e financeiro.'
      },
      'motorista': {
                'label': 'Motorista',
                'emoji': '🚛',
                'pode_ver': ['os_propria', 'programacao_propria', 'despesas_proprias'],
                'pode_fazer': ['registrar_despesa_propria', 'registrar_ocorrencia', 'consultar_os_hoje'],
                'saudacao': 'Ola! Pode mandar foto de comprovante, registrar ocorrencia ou consultar sua agenda do dia.'
      },
      'operacional': {
                'label': 'Equipe Operacional',
                'emoji': '📦',
                'pode_ver': ['os_hoje', 'programacao_hoje'],
                'pode_fazer': ['registrar_ocorrencia', 'registrar_avaria', 'consultar_os_hoje'],
                'saudacao': 'Ola! Posso te ajudar com as OS do dia, registrar ocorrencias ou avarias.'
      },
      'comercial': {
                'label': 'Comercial / Vendedor',
                'emoji': '💼',
                'pode_ver': ['leads', 'clientes', 'orcamentos'],
                'pode_fazer': ['criar_lead', 'consultar_leads', 'consultar_clientes'],
                'saudacao': 'Ola! Posso te ajudar a registrar leads, consultar clientes e acompanhar orcamentos.'
      },
      'financeiro': {
                'label': 'Financeiro',
                'emoji': '💰',
                'pode_ver': ['financeiro', 'despesas', 'recibos', 'fechamentos'],
                'pode_fazer': ['registrar_despesa', 'consultar_financeiro', 'consultar_recibos'],
                'saudacao': 'Ola! Posso te ajudar com lancamentos financeiros, despesas e consultas de recibos.'
      },
      'bloqueado': {
                'label': 'Sem Acesso',
                'emoji': '🔒',
                'pode_ver': [],
                'pode_fazer': [],
                'saudacao': f'Seu numero nao esta cadastrado no sistema {COMPANY_NAME}. Solicite acesso ao administrador: {COMPANY_EMAIL}'
      }
}


# ── GERENCIAMENTO DE PERFIS ────────────────────────────────────────────────────

class ProfileManager:
      """Gerencia o cadastro de usuarios por numero de WhatsApp."""

    def __init__(self):
              self._profiles = self._carregar()

    def _carregar(self) -> dict:
              """Carrega perfis do arquivo JSON."""
              if PROFILES_FILE.exists():
                            try:
                                              return json.loads(PROFILES_FILE.read_text())
except Exception as e:
                logger.error(f'Erro ao carregar perfis: {e}')
        return {}

    def _salvar(self):
              """Salva perfis no arquivo JSON."""
              try:
                            PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
                            PROFILES_FILE.write_text(json.dumps(self._profiles, ensure_ascii=False, indent=2))
except Exception as e:
            logger.error(f'Erro ao salvar perfis: {e}')

    def get_perfil(self, phone: str) -> dict:
              """Retorna o perfil de um usuario pelo numero."""
              phone = _normalizar_phone(phone)
              perfil = self._profiles.get(phone)

        if not perfil:
                      return {
                                        'phone': phone,
                                        'nome': 'Desconhecido',
                                        'role': DEFAULT_ROLE,
                                        'ativo': DEFAULT_ROLE != 'bloqueado',
                                        'cadastrado': False
                      }

        return {**perfil, 'cadastrado': True}

    def cadastrar(self, phone: str, nome: str, role: str, funcionario_id: int = None) -> dict:
              """Cadastra ou atualiza um usuario."""
              phone = _normalizar_phone(phone)
              if role not in ROLE_PERMISSIONS:
                            return {'erro': f'Role invalido: {role}. Use: {list(ROLE_PERMISSIONS.keys())}'}

              self._profiles[phone] = {
                  'phone': phone,
                  'nome': nome,
                  'role': role,
                  'funcionario_id': funcionario_id,
                  'ativo': True,
                  'cadastrado_em': datetime.now().isoformat(),
                  'ultimo_acesso': None
              }
              self._salvar()
              logger.info(f'Usuario cadastrado: {nome} ({phone}) como {role}')
              return {'ok': True, 'mensagem': f'{nome} cadastrado como {role}'}

    def registrar_acesso(self, phone: str):
              """Atualiza timestamp de ultimo acesso."""
              phone = _normalizar_phone(phone)
              if phone in self._profiles:
                            self._profiles[phone]['ultimo_acesso'] = datetime.now().isoformat()
                            self._salvar()

          def listar_usuarios(self) -> list:
                    """Lista todos os usuarios cadastrados."""
                    return list(self._profiles.values())

    def remover(self, phone: str) -> dict:
              """Remove um usuario."""
              phone = _normalizar_phone(phone)
              if phone in self._profiles:
                            nome = self._profiles[phone].get('nome', phone)
                            del self._profiles[phone]
                            self._salvar()
                            return {'ok': True, 'mensagem': f'{nome} removido'}
                        return {'erro': 'Usuario nao encontrado'}

    def pode_fazer(self, phone: str, acao: str) -> bool:
              """Verifica se um usuario tem permissao para uma acao."""
        perfil = self.get_perfil(phone)
        role = perfil.get('role', 'bloqueado')
        perms = ROLE_PERMISSIONS.get(role, {})
        pode = perms.get('pode_fazer', [])
        return '*' in pode or acao in pode or any(p in acao for p in pode)

    def get_saudacao(self, phone: str) -> str:
              """Retorna saudacao personalizada para o usuario."""
        perfil = self.get_perfil(phone)
        role = perfil.get('role', 'bloqueado')
        nome = perfil.get('nome', '')
        role_info = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['bloqueado'])
        emoji = role_info['emoji']
        saudacao = role_info['saudacao']
        if nome and nome != 'Desconhecido':
                      return f'{emoji} Ola, *{nome}*! {saudacao}'
                  return f'{emoji} {saudacao}'


def _normalizar_phone(phone: str) -> str:
      """Normaliza numero de telefone removendo caracteres especiais."""
    return ''.join(c for c in str(phone) if c.isdigit())


# Instancia global
profile_manager = ProfileManager()
