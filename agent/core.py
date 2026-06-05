"""
agent/core.py — Legacy Moving Agent v5.1

Núcleo do agente: orquestra Claude + ferramentas + memória + perfis + visão.

Correções v5.1:
- Alinhado com novos nomes: executar_ferramenta, get_system_prompt
- DamageRegistry integrado ao fluxo de imagem
- Handler de áudio via Whisper/OpenAI
- Rate limiting simples por telefone
"""

import os
import json
import logging
import time
from collections import defaultdict
from anthropic import Anthropic
from agent.tools import TOOLS, executar_ferramenta
from agent.prompts import get_system_prompt
from agent.memory import ConversationMemory
from agent.profiles import profile_manager, ROLE_PERMISSIONS
from agent.user_context import user_context_manager

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
memory = ConversationMemory()

# Rate limiting simples: máx N chamadas por janela de tempo por telefone
_rate_buckets: dict = defaultdict(list)
RATE_MAX_CALLS = int(os.getenv("RATE_MAX_CALLS", "10"))   # máx 10 msgs
RATE_WINDOW_SEC = int(os.getenv("RATE_WINDOW_SEC", "60"))  # por minuto


def _check_rate_limit(telefone: str) -> bool:
    """Retorna True se dentro do limite, False se excedeu."""
    agora = time.time()
    bucket = _rate_buckets[telefone]
    # Remove chamadas fora da janela
    _rate_buckets[telefone] = [t for t in bucket if agora - t < RATE_WINDOW_SEC]
    if len(_rate_buckets[telefone]) >= RATE_MAX_CALLS:
        return False
    _rate_buckets[telefone].append(agora)
    return True


def processar_mensagem(mensagem: str, context: dict = None) -> str:
    """
    Ponto de entrada principal — processa qualquer mensagem recebida.

    Args:
        mensagem: Texto já extraído (ou prompt de avaria/sistema)
        context: dict com telefone, nome, message_id, instancia, tipo_mensagem

    Returns:
        Resposta em texto para enviar via WhatsApp
    """
    ctx = context or {}
    telefone = ctx.get("telefone", "desconhecido")
    nome = ctx.get("nome", "Usuário")
    tipo = ctx.get("tipo_mensagem", "text")
    message_id = ctx.get("message_id", "")
    media_url = ctx.get("media_url", "")

    logger.info("[%s] Mensagem (%s): %s", telefone, tipo, mensagem[:80])

    # ── Rate limiting ──
    if not _check_rate_limit(telefone):
        logger.warning("[%s] Rate limit excedido", telefone)
        return "⚠️ Muitas mensagens em pouco tempo. Aguarde um momento."

    # ── Verificar perfil ──
    perfil = profile_manager.get_perfil(telefone)
    role = perfil.get("role", "bloqueado")
    nome_perfil = perfil.get("nome", nome)

    if role == "bloqueado":
        return profile_manager.get_saudacao(telefone)

    profile_manager.registrar_acesso(telefone)
    user_context_manager._get_or_create(telefone, role)

    # ── Áudio: transcrever com Whisper ──
    if tipo == "audio" and media_url:
        mensagem = _transcrever_audio(media_url)
        if not mensagem:
            return "Não consegui transcrever o áudio. Tente escrever a mensagem."
        logger.info("[%s] Áudio transcrito: %s", telefone, mensagem[:80])

    # ── Imagem: analisar com Vision + registrar avaria se necessário ──
    if tipo == "image" and (media_url or message_id):
        return _processar_imagem(
            telefone=telefone,
            perfil=perfil,
            media_url=media_url,
            message_id=message_id,
            caption=mensagem
        )

    # ── Texto: processar com Claude + ferramentas ──
    return _processar_texto(telefone, nome_perfil, role, perfil, mensagem, context)


# ────────────────────────────────────────────────
# PROCESSAMENTO DE TEXTO
# ────────────────────────────────────────────────

def _processar_texto(telefone: str, nome: str, role: str,
                     perfil: dict, mensagem: str, context: dict) -> str:
    """Processa mensagem de texto com Claude e ferramentas."""
    history = memory.get_history(telefone)
    history.append({"role": "user", "content": mensagem})

    # System prompt personalizado com contexto individual
    system = get_system_prompt(telefone=telefone, nome_usuario=nome, perfil=role)
    ctx_extra = user_context_manager.get_contexto_para_prompt(telefone, role)
    if ctx_extra:
        system = system + "\n\n" + ctx_extra

    resposta = _call_claude_with_tools(telefone, history, system, context)
    memory.save_history(telefone, history)
    return resposta


def _call_claude_with_tools(telefone: str, history: list,
                             system: str, context: dict) -> str:
    """Chama Claude com suporte a tool use em loop até resposta final."""
    messages = list(history)
    MAX_ITER = 8

    for iteration in range(MAX_ITER):
        try:
            response = client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
                max_tokens=2048,
                system=system,
                tools=TOOLS,
                messages=messages
            )
        except Exception as e:
            logger.error("[%s] Erro Claude API: %s", telefone, e)
            return "⚠️ Erro ao processar. Tente novamente."

        # Resposta final de texto
        if response.stop_reason == "end_turn":
            texto = _extrair_texto(response)
            history.append({"role": "assistant", "content": texto})
            return texto

        # Tool use: executar ferramenta(s) e continuar
        if response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    logger.info("[%s] Tool: %s %s", telefone, block.name, str(block.input)[:100])
                    resultado = executar_ferramenta(
                        tool_name=block.name,
                        tool_input=block.input,
                        context=context
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str)
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Stop reason inesperado
        logger.warning("[%s] stop_reason inesperado: %s", telefone, response.stop_reason)
        break

    return "Não consegui completar a operação. Tente novamente."


def _extrair_texto(response) -> str:
    """Extrai texto da resposta do Claude."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


# ────────────────────────────────────────────────
# PROCESSAMENTO DE IMAGEM
# ────────────────────────────────────────────────

def _processar_imagem(telefone: str, perfil: dict, media_url: str,
                      message_id: str, caption: str) -> str:
    """
    Processa imagem recebida:
    1. Analisa com Claude Vision para identificar o tipo
    2. Se for avaria → aciona DamageRegistry
    3. Se for comprovante/nota → registra despesa
    4. Outros → responde com descrição
    """
    role = perfil.get("role", "operacional")
    nome = perfil.get("nome", "Funcionário")

    try:
        from agent.vision import analisar_imagem, TIPO_PARA_CATEGORIA
        analise = analisar_imagem(media_url or "", contexto=caption)
    except Exception as e:
        logger.error("[%s] Erro vision: %s", telefone, e)
        analise = {"tipo": "outro", "acao": "nenhuma", "descricao": caption or "imagem"}

    tipo = analise.get("tipo", "outro")
    acao = analise.get("acao", "nenhuma")
    descricao = analise.get("descricao", caption or "Imagem recebida")
    valor = analise.get("valor")

    # ── Avaria detectada pelo Vision ──
    if acao == "registrar_avaria" or tipo == "foto_avaria":
        return _registrar_avaria_via_vision(
            telefone=telefone,
            nome=nome,
            descricao=descricao,
            message_id=message_id,
            caption=caption
        )

    # ── Despesa/comprovante ──
    if acao == "registrar_despesa" and valor and role in ("admin", "supervisor", "motorista", "financeiro"):
        from integrations.legacy_api import legacy_api
        if legacy_api:
            cat = TIPO_PARA_CATEGORIA.get(tipo, "outros")
            resultado = legacy_api.registrar_despesa(
                descricao=descricao,
                valor=float(valor),
                categoria=cat,
                registrado_por=telefone,
                registrado_por_nome=nome
            )
            if resultado.get("id") or resultado.get("success"):
                return f"✅ Despesa registrada!\n*Descrição:* {descricao}\n*Valor:* R$ {valor}\n*Categoria:* {cat}"
        return f"⚠️ ERP indisponível. Anote manualmente: {descricao} — R$ {valor}"

    # ── Outros tipos de imagem ──
    return f"📎 Imagem recebida\n*Análise:* {descricao}\n\nSe precisar registrar algo, me diga o que fazer com essa foto."


def _registrar_avaria_via_vision(telefone: str, nome: str, descricao: str,
                                  message_id: str, caption: str) -> str:
    """
    Registra avaria detectada pelo Vision no DamageRegistry.
    Se não souber a OS, pede ao funcionário.
    """
    import re
    # Tenta extrair OS da legenda
    os_match = re.search(r"(?:os|o\.s\.|ordem)[\s\-\.#]*([\w\-]+)", caption or "", re.IGNORECASE)
    numero_os = os_match.group(1) if os_match else ""

    if not numero_os:
        # Sem OS identificada — armazena contexto e pede ao funcionário
        user_context_manager.update_preferences(telefone, {
            "avaria_pendente": {
                "message_id": message_id,
                "descricao": descricao,
                "aguardando_os": True
            }
        })
        return (
            f"📸 Foto de avaria recebida!\n"
            f"*Item identificado:* {descricao}\n\n"
            f"Para registrar, preciso do *número da OS* desta mudança.\n"
            f"Responda com: OS [número] — ex: OS 042"
        )

    # Com OS — registrar imediatamente
    from integrations.damage_registry import damage_registry
    if damage_registry:
        resultado = damage_registry.registrar_avaria(
            numero_os=numero_os,
            descricao=descricao,
            funcionario_nome=nome,
            funcionario_telefone=telefone,
            message_id=message_id
        )
        if resultado.get("success"):
            url = resultado.get("drive_url", "")
            url_txt = f"\n📁 Drive: {url}" if url else ""
            return (
                f"📸 Avaria registrada com sucesso!\n"
                f"*OS:* {numero_os}\n"
                f"*Item:* {descricao}{url_txt}\n"
                f"✅ Documentação interna salva."
            )
        erros = ", ".join(resultado.get("erros", []))
        return f"⚠️ Erro ao registrar avaria: {erros}. Tente novamente ou anote manualmente."

    return f"⚠️ Sistema de avarias indisponível. Anote: OS {numero_os} — {descricao}"


# ────────────────────────────────────────────────
# PROCESSAMENTO DE ÁUDIO
# ────────────────────────────────────────────────

def _transcrever_audio(media_url: str) -> str:
    """Transcreve áudio usando OpenAI Whisper."""
    import io
    import requests as req
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        logger.warning("OPENAI_API_KEY não configurada — áudio não suportado")
        return ""

    evolution_key = os.getenv("EVOLUTION_API_KEY", "")
    headers = {"apikey": evolution_key} if evolution_key else {}

    try:
        # Baixar áudio
        resp = req.get(media_url, headers=headers, timeout=30)
        resp.raise_for_status()
        audio_bytes = resp.content

        # Transcrever com Whisper
        openai_client = OpenAI(api_key=openai_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"  # WhatsApp usa ogg/opus

        transcription = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt"
        )
        return transcription.text
    except Exception as e:
        logger.error("Erro ao transcrever áudio: %s", e)
        return ""
