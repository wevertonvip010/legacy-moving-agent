"""
webhooks/whatsapp.py
Receptor de mensagens do WhatsApp via Evolution API.
Processa textos e audios, chama o agente e responde ao usuario.
"""
import os
import json
import logging
import hashlib
import requests
from flask import Blueprint, request, jsonify
from agent.core import process_message
from utils.audio import transcribe_audio

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint('whatsapp', __name__)

EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL', '')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY', '')
EVOLUTION_INSTANCE = os.environ.get('EVOLUTION_INSTANCE', 'legacy-moving')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# Numeros autorizados a usar o agente (deixar vazio para liberar todos)
NUMEROS_AUTORIZADOS = os.environ.get('NUMEROS_AUTORIZADOS', '').split(',')
NUMEROS_AUTORIZADOS = [n.strip() for n in NUMEROS_AUTORIZADOS if n.strip()]


@whatsapp_bp.route('/whatsapp', methods=['POST'])
def receber_mensagem():
      """Endpoint principal que recebe todos os eventos da Evolution API."""
      try:
                payload = request.get_json(force=True) or {}
                event = payload.get('event', '')

        logger.info(f'Evento recebido: {event}')

        # Processar apenas mensagens recebidas (ignorar enviadas)
        if event not in ('messages.upsert', 'MESSAGES_UPSERT'):
                      return jsonify({'ok': True, 'event': event, 'action': 'ignored'}), 200

        # Extrair dados da mensagem
        data = payload.get('data', {})
        msg_info = _extrair_mensagem(data)

        if not msg_info:
                      return jsonify({'ok': True, 'action': 'no_message'}), 200

        phone = msg_info['phone']
        msg_type = msg_info['type']
        content = msg_info['content']

        # Ignorar mensagens do proprio bot (fromMe)
        if msg_info.get('from_me'):
                      return jsonify({'ok': True, 'action': 'own_message_ignored'}), 200

        # Verificar autorizacao (se configurado)
        if NUMEROS_AUTORIZADOS and phone not in NUMEROS_AUTORIZADOS:
                      logger.warning(f'Numero nao autorizado tentou acessar o agente: {phone}')
                      _enviar_mensagem(phone, 'Acesso nao autorizado. Entre em contato com o administrador.')
                      return jsonify({'ok': False, 'error': 'unauthorized'}), 403

        # Transcrever audio se necessario
        if msg_type == 'audio':
                      audio_url = content
                      logger.info(f'[{phone}] Transcrevendo audio: {audio_url}')
                      content = transcribe_audio(audio_url)
                      if not content:
                                        _enviar_mensagem(phone, 'Nao consegui entender o audio. Pode digitar sua mensagem?')
                                        return jsonify({'ok': True, 'action': 'audio_transcription_failed'}), 200
                                    logger.info(f'[{phone}] Audio transcrito: {content}')

        # Ignorar mensagens muito curtas ou vazias
        if not content or len(content.strip()) < 2:
                      return jsonify({'ok': True, 'action': 'empty_message'}), 200

        # Processar com o agente
        logger.info(f'[{phone}] Processando: {content[:100]}')
        resposta = process_message(phone, content.strip(), msg_type)

        # Enviar resposta via Evolution API
        _enviar_mensagem(phone, resposta)

        return jsonify({'ok': True, 'phone': phone, 'response_length': len(resposta)}), 200

except Exception as e:
        logger.error(f'Erro no webhook: {e}', exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500


def _extrair_mensagem(data: dict) -> dict | None:
      """Extrai informacoes relevantes do payload da Evolution API."""
    try:
              # Formato Evolution API v2
              key = data.get('key', {})
        phone = key.get('remoteJid', '').replace('@s.whatsapp.net', '').replace('@g.us', '')
        from_me = key.get('fromMe', False)

        if not phone:
                      return None

        message = data.get('message', {})

        # Mensagem de texto
        if 'conversation' in message:
                      return {'phone': phone, 'type': 'text', 'content': message['conversation'], 'from_me': from_me}

        # Mensagem de texto estendida
        if 'extendedTextMessage' in message:
                      return {'phone': phone, 'type': 'text', 'content': message['extendedTextMessage'].get('text', ''), 'from_me': from_me}

        # Audio/PTT
        if 'audioMessage' in message or 'pttMessage' in message:
                      audio_key = 'audioMessage' if 'audioMessage' in message else 'pttMessage'
            audio_url = message[audio_key].get('url', '')
            return {'phone': phone, 'type': 'audio', 'content': audio_url, 'from_me': from_me}

        return None

except Exception as e:
        logger.error(f'Erro ao extrair mensagem: {e}')
        return None


def _enviar_mensagem(phone: str, texto: str):
      """Envia uma mensagem de texto via Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
              logger.warning('Evolution API nao configurada — simulando envio')
        logger.info(f'[SIMULATED] Para {phone}: {texto[:200]}')
        return

    url = f'{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}'
    headers = {'apikey': EVOLUTION_API_KEY, 'Content-Type': 'application/json'}
    payload = {'number': phone, 'text': texto}

    try:
              resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f'[{phone}] Mensagem enviada com sucesso')
except Exception as e:
        logger.error(f'[{phone}] Erro ao enviar mensagem: {e}')


@whatsapp_bp.route('/whatsapp', methods=['GET'])
def verificar_webhook():
      """Verificacao do webhook (alguns provedores usam GET para validar)."""
    return jsonify({'status': 'ok', 'webhook': 'legacy-moving-agent'}), 200
