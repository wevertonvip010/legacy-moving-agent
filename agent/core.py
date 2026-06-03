"""
agent/core.py
Nucleo do agente Legacy Moving v2 — orquestra Claude + ferramentas + memoria + perfis + vision
"""
import os
import json
import logging
from anthropic import Anthropic
from agent.tools import TOOLS, execute_tool, get_tools_for_role
from agent.prompts import build_system_prompt
from agent.memory import ConversationMemory
from agent.profiles import profile_manager, ROLE_PERMISSIONS
from agent.vision import analisar_imagem, TIPO_PARA_CATEGORIA

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
memory = ConversationMemory()


def process_message(phone: str, message: str, message_type: str = 'text', media_url: str = None) -> str:
      """
          Processa uma mensagem recebida do WhatsApp e retorna a resposta.

              Args:
                      phone: Numero do WhatsApp do usuario
                              message: Texto da mensagem (ja transcrito se for audio)
                                      message_type: 'text' | 'audio' | 'image' | 'document'
                                              media_url: URL da midia (para imagens e documentos)

                                                  Returns:
                                                          Resposta formatada para enviar via WhatsApp
                                                              """
      logger.info(f'[{phone}] Mensagem ({message_type}): {message[:80]}')

    # Identificar perfil do usuario
      perfil = profile_manager.get_perfil(phone)
      role = perfil.get('role', 'bloqueado')
      nome = perfil.get('nome', 'Usuario')

    # Bloquear acesso se sem permissao
      if role == 'bloqueado':
                return profile_manager.get_saudacao(phone)

      # Registrar acesso
      profile_manager.registrar_acesso(phone)

    # Processar imagem se recebida
      if message_type == 'image' and media_url:
                return _processar_imagem(phone, media_url, perfil)

      # Verificar comandos especiais de admin
      if role == 'admin':
                cmd = _verificar_comando_admin(phone, message)
                if cmd:
                              return cmd

            # Buscar historico de conversa
            history = memory.get_history(phone)
    history.append({'role': 'user', 'content': message})

    # Obter ferramentas permitidas para o role
    tools_permitidas = get_tools_for_role(role)

    # Montar system prompt personalizado
    system = build_system_prompt(perfil)

    # Chamar Claude com tool use
    response = _call_claude_with_tools(phone, history, system, tools_permitidas)

    # Salvar historico
    memory.save_history(phone, history)

    return response


def _processar_imagem(phone: str, image_url: str, perfil: dict) -> str:
      """
          Processa uma imagem recebida — analisa com Vision e executa acao automatica.
              """
    role = perfil.get('role', 'bloqueado')
    nome = perfil.get('nome', 'Usuario')
    funcionario_id = perfil.get('funcionario_id')

    logger.info(f'[{phone}] Analisando imagem...')

    # Analisar imagem com Claude Vision
    analise = analisar_imagem(image_url)

    if 'erro' in analise:
              return 'Nao consegui analisar a imagem. Tente enviar novamente ou descreva o que precisa registrar.'

    tipo = analise.get('tipo', 'outro')
    valor = analise.get('valor')
    descricao = analise.get('descricao', '')
    acao = analise.get('acao', 'nenhuma')
    dados = analise.get('dados', '')

    # Executar acao automatica baseada no tipo de imagem
    if acao == 'registrar_despesa' and valor:
              categoria = TIPO_PARA_CATEGORIA.get(tipo, 'outros')

        # Motoristas so podem registrar proprias despesas
              params = {
                  'descricao': descricao,
                  'valor': valor,
                  'categoria': categoria or 'outros',
                  'registrado_por': phone,
                  'registrado_por_nome': nome,
                  'funcionario_id': funcionario_id
              }

        from agent.tools import execute_tool
        resultado = execute_tool('registrar_despesa', params)

        if isinstance(resultado, dict) and not resultado.get('erro'):
                      return (
                                        f'Comprovante registrado automaticamente!\n\n'
                                        f'Tipo: {tipo.replace("_", " ").title()}\n'
                                        f'Valor: R$ {valor:,.2f}\n'
                                        f'Categoria: {(categoria or "outros").replace("_", " ").title()}\n'
                                        f'Descricao: {descricao}\n'
                                        f'Registrado por: {nome}\n\n'
                                        f'Tudo certo! O admin pode ver esse lancamento no painel financeiro.'
                      )
else:
            erro = resultado.get('erro', 'Erro desconhecido') if isinstance(resultado, dict) else str(resultado)
              return f'Imagem reconhecida como {tipo.replace("_", " ")}, mas nao consegui registrar no sistema: {erro}\n\nDescreva manualmente o que precisa lancar.'

elif acao == 'registrar_avaria':
        return (
                      f'Foto de avaria identificada!\n\n'
                      f'Descricao: {descricao}\n'
                      f'{("Dados: " + dados) if dados else ""}\n\n'
                      f'Para registrar oficialmente, me informe:\n'
                      f'1. Numero da OS relacionada\n'
                      f'2. Valor estimado do dano (se souber)\n\n'
                      f'Exemplo: "OS 2026-012, dano estimado R$ 500"'
        )

else:
        # Imagem nao reconhecida como acao automatica — informar o que foi visto
          return (
                        f'Imagem recebida e analisada!\n\n'
                        f'O que identifiquei: {descricao}\n'
                        f'{("Dados: " + dados) if dados else ""}\n\n'
                        f'A imagem foi salva no seu historico. Precisa fazer algum lancamento relacionado?'
          )


def _verificar_comando_admin(phone: str, message: str) -> str | None:
      """
          Verifica comandos especiais que so o admin pode usar.
              Retorna resposta ou None se nao for um comando especial.
                  """
    msg = message.strip().lower()

    # Cadastrar usuario: "cadastrar 5511999998888 Diego motorista"
    if msg.startswith('cadastrar '):
              partes = message.strip().split()
              if len(partes) >= 4:
                            _, phone_novo, nome, role = partes[0], partes[1], partes[2], partes[3]
                            resultado = profile_manager.cadastrar(phone_novo, nome, role)
                            if resultado.get('ok'):
                                              return f'Usuario cadastrado com sucesso!\n\nNumero: {phone_novo}\nNome: {nome}\nRole: {role}\n\nAgora {nome} pode usar o agente.'
                                          return f'Erro: {resultado.get("erro")}'

          # Listar usuarios: "listar usuarios"
          if msg in ('listar usuarios', 'ver usuarios', 'quem esta cadastrado'):
                    usuarios = profile_manager.listar_usuarios()
                    if not usuarios:
                                  return 'Nenhum usuario cadastrado ainda. Use: cadastrar [numero] [nome] [role]'
                              linhas = ['Usuarios cadastrados:\n']
        for u in usuarios:
                      role_info = ROLE_PERMISSIONS.get(u.get('role', 'bloqueado'), {})
                      emoji = role_info.get('emoji', '')
                      linhas.append(f'{emoji} {u.get("nome")} — {u.get("role")} ({u.get("phone")})')
                  return '\n'.join(linhas)

    # Remover usuario: "remover 5511999998888"
    if msg.startswith('remover '):
              phone_rem = message.strip().split()[1] if len(message.strip().split()) > 1 else ''
        if phone_rem:
                      resultado = profile_manager.remover(phone_rem)
                      return resultado.get('mensagem') or resultado.get('erro', 'Erro')

    return None


def _call_claude_with_tools(phone: str, history: list, system: str, tools: list) -> str:
      """
          Chama Claude com suporte a ferramentas filtradas pelo role do usuario.
              """
    messages = history.copy()

    while True:
              response = client.messages.create(
                            model='claude-sonnet-4-5',
                            max_tokens=4096,
                            system=system,
                            tools=tools,
                            messages=messages
              )

        if response.stop_reason == 'tool_use':
                      tool_results = []
                      assistant_content = response.content

            for block in response.content:
                              if block.type == 'tool_use':
                                                    logger.info(f'[{phone}] Ferramenta: {block.name}')
                                                    result = execute_tool(block.name, block.input)
                                                    tool_results.append({
                                                        'type': 'tool_result',
                                                        'tool_use_id': block.id,
                                                        'content': json.dumps(result, ensure_ascii=False)
                                                    })

                          messages.append({'role': 'assistant', 'content': assistant_content})
            messages.append({'role': 'user', 'content': tool_results})
            continue

        # Resposta final
        text_response = ''
        for block in response.content:
                      if hasattr(block, 'text'):
                                        text_response += block.text

                  history.append({'role': 'assistant', 'content': text_response})
        return text_response or 'Nao foi possivel processar sua solicitacao.'
