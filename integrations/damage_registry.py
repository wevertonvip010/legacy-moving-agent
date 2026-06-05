"""
Módulo de Registro de Avarias — Legacy Moving Agent

Responsável por:
- Receber fotos de itens avariados enviadas pelos funcionários via WhatsApp
- Baixar a mídia da Evolution API
- Salvar automaticamente no Google Drive na pasta do cliente/OS
- Registrar metadados no ERP (Legacy API)
- Gerar relatório de avarias por OS
"""

import os
import io
import logging
import requests
import base64
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "legacy")


class DamageRegistry:
    """Gerencia o registro fotográfico de avarias em mudanças."""

    def __init__(self, drive_integration=None, legacy_api=None):
        """
        Args:
            drive_integration: Instância de GoogleDriveIntegration
            legacy_api: Instância de LegacyAPI
        """
        self.drive = drive_integration
        self.api = legacy_api

    def download_media_from_evolution(self, message_id: str, instance: str = None) -> Optional[bytes]:
        """
        Baixa a mídia (imagem) de uma mensagem WhatsApp via Evolution API.

        Args:
            message_id: ID da mensagem no WhatsApp
            instance: Nome da instância Evolution (usa padrão se None)

        Returns:
            bytes da imagem ou None em caso de erro
        """
        inst = instance or EVOLUTION_INSTANCE
        url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{inst}"
        headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
        payload = {"message": {"key": {"id": message_id}}, "convertToMp4": False}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Evolution retorna {"base64": "...", "mimetype": "image/jpeg"}
            base64_str = data.get("base64", "")
            if base64_str:
                return base64.b64decode(base64_str)
            logger.warning("Resposta da Evolution sem campo base64: %s", data)
            return None
        except Exception as e:
            logger.error("Erro ao baixar mídia da Evolution: %s", e)
            return None

    def registrar_avaria(self,
                         numero_os: str,
                         descricao: str,
                         funcionario_nome: str,
                         funcionario_telefone: str,
                         image_bytes: Optional[bytes] = None,
                         message_id: Optional[str] = None,
                         nome_cliente: str = "",
                         data_mudanca: str = "") -> dict:
        """
        Registra uma avaria: salva foto no Drive e metadata no ERP.

        Args:
            numero_os: Número da Ordem de Serviço
            descricao: Descrição do item avariado
            funcionario_nome: Nome do funcionário que reportou
            funcionario_telefone: Telefone do funcionário
            image_bytes: Bytes da imagem (se já baixada)
            message_id: ID da mensagem no WhatsApp (para baixar mídia)
            nome_cliente: Nome do cliente (para organizar no Drive)
            data_mudanca: Data da mudança no formato dd/mm/aaaa

        Returns:
            dict com status e informações do registro
        """
        resultado = {
            "success": False,
            "os": numero_os,
            "descricao": descricao,
            "drive_url": None,
            "drive_file_id": None,
            "registro_erp": None,
            "timestamp": datetime.now().isoformat(),
            "erros": []
        }

        # 1. Obter bytes da imagem (download se necessário)
        if not image_bytes and message_id:
            logger.info("Baixando mídia da mensagem %s", message_id)
            image_bytes = self.download_media_from_evolution(message_id)
            if not image_bytes:
                resultado["erros"].append("Falha ao baixar imagem da Evolution API")

        # 2. Salvar no Google Drive
        if image_bytes and self.drive:
            try:
                drive_result = self._salvar_foto_drive(
                    image_bytes=image_bytes,
                    numero_os=numero_os,
                    descricao=descricao,
                    nome_cliente=nome_cliente,
                    funcionario_nome=funcionario_nome
                )
                resultado["drive_url"] = drive_result.get("webViewLink")
                resultado["drive_file_id"] = drive_result.get("id")
                logger.info("Foto de avaria salva no Drive: %s", resultado["drive_url"])
            except Exception as e:
                erro = f"Erro ao salvar no Drive: {e}"
                logger.error(erro)
                resultado["erros"].append(erro)
        elif not self.drive:
            resultado["erros"].append("Drive não configurado — foto não salva no Drive")

        # 3. Registrar no ERP como observação da OS
        if self.api:
            try:
                obs_texto = self._formatar_observacao_erp(
                    descricao=descricao,
                    funcionario_nome=funcionario_nome,
                    drive_url=resultado["drive_url"]
                )
                erp_result = self.api.adicionar_observacao_os(
                    numero_os=numero_os,
                    observacao=obs_texto,
                    tipo="AVARIA"
                )
                resultado["registro_erp"] = erp_result
            except Exception as e:
                erro = f"Erro ao registrar no ERP: {e}"
                logger.error(erro)
                resultado["erros"].append(erro)

        # Definir sucesso: pelo menos Drive ou ERP deve ter registrado
        resultado["success"] = (
            resultado["drive_url"] is not None or
            resultado["registro_erp"] is not None
        )

        return resultado

    def _salvar_foto_drive(self,
                           image_bytes: bytes,
                           numero_os: str,
                           descricao: str,
                           nome_cliente: str,
                           funcionario_nome: str) -> dict:
        """
        Salva a foto de avaria no Google Drive na pasta correta.

        Estrutura de pastas:
          Legacy Moving Agent/
            Clientes/
              {nome_cliente} — OS {numero_os}/
                Avarias/
                  avaria_{timestamp}_{descricao_curta}.jpg
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        descricao_curta = descricao[:30].replace(" ", "_").replace("/", "-")
        nome_arquivo = f"avaria_{timestamp}_{descricao_curta}.jpg"

        # Construir caminho de pasta no Drive
        pasta_cliente = f"{nome_cliente} — OS {numero_os}" if nome_cliente else f"OS_{numero_os}"
        caminho = f"Clientes/{pasta_cliente}/Avarias"

        # Metadados do arquivo
        descricao_drive = (
            f"Avaria registrada por {funcionario_nome}\n"
            f"OS: {numero_os}\n"
            f"Item: {descricao}\n"
            f"Registrado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"INTERNO — Não compartilhar com cliente"
        )

        return self.drive.upload_file(
            file_content=image_bytes,
            filename=nome_arquivo,
            folder_path=caminho,
            description=descricao_drive,
            mimetype="image/jpeg"
        )

    def _formatar_observacao_erp(self, descricao: str, funcionario_nome: str, drive_url: Optional[str]) -> str:
        """Formata o texto de observação para registrar no ERP."""
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        texto = f"[AVARIA REGISTRADA — {data_hora}]\n"
        texto += f"Reportado por: {funcionario_nome}\n"
        texto += f"Item avariado: {descricao}\n"
        if drive_url:
            texto += f"Foto: {drive_url}\n"
        texto += "Status: INTERNO — Não visível ao cliente"
        return texto

    def listar_avarias_os(self, numero_os: str) -> list:
        """
        Lista todas as avarias registradas para uma OS.

        Returns:
            Lista de dicts com informações de cada avaria
        """
        avarias = []

        # Buscar no Drive
        if self.drive:
            try:
                termo_busca = f"avaria_ name contains 'OS_{numero_os}'"
                arquivos = self.drive.search_files(query=f"name contains 'avaria_' and 'OS {numero_os}' in parents")
                for arq in arquivos:
                    avarias.append({
                        "fonte": "drive",
                        "nome": arq.get("name"),
                        "url": arq.get("webViewLink"),
                        "data": arq.get("createdTime"),
                        "id": arq.get("id")
                    })
            except Exception as e:
                logger.error("Erro ao listar avarias no Drive: %s", e)

        return avarias

    def gerar_relatorio_avarias(self, numero_os: str, nome_cliente: str = "") -> str:
        """
        Gera um relatório textual de avarias de uma OS para o assessor.

        Returns:
            String formatada com o relatório
        """
        avarias = self.listar_avarias_os(numero_os)

        if not avarias:
            return f"✅ Nenhuma avaria registrada para a OS {numero_os}."

        cliente_txt = f" — Cliente: {nome_cliente}" if nome_cliente else ""
        relatorio = f"📋 *Relatório de Avarias — OS {numero_os}{cliente_txt}*\n\n"
        relatorio += f"Total de registros: {len(avarias)}\n\n"

        for i, av in enumerate(avarias, 1):
            relatorio += f"*{i}. {av.get('nome', 'Arquivo')}*\n"
            if av.get("url"):
                relatorio += f"   🔗 {av['url']}\n"
            if av.get("data"):
                relatorio += f"   📅 {av['data']}\n"
            relatorio += "\n"

        relatorio += "_Documentação interna — não compartilhar com o cliente._"
        return relatorio


# Instância global (inicializada em main.py com as dependências)
damage_registry: Optional[DamageRegistry] = None


def init_damage_registry(drive_integration=None, legacy_api=None):
    """Inicializa a instância global do DamageRegistry."""
    global damage_registry
    damage_registry = DamageRegistry(
        drive_integration=drive_integration,
        legacy_api=legacy_api
    )
    logger.info("DamageRegistry inicializado.")
    return damage_registry
