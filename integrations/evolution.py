"""
integrations/evolution.py
Cliente dedicado para a Evolution API (WhatsApp open-source)
Gerencia instâncias, envia mensagens, baixa mídia
"""

import os
import httpx
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY  = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "legacy-moving")


def _headers() -> dict:
    return {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────
# INSTÂNCIA
# ──────────────────────────────────────────

def create_instance(instance_name: str = EVOLUTION_INSTANCE) -> dict:
    """Cria uma nova instância no Evolution API."""
    url = f"{EVOLUTION_BASE_URL}/instance/create"
    payload = {
        "instanceName": instance_name,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def get_instance_status(instance_name: str = EVOLUTION_INSTANCE) -> dict:
    """Retorna o status de conexão da instância."""
    url = f"{EVOLUTION_BASE_URL}/instance/connectionState/{instance_name}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def get_qrcode(instance_name: str = EVOLUTION_INSTANCE) -> dict:
    """Retorna o QR code para conectar o WhatsApp."""
    url = f"{EVOLUTION_BASE_URL}/instance/connect/{instance_name}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def disconnect_instance(instance_name: str = EVOLUTION_INSTANCE) -> dict:
    """Desconecta a instância do WhatsApp."""
    url = f"{EVOLUTION_BASE_URL}/instance/logout/{instance_name}"
    r = httpx.delete(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def delete_instance(instance_name: str = EVOLUTION_INSTANCE) -> dict:
    """Remove completamente uma instância."""
    url = f"{EVOLUTION_BASE_URL}/instance/delete/{instance_name}"
    r = httpx.delete(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def set_webhook(
    webhook_url: str,
    instance_name: str = EVOLUTION_INSTANCE,
    events: Optional[list] = None,
) -> dict:
    """Configura o webhook da instância para receber mensagens."""
    if events is None:
        events = [
            "MESSAGES_UPSERT",
            "MESSAGES_UPDATE",
            "CONNECTION_UPDATE",
            "SEND_MESSAGE",
        ]
    url = f"{EVOLUTION_BASE_URL}/webhook/set/{instance_name}"
    payload = {
        "url": webhook_url,
        "webhook_by_events": False,
        "webhook_base64": False,
        "events": events,
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────
# ENVIO DE MENSAGENS
# ──────────────────────────────────────────

def send_text(
    to: str,
    text: str,
    instance_name: str = EVOLUTION_INSTANCE,
    delay: int = 1200,
) -> dict:
    """Envia mensagem de texto para um número WhatsApp.
    
    Args:
        to: Número no formato 5511999999999 (sem + ou @s.whatsapp.net)
        text: Texto da mensagem (suporta markdown WhatsApp: *bold*, _italic_, ~strike~)
        delay: Delay em ms antes de enviar (simula digitação humana)
    """
    url = f"{EVOLUTION_BASE_URL}/message/sendText/{instance_name}"
    # Garante formato correto
    number = _format_number(to)
    payload = {
        "number": number,
        "text": text,
        "delay": delay,
    }
    try:
        r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
        r.raise_for_status()
        logger.info(f"[Evolution] Mensagem enviada para {number}")
        return r.json()
    except httpx.HTTPError as e:
        logger.error(f"[Evolution] Erro ao enviar para {number}: {e}")
        raise


def send_image(
    to: str,
    image_url: str,
    caption: str = "",
    instance_name: str = EVOLUTION_INSTANCE,
) -> dict:
    """Envia imagem com legenda opcional."""
    url = f"{EVOLUTION_BASE_URL}/message/sendMedia/{instance_name}"
    payload = {
        "number": _format_number(to),
        "mediatype": "image",
        "media": image_url,
        "caption": caption,
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def send_document(
    to: str,
    document_url: str,
    filename: str,
    caption: str = "",
    instance_name: str = EVOLUTION_INSTANCE,
) -> dict:
    """Envia documento (PDF, Excel, etc)."""
    url = f"{EVOLUTION_BASE_URL}/message/sendMedia/{instance_name}"
    payload = {
        "number": _format_number(to),
        "mediatype": "document",
        "media": document_url,
        "fileName": filename,
        "caption": caption,
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def send_audio(
    to: str,
    audio_url: str,
    instance_name: str = EVOLUTION_INSTANCE,
) -> dict:
    """Envia áudio como nota de voz (ptt)."""
    url = f"{EVOLUTION_BASE_URL}/message/sendWhatsAppAudio/{instance_name}"
    payload = {
        "number": _format_number(to),
        "audio": audio_url,
        "encoding": True,
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def send_reaction(
    to: str,
    message_id: str,
    emoji: str,
    instance_name: str = EVOLUTION_INSTANCE,
) -> dict:
    """Envia reação emoji para uma mensagem específica."""
    url = f"{EVOLUTION_BASE_URL}/message/sendReaction/{instance_name}"
    payload = {
        "key": {"remoteJid": _format_jid(to), "id": message_id},
        "reaction": emoji,
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def send_read_receipt(
    to: str,
    message_ids: list,
    instance_name: str = EVOLUTION_INSTANCE,
) -> dict:
    """Marca mensagens como lidas."""
    url = f"{EVOLUTION_BASE_URL}/chat/markMessageAsRead/{instance_name}"
    payload = {
        "readMessages": [
            {"remoteJid": _format_jid(to), "id": mid} for mid in message_ids
        ]
    }
    r = httpx.post(url, json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────
# MÍDIA
# ──────────────────────────────────────────

def download_media(message_id: str, instance_name: str = EVOLUTION_INSTANCE) -> bytes:
    """Baixa a mídia de uma mensagem e retorna como bytes."""
    url = f"{EVOLUTION_BASE_URL}/chat/getBase64FromMediaMessage/{instance_name}"
    payload = {"message": {"key": {"id": message_id}}, "convertToMp4": False}
    r = httpx.post(url, json=payload, headers=_headers(), timeout=60)
    r.raise_for_status()
    data = r.json()
    b64 = data.get("base64", "")
    return base64.b64decode(b64)


def download_media_as_base64(
    message: dict, instance_name: str = EVOLUTION_INSTANCE
) -> str:
    """Baixa mídia e retorna como base64 string (para Claude Vision)."""
    url = f"{EVOLUTION_BASE_URL}/chat/getBase64FromMediaMessage/{instance_name}"
    payload = {"message": message, "convertToMp4": False}
    r = httpx.post(url, json=payload, headers=_headers(), timeout=60)
    r.raise_for_status()
    data = r.json()
    return data.get("base64", "")


# ──────────────────────────────────────────
# GRUPOS (futuro)
# ──────────────────────────────────────────

def get_groups(instance_name: str = EVOLUTION_INSTANCE) -> list:
    """Lista todos os grupos da instância."""
    url = f"{EVOLUTION_BASE_URL}/group/fetchAllGroups/{instance_name}?getParticipants=false"
    r = httpx.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────
# HELPERS INTERNOS
# ──────────────────────────────────────────

def _format_number(number: str) -> str:
    """Normaliza número para formato 5511999999999."""
    cleaned = "".join(filter(str.isdigit, number))
    # Remove @s.whatsapp.net se presente
    cleaned = cleaned.replace("s.whatsapp.net", "").replace("@", "")
    # Adiciona 55 (Brasil) se não tiver código de país
    if len(cleaned) <= 11:
        cleaned = "55" + cleaned
    return cleaned


def _format_jid(number: str) -> str:
    """Formata número como JID do WhatsApp: 5511999999999@s.whatsapp.net"""
    return f"{_format_number(number)}@s.whatsapp.net"


def is_connected(instance_name: str = EVOLUTION_INSTANCE) -> bool:
    """Verifica se a instância está conectada ao WhatsApp."""
    try:
        status = get_instance_status(instance_name)
        state = status.get("instance", {}).get("state", "")
        return state == "open"
    except Exception:
        return False
