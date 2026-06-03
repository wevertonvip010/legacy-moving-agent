"""
agent/notifications.py
Motor de notificações automáticas da Legacy Moving
Dispara lembretes, alertas e confirmações via WhatsApp
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")


def _tz() -> ZoneInfo:
    return ZoneInfo(TIMEZONE)


def _now() -> datetime:
    return datetime.now(_tz())


# ──────────────────────────────────────────
# TIPOS DE NOTIFICAÇÃO
# ──────────────────────────────────────────

class TipoNotificacao:
    LEMBRETE_OS       = "lembrete_os"         # Lembrete antes de uma mudança
    CONFIRMACAO_OS    = "confirmacao_os"       # Confirmação de OS ao cliente
    ALERTA_AVARIA     = "alerta_avaria"        # Alerta de avaria registrada
    ALERTA_ESTOQUE    = "alerta_estoque"       # Estoque abaixo do mínimo
    RESUMO_DIARIO     = "resumo_diario"        # Resumo diário para admin/supervisor
    ANIVERSARIO_OS    = "aniversario_os"       # Mudança hoje (dia D)
    DESPESA_APROVACAO = "despesa_aprovacao"    # Despesa aguardando aprovação
    NOVO_LEAD         = "novo_lead"            # Lead novo no CRM
    TAREFA_VENCIDA    = "tarefa_vencida"       # Tarefa com prazo vencido


# ──────────────────────────────────────────
# TEMPLATES DE MENSAGEM
# ──────────────────────────────────────────

def msg_lembrete_os(
    numero_os: str,
    cliente: str,
    data_hora: str,
    origem: str,
    destino: str,
    horas_antes: int = 24,
) -> str:
    """Lembrete enviado para a equipe antes de uma mudança."""
    emoji = "🔔" if horas_antes >= 24 else "⚡"
    return (
        f"{emoji} *LEMBRETE — OS #{numero_os}*\n"
        f"{'─' * 25}\n"
        f"⏰ Em *{horas_antes}h* você tem uma mudança!\n\n"
        f"👤 *Cliente:* {cliente}\n"
        f"📅 *Data/Hora:* {data_hora}\n"
        f"📍 *Saída:* {origem}\n"
        f"🏁 *Destino:* {destino}\n\n"
        f"_Responda *confirmar* para confirmar presença ou *problema* para avisar._"
    )


def msg_confirmacao_os_cliente(
    numero_os: str,
    cliente: str,
    data_hora: str,
    origem: str,
    destino: str,
    motorista: str = "",
    contato_empresa: str = "",
) -> str:
    """Confirmação enviada para o cliente antes da mudança."""
    linhas = [
        f"✅ *Confirmação de Mudança — Legacy Moving*",
        f"{'─' * 25}",
        f"Olá, *{cliente}*! Sua mudança está confirmada.",
        f"",
        f"📋 *OS:* #{numero_os}",
        f"📅 *Data/Hora:* {data_hora}",
        f"📍 *Endereço de saída:* {origem}",
        f"🏁 *Endereço de destino:* {destino}",
    ]
    if motorista:
        linhas.append(f"🚗 *Motorista:* {motorista}")
    if contato_empresa:
        linhas.append(f"📞 *Dúvidas:* {contato_empresa}")
    linhas.append("")
    linhas.append("_Legacy Moving — Cuidando do que é seu_")
    return "\n".join(linhas)


def msg_alerta_avaria(
    numero_os: str,
    cliente: str,
    descricao: str,
    responsavel: str,
    foto: bool = False,
) -> str:
    """Alerta de avaria registrada — vai para admin/supervisor."""
    return (
        f"⚠️ *ALERTA DE AVARIA*\n"
        f"{'─' * 25}\n"
        f"📋 *OS:* #{numero_os}\n"
        f"👤 *Cliente:* {cliente}\n"
        f"👷 *Registrado por:* {responsavel}\n\n"
        f"📝 *Descrição:*\n{descricao}\n\n"
        + (f"📸 _Foto anexada_\n\n" if foto else "")
        + f"_Verifique e tome as providências necessárias._"
    )


def msg_alerta_estoque(
    item: str,
    quantidade_atual: int,
    quantidade_minima: int,
    unidade: str = "un",
) -> str:
    """Alerta de estoque baixo."""
    return (
        f"📦 *ESTOQUE BAIXO*\n"
        f"{'─' * 25}\n"
        f"Item: *{item}*\n"
        f"Qtd atual: *{quantidade_atual} {unidade}*\n"
        f"Qtd mínima: *{quantidade_minima} {unidade}*\n\n"
        f"_Faça o pedido de reposição._"
    )


def msg_resumo_diario(
    data: str,
    total_os_hoje: int,
    os_pendentes: int,
    os_concluidas: int,
    total_despesas_hoje: float,
    motoristas_ativos: int,
    pendencias: Optional[list] = None,
) -> str:
    """Resumo diário para admin/supervisor — enviado todo dia às 7h."""
    linhas = [
        f"🌅 *BOM DIA — RESUMO {data}*",
        f"{'─' * 25}",
        f"",
        f"📋 *Ordens de Serviço*",
        f"   • Total hoje: *{total_os_hoje}*",
        f"   • Pendentes: *{os_pendentes}*",
        f"   • Concluídas: *{os_concluidas}*",
        f"",
        f"💰 *Financeiro*",
        f"   • Despesas hoje: *R$ {total_despesas_hoje:,.2f}*".replace(",", "X").replace(".", ",").replace("X", "."),
        f"",
        f"👥 *Equipe*",
        f"   • Motoristas ativos: *{motoristas_ativos}*",
    ]

    if pendencias:
        linhas.append("")
        linhas.append(f"⚡ *Pendências ({len(pendencias)})*")
        for p in pendencias[:5]:
            linhas.append(f"   • {p}")
        if len(pendencias) > 5:
            linhas.append(f"   _... e mais {len(pendencias) - 5} pendência(s)_")

    linhas.append("")
    linhas.append("_Tenha um ótimo dia! 💪_")
    return "\n".join(linhas)


def msg_nova_despesa_aprovacao(
    responsavel: str,
    descricao: str,
    valor: float,
    categoria: str,
    id_despesa: str,
) -> str:
    """Notificação de despesa aguardando aprovação."""
    valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (
        f"💸 *DESPESA AGUARDANDO APROVAÇÃO*\n"
        f"{'─' * 25}\n"
        f"👤 *Responsável:* {responsavel}\n"
        f"📝 *Descrição:* {descricao}\n"
        f"💰 *Valor:* {valor_fmt}\n"
        f"🏷️ *Categoria:* {categoria}\n\n"
        f"_Responda *aprovar {id_despesa}* ou *rejeitar {id_despesa}_"
    )


def msg_novo_lead(
    nome: str,
    contato: str,
    origem: str,
    interesse: str,
    responsavel_comercial: str,
) -> str:
    """Notifica equipe comercial de novo lead."""
    return (
        f"🎯 *NOVO LEAD*\n"
        f"{'─' * 25}\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Contato:* {contato}\n"
        f"📣 *Origem:* {origem}\n"
        f"🏠 *Interesse:* {interesse}\n"
        f"👥 *Responsável:* {responsavel_comercial}\n\n"
        f"_Entre em contato nas próximas 2 horas!_"
    )


def msg_tarefa_vencida(
    titulo: str,
    prazo: str,
    responsavel: str,
    dias_atraso: int,
) -> str:
    """Alerta de tarefa com prazo vencido."""
    return (
        f"🔴 *TAREFA VENCIDA*\n"
        f"{'─' * 25}\n"
        f"📌 *Tarefa:* {titulo}\n"
        f"📅 *Prazo era:* {prazo}\n"
        f"👤 *Responsável:* {responsavel}\n"
        f"⏱️ *Atraso:* {dias_atraso} dia(s)\n\n"
        f"_Atualize o status da tarefa._"
    )


# ──────────────────────────────────────────
# ROTEADOR DE NOTIFICAÇÕES
# ──────────────────────────────────────────

class NotificationRouter:
    """Roteador: decide quais usuários recebem cada tipo de notificação."""

    # Cargos que recebem cada tipo
    ROUTING = {
        TipoNotificacao.ALERTA_AVARIA:     ["admin", "supervisor"],
        TipoNotificacao.ALERTA_ESTOQUE:    ["admin", "supervisor", "operacional"],
        TipoNotificacao.RESUMO_DIARIO:     ["admin", "supervisor"],
        TipoNotificacao.NOVO_LEAD:         ["admin", "comercial"],
        TipoNotificacao.DESPESA_APROVACAO: ["admin", "financeiro"],
        TipoNotificacao.LEMBRETE_OS:       ["motorista", "operacional"],
        TipoNotificacao.TAREFA_VENCIDA:    ["admin"],
    }

    @classmethod
    def get_roles_for(cls, tipo: str) -> list:
        """Retorna os cargos que devem receber este tipo de notificação."""
        return cls.ROUTING.get(tipo, ["admin"])

    @classmethod
    def should_notify(cls, role: str, tipo: str) -> bool:
        """Verifica se um cargo deve receber determinada notificação."""
        return role in cls.get_roles_for(tipo)


# ──────────────────────────────────────────
# DISPATCHER (orquestra envio)
# ──────────────────────────────────────────

async def dispatch_notification(
    tipo: str,
    message: str,
    profiles_manager,
    evolution_client,
    target_numbers: Optional[list] = None,
) -> dict:
    """Envia uma notificação para os usuários corretos.

    Args:
        tipo: TipoNotificacao.*
        message: Texto formatado da mensagem
        profiles_manager: Instância de ProfileManager
        evolution_client: Módulo evolution (integrations.evolution)
        target_numbers: Lista de números específicos (se None, usa routing por cargo)

    Returns:
        dict com contagens de envios e erros
    """
    results = {"enviados": 0, "erros": 0, "numeros": []}

    if target_numbers:
        destinatarios = target_numbers
    else:
        # Usa routing automático por cargo
        roles = NotificationRouter.get_roles_for(tipo)
        destinatarios = profiles_manager.get_numbers_by_roles(roles)

    for number in destinatarios:
        try:
            evolution_client.send_text(number, message)
            results["enviados"] += 1
            results["numeros"].append(number[-4:])
            logger.info(f"[NOTIF] {tipo} enviado para ...{number[-4:]}")
        except Exception as e:
            results["erros"] += 1
            logger.error(f"[NOTIF] Erro ao enviar {tipo} para ...{number[-4:]}: {e}")

    return results


def build_resumo_diario_from_api(legacy_api) -> str:
    """Monta o resumo diário consultando o ERP Legacy."""
    hoje = datetime.now(_tz()).strftime("%d/%m/%Y")
    try:
        # Tenta buscar dados do ERP
        os_data = legacy_api.listar_ordens_servico(status="hoje") or []
        despesas = legacy_api.listar_despesas(periodo="hoje") or []
        motoristas = legacy_api.listar_equipe(role="motorista", disponivel=True) or []

        os_pendentes = [o for o in os_data if o.get("status") == "pendente"]
        os_concluidas = [o for o in os_data if o.get("status") == "concluida"]
        total_despesas = sum(d.get("valor", 0) for d in despesas)

        return msg_resumo_diario(
            data=hoje,
            total_os_hoje=len(os_data),
            os_pendentes=len(os_pendentes),
            os_concluidas=len(os_concluidas),
            total_despesas_hoje=total_despesas,
            motoristas_ativos=len(motoristas),
        )
    except Exception as e:
        logger.warning(f"[NOTIF] Fallback no resumo diário: {e}")
        return msg_resumo_diario(
            data=hoje,
            total_os_hoje=0,
            os_pendentes=0,
            os_concluidas=0,
            total_despesas_hoje=0.0,
            motoristas_ativos=0,
            pendencias=["Erro ao carregar dados do ERP — verifique a conexão"],
        )
