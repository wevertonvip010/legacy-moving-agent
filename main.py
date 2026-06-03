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

# Registrar blueprints
from webhooks.whatsapp import whatsapp_bp
app.register_blueprint(whatsapp_bp, url_prefix='/webhook')


# ── ROTAS DE STATUS ───────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    from integrations.evolution import is_connected
    from utils.scheduler import list_jobs
    connected = is_connected()
    jobs = list_jobs()
    return jsonify({
        'status': 'ok',
        'service': 'legacy-moving-agent',
        'version': '2.0.0',
        'whatsapp_connected': connected,
        'scheduled_jobs': len(jobs),
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Status detalhado do sistema."""
    from integrations.evolution import get_instance_status, EVOLUTION_INSTANCE
    from integrations.google_calendar import is_available as gcal_available
    from utils.scheduler import list_jobs

    whatsapp_status = {}
    try:
        whatsapp_status = get_instance_status(EVOLUTION_INSTANCE)
    except Exception as e:
        whatsapp_status = {'error': str(e)}

    return jsonify({
        'status': 'ok',
        'version': '2.0.0',
        'components': {
            'whatsapp': whatsapp_status,
            'google_calendar': gcal_available(),
            'scheduler_jobs': list_jobs(),
        }
    }), 200


@app.route('/admin/jobs', methods=['GET'])
def list_scheduled_jobs():
    """Lista todos os jobs agendados (admin)."""
    from utils.scheduler import list_jobs
    return jsonify({'jobs': list_jobs()}), 200


# ── INICIALIZACAO ─────────────────────────────────────────────────────────

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
            # Para o scheduler limpo ao encerrar a aplicacao
            atexit.register(stop_scheduler)
        else:
            logger.warning("[Main] Scheduler nao disponivel — notificacoes automaticas desativadas")
    except Exception as e:
        logger.error(f"[Main] Erro ao inicializar scheduler: {e}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    logger.info(f'Legacy Moving Agent v2.0 rodando na porta {port}')
    logger.info('Fase 2: Notificacoes automaticas + Google Calendar')

    # Inicializa scheduler (nao bloqueia se falhar)
    init_scheduler()

    app.run(host='0.0.0.0', port=port, debug=False)
