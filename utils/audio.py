"""
utils/audio.py
Transcricao de mensagens de audio do WhatsApp usando OpenAI Whisper.
"""
import os
import logging
import tempfile
import requests

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY', '')


def transcribe_audio(audio_url: str) -> str | None:
      """
          Transcreve um audio do WhatsApp para texto usando OpenAI Whisper.

                  Args:
                          audio_url: URL do audio no servidor da Evolution API

                                  Returns:
                                          Texto transcrito ou None em caso de erro
                                              """
      if not OPENAI_API_KEY:
                logger.warning('OPENAI_API_KEY nao configurada — transcricao de audio indisponivel')
                return None

      try:
                # Baixar o audio da Evolution API
                headers = {}
                if EVOLUTION_API_KEY:
                              headers['apikey'] = EVOLUTION_API_KEY

                resp = requests.get(audio_url, headers=headers, timeout=30)
                resp.raise_for_status()

        # Salvar em arquivo temporario
                with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                              tmp.write(resp.content)
                              tmp_path = tmp.name

                # Transcrever com Whisper
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)

        with open(tmp_path, 'rb') as audio_file:
                      result = client.audio.transcriptions.create(
                                        model='whisper-1',
                                        file=audio_file,
                                        language='pt'
                      )

        # Limpar arquivo temporario
        os.unlink(tmp_path)

        transcricao = result.text.strip()
        logger.info(f'Audio transcrito: {transcricao[:100]}')
        return transcricao

except Exception as e:
        logger.error(f'Erro ao transcrever audio: {e}')
        return None
