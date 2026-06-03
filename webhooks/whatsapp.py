"""
webhooks/whatsapp.py v2
Receptor de mensagens do WhatsApp via Evolution API.
Suporta: texto, audio (transcrito), imagens (Vision), documentos.
"""
import os
import logging
import requests
from flask import Blueprint, request, jsonify
from agent.core import process_message
from utils.audio import transcribe_audio

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint('whatsapp', __name__)

EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL', '')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY', '')
EVOLUTION_INSTANCE = os.environ.get('EVOLUTION_INSTANCE', 'legacy-moving')
NUMEROS_AUTORIZADOS = [n.strip() for n in os.environ.get('NUMEROS_AUTORIZADOS', '').split(',') if n.strip()]


@whatsapp_bp.route('/whatsapp', methods=['POST'])
def receber_mensagem():
          """Endpoint principal que recebe todos os eventos da Evolution API."""
          try:
                        payload = request.get_json(force=True) or {}
                        event = payload.get('event', '')

              if event not in ('messages.upsert', 'MESSAGES_UPSERT'):
                                return jsonify({'ok': True, 'event': event, 'action': 'ignored'}), 200

        data = payload.get('data', {})
        msg_info = _extrair_mensagem(data)

        if not msg_info or msg_info.get('from_me'):
                          return jsonify({'ok': True, 'action': 'skipped'}), 200

        phone = msg_info['phone']
        msg_type = msg_info['type']
        content = msg_info['content']
        media_url = msg_info.get('media_url')

        # Verificar autorizacao
        if NUMEROS_AUTORIZADOS and phone not in NUMEROS_AUTORIZADOS:
                          logger.warning(f'Numero nao autorizado: {phone}')
                          _enviar_mensagem(phone, 'Acesso nao autorizado. Fale com o administrador.')
                          return jsonify({'ok': False, 'error': 'unauthorized'}), 403

        # Processar por tipo de mensagem
        if msg_type == 'audio':
                          logger.info(f'[{phone}] Transcrevendo audio...')
                          content = transcribe_audio(media_url or content)
                          if not content:
                                                _enviar_mensagem(phone, 'Nao consegui entender o audio. Pode digitar?')
                                                return jsonify({'ok': True}), 200
                                            msg_type = 'text'

elif msg_type == 'image':
            # Imagem: passar direto para o core com a URL da midia
            logger.info(f'[{phone}] Imagem recebida, processando com Vision...')
            resposta = process_message(phone, content or 'foto enviada', 'image', media_url)
            _enviar_mensagem(phone, resposta)
            return jsonify({'ok': True}), 200

elif msg_type == 'document':
            _enviar_mensagem(phone, 'Documento recebido! Por enquanto aceito apenas fotos e mensagens de texto/audio. Em breve terei suporte a documentos.')
            return jsonify({'ok': True}), 200

        if not content or len(content.strip()) < 2:
                          return jsonify({'ok': True, 'action': 'empty'}), 200

        # Processar texto/audio transcrito
        resposta = process_message(phone, content.strip(), msg_type)
        _enviar_mensagem(phone, resposta)

        return jsonify({'ok': True, 'phone': phone}), 200

except Exception as e:
        logger.error(f'Erro no webhook: {e}', exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500


def _extrair_mensagem(data: dict) -> dict | None:
          """Extrai dados da mensagem do payload da Evolution API v2."""
    try:
                  key = data.get('key', {})
        phone = key.get('remoteJid', '').replace('@s.whatsapp.net', '').replace('@g.us', '')
        from_me = key.get('fromMe', False)

        if not phone:
                          return None

        message = data.get('message', {})

        # Texto simples
        if 'conversation' in message:
                          return {'phone': phone, 'type': 'text', 'content': message['conversation'], 'from_me': from_me}

        # Texto estendido
        if 'extendedTextMessage' in message:
                          return {'phone': phone, 'type': 'text', 'content': message['extendedTextMessage'].get('text', ''), 'from_me': from_me}

        # Audio / PTT (mensagem de voz)
        for audio_key in ('audioMessage', 'pttMessage'):
                          if audio_key in message:
                                                url = message[audio_key].get('url', '')
                                                return {'phone': phone, 'type': 'audio', 'content': url, 'media_url': url, 'from_me': from_me}

        # Imagem
        if 'imageMessage' in message:
                          url = message['imageMessage'].get('url', '')
            caption = message['imageMessage'].get('caption', '')
            return {'phone': phone, 'type': 'image', 'content': caption, 'media_url': url, 'from_me': from_me}

        # Documento
        if 'documentMessage' in message:
                          url = message['documentMessage'].get('url', '')
            filename = message['documentMessage'].get('fileName', 'documento')
            return {'phone': phone, 'type': 'document', 'content': filename, 'media_url': url, 'from_me': from_me}

        return None

except Exception as e:
        logger.error(f'Erro ao extrair mensagem: {e}')
        return None


def _enviar_mensagem(phone: str, texto: str):
          """Envia mensagem de texto via Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
                  logger.info(f'[SIMULADO] Para {phone}: {texto[:150]}')
        return

    url = f'{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}'
    headers = {'apikey': EVOLUTION_API_KEY, 'Content-Type': 'application/json'}
    payload = {'number': phone, 'text': texto}

    try:
                  resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f'[{phone}] Mensagem enviada')
except Exception as e:
        logger.error(f'[{phone}] Erro ao enviar: {e}')


@whatsapp_bp.route('/whatsapp', methods=['GET'])
def verificar_webhook():
          return jsonify({'status': 'ok', 'webhook': 'legacy-moving-agent-v2'}), 200
