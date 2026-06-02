"""
  agent/core.py
  Nucleo do agente Legacy Moving — orquestra Claude + ferramentas + memoria
    """
    import os
import json
import logging
from anthropic import Anthropic
from agent.tools import TOOLS, execute_tool
  from agent.prompts import SYSTEM_PROMPT
from agent.memory import ConversationMemory

logger = logging.getLogger(__name__)

  client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
  memory = ConversationMemory()


  def process_message(phone: str, message: str, message_type: str = 'text') -> str:
    """
      Processa uma mensagem recebida do WhatsApp e retorna a resposta.

      Args:
        phone: Numero do WhatsApp do usuario (ex: 5511999999999)
          message: Texto da mensagem (ja transcrito se for audio)
        message_type: 'text' | 'audio' | 'image' | 'document'

      Returns:
        Resposta formatada para enviar de volta via WhatsApp
    """
      logger.info(f'[{phone}] Mensagem recebida ({message_type}): {message[:100]}')

    # Buscar historico de conversa do usuario
      history = memory.get_history(phone)

      # Adicionar mensagem atual ao historico
      history.append({'role': 'user', 'content': message})

      # Chamar Claude com tool use
      response = _call_claude_with_tools(phone, history)

      # Salvar historico atualizado
      memory.save_history(phone, history)

      logger.info(f'[{phone}] Resposta enviada: {response[:100]}')
    return response


  def _call_claude_with_tools(phone: str, history: list) -> str:
    """
      Chama o Claude com suporte a ferramentas (tool use).
    Executa as ferramentas necessarias e retorna a resposta final.
      """
      messages = history.copy()

      while True:
        # Chamar Claude
        response = client.messages.create(
                      model='claude-sonnet-4-5',
                      max_tokens=4096,
                      system=SYSTEM_PROMPT,
                      tools=TOOLS,
                      messages=messages
                  )

                  # Verificar se Claude quer usar uma ferramenta
                  if response.stop_reason == 'tool_use':
            # Processar todas as chamadas de ferramentas
              tool_results = []
              assistant_content = response.content

              for block in response.content:
                if block.type == 'tool_use':
                    logger.info(f'[{phone}] Executando ferramenta: {block.name} | params: {json.dumps(block.input, ensure_ascii=False)[:200]}')

                    # Executar a ferramenta
                      result = execute_tool(block.name, block.input)

                      tool_results.append({
                          'type': 'tool_result',
                          'tool_use_id': block.id,
                          'content': json.dumps(result, ensure_ascii=False)
  })

              # Adicionar resposta do assistente e resultados das ferramentas ao historico
              messages.append({'role': 'assistant', 'content': assistant_content})
              messages.append({'role': 'user', 'content': tool_results})

              # Continuar o loop para obter a resposta final
              continue

        # Resposta final (sem uso de ferramentas)
          text_response = ''
          for block in response.content:
            if hasattr(block, 'text'):
                  text_response += block.text

          # Atualizar historico com resposta do assistente
          history.append({'role': 'assistant', 'content': text_response})

          return text_response or 'Desculpe, nao consegui processar sua solicitacao.'
  
