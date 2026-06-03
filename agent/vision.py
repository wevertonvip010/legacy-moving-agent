"""
agent/vision.py
Analise de imagens via Claude Vision.
Interpreta fotos de comprovantes, notas fiscais, recibos, avarias, etc.
"""
import os
import base64
import logging
import requests
from anthropic import Anthropic

logger = logging.getLogger(__name__)
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY', '')


def analisar_imagem(image_url: str, contexto: str = '') -> dict:
      """
          Analisa uma imagem enviada pelo WhatsApp usando Claude Vision.

              Args:
                      image_url: URL da imagem no servidor da Evolution API
                              contexto: Contexto adicional (ex: 'comprovante de abastecimento')

                                  Returns:
                                          dict com: tipo, descricao, valor (se houver), dados_extraidos, acao_sugerida
                                              """
      try:
                # Baixar imagem
                image_data, media_type = _baixar_imagem(image_url)
                if not image_data:
                              return {'erro': 'Nao foi possivel baixar a imagem'}

                # Montar prompt de analise
                prompt = _montar_prompt_analise(contexto)

          # Chamar Claude Vision
                response = client.messages.create(
                    model='claude-opus-4-5',
                    max_tokens=1024,
                    messages=[{
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': media_type,
                                    'data': image_data
                                }
                            },
                            {
                                'type': 'text',
                                'text': prompt
                            }
                        ]
                    }]
                )

          analise_texto = response.content[0].text
        logger.info(f'Imagem analisada: {analise_texto[:200]}')

        # Parsear resultado estruturado
        return _parsear_analise(analise_texto)

except Exception as e:
        logger.error(f'Erro ao analisar imagem: {e}')
        return {'erro': str(e)}


def _baixar_imagem(url: str) -> tuple:
      """Baixa imagem e retorna (base64_data, media_type)."""
    try:
              headers = {}
              if EVOLUTION_API_KEY:
                            headers['apikey'] = EVOLUTION_API_KEY

              resp = requests.get(url, headers=headers, timeout=30)
              resp.raise_for_status()

        # Detectar media type
              content_type = resp.headers.get('content-type', 'image/jpeg')
              if 'png' in content_type:
                            media_type = 'image/png'
elif 'gif' in content_type:
            media_type = 'image/gif'
elif 'webp' in content_type:
            media_type = 'image/webp'
else:
            media_type = 'image/jpeg'

        image_b64 = base64.standard_b64encode(resp.content).decode('utf-8')
        return image_b64, media_type

except Exception as e:
        logger.error(f'Erro ao baixar imagem de {url}: {e}')
        return None, None


def _montar_prompt_analise(contexto: str) -> str:
      ctx = f'Contexto adicional: {contexto}' if contexto else ''
    return f"""Analise esta imagem e responda em formato estruturado.

    {ctx}

    Identifique:
    1. TIPO: qual tipo de documento/imagem e esta (comprovante_abastecimento | nota_fiscal | recibo | foto_avaria | foto_os | foto_entrega | documento | outro)
    2. VALOR: se houver valor monetario, extraia o valor numerico (apenas numero, ex: 280.50)
    3. DATA: se houver data, extraia no formato DD/MM/YYYY
    4. DESCRICAO: descricao curta do que e a imagem (1-2 frases)
    5. DADOS: outros dados relevantes extraidos (estabelecimento, placa, endereço, etc.)
    6. ACAO: qual acao o sistema deve tomar (registrar_despesa | registrar_avaria | registrar_entrega | salvar_documento | nenhuma)

    Responda EXATAMENTE neste formato:
    TIPO: [tipo]
    VALOR: [valor ou null]
    DATA: [data ou null]
    DESCRICAO: [descricao]
    DADOS: [dados relevantes]
    ACAO: [acao]"""


def _parsear_analise(texto: str) -> dict:
      """Parseia a resposta estruturada do Claude."""
    resultado = {
              'tipo': 'outro',
              'valor': None,
              'data': None,
              'descricao': texto,
              'dados': '',
              'acao': 'nenhuma',
              'texto_completo': texto
    }

    for linha in texto.split('\n'):
              linha = linha.strip()
              if linha.startswith('TIPO:'):
                            resultado['tipo'] = linha.replace('TIPO:', '').strip()
elif linha.startswith('VALOR:'):
            val = linha.replace('VALOR:', '').strip()
            if val.lower() not in ('null', 'none', ''):
                              try:
                                                    resultado['valor'] = float(val.replace(',', '.'))
except Exception:
                    resultado['valor'] = None
elif linha.startswith('DATA:'):
            d = linha.replace('DATA:', '').strip()
            if d.lower() not in ('null', 'none', ''):
                              resultado['data'] = d
elif linha.startswith('DESCRICAO:'):
            resultado['descricao'] = linha.replace('DESCRICAO:', '').strip()
elif linha.startswith('DADOS:'):
            resultado['dados'] = linha.replace('DADOS:', '').strip()
elif linha.startswith('ACAO:'):
            resultado['acao'] = linha.replace('ACAO:', '').strip()

    return resultado


# Mapeamento de tipo de imagem para categoria de despesa
TIPO_PARA_CATEGORIA = {
      'comprovante_abastecimento': 'combustivel',
      'nota_fiscal': 'materiais',
      'recibo': 'outros',
      'foto_avaria': None,
      'foto_os': None,
      'foto_entrega': None,
      'documento': None,
      'outro': 'outros'
}
