import os
import logging
import atexit
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from utils.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*")

# ── BLUEPRINTS ────────────────────────────────────────────────────────────────

from webhooks.whatsapp import whatsapp_bp
app.register_blueprint(whatsapp_bp, url_prefix="/webhook")

from webhooks.admin import admin_bp
app.register_blueprint(admin_bp)

# ── ROTAS DE STATUS ───────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    from integrations.evolution import is_connected
    from utils.scheduler import list_jobs
    connected = is_connected()
    jobs = list_jobs()
    return jsonify({
        "status": "ok",
        "service": "legacy-moving-agent",
        "version": "4.0.0",
        "whatsapp_connected": connected,
        "scheduled_jobs": len(jobs),
    }), 200


@app.route("/status", methods=["GET"])
def status():
    """Status detalhado de todos os componentes do sistema."""
    from integrations.evolution import get_instance_status, EVOLUTION_INSTANCE
    from integrations.google_calendar import is_available as gcal_available
    from integrations.google_drive import is_available as drive_available
    from utils.scheduler import list_jobs
    from integrations.legacy_api import LegacyAPI

    api = LegacyAPI()
    whatsapp_status = {}
    try:
        whatsapp_status = get_instance_status(EVOLUTION_INSTANCE)
    except Exception as e:
        whatsapp_status = {"erro": str(e)}

    return jsonify({
        "status": "ok",
        "version": "4.0.0",
        "fases": {
            "fase1": "Estrutura base + ferramentas principais",
            "fase2": "Notificacoes automaticas + Google Agenda",
            "fase3": "Drive inteligente + Analytics proativos",
            "fase4": "Multi-usuario com contexto individual",
        },
        "components": {
            "whatsapp": whatsapp_status,
            "erp_online": api.health_check(),
            "google_calendar": gcal_available(),
            "google_drive": drive_available(),
            "scheduler_jobs": list_jobs(),
        },
    }), 200


@app.route("/admin/jobs", methods=["GET"])
def list_scheduled_jobs():
    """Lista todos os jobs agendados (compatibilidade com rota legada)."""
    from utils.scheduler import list_jobs
    return jsonify({"jobs": list_jobs()}), 200


# ── INICIALIZACAO ─────────────────────────────────────────────────────────────

def init_scheduler():
    """Inicializa o scheduler de notificacoes automaticas."""
    try:
        from utils.scheduler import start_scheduler, stop_scheduler
        from agent.profiles import ProfileManager
        import integrations.evolution as evolution
        from integrations.legacy_api import LegacyAPI

        profiles = ProfileManager()
        legacy_api = LegacyAPI()

        started = start_scheduler(profiles, evolution, legacy_api)
        if started:
            logger.info("[Main] Scheduler iniciado com sucesso")
            atexit.register(stop_scheduler)
        else:
            logger.warning("[Main] Scheduler nao disponivel")
    except Exception as e:
        logger.error(f"[Main] Erro ao inicializar scheduler: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info(f"Legacy Moving Agent v4.0 rodando na porta {port}")
    logger.info("Fases 1-4 implementadas")
    init_scheduler()
    app.run(host="0.0.0.0", port=port, debug=False)
