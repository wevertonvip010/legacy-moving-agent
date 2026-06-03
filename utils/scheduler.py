"""
utils/scheduler.py
Agendador de tarefas periódicas usando APScheduler
Dispara notificações automáticas: resumo diário, lembretes, alertas
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")
RESUMO_HORA = int(os.getenv("RESUMO_HORA", "7"))          # 07:00
RESUMO_MINUTO = int(os.getenv("RESUMO_MINUTO", "0"))
LEMBRETE_HORAS_ANTES = int(os.getenv("LEMBRETE_HORAS", "24"))  # 24h antes

_scheduler = None


def get_scheduler():
    """Retorna instância do scheduler (lazy init)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.jobstores.memory import MemoryJobStore
        from apscheduler.executors.pool import ThreadPoolExecutor

        jobstores = {"default": MemoryJobStore()}
        executors = {"default": ThreadPoolExecutor(5)}
        job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}

        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=TIMEZONE,
        )
        logger.info("[Scheduler] Inicializado")
        return _scheduler

    except ImportError:
        logger.warning("[Scheduler] APScheduler não instalado. pip install apscheduler")
        return None


# ──────────────────────────────────────────
# JOBS PRINCIPAIS
# ──────────────────────────────────────────

def job_resumo_diario(profiles_manager, evolution_client, legacy_api):
    """Job: envia resumo diário às 7h para admin/supervisor."""
    from agent.notifications import (
        build_resumo_diario_from_api,
        dispatch_notification,
        TipoNotificacao,
    )
    import asyncio

    logger.info("[Scheduler] Executando job_resumo_diario")
    message = build_resumo_diario_from_api(legacy_api)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            dispatch_notification(
                tipo=TipoNotificacao.RESUMO_DIARIO,
                message=message,
                profiles_manager=profiles_manager,
                evolution_client=evolution_client,
            )
        )
        loop.close()
        logger.info(f"[Scheduler] Resumo diário enviado: {result}")
    except Exception as e:
        logger.error(f"[Scheduler] Erro no job_resumo_diario: {e}")


def job_lembretes_os(profiles_manager, evolution_client, legacy_api):
    """Job: verifica OS que iniciam em X horas e envia lembretes para a equipe."""
    from agent.notifications import msg_lembrete_os, TipoNotificacao
    import integrations.evolution as evo

    logger.info("[Scheduler] Executando job_lembretes_os")

    try:
        agora = datetime.now(ZoneInfo(TIMEZONE))
        janela_inicio = agora + timedelta(hours=LEMBRETE_HORAS_ANTES - 1)
        janela_fim = agora + timedelta(hours=LEMBRETE_HORAS_ANTES + 1)

        # Busca OS que começam dentro da janela
        os_list = legacy_api.listar_ordens_servico(
            data_inicio=janela_inicio.isoformat(),
            data_fim=janela_fim.isoformat(),
            status="agendada",
        ) or []

        for os_item in os_list:
            # Encontra motorista/equipe da OS
            responsavel_number = os_item.get("motorista_whatsapp")
            if not responsavel_number:
                continue

            data_hora = os_item.get("data_hora_inicio", "")
            message = msg_lembrete_os(
                numero_os=os_item.get("numero", ""),
                cliente=os_item.get("cliente_nome", ""),
                data_hora=data_hora,
                origem=os_item.get("endereco_origem", ""),
                destino=os_item.get("endereco_destino", ""),
                horas_antes=LEMBRETE_HORAS_ANTES,
            )
            evo.send_text(responsavel_number, message)
            logger.info(f"[Scheduler] Lembrete OS#{os_item.get('numero')} enviado")

    except Exception as e:
        logger.error(f"[Scheduler] Erro no job_lembretes_os: {e}")


def job_verificar_estoque(profiles_manager, evolution_client, legacy_api):
    """Job: verifica itens com estoque abaixo do mínimo e alerta."""
    from agent.notifications import msg_alerta_estoque, TipoNotificacao, NotificationRouter
    import integrations.evolution as evo

    logger.info("[Scheduler] Executando job_verificar_estoque")

    try:
        itens_baixos = legacy_api.listar_estoque(abaixo_minimo=True) or []
        if not itens_baixos:
            return

        destinatarios = profiles_manager.get_numbers_by_roles(
            NotificationRouter.get_roles_for(TipoNotificacao.ALERTA_ESTOQUE)
        )

        for item in itens_baixos:
            message = msg_alerta_estoque(
                item=item.get("nome", ""),
                quantidade_atual=item.get("quantidade", 0),
                quantidade_minima=item.get("quantidade_minima", 0),
                unidade=item.get("unidade", "un"),
            )
            for number in destinatarios:
                evo.send_text(number, message)

        logger.info(f"[Scheduler] {len(itens_baixos)} alertas de estoque enviados")

    except Exception as e:
        logger.error(f"[Scheduler] Erro no job_verificar_estoque: {e}")


def job_verificar_tarefas_vencidas(profiles_manager, evolution_client, legacy_api):
    """Job: verifica tarefas vencidas e alerta admins."""
    from agent.notifications import msg_tarefa_vencida, NotificationRouter, TipoNotificacao
    import integrations.evolution as evo

    logger.info("[Scheduler] Executando job_verificar_tarefas_vencidas")

    try:
        tarefas = legacy_api.listar_tarefas(vencidas=True) or []
        if not tarefas:
            return

        admins = profiles_manager.get_numbers_by_roles(["admin"])
        agora = datetime.now(ZoneInfo(TIMEZONE))

        for tarefa in tarefas[:10]:  # Limita a 10 alertas por vez
            prazo_str = tarefa.get("prazo", "")
            try:
                prazo_dt = datetime.fromisoformat(prazo_str)
                dias_atraso = (agora.date() - prazo_dt.date()).days
            except Exception:
                dias_atraso = 1

            message = msg_tarefa_vencida(
                titulo=tarefa.get("titulo", ""),
                prazo=prazo_str[:10],
                responsavel=tarefa.get("responsavel_nome", ""),
                dias_atraso=max(dias_atraso, 1),
            )
            for number in admins:
                evo.send_text(number, message)

        logger.info(f"[Scheduler] {len(tarefas)} alertas de tarefas vencidas")

    except Exception as e:
        logger.error(f"[Scheduler] Erro no job_verificar_tarefas_vencidas: {e}")


# ──────────────────────────────────────────
# INICIALIZAÇÃO DO SCHEDULER
# ──────────────────────────────────────────

def start_scheduler(profiles_manager, evolution_client, legacy_api):
    """Inicia o scheduler com todos os jobs configurados."""
    scheduler = get_scheduler()
    if scheduler is None:
        logger.warning("[Scheduler] Scheduler não disponível — notificações automáticas desativadas")
        return False

    # ── Resumo diário (todo dia às RESUMO_HORA:RESUMO_MINUTO) ──
    scheduler.add_job(
        job_resumo_diario,
        trigger="cron",
        hour=RESUMO_HORA,
        minute=RESUMO_MINUTO,
        id="resumo_diario",
        replace_existing=True,
        kwargs={
            "profiles_manager": profiles_manager,
            "evolution_client": evolution_client,
            "legacy_api": legacy_api,
        },
    )

    # ── Lembretes de OS (a cada 1 hora) ──
    scheduler.add_job(
        job_lembretes_os,
        trigger="interval",
        hours=1,
        id="lembretes_os",
        replace_existing=True,
        kwargs={
            "profiles_manager": profiles_manager,
            "evolution_client": evolution_client,
            "legacy_api": legacy_api,
        },
    )

    # ── Verificação de estoque (a cada 6 horas) ──
    scheduler.add_job(
        job_verificar_estoque,
        trigger="interval",
        hours=6,
        id="verificar_estoque",
        replace_existing=True,
        kwargs={
            "profiles_manager": profiles_manager,
            "evolution_client": evolution_client,
            "legacy_api": legacy_api,
        },
    )

    # ── Tarefas vencidas (todo dia às 8h) ──
    scheduler.add_job(
        job_verificar_tarefas_vencidas,
        trigger="cron",
        hour=8,
        minute=0,
        id="tarefas_vencidas",
        replace_existing=True,
        kwargs={
            "profiles_manager": profiles_manager,
            "evolution_client": evolution_client,
            "legacy_api": legacy_api,
        },
    )

    scheduler.start()
    logger.info(
        f"[Scheduler] Iniciado com {len(scheduler.get_jobs())} jobs | "
        f"Resumo diário às {RESUMO_HORA:02d}:{RESUMO_MINUTO:02d}"
    )
    return True


def stop_scheduler():
    """Para o scheduler (usado no shutdown da aplicação)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Encerrado")


def list_jobs() -> list:
    """Lista todos os jobs agendados (para debug)."""
    scheduler = get_scheduler()
    if not scheduler:
        return []
    return [
        {
            "id": job.id,
            "proximo_disparo": str(job.next_run_time),
        }
        for job in scheduler.get_jobs()
    ]
