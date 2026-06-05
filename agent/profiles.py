"""
agent/profiles.py — Legacy Moving Agent

Gerencia perfis de usuários por número de WhatsApp.
Define quem é cada pessoa, seu cargo e o que pode ver/fazer.

Persistência: SQLite via utils/database.py (com fallback em arquivo JSON).

ROLES DISPONÍVEIS:
  admin       — Vê e faz tudo (dono/gerente)
  supervisor  — Vê tudo, registra qualquer despesa/OS
  motorista   — Registra despesas próprias, vê agenda própria
  operacional — Registra ocorrências/avarias, vê OS do dia
  comercial   — Registra leads, vê leads e clientes
  financeiro  — Vê financeiro, registra despesas
  bloqueado   — Sem acesso (padrão para números não cadastrados)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Fallback em arquivo (caso banco não esteja disponível)
PROFILES_FILE = Path(os.environ.get("PROFILES_FILE", "/tmp/agent_profiles.json"))
DEFAULT_ROLE = os.environ.get("DEFAULT_ROLE", "bloqueado")

# Dados da empresa (lidos via env para flexibilidade)
COMPANY_NAME = os.getenv("COMPANY_NAME", "Legacy Moving")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "legacymovingbr@gmail.com")

# ── PERMISSÕES POR ROLE ──────────────────────────────────────────────────────

ROLE_PERMISSIONS = {
    "admin": {
        "label": "Administrador",
        "emoji": "👑",
        "pode_ver": ["*"],
        "pode_fazer": ["*"],
        "saudacao": f"Olá, Admin da {COMPANY_NAME}! Tudo pronto. Contato: {COMPANY_EMAIL}"
    },
    "supervisor": {
        "label": "Supervisor",
        "emoji": "🔧",
        "pode_ver": ["os", "programacao", "equipe", "estoque", "financeiro", "avarias", "leads", "clientes"],
        "pode_fazer": ["registrar_despesa", "registrar_avaria", "consultar_os", "consultar_equipe"],
        "saudacao": "Olá, Supervisor! Posso te ajudar com OS, equipe, estoque e financeiro."
    },
    "motorista": {
        "label": "Motorista",
        "emoji": "🚛",
        "pode_ver": ["os_propria", "programacao_propria", "despesas_proprias"],
        "pode_fazer": ["registrar_despesa_propria", "registrar_ocorrencia", "consultar_os_hoje"],
        "saudacao": "Olá! Mande foto de comprovante, registre ocorrência ou consulte sua agenda."
    },
    "operacional": {
        "label": "Equipe Operacional",
        "emoji": "📦",
        "pode_ver": ["os_hoje", "programacao_hoje"],
        "pode_fazer": ["registrar_ocorrencia", "registrar_avaria", "consultar_os_hoje"],
        "saudacao": "Olá! Posso ajudar com as OS do dia, registrar ocorrências ou avarias."
    },
    "comercial": {
        "label": "Comercial / Vendedor",
        "emoji": "💼",
        "pode_ver": ["leads", "clientes", "orcamentos"],
        "pode_fazer": ["criar_lead", "consultar_leads", "consultar_clientes"],
        "saudacao": "Olá! Posso ajudar com leads, clientes e orçamentos."
    },
    "financeiro": {
        "label": "Financeiro",
        "emoji": "💰",
        "pode_ver": ["financeiro", "despesas", "recibos", "fechamentos"],
        "pode_fazer": ["registrar_despesa", "consultar_financeiro", "consultar_recibos"],
        "saudacao": "Olá! Posso ajudar com lançamentos financeiros e despesas."
    },
    "bloqueado": {
        "label": "Sem Acesso",
        "emoji": "🔒",
        "pode_ver": [],
        "pode_fazer": [],
        "saudacao": (
            f"Seu número não está cadastrado no sistema {COMPANY_NAME}.\n"
            f"Solicite acesso ao administrador: {COMPANY_EMAIL}"
        )
    }
}


# ── NORMALIZAÇÃO ─────────────────────────────────────────────────────────────

def _normalizar_phone(phone: str) -> str:
    """Remove caracteres não numéricos do número de telefone."""
    return "".join(c for c in str(phone) if c.isdigit())


# ── GERENCIADOR DE PERFIS ─────────────────────────────────────────────────────

class ProfileManager:
    """
    Gerencia o cadastro de usuários por número de WhatsApp.
    Usa banco SQLite via utils/database.py.
    Fallback automático para arquivo JSON em /tmp se banco indisponível.
    """

    def __init__(self):
        self._use_db = self._check_db()
        if not self._use_db:
            self._profiles = self._file_carregar()
        else:
            self._profiles = {}  # banco é a fonte da verdade

    def _check_db(self) -> bool:
        """Verifica se o banco de dados está disponível."""
        try:
            from utils.database import db_get_profile
            db_get_profile("__test__")
            return True
        except Exception as e:
            logger.warning("[Profiles] Banco não disponível, usando arquivo: %s", e)
            return False

    # ── Operações principais ──

    def get_perfil(self, phone: str) -> dict:
        """Retorna o perfil de um usuário pelo número."""
        phone = _normalizar_phone(phone)

        perfil = self._backend_get(phone)
        if not perfil:
            return {
                "phone": phone,
                "nome": "Desconhecido",
                "role": DEFAULT_ROLE,
                "ativo": DEFAULT_ROLE != "bloqueado",
                "cadastrado": False
            }
        return {**perfil, "cadastrado": True}

    def cadastrar(self, phone: str, nome: str, role: str,
                  funcionario_id: str = None, ativo: bool = True) -> dict:
        """Cadastra ou atualiza um usuário."""
        phone = _normalizar_phone(phone)
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Role inválido: {role}. Use: {list(ROLE_PERMISSIONS.keys())}")

        if self._use_db:
            try:
                from utils.database import db_upsert_profile
                return db_upsert_profile(phone, nome, role, funcionario_id, ativo)
            except Exception as e:
                logger.error("[Profiles] Erro DB cadastrar: %s", e)

        # Fallback arquivo
        self._profiles[phone] = {
            "phone": phone, "nome": nome, "role": role,
            "ativo": ativo, "funcionario_id": funcionario_id,
            "criado_em": datetime.now().isoformat()
        }
        self._file_salvar()
        return self._profiles[phone]

    def atualizar(self, phone: str, dados: dict) -> dict:
        """Atualiza campos de um perfil existente."""
        phone = _normalizar_phone(phone)
        perfil = self.get_perfil(phone)
        if not perfil.get("cadastrado"):
            raise ValueError(f"Usuário {phone} não cadastrado")
        nome = dados.get("nome", perfil["nome"])
        role = dados.get("role", perfil["role"])
        fid = dados.get("funcionario_id", perfil.get("funcionario_id"))
        ativo = dados.get("ativo", perfil.get("ativo", True))
        return self.cadastrar(phone, nome, role, fid, ativo)

    def remover(self, phone: str):
        """Remove (bloqueia) um usuário do sistema."""
        phone = _normalizar_phone(phone)
        if self._use_db:
            try:
                from utils.database import db_delete_profile
                db_delete_profile(phone)
                return
            except Exception as e:
                logger.error("[Profiles] Erro DB remover: %s", e)
        self._profiles.pop(phone, None)
        self._file_salvar()

    def registrar_acesso(self, phone: str):
        """Atualiza timestamp de último acesso."""
        phone = _normalizar_phone(phone)
        if self._use_db:
            try:
                from utils.database import db_registrar_acesso
                db_registrar_acesso(phone)
                return
            except Exception as e:
                logger.error("[Profiles] Erro DB registrar_acesso: %s", e)
        # Fallback
        if phone in self._profiles:
            self._profiles[phone]["ultimo_acesso"] = datetime.now().isoformat()
            self._file_salvar()

    def listar_usuarios(self) -> list:
        """Lista todos os usuários cadastrados."""
        if self._use_db:
            try:
                from utils.database import db_list_profiles
                return db_list_profiles()
            except Exception as e:
                logger.error("[Profiles] Erro DB listar: %s", e)
        return list(self._profiles.values())

    def pode_fazer(self, phone: str, acao: str) -> bool:
        """Verifica se um usuário pode executar uma ação."""
        perfil = self.get_perfil(phone)
        role = perfil.get("role", "bloqueado")
        perms = ROLE_PERMISSIONS.get(role, {})
        pode = perms.get("pode_fazer", [])
        return "*" in pode or acao in pode

    def get_saudacao(self, phone: str) -> str:
        """Retorna a saudação personalizada para o usuário."""
        perfil = self.get_perfil(phone)
        role = perfil.get("role", "bloqueado")
        nome = perfil.get("nome", "")
        role_info = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["bloqueado"])
        emoji = role_info["emoji"]
        saudacao = role_info["saudacao"]
        if nome and nome != "Desconhecido":
            return f"{emoji} Olá, *{nome}*! {saudacao}"
        return f"{emoji} {saudacao}"

    # ── Backend helpers ──

    def _backend_get(self, phone: str) -> dict | None:
        """Lê perfil do banco ou do arquivo."""
        if self._use_db:
            try:
                from utils.database import db_get_profile
                return db_get_profile(phone)
            except Exception as e:
                logger.error("[Profiles] Erro DB get: %s", e)
        return self._profiles.get(phone)

    # ── Fallback arquivo JSON ──

    def _file_carregar(self) -> dict:
        if PROFILES_FILE.exists():
            try:
                return json.loads(PROFILES_FILE.read_text())
            except Exception as e:
                logger.error("[Profiles] Erro arquivo carregar: %s", e)
        return {}

    def _file_salvar(self):
        try:
            PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
            PROFILES_FILE.write_text(json.dumps(self._profiles, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error("[Profiles] Erro arquivo salvar: %s", e)


# Instância global
profile_manager = ProfileManager()
