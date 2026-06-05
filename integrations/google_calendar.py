"""
integrations/google_calendar.py
Integração com Google Calendar via OAuth2 / Service Account
Cria, lista, atualiza e deleta eventos da agenda da Legacy Moving
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")

_service = None  # Lazy init


def _get_service():
    """Inicializa o serviço Google Calendar (lazy)."""
    global _service
    if _service is not None:
        return _service

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if not GOOGLE_CREDENTIALS_JSON:
            raise ValueError("GOOGLE_CREDENTIALS_JSON não configurado no .env")

        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        logger.info("[GCal] Serviço inicializado com sucesso")
        return _service

    except ImportError:
        raise ImportError(
            "Instale: pip install google-auth google-auth-httplib2 google-api-python-client"
        )
    except Exception as e:
        logger.error(f"[GCal] Erro ao inicializar: {e}")
        raise


def _tz() -> ZoneInfo:
    return ZoneInfo(TIMEZONE)


def _to_rfc3339(dt: datetime) -> str:
    """Converte datetime para formato RFC3339 exigido pela API."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.isoformat()


# ──────────────────────────────────────────
# EVENTOS
# ──────────────────────────────────────────

def criar_evento(
    titulo: str,
    inicio: datetime,
    fim: Optional[datetime] = None,
    descricao: str = "",
    local: str = "",
    convidados: Optional[list] = None,
    cor: str = "1",
    lembrete_minutos: int = 30,
) -> dict:
    """Cria um evento no Google Calendar.

    Args:
        titulo: Título do evento
        inicio: Data/hora de início
        fim: Data/hora de fim (padrão: início + 1h)
        descricao: Descrição/notas do evento
        local: Endereço ou local do evento
        convidados: Lista de e-mails para convidar
        cor: ID de cor 1-11 (1=azul, 2=verde, 3=roxo, 4=rosa, 6=vermelho, 10=verde-limão)
        lembrete_minutos: Minutos antes para lembrete (0 = sem lembrete)
    """
    if fim is None:
        fim = inicio + timedelta(hours=1)

    service = _get_service()

    event_body = {
        "summary": titulo,
        "description": descricao,
        "location": local,
        "start": {
            "dateTime": _to_rfc3339(inicio),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": _to_rfc3339(fim),
            "timeZone": TIMEZONE,
        },
        "colorId": str(cor),
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": lembrete_minutos}] if lembrete_minutos > 0 else [],
        },
    }

    if convidados:
        event_body["attendees"] = [{"email": email} for email in convidados]

    event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    logger.info(f"[GCal] Evento criado: {event.get('id')} — {titulo}")
    return {
        "id": event.get("id"),
        "titulo": titulo,
        "inicio": _to_rfc3339(inicio),
        "fim": _to_rfc3339(fim),
        "link": event.get("htmlLink"),
    }


def listar_eventos(
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    max_resultados: int = 20,
    busca: str = "",
) -> list:
    """Lista eventos do calendário em um período.

    Args:
        data_inicio: Início do período (padrão: hoje 00:00)
        data_fim: Fim do período (padrão: início + 7 dias)
        max_resultados: Máximo de eventos a retornar
        busca: Texto livre para filtrar eventos
    """
    if data_inicio is None:
        data_inicio = datetime.now(_tz()).replace(hour=0, minute=0, second=0)
    if data_fim is None:
        data_fim = data_inicio + timedelta(days=7)

    service = _get_service()

    params = {
        "calendarId": CALENDAR_ID,
        "timeMin": _to_rfc3339(data_inicio),
        "timeMax": _to_rfc3339(data_fim),
        "maxResults": max_resultados,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if busca:
        params["q"] = busca

    result = service.events().list(**params).execute()
    events = result.get("items", [])

    return [_format_event(e) for e in events]


def listar_eventos_hoje() -> list:
    """Atalho: lista todos os eventos de hoje."""
    now = datetime.now(_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return listar_eventos(start, end)


def listar_eventos_semana() -> list:
    """Atalho: lista eventos da semana atual."""
    now = datetime.now(_tz())
    # Segunda-feira da semana atual
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return listar_eventos(start, end)


def buscar_evento(event_id: str) -> Optional[dict]:
    """Busca um evento específico pelo ID."""
    service = _get_service()
    try:
        event = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return _format_event(event)
    except Exception:
        return None


def atualizar_evento(
    event_id: str,
    titulo: Optional[str] = None,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    descricao: Optional[str] = None,
    local: Optional[str] = None,
) -> dict:
    """Atualiza um evento existente."""
    service = _get_service()
    event = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

    if titulo:
        event["summary"] = titulo
    if descricao is not None:
        event["description"] = descricao
    if local is not None:
        event["location"] = local
    if inicio:
        event["start"] = {"dateTime": _to_rfc3339(inicio), "timeZone": TIMEZONE}
    if fim:
        event["end"] = {"dateTime": _to_rfc3339(fim), "timeZone": TIMEZONE}

    updated = service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event).execute()
    logger.info(f"[GCal] Evento atualizado: {event_id}")
    return _format_event(updated)


def deletar_evento(event_id: str) -> bool:
    """Remove um evento do calendário."""
    service = _get_service()
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        logger.info(f"[GCal] Evento deletado: {event_id}")
        return True
    except Exception as e:
        logger.error(f"[GCal] Erro ao deletar {event_id}: {e}")
        return False


def criar_lembrete_mudanca(
    numero_os: str,
    cliente: str,
    data_mudanca: datetime,
    origem: str,
    destino: str,
    motorista: str = "",
    equipe: Optional[list] = None,
) -> dict:
    """Cria evento padrão para uma Ordem de Serviço de mudança."""
    titulo = f"🚚 Mudança OS#{numero_os} — {cliente}"
    descricao = f"""Ordem de Serviço: {numero_os}
Cliente: {cliente}
Origem: {origem}
Destino: {destino}
Motorista: {motorista or "A definir"}
Equipe: {", ".join(equipe) if equipe else "A definir"}"""

    local = origem
    fim = data_mudanca + timedelta(hours=4)  # Estimativa de 4h

    return criar_evento(
        titulo=titulo,
        inicio=data_mudanca,
        fim=fim,
        descricao=descricao,
        local=local,
        cor="10",  # Verde para mudanças
        lembrete_minutos=60,
    )


# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────

def _format_event(event: dict) -> dict:
    """Normaliza o formato de um evento para uso interno."""
    start = event.get("start", {})
    end = event.get("end", {})

    return {
        "id": event.get("id"),
        "titulo": event.get("summary", "(sem título)"),
        "descricao": event.get("description", ""),
        "local": event.get("location", ""),
        "inicio": start.get("dateTime") or start.get("date"),
        "fim": end.get("dateTime") or end.get("date"),
        "link": event.get("htmlLink"),
        "convidados": [a.get("email") for a in event.get("attendees", [])],
        "status": event.get("status", "confirmed"),
    }


def formatar_agenda_whatsapp(eventos: list, titulo: str = "AGENDA") -> str:
    """Formata lista de eventos para envio no WhatsApp."""
    if not eventos:
        return f"📅 *{titulo}*\n\n_Nenhum evento encontrado._"

    lines = [f"📅 *{titulo}*", "─" * 25]
    for ev in eventos:
        inicio_str = _format_datetime_br(ev.get("inicio", ""))
        lines.append(f"\n🔹 *{ev['titulo']}*")
        lines.append(f"   ⏰ {inicio_str}")
        if ev.get("local"):
            lines.append(f"   📍 {ev['local']}")
        if ev.get("descricao"):
            desc = ev["descricao"][:80] + "..." if len(ev["descricao"]) > 80 else ev["descricao"]
            lines.append(f"   📝 {desc}")

    return "\n".join(lines)


def _format_datetime_br(iso_str: str) -> str:
    """Converte ISO 8601 para formato brasileiro."""
    if not iso_str:
        return "—"
    try:
        if "T" in iso_str:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            dt = dt.astimezone(_tz())
            return dt.strftime("%d/%m/%Y %H:%M")
        else:
            d = date.fromisoformat(iso_str)
            return d.strftime("%d/%m/%Y")
    except Exception:
        return iso_str


def is_available() -> bool:
    """Verifica se a integração com Google Calendar está configurada."""
    return bool(GOOGLE_CREDENTIALS_JSON and CALENDAR_ID)
