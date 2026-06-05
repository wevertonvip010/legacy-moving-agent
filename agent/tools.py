"""
Ferramentas do Agente — Legacy Moving Agent

Define todas as ferramentas disponíveis para o Claude via function calling.
Fases 1-4 + Sistema de Avarias (Fase 5)
"""

import os
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DEFINIÇÕES DAS FERRAMENTAS (passadas ao Claude)
# ─────────────────────────────────────────────

TOOLS = [
    # ── OS e Agenda ────────────────────────────
    {
        "name": "consultar_os",
        "description": "Consulta os detalhes de uma Ordem de Serviço pelo número ou pelo nome do cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_os": {"type": "string", "description": "Número da OS (ex: OS-2024-001)"},
                "nome_cliente": {"type": "string", "description": "Nome do cliente para busca"}
            }
        }
    },
    {
        "name": "listar_os_do_dia",
        "description": "Lista todas as OSs agendadas para hoje ou para uma data específica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data no formato dd/mm/aaaa. Se vazio, usa hoje."}
            }
        }
    },
    {
        "name": "criar_evento_agenda",
        "description": "Cria um evento no Google Agenda para uma mudança ou compromisso.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título do evento"},
                "data_hora_inicio": {"type": "string", "description": "Início no formato ISO 8601"},
                "data_hora_fim": {"type": "string", "description": "Fim no formato ISO 8601"},
                "descricao": {"type": "string", "description": "Descrição/detalhes do evento"},
                "numero_os": {"type": "string", "description": "Número da OS vinculada"}
            },
            "required": ["titulo", "data_hora_inicio"]
        }
    },
    # ── Drive ───────────────────────────────────
    {
        "name": "drive_salvar_arquivo",
        "description": "Salva um arquivo de texto ou relatório no Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome_arquivo": {"type": "string", "description": "Nome do arquivo com extensão"},
                "conteudo": {"type": "string", "description": "Conteúdo do arquivo"},
                "pasta": {"type": "string", "description": "Caminho da pasta no Drive"}
            },
            "required": ["nome_arquivo", "conteudo"]
        }
    },
    {
        "name": "drive_buscar_arquivos",
        "description": "Busca arquivos no Google Drive por nome ou conteúdo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "Termo de busca"},
                "pasta": {"type": "string", "description": "Pasta para limitar a busca (opcional)"}
            },
            "required": ["termo"]
        }
    },
    {
        "name": "drive_listar_arquivos_os",
        "description": "Lista todos os arquivos do Drive relacionados a uma OS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_os": {"type": "string", "description": "Número da OS"}
            },
            "required": ["numero_os"]
        }
    },
    # ── Avarias ─────────────────────────────────
    {
        "name": "registrar_avaria",
        "description": ("Registra uma avaria de item durante a mudança. "
                        "Salva a foto no Google Drive na pasta do cliente (OS) e registra no ERP. "
                        "Use quando um funcionário enviar foto de item danificado/avariado antes, durante ou após a mudança. "
                        "A foto é armazenada INTERNAMENTE — nunca compartilhada com o cliente automaticamente."),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_os": {"type": "string", "description": "Número da OS vinculada à mudança"},
                "descricao": {"type": "string", "description": "Descrição detalhada do item e da avaria (ex: 'Sofá 3 lugares — arranhão na lateral direita')"},
                "funcionario_nome": {"type": "string", "description": "Nome do funcionário que reportou"},
                "nome_cliente": {"type": "string", "description": "Nome do cliente (para organizar pasta no Drive)"},
                "message_id": {"type": "string", "description": "ID da mensagem WhatsApp contendo a foto (para download automático)"}
            },
            "required": ["numero_os", "descricao", "funcionario_nome"]
        }
    },
    {
        "name": "listar_avarias_os",
        "description": "Lista todas as avarias registradas para uma OS, com links das fotos no Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_os": {"type": "string", "description": "Número da OS"},
                "nome_cliente": {"type": "string", "description": "Nome do cliente (opcional)"}
            },
            "required": ["numero_os"]
        }
    },
    # ── Analytics ───────────────────────────────
    {
        "name": "gerar_analise_proativa",
        "description": "Gera análise proativa de métricas operacionais (financeiro, leads, estoque).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["financeiro", "operacional", "leads", "estoque", "completo"],
                    "description": "Tipo de análise"
                },
                "periodo_dias": {"type": "integer", "description": "Período em dias (padrão: 30)"}
            }
        }
    },
    # ── Leads ───────────────────────────────────
    {
        "name": "consultar_leads",
        "description": "Consulta leads/oportunidades de venda no ERP.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filtro por status (aberto, ganho, perdido)"},
                "periodo_dias": {"type": "integer", "description": "Período em dias"}
            }
        }
    },
    # ── Usuário/Contexto ────────────────────────
    {
        "name": "configurar_preferencias",
        "description": "Configura preferências e perfil do usuário atual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "preferencias": {"type": "object", "description": "Dict com preferências a atualizar"}
            },
            "required": ["preferencias"]
        }
    },
    {
        "name": "consultar_meu_contexto",
        "description": "Consulta o histórico e contexto do usuário atual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incluir_historico": {"type": "boolean", "description": "Incluir histórico de ações"}
            }
        }
    },
    # ── Notificações ────────────────────────────
    {
        "name": "enviar_notificacao_cliente",
        "description": "Envia uma notificação WhatsApp ao cliente sobre o status da mudança.",
        "input_schema": {
            "type": "object",
            "properties": {
                "telefone_cliente": {"type": "string", "description": "Telefone do cliente com DDD"},
                "mensagem": {"type": "string", "description": "Mensagem a enviar"},
                "tipo": {
                    "type": "string",
                    "enum": ["confirmacao", "lembrete", "em_rota", "concluido", "personalizado"],
                    "description": "Tipo de notificação"
                }
            },
            "required": ["telefone_cliente", "mensagem"]
        }
    }
]


# ─────────────────────────────────────────────
# EXECUTOR DAS FERRAMENTAS
# ─────────────────────────────────────────────

def executar_ferramenta(tool_name: str, tool_input: dict, context: dict = None) -> Any:
    """
    Executa a ferramenta solicitada pelo Claude e retorna o resultado.

    Args:
        tool_name: Nome da ferramenta
        tool_input: Parâmetros da ferramenta
        context: Contexto adicional (telefone do usuário, instância, etc.)

    Returns:
        Resultado da ferramenta (dict ou string)
    """
    ctx = context or {}
    telefone = ctx.get("telefone", "")
    message_id = ctx.get("message_id", "")

    try:
        # ── Importações locais para evitar circular imports ──
        from integrations.legacy_api import legacy_api
        from integrations.google_calendar import google_calendar
        from integrations.google_drive import google_drive
        from integrations.damage_registry import damage_registry
        from agent.analytics import AnalisesProativas
        from agent.user_context import user_context_manager

        # ── OS e Agenda ──
        if tool_name == "consultar_os":
            if not legacy_api:
                return {"erro": "ERP não disponível"}
            numero = tool_input.get("numero_os", "")
            cliente = tool_input.get("nome_cliente", "")
            if numero:
                return legacy_api.obter_os(numero)
            elif cliente:
                return legacy_api.buscar_os_por_cliente(cliente)
            return {"erro": "Informe numero_os ou nome_cliente"}

        elif tool_name == "listar_os_do_dia":
            if not legacy_api:
                return {"erro": "ERP não disponível"}
            data = tool_input.get("data", datetime.now().strftime("%d/%m/%Y"))
            return legacy_api.listar_os_do_dia(data)

        elif tool_name == "criar_evento_agenda":
            if not google_calendar:
                return {"erro": "Google Calendar não disponível"}
            return google_calendar.criar_evento(
                titulo=tool_input.get("titulo", ""),
                inicio=tool_input.get("data_hora_inicio", ""),
                fim=tool_input.get("data_hora_fim", ""),
                descricao=tool_input.get("descricao", ""),
                numero_os=tool_input.get("numero_os", "")
            )

        # ── Drive ──
        elif tool_name == "drive_salvar_arquivo":
            if not google_drive:
                return {"erro": "Google Drive não disponível"}
            conteudo_bytes = tool_input.get("conteudo", "").encode("utf-8")
            return google_drive.upload_file(
                file_content=conteudo_bytes,
                filename=tool_input.get("nome_arquivo", "arquivo.txt"),
                folder_path=tool_input.get("pasta", "Documentos"),
                mimetype="text/plain"
            )

        elif tool_name == "drive_buscar_arquivos":
            if not google_drive:
                return {"erro": "Google Drive não disponível"}
            return google_drive.search_files(query=tool_input.get("termo", ""))

        elif tool_name == "drive_listar_arquivos_os":
            if not google_drive:
                return {"erro": "Google Drive não disponível"}
            numero_os = tool_input.get("numero_os", "")
            return google_drive.search_files(query=f"OS {numero_os}")

        # ── Avarias ──
        elif tool_name == "registrar_avaria":
            if not damage_registry:
                return {"erro": "Módulo de avarias não inicializado"}
            return damage_registry.registrar_avaria(
                numero_os=tool_input.get("numero_os", ""),
                descricao=tool_input.get("descricao", ""),
                funcionario_nome=tool_input.get("funcionario_nome", "Funcionário"),
                funcionario_telefone=telefone,
                message_id=tool_input.get("message_id", message_id),
                nome_cliente=tool_input.get("nome_cliente", "")
            )

        elif tool_name == "listar_avarias_os":
            if not damage_registry:
                return {"erro": "Módulo de avarias não inicializado"}
            numero_os = tool_input.get("numero_os", "")
            nome_cliente = tool_input.get("nome_cliente", "")
            relatorio = damage_registry.gerar_relatorio_avarias(numero_os, nome_cliente)
            return {"relatorio": relatorio, "os": numero_os}

        # ── Analytics ──
        elif tool_name == "gerar_analise_proativa":
            if not legacy_api:
                return {"erro": "ERP não disponível"}
            analytics = AnalisesProativas(legacy_api)
            tipo = tool_input.get("tipo", "completo")
            periodo = tool_input.get("periodo_dias", 30)
            return analytics.gerar_relatorio_completo(periodo_dias=periodo)

        # ── Leads ──
        elif tool_name == "consultar_leads":
            if not legacy_api:
                return {"erro": "ERP não disponível"}
            status = tool_input.get("status", "")
            periodo = tool_input.get("periodo_dias", 30)
            return legacy_api.listar_leads(status=status, periodo_dias=periodo)

        # ── Usuário/Contexto ──
        elif tool_name == "configurar_preferencias":
            prefs = tool_input.get("preferencias", {})
            user_context_manager.update_preferences(telefone, prefs)
            return {"success": True, "message": "Preferências atualizadas."}

        elif tool_name == "consultar_meu_contexto":
            ctx_user = user_context_manager.get_context(telefone)
            return ctx_user

        # ── Notificações ──
        elif tool_name == "enviar_notificacao_cliente":
            from agent.notifications import NotificationManager
            from integrations.evolution import EvolutionAPI
            evolution = EvolutionAPI()
            nm = NotificationManager(evolution)
            fone = tool_input.get("telefone_cliente", "")
            msg = tool_input.get("mensagem", "")
            result = evolution.send_text(fone, msg)
            return {"success": True, "resultado": result}

        else:
            return {"erro": f"Ferramenta desconhecida: {tool_name}"}

    except Exception as e:
        logger.error("Erro ao executar ferramenta %s: %s", tool_name, e)
        return {"erro": str(e)}
