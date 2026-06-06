"""
main.py — Legacy Moving Agent v5.2

Ponto de entrada da aplicação Flask.
Inicializa todas as integrações, registra blueprints e inicia o scheduler.

Novidades v5.0:
- Sistema de Avarias: DamageRegistry inicializado e disponível
- Webhook WhatsApp com detecção automática de fotos de avaria
"""

import os
import logging
from flask import Flask, jsonify
from datetime import datetime

# ── Configuração de logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ── Criação do app Flask ──
app = Flask(__name__)


def init_integrations():
    """Inicializa todas as integrações externas."""
    logger.info("Inicializando integrações...")

    # Google Drive
    try:
        from integrations.google_drive import init_google_drive
        drive = init_google_drive()
        logger.info("✅ Google Drive inicializado")
    except Exception as e:
        logger.warning("⚠️ Google Drive não disponível: %s", e)
        drive = None

    # Legacy API (ERP)
    try:
        from integrations.legacy_api import LegacyAPI
        import integrations.legacy_api as la_module
        api = LegacyAPI(
            base_url=os.getenv("LEGACY_API_URL", ""),
            api_key=os.getenv("LEGACY_API_KEY", "")
        )
        la_module.legacy_api = api
        logger.info("✅ Legacy API (ERP) inicializada")
    except Exception as e:
        logger.warning("⚠️ Legacy API não disponível: %s", e)
        api = None

    # Google Calendar
    try:
        from integrations.google_calendar import init_google_calendar
        cal = init_google_calendar()
        logger.info("✅ Google Calendar inicializado")
    except Exception as e:
        logger.warning("⚠️ Google Calendar não disponível: %s", e)

    # DamageRegistry — Sistema de Avarias
    try:
        from integrations.damage_registry import init_damage_registry
        init_damage_registry(drive_integration=drive, legacy_api=api)
        logger.info("✅ DamageRegistry (avarias) inicializado")
    except Exception as e:
        logger.warning("⚠️ DamageRegistry não disponível: %s", e)

    logger.info("Integrações concluídas.")


def register_blueprints():
    """Registra todos os blueprints Flask."""
    # Webhook WhatsApp
    try:
        from webhooks.whatsapp import whatsapp_bp
        app.register_blueprint(whatsapp_bp)
        logger.info("✅ Blueprint webhook/whatsapp registrado")
    except Exception as e:
        logger.error("❌ Erro ao registrar webhook/whatsapp: %s", e)

    # Admin API
    try:
        from webhooks.admin import admin_bp
        app.register_blueprint(admin_bp)
        logger.info("✅ Blueprint admin registrado")
    except Exception as e:
        logger.error("❌ Erro ao registrar admin: %s", e)


def start_scheduler():
    """Inicia o scheduler de tarefas automáticas."""
    try:
        from utils.scheduler import start_scheduler
        import integrations.evolution as evolution_module
        from agent.profiles import profile_manager
        from integrations.legacy_api import legacy_api as _api
        start_scheduler(
            profiles_manager=profile_manager,
            evolution_client=evolution_module,
            legacy_api=_api
        )
        logger.info("✅ Scheduler iniciado")
    except Exception as e:
        logger.warning("⚠️ Scheduler não iniciado: %s", e)


# ── Rotas principais ──

@app.route("/", methods=["GET"])
def index():
    """Rota raiz — informações básicas da API."""
    return jsonify({
        "app": "Legacy Moving Agent",
        "version": "5.2.0",
        "email": os.getenv("COMPANY_EMAIL", "legacymovingbr@gmail.com"),
        "status": "online",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/status", methods=["GET"])
def status():
    """Health check detalhado."""
    from integrations import google_drive as gd_module
    import integrations.legacy_api as la_module
    from integrations.damage_registry import damage_registry

    return jsonify({
        "status": "ok",
        "version": "5.0.0",
        "timestamp": datetime.now().isoformat(),
        "integrations": {
            "google_drive": gd_module.google_drive is not None,
            "legacy_api": la_module.legacy_api is not None,
            "damage_registry": damage_registry is not None,
        },
        "features": [
            "OS e Google Agenda",
            "Notificacoes WhatsApp",
            "Google Drive",
            "Analises Proativas",
            "Multi-usuario",
            "Registro de Avarias (Fase 5)"
        ]
    })


# ── Inicialização ──

with app.app_context():
    # 0. Inicializar banco de dados (deve ser primeiro)
    try:
        from utils.database import init_db
        init_db()
        logger.info("✅ Banco de dados inicializado")
    except Exception as e:
        logger.error("❌ Erro ao inicializar banco: %s", e)

    init_integrations()
    register_blueprints()
    start_scheduler()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    logger.info("Iniciando Legacy Moving Agent v5.0 na porta %d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
