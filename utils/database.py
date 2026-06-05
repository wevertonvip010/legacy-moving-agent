"""
utils/database.py — Legacy Moving Agent

Camada de persistência SQLite via SQLAlchemy.
Substitui os arquivos JSON em /tmp por banco de dados persistente.

Tabelas:
  - user_profiles: perfis e permissões dos funcionários
  - conversation_memory: histórico de conversa por telefone
  - user_context: contexto individual e preferências

O banco fica em DATABASE_URL (padrão: sqlite:///agent_data.db)
No Railway: configure DATABASE_URL como variável de ambiente.
"""

import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# URL do banco — padrão SQLite local, aceita PostgreSQL em produção
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agent_data.db")
# Railway usa postgres://, SQLAlchemy precisa de postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    """Perfil de usuário por número de WhatsApp."""
    __tablename__ = "user_profiles"

    phone = Column(String(30), primary_key=True)
    nome = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False, default="operacional")
    ativo = Column(Boolean, default=True)
    funcionario_id = Column(String(50), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    ultimo_acesso = Column(DateTime, nullable=True)
    total_acessos = Column(Integer, default=0)
    dados_extras = Column(Text, default="{}")  # JSON livre para extensões

    def to_dict(self) -> dict:
        return {
            "phone": self.phone,
            "nome": self.nome,
            "role": self.role,
            "ativo": self.ativo,
            "funcionario_id": self.funcionario_id,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "ultimo_acesso": self.ultimo_acesso.isoformat() if self.ultimo_acesso else None,
            "total_acessos": self.total_acessos,
        }


class ConversationHistory(Base):
    """Histórico de conversa por número de WhatsApp."""
    __tablename__ = "conversation_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(30), nullable=False, index=True)
    messages_json = Column(Text, default="[]")  # Lista de mensagens em JSON
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_messages = Column(Integer, default=0)


class UserContextDB(Base):
    """Contexto e preferências individuais por usuário."""
    __tablename__ = "user_context"

    phone = Column(String(30), primary_key=True)
    role = Column(String(30), default="operacional")
    preferences_json = Column(Text, default="{}")
    actions_json = Column(Text, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Cria todas as tabelas se não existirem."""
    try:
        Base.metadata.create_all(engine)
        logger.info("[DB] Banco de dados inicializado: %s", DATABASE_URL.split("///")[-1])
    except Exception as e:
        logger.error("[DB] Erro ao inicializar banco: %s", e)
        raise


def get_session() -> Session:
    """Retorna uma sessão do banco de dados."""
    return SessionLocal()


# ────────────────────────────────────────────────
# HELPERS — UserProfile
# ────────────────────────────────────────────────

def db_get_profile(phone: str) -> dict | None:
    """Busca perfil pelo telefone. Retorna dict ou None."""
    with get_session() as session:
        p = session.get(UserProfile, phone)
        return p.to_dict() if p else None


def db_upsert_profile(phone: str, nome: str, role: str,
                      funcionario_id: str = None, ativo: bool = True) -> dict:
    """Cria ou atualiza um perfil."""
    with get_session() as session:
        p = session.get(UserProfile, phone)
        if p:
            p.nome = nome
            p.role = role
            p.ativo = ativo
            if funcionario_id is not None:
                p.funcionario_id = funcionario_id
        else:
            p = UserProfile(
                phone=phone, nome=nome, role=role,
                ativo=ativo, funcionario_id=funcionario_id
            )
            session.add(p)
        session.commit()
        session.refresh(p)
        return p.to_dict()


def db_registrar_acesso(phone: str):
    """Atualiza último acesso e incrementa contador."""
    with get_session() as session:
        p = session.get(UserProfile, phone)
        if p:
            p.ultimo_acesso = datetime.utcnow()
            p.total_acessos = (p.total_acessos or 0) + 1
            session.commit()


def db_list_profiles() -> list:
    """Lista todos os perfis ativos."""
    with get_session() as session:
        profiles = session.query(UserProfile).all()
        return [p.to_dict() for p in profiles]


def db_delete_profile(phone: str):
    """Remove um perfil."""
    with get_session() as session:
        p = session.get(UserProfile, phone)
        if p:
            session.delete(p)
            session.commit()


# ────────────────────────────────────────────────
# HELPERS — ConversationMemory
# ────────────────────────────────────────────────

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))
SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "2"))


def db_get_history(phone: str) -> list:
    """Retorna histórico de mensagens, respeitando timeout de sessão."""
    from datetime import timedelta
    with get_session() as session:
        row = session.query(ConversationHistory).filter_by(phone=phone).first()
        if not row:
            return []
        # Verificar timeout
        if row.last_activity:
            age = datetime.utcnow() - row.last_activity
            if age.total_seconds() > SESSION_TIMEOUT_HOURS * 3600:
                db_clear_history(phone)
                return []
        try:
            return json.loads(row.messages_json)
        except Exception:
            return []


def db_save_history(phone: str, messages: list):
    """Salva histórico (truncando para MAX_HISTORY mensagens)."""
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]
    with get_session() as session:
        row = session.query(ConversationHistory).filter_by(phone=phone).first()
        if row:
            row.messages_json = json.dumps(messages, ensure_ascii=False)
            row.last_activity = datetime.utcnow()
            row.total_messages = len(messages)
        else:
            row = ConversationHistory(
                phone=phone,
                messages_json=json.dumps(messages, ensure_ascii=False),
                total_messages=len(messages)
            )
            session.add(row)
        session.commit()


def db_clear_history(phone: str):
    """Limpa histórico de um usuário."""
    with get_session() as session:
        session.query(ConversationHistory).filter_by(phone=phone).delete()
        session.commit()
