"""
Webhook WhatsApp — Legacy Moving Agent

Recebe eventos da Evolution API:
- Mensagens de texto → encaminha ao agente
- Mensagens com imagem → verifica se é avaria de funcionário
- Atualização de status de mensagem
"""

import os
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/webhook")

# Tipos de mídia de imagem aceitos
IMAGE_MIMETYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _extrair_dados_mensagem(data: dict) -> dict:
    """
    Extrai os dados relevantes do payload da Evolution API.

    Retorna dict com:
        telefone, nome, texto, tipo_mensagem, message_id,
        is_image, mimetype, caption, instancia
    """
    try:
        dados = data.get("data", {})
        key = dados.get("key", {})
        msg = dados.get("message", {})
        push_name = dados.get("pushName", "Usuário")
        instancia = data.get("instance", os.getenv("EVOLUTION_INSTANCE", "legacy"))

        telefone = key.get("remoteJid", "").replace("@s.whatsapp.net", "").replace("@g.us", "")
        message_id = key.get("id", "")
        from_me = key.get("fromMe", False)

        # Texto simples
        texto = msg.get("conversation", "")
        if not texto:
            # Mensagem extendida (texto dentro de extendedTextMessage)
            ext = msg.get("extendedTextMessage", {})
            texto = ext.get("text", "")

        # Imagem
        img_msg = msg.get("imageMessage", {})
        is_image = bool(img_msg)
        mimetype = img_msg.get("mimetype", "")
        caption = img_msg.get("caption", "")  # Legenda da foto

        # Documento com imagem
        if not is_image:
            doc_msg = msg.get("documentMessage", {})
            doc_mime = doc_msg.get("mimetype", "")
            if doc_mime in IMAGE_MIMETYPES:
                is_image = True
                mimetype = doc_mime
                caption = doc_msg.get("caption", "") or doc_msg.get("title", "")

        return {
            "telefone": telefone,
            "nome": push_name,
            "texto": texto or caption,
            "tipo_mensagem": "image" if is_image else "text",
            "message_id": message_id,
            "is_image": is_image,
            "mimetype": mimetype,
            "caption": caption,
            "from_me": from_me,
            "instancia": instancia,
        }
    except Exception as e:
        logger.error("Erro ao extrair dados da mensagem: %s", e)
        return {}


def _eh_mensagem_de_avaria(caption: str, texto: str) -> bool:
    """
    Heurística para detectar se uma imagem enviada por funcionário
    é um registro de avaria.

    Palavras-chave que indicam avaria: avaria, danificado, dano, arranhado,
    quebrado, amassado, riscado, problema, defeito, OS, os-
    """
    palavras_avaria = [
        # avaria/dano (masculino e feminino)
        "avaria", "avariado", "avariada",
        "danificado", "danificada", "dano",
        "arranhado", "arranhada", "arranhão",
        "quebrado", "quebrada",
        "amassado", "amassada",
        "riscado", "riscada",
        "destruído", "destruída",
        # contexto de ocorrência
        "problema", "defeito",
        "já veio", "ja veio",
        "já estava", "ja estava",
        "antes da mudança", "antes da mudanca",
        "documentando", "registrando",
        # frases comuns de funcionários
        "já tava assim", "ja tava assim",
        "veio assim", "achei assim",
        "pre-existente", "preexistente",
    ]
    texto_lower = (caption + " " + texto).lower()
    return any(p in texto_lower for p in palavras_avaria)


def _processar_imagem_avaria(dados: dict) -> dict:
    """
    Processa uma imagem de avaria:
    1. Verifica se o funcionário mencionou número de OS na legenda
    2. Encaminha ao agente para completar o registro

    Returns:
        Dict com instrução para o agente processar
    """
    caption = dados.get("caption", "")
    texto = dados.get("texto", "")
    message_id = dados.get("message_id", "")

    # Tentar extrair número de OS da legenda
    import re
    os_match = re.search(r"(?:os|o.s.|ordem)[\s\-\.#]*([\w\-]+)", caption + " " + texto,
                         re.IGNORECASE)
    numero_os = os_match.group(1) if os_match else ""

    # Montar prompt para o agente processar como avaria
    prompt_avaria = (
        f"[SISTEMA: Funcionário enviou foto de item avariado]\n"
        f"Legenda: {caption or '(sem legenda)'}\n"
        f"ID da mensagem (para baixar foto): {message_id}\n"
        f"OS detectada na legenda: {numero_os or 'não identificada'}\n\n"
        "Por favor:\n"
        "1. Se a OS foi identificada, use a ferramenta registrar_avaria imediatamente\n"
        "2. Se não, pergunte o número da OS ao funcionário\n"
        "3. Use o message_id informado para baixar a foto automaticamente\n"
        "4. Confirme ao funcionário que a avaria foi registrada com sucesso"
    )

    return {
        "tipo": "avaria",
        "prompt": prompt_avaria,
        "numero_os": numero_os,
        "message_id": message_id,
        "caption": caption
    }


@whatsapp_bp.route("/messages-upsert", methods=["POST"])
def messages_upsert():
    """Recebe novas mensagens WhatsApp da Evolution API."""
    try:
        data = request.get_json(force=True) or {}

        # Ignorar mensagens de grupos (opcional — configurável)
        ignore_groups = os.getenv("IGNORE_GROUPS", "true").lower() == "true"
        if ignore_groups and "@g.us" in str(data.get("data", {}).get("key", {}).get("remoteJid", "")):
            return jsonify({"status": "ignored", "reason": "group message"}), 200

        dados = _extrair_dados_mensagem(data)
        if not dados:
            return jsonify({"status": "error", "reason": "invalid payload"}), 400

        # Ignorar mensagens enviadas pelo próprio bot
        if dados.get("from_me"):
            return jsonify({"status": "ignored", "reason": "own message"}), 200

        telefone = dados["telefone"]
        nome = dados["nome"]
        message_id = dados["message_id"]
        instancia = dados["instancia"]

        # ── Caso 1: Imagem enviada ──
        if dados["is_image"]:
            caption = dados.get("caption", "")
            texto = dados.get("texto", "")

            # Verificar se é registro de avaria
            if _eh_mensagem_de_avaria(caption, texto):
                info_avaria = _processar_imagem_avaria(dados)
                texto_para_agente = info_avaria["prompt"]
                logger.info("Avaria detectada de %s (OS: %s)", telefone, info_avaria.get("numero_os"))
            else:
                # Imagem sem contexto de avaria — tratar como texto com descrição
                texto_para_agente = (
                    f"[Funcionário enviou uma imagem]\n"
                    f"Legenda: {caption or '(sem legenda)'}\n"
                    f"ID da mensagem: {message_id}\n"
                    "Se for uma avaria ou item danificado, me informe o número da OS e descreverei o problema."
                )
        else:
            # ── Caso 2: Mensagem de texto ──
            texto_para_agente = dados.get("texto", "").strip()

        if not texto_para_agente:
            return jsonify({"status": "ignored", "reason": "empty message"}), 200

        # ── Processar com o agente ──
        from agent.core import processar_mensagem
        context = {
            "telefone": telefone,
            "nome": nome,
            "message_id": message_id,
            "instancia": instancia,
            "tipo_mensagem": dados["tipo_mensagem"]
        }
        resposta = processar_mensagem(texto_para_agente, context)

        # ── Enviar resposta via Evolution API ──
        from integrations.evolution import EvolutionAPI
        evolution = EvolutionAPI(instance=instancia)
        evolution.send_text(telefone, resposta)

        return jsonify({"status": "ok", "telefone": telefone}), 200

    except Exception as e:
        logger.error("Erro no webhook messages-upsert: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@whatsapp_bp.route("/messages-update", methods=["POST"])
def messages_update():
    """Recebe atualizações de status de mensagens (entregue, lido, etc.)."""
    # Por ora apenas registra — pode ser usado para analytics futuros
    data = request.get_json(force=True) or {}
    logger.debug("Status atualizado: %s", data)
    return jsonify({"status": "ok"}), 200


@whatsapp_bp.route("/connection-update", methods=["POST"])
def connection_update():
    """Recebe atualizações de conexão da Evolution API."""
    data = request.get_json(force=True) or {}
    state = data.get("data", {}).get("state", "unknown")
    logger.info("Estado da conexão WhatsApp: %s", state)
    return jsonify({"status": "ok", "state": state}), 200


@whatsapp_bp.route("/health", methods=["GET"])
def health():
    """Health check do webhook."""
    return jsonify({"status": "ok", "module": "webhook/whatsapp"}), 200
