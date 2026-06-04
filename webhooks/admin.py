"""
webhooks/admin.py
Blueprint Flask com rotas de administracao do agente.
Permite gerenciar usuarios, disparar relatorios e monitorar o sistema.
TODAS as rotas exigem o header: X-Admin-Token: <AGENT_SECRET>
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

AGENT_SECRET = os.environ.get("AGENT_SECRET", "")
TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")


def _autenticar(req) -> bool:
    """Verifica o token de admin no header."""
    if not AGENT_SECRET:
        return True  # Sem token configurado, permite (dev mode)
    token = req.headers.get("X-Admin-Token", "")
    return token == AGENT_SECRET


def _erro_auth():
    return jsonify({"erro": "Token invalido ou ausente. Use X-Admin-Token."}), 401


# ─────────────────────────────────────────────────────────────
# USUARIOS / PERFIS
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/usuarios", methods=["GET"])
def listar_usuarios():
    """Lista todos os usuarios cadastrados no sistema."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.profiles import profile_manager
        usuarios = profile_manager.listar_usuarios()
        return jsonify({"usuarios": usuarios, "total": len(usuarios)}), 200
    except Exception as e:
        logger.error(f"[Admin] Erro listar_usuarios: {e}")
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/usuarios", methods=["POST"])
def cadastrar_usuario():
    """
    Cadastra um novo usuario.
    Body JSON: {phone, nome, role, funcionario_id (opcional)}
    """
    if not _autenticar(request):
        return _erro_auth()
    try:
        dados = request.get_json() or {}
        phone = dados.get("phone", "").strip()
        nome = dados.get("nome", "").strip()
        role = dados.get("role", "operacional").strip()
        funcionario_id = dados.get("funcionario_id")

        if not phone or not nome:
            return jsonify({"erro": "phone e nome sao obrigatorios"}), 400

        from agent.profiles import profile_manager, ROLE_PERMISSIONS
        if role not in ROLE_PERMISSIONS:
            roles_validos = list(ROLE_PERMISSIONS.keys())
            return jsonify({"erro": f"Role invalido. Use: {roles_validos}"}), 400

        profile_manager.cadastrar(phone, nome, role, funcionario_id=funcionario_id)
        return jsonify({"ok": True, "phone": phone, "nome": nome, "role": role}), 201
    except Exception as e:
        logger.error(f"[Admin] Erro cadastrar_usuario: {e}")
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/usuarios/<phone>", methods=["DELETE"])
def remover_usuario(phone: str):
    """Remove (bloqueia) um usuario do sistema."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.profiles import profile_manager
        profile_manager.remover(phone)
        return jsonify({"ok": True, "phone": phone}), 200
    except Exception as e:
        logger.error(f"[Admin] Erro remover_usuario: {e}")
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/usuarios/<phone>", methods=["PUT"])
def atualizar_usuario(phone: str):
    """Atualiza role ou nome de um usuario."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        dados = request.get_json() or {}
        from agent.profiles import profile_manager
        profile_manager.atualizar(phone, dados)
        return jsonify({"ok": True, "phone": phone}), 200
    except Exception as e:
        logger.error(f"[Admin] Erro atualizar_usuario: {e}")
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# CONTEXTO INDIVIDUAL
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/contextos", methods=["GET"])
def listar_contextos():
    """Lista contextos de todos os usuarios (preferencias, ultima acao)."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.user_context import user_context_manager
        contextos = user_context_manager.listar_usuarios_com_contexto()
        return jsonify({"contextos": contextos, "total": len(contextos)}), 200
    except Exception as e:
        logger.error(f"[Admin] Erro listar_contextos: {e}")
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/contextos/<phone>", methods=["DELETE"])
def limpar_contexto(phone: str):
    """Limpa o estado e historico de um usuario especifico."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.user_context import user_context_manager
        user_context_manager.limpar_estado(phone)
        return jsonify({"ok": True, "phone": phone}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# RELATORIOS E ANALYTICS
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/analytics", methods=["GET"])
def obter_analytics():
    """Retorna analytics proativos consolidados (financeiro, operacional, leads, estoque)."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.analytics import (
            analisar_financeiro, analisar_operacional,
            analisar_estoque, analisar_leads,
        )
        from integrations.legacy_api import LegacyAPI
        api = LegacyAPI()
        return jsonify({
            "financeiro": analisar_financeiro(api),
            "operacional": analisar_operacional(api),
            "estoque": analisar_estoque(api),
            "leads": analisar_leads(api),
            "gerado_em": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"[Admin] Erro analytics: {e}")
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/relatorio-proativo", methods=["POST"])
def disparar_relatorio_proativo():
    """Dispara o relatorio proativo imediatamente (sem esperar o scheduler)."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.analytics import gerar_relatorio_proativo
        from agent.notifications import dispatch_notification, TipoNotificacao
        from agent.profiles import ProfileManager
        from integrations.legacy_api import LegacyAPI
        import integrations.evolution as evolution
        import asyncio

        api = LegacyAPI()
        profiles = ProfileManager()
        relatorio = gerar_relatorio_proativo(api)

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            dispatch_notification(
                tipo=TipoNotificacao.RESUMO_DIARIO,
                message=relatorio,
                profiles_manager=profiles,
                evolution_client=evolution,
            )
        )
        loop.close()

        return jsonify({"ok": True, "enviado_para": result, "relatorio": relatorio}), 200
    except Exception as e:
        logger.error(f"[Admin] Erro relatorio_proativo: {e}")
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# GOOGLE DRIVE
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/drive/arquivos", methods=["GET"])
def listar_arquivos_drive():
    """Lista arquivos no Drive com filtros opcionais."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from integrations.google_drive import buscar_arquivos, is_available
        if not is_available():
            return jsonify({"erro": "Google Drive nao configurado."}), 503
        categoria = request.args.get("categoria")
        query = request.args.get("q", "")
        limite = int(request.args.get("limite", 20))
        arquivos = buscar_arquivos(query_texto=query, categoria=categoria, limite=limite)
        return jsonify({"arquivos": arquivos, "total": len(arquivos)}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/drive/upload", methods=["POST"])
def upload_drive():
    """
    Faz upload de um arquivo (por URL) para o Drive.
    Body JSON: {url, nome, categoria, descricao, os_id}
    """
    if not _autenticar(request):
        return _erro_auth()
    try:
        from integrations.google_drive import upload_from_url, is_available
        if not is_available():
            return jsonify({"erro": "Google Drive nao configurado."}), 503
        dados = request.get_json() or {}
        url = dados.get("url", "")
        nome = dados.get("nome", "arquivo")
        if not url:
            return jsonify({"erro": "url e obrigatorio"}), 400
        result = upload_from_url(
            url=url,
            filename=nome,
            categoria=dados.get("categoria", "outros"),
            descricao=dados.get("descricao", ""),
            os_id=dados.get("os_id"),
        )
        return jsonify(result), 200 if "id" in result else 500
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MENSAGENS DIRETAS
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/mensagem", methods=["POST"])
def enviar_mensagem():
    """
    Envia uma mensagem direta para um ou mais numeros.
    Body JSON: {numeros: [...], mensagem: "..."} ou {cargo: "...", mensagem: "..."}
    """
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.profiles import ProfileManager
        import integrations.evolution as evo

        dados = request.get_json() or {}
        mensagem = dados.get("mensagem", "").strip()
        if not mensagem:
            return jsonify({"erro": "mensagem e obrigatoria"}), 400

        numeros = dados.get("numeros", [])
        cargo = dados.get("cargo", "")

        if not numeros and cargo:
            pm = ProfileManager()
            roles = [cargo] if cargo != "todos" else ["admin", "supervisor", "motorista",
                                                       "operacional", "comercial", "financeiro"]
            numeros = pm.get_numbers_by_roles(roles)

        if not numeros:
            return jsonify({"erro": "Nenhum destinatario encontrado"}), 400

        enviados = []
        erros = []
        for num in numeros:
            try:
                evo.send_text(num, mensagem)
                enviados.append(num)
            except Exception as ex:
                erros.append({"numero": num, "erro": str(ex)})

        return jsonify({
            "ok": True,
            "enviados": enviados,
            "total_enviados": len(enviados),
            "erros": erros,
        }), 200
    except Exception as e:
        logger.error(f"[Admin] Erro enviar_mensagem: {e}")
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MEMORIA / HISTORICO
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/memoria/<phone>", methods=["DELETE"])
def limpar_memoria(phone: str):
    """Limpa o historico de conversa de um usuario especifico."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.memory import ConversationMemory
        mem = ConversationMemory()
        mem.clear_history(phone)
        return jsonify({"ok": True, "phone": phone}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/memoria", methods=["DELETE"])
def limpar_toda_memoria():
    """Limpa o historico de conversa de TODOS os usuarios."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from agent.memory import ConversationMemory
        mem = ConversationMemory()
        mem.clear_all()
        return jsonify({"ok": True, "mensagem": "Toda a memoria foi limpa."}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# JOBS / SCHEDULER
# ─────────────────────────────────────────────────────────────

@admin_bp.route("/admin/jobs", methods=["GET"])
def listar_jobs():
    """Lista todos os jobs agendados e seus proximos disparos."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from utils.scheduler import list_jobs
        jobs = list_jobs()
        return jsonify({"jobs": jobs, "total": len(jobs)}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@admin_bp.route("/admin/jobs/resumo-diario", methods=["POST"])
def disparar_resumo_diario():
    """Dispara o resumo diario agora (sem esperar o horario agendado)."""
    if not _autenticar(request):
        return _erro_auth()
    try:
        from utils.scheduler import job_resumo_diario
        from agent.profiles import ProfileManager
        from integrations.legacy_api import LegacyAPI
        import integrations.evolution as evolution

        job_resumo_diario(ProfileManager(), evolution, LegacyAPI())
        return jsonify({"ok": True, "mensagem": "Resumo diario disparado."}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
