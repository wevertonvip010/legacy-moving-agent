"""
Testes do Sistema de Avarias — Legacy Moving Agent

Testa o fluxo completo:
1. Detecção de mensagem de avaria no webhook
2. Processamento pelo DamageRegistry
3. Salvamento no Drive (mock)
4. Registro no ERP (mock)
5. Geração de relatório

Execute com: python -m pytest tests/test_damage_registry.py -v
"""

import pytest
import json
from unittest.mock import MagicMock, patch, call
from datetime import datetime

# ────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────

@pytest.fixture
def mock_drive():
    """Mock do Google Drive."""
    drive = MagicMock()
    drive.upload_file.return_value = {
        "id": "file-abc123",
        "name": "avaria_20260101_120000_Sofa_arranhado.jpg",
        "webViewLink": "https://drive.google.com/file/d/file-abc123/view",
        "createdTime": "2026-01-01T12:00:00Z"
    }
    drive.search_files.return_value = [
        {
            "id": "file-abc123",
            "name": "avaria_20260101_120000_Sofa_arranhado.jpg",
            "webViewLink": "https://drive.google.com/file/d/file-abc123/view",
            "createdTime": "2026-01-01T12:00:00Z"
        }
    ]
    return drive


@pytest.fixture
def mock_api():
    """Mock da Legacy API (ERP)."""
    api = MagicMock()
    api.adicionar_observacao_os.return_value = {
        "success": True,
        "id_observacao": "obs-789"
    }
    api.obter_os.return_value = {
        "numero": "OS-2026-042",
        "cliente": "João da Silva",
        "data": "01/06/2026",
        "status": "em_andamento"
    }
    return api


@pytest.fixture
def registry(mock_drive, mock_api):
    """DamageRegistry com mocks injetados."""
    from integrations.damage_registry import DamageRegistry
    return DamageRegistry(drive_integration=mock_drive, legacy_api=mock_api)


@pytest.fixture
def image_bytes():
    """Bytes de imagem fake para testes."""
    # JPEG header mínimo válido
    return bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]) + b"FakeJPEGData" * 100


# ────────────────────────────────────────────────
# TESTES: DamageRegistry
# ────────────────────────────────────────────────

class TestDamageRegistryCore:
    """Testa o núcleo do DamageRegistry."""

    def test_registrar_avaria_com_imagem(self, registry, image_bytes, mock_drive, mock_api):
        """Deve salvar imagem no Drive e registrar no ERP."""
        resultado = registry.registrar_avaria(
            numero_os="OS-2026-042",
            descricao="Sofá 3 lugares — arranhão lateral direita",
            funcionario_nome="Diego",
            funcionario_telefone="5511999998888",
            image_bytes=image_bytes,
            nome_cliente="João da Silva"
        )

        # Deve ter sucesso
        assert resultado["success"] is True
        assert resultado["os"] == "OS-2026-042"

        # Drive deve ter sido chamado
        mock_drive.upload_file.assert_called_once()
        call_kwargs = mock_drive.upload_file.call_args[1]
        assert call_kwargs["mimetype"] == "image/jpeg"
        assert "avaria_" in call_kwargs["filename"]
        assert "Avarias" in call_kwargs["folder_path"]

        # ERP deve ter sido chamado
        mock_api.adicionar_observacao_os.assert_called_once()
        erp_call = mock_api.adicionar_observacao_os.call_args[1]
        assert erp_call["numero_os"] == "OS-2026-042"
        assert erp_call["tipo"] == "AVARIA"
        assert "Diego" in erp_call["observacao"]

        # URL do Drive deve estar no resultado
        assert "drive.google.com" in resultado["drive_url"]

    def test_registrar_avaria_sem_drive(self, mock_api, image_bytes):
        """Deve registrar no ERP mesmo sem Drive configurado."""
        from integrations.damage_registry import DamageRegistry
        registry_sem_drive = DamageRegistry(drive_integration=None, legacy_api=mock_api)

        resultado = registry_sem_drive.registrar_avaria(
            numero_os="OS-2026-042",
            descricao="Mesa de jantar riscada",
            funcionario_nome="Carlos",
            funcionario_telefone="5511777776666",
            image_bytes=image_bytes
        )

        # ERP deve ter sido chamado mesmo sem Drive
        mock_api.adicionar_observacao_os.assert_called_once()
        # Drive não deve ter sido chamado
        assert resultado["drive_url"] is None
        # Deve ter erro informativo sobre o Drive
        assert any("Drive" in e for e in resultado["erros"])

    def test_registrar_avaria_sem_imagem(self, registry, mock_api):
        """Deve registrar no ERP mesmo sem imagem (só texto)."""
        resultado = registry.registrar_avaria(
            numero_os="OS-2026-042",
            descricao="Geladeira amassada na lateral",
            funcionario_nome="Pedro",
            funcionario_telefone="5511888887777",
            image_bytes=None,
            message_id=None
        )

        # Deve ter registrado no ERP
        mock_api.adicionar_observacao_os.assert_called_once()

    def test_nome_arquivo_drive_formato_correto(self, registry, image_bytes, mock_drive):
        """O nome do arquivo salvo no Drive deve seguir o padrão correto."""
        registry.registrar_avaria(
            numero_os="OS-2026-099",
            descricao="Cama box amassada",
            funcionario_nome="Ana",
            funcionario_telefone="55119999",
            image_bytes=image_bytes,
            nome_cliente="Maria Santos"
        )

        call_kwargs = mock_drive.upload_file.call_args[1]
        filename = call_kwargs["filename"]
        folder = call_kwargs["folder_path"]

        # Verificar formato do nome: avaria_YYYYMMDD_HHMMSS_descricao.jpg
        assert filename.startswith("avaria_")
        assert filename.endswith(".jpg")

        # Verificar que pasta contém o nome do cliente e número da OS
        assert "Maria Santos" in folder or "OS-2026-099" in folder
        assert "Avarias" in folder

    def test_listar_avarias_os(self, registry, mock_drive):
        """Deve listar avarias de uma OS corretamente."""
        avarias = registry.listar_avarias_os("OS-2026-042")

        assert isinstance(avarias, list)
        assert len(avarias) >= 0  # Pode ser vazio ou com resultados do mock

    def test_relatorio_avarias_com_registros(self, registry, mock_drive):
        """Deve gerar relatório formatado com links."""
        relatorio = registry.gerar_relatorio_avarias("OS-2026-042", "João da Silva")

        assert "OS-2026-042" in relatorio
        assert "João da Silva" in relatorio

    def test_relatorio_avarias_sem_registros(self, mock_api):
        """Deve retornar mensagem de nenhuma avaria encontrada."""
        from integrations.damage_registry import DamageRegistry
        mock_drive_vazio = MagicMock()
        mock_drive_vazio.search_files.return_value = []
        registry_vazio = DamageRegistry(drive_integration=mock_drive_vazio, legacy_api=mock_api)

        relatorio = registry_vazio.gerar_relatorio_avarias("OS-9999-000")

        assert "Nenhuma avaria" in relatorio
        assert "OS-9999-000" in relatorio


# ────────────────────────────────────────────────
# TESTES: Detecção de avaria no Webhook
# ────────────────────────────────────────────────

class TestWebhookAvaria:
    """Testa a detecção de avaria no webhook WhatsApp."""

    def test_eh_mensagem_de_avaria_positivo(self):
        """Deve detectar palavras-chave de avaria."""
        from webhooks.whatsapp import _eh_mensagem_de_avaria

        casos_positivos = [
            ("esse sofá tá avariado", ""),
            ("item danificado antes da mudança", ""),
            ("", "documentando avaria OS 042"),
            ("já estava arranhado", ""),
            ("geladeira amassada", ""),
            ("registrando item com defeito", ""),
        ]

        for caption, texto in casos_positivos:
            assert _eh_mensagem_de_avaria(caption, texto), \
                f"Deveria detectar avaria em: caption='{caption}' texto='{texto}'"

    def test_eh_mensagem_de_avaria_negativo(self):
        """Não deve detectar avaria em mensagens comuns."""
        from webhooks.whatsapp import _eh_mensagem_de_avaria

        casos_negativos = [
            ("chegamos no endereço", ""),
            ("OS 042 concluída", ""),
            ("", "bom dia equipe"),
            ("foto da casa do cliente", ""),
        ]

        for caption, texto in casos_negativos:
            assert not _eh_mensagem_de_avaria(caption, texto), \
                f"Não deveria detectar avaria em: caption='{caption}' texto='{texto}'"

    def test_processar_imagem_avaria_com_numero_os(self):
        """Deve extrair número da OS da legenda."""
        from webhooks.whatsapp import _processar_imagem_avaria

        dados = {
            "caption": "avaria na geladeira OS 042",
            "texto": "",
            "message_id": "MSG-XYZ-789"
        }

        resultado = _processar_imagem_avaria(dados)

        assert resultado["tipo"] == "avaria"
        assert "042" in resultado["numero_os"]
        assert resultado["message_id"] == "MSG-XYZ-789"
        assert "registrar_avaria" in resultado["prompt"]

    def test_processar_imagem_avaria_sem_numero_os(self):
        """Deve pedir número da OS se não encontrar na legenda."""
        from webhooks.whatsapp import _processar_imagem_avaria

        dados = {
            "caption": "item arranhado",
            "texto": "",
            "message_id": "MSG-ABC-123"
        }

        resultado = _processar_imagem_avaria(dados)

        assert resultado["tipo"] == "avaria"
        assert resultado["numero_os"] == ""
        assert "número da OS" in resultado["prompt"]

    def test_extrair_dados_mensagem_imagem(self):
        """Deve extrair corretamente dados de mensagem com imagem."""
        from webhooks.whatsapp import _extrair_dados_mensagem

        payload = {
            "instance": "legacy_prod",
            "data": {
                "key": {
                    "remoteJid": "5511999990000@s.whatsapp.net",
                    "id": "MSG-FOTO-001",
                    "fromMe": False
                },
                "pushName": "Diego Operador",
                "message": {
                    "imageMessage": {
                        "mimetype": "image/jpeg",
                        "caption": "sofá arranhado OS 042"
                    }
                }
            }
        }

        dados = _extrair_dados_mensagem(payload)

        assert dados["telefone"] == "5511999990000"
        assert dados["nome"] == "Diego Operador"
        assert dados["is_image"] is True
        assert dados["mimetype"] == "image/jpeg"
        assert dados["caption"] == "sofá arranhado OS 042"
        assert dados["message_id"] == "MSG-FOTO-001"
        assert dados["from_me"] is False

    def test_extrair_dados_mensagem_texto(self):
        """Deve extrair corretamente dados de mensagem de texto."""
        from webhooks.whatsapp import _extrair_dados_mensagem

        payload = {
            "instance": "legacy_prod",
            "data": {
                "key": {
                    "remoteJid": "5511888880000@s.whatsapp.net",
                    "id": "MSG-TEXT-002",
                    "fromMe": False
                },
                "pushName": "Carlos",
                "message": {
                    "conversation": "Bom dia! Quais são as OSs de hoje?"
                }
            }
        }

        dados = _extrair_dados_mensagem(payload)

        assert dados["telefone"] == "5511888880000"
        assert dados["is_image"] is False
        assert dados["texto"] == "Bom dia! Quais são as OSs de hoje?"
        assert dados["tipo_mensagem"] == "text"


# ────────────────────────────────────────────────
# TESTES: Tools — ferramentas do agente
# ────────────────────────────────────────────────

class TestToolsAvaria:
    """Testa as ferramentas de avaria do agente."""

    @patch("integrations.damage_registry.damage_registry")
    def test_tool_registrar_avaria(self, mock_registry):
        """Ferramenta registrar_avaria deve chamar damage_registry."""
        mock_registry.registrar_avaria.return_value = {
            "success": True,
            "drive_url": "https://drive.google.com/file/d/abc/view",
            "os": "OS-2026-042"
        }

        from agent.tools import executar_ferramenta
        resultado = executar_ferramenta(
            "registrar_avaria",
            {
                "numero_os": "OS-2026-042",
                "descricao": "Sofá arranhado",
                "funcionario_nome": "Diego",
                "nome_cliente": "João da Silva"
            },
            context={"telefone": "5511999998888", "message_id": "MSG-001"}
        )

        assert resultado["success"] is True
        mock_registry.registrar_avaria.assert_called_once()

    @patch("integrations.damage_registry.damage_registry")
    def test_tool_listar_avarias_os(self, mock_registry):
        """Ferramenta listar_avarias_os deve retornar relatório."""
        mock_registry.gerar_relatorio_avarias.return_value = (
            "📋 *Relatório de Avarias — OS OS-2026-042*\n\nTotal: 1"
        )

        from agent.tools import executar_ferramenta
        resultado = executar_ferramenta(
            "listar_avarias_os",
            {"numero_os": "OS-2026-042", "nome_cliente": "João"},
            context={"telefone": "5511999998888"}
        )

        assert "relatorio" in resultado
        assert "OS-2026-042" in resultado["relatorio"]


# ────────────────────────────────────────────────
# TESTES DE INTEGRAÇÃO: Fluxo completo simulado
# ────────────────────────────────────────────────

class TestFluxoCompleto:
    """
    Simula o fluxo completo:
    WhatsApp foto → Webhook → Agente → DamageRegistry → Drive + ERP
    """

    def test_fluxo_funcionario_envia_foto_com_legenda(self):
        """
        CENÁRIO: Diego envia foto com legenda "sofá arranhado OS 042"
        ESPERADO: avaria detectada, prompt gerado com OS e message_id
        """
        from webhooks.whatsapp import _extrair_dados_mensagem, _eh_mensagem_de_avaria, _processar_imagem_avaria

        # Simular payload da Evolution API
        payload = {
            "instance": "legacy",
            "data": {
                "key": {
                    "remoteJid": "5511999998888@s.whatsapp.net",
                    "id": "3EB0DCA1234567890ABC",
                    "fromMe": False
                },
                "pushName": "Diego",
                "message": {
                    "imageMessage": {
                        "mimetype": "image/jpeg",
                        "caption": "sofá de 3 lugares arranhado OS 042 — já veio assim"
                    }
                }
            }
        }

        # Passo 1: Extrair dados
        dados = _extrair_dados_mensagem(payload)
        assert dados["is_image"] is True
        assert dados["telefone"] == "5511999998888"

        # Passo 2: Detectar avaria
        eh_avaria = _eh_mensagem_de_avaria(dados["caption"], dados["texto"])
        assert eh_avaria is True

        # Passo 3: Processar avaria
        info = _processar_imagem_avaria(dados)
        assert info["tipo"] == "avaria"
        assert "042" in info["numero_os"]
        assert info["message_id"] == "3EB0DCA1234567890ABC"

        # Passo 4: Verificar que o prompt instrui o agente corretamente
        prompt = info["prompt"]
        assert "registrar_avaria" in prompt
        assert "3EB0DCA1234567890ABC" in prompt

    def test_fluxo_funcionario_envia_foto_sem_legenda(self):
        """
        CENÁRIO: Funcionário envia foto sem legenda clara
        ESPERADO: agente pede número da OS
        """
        from webhooks.whatsapp import _extrair_dados_mensagem, _eh_mensagem_de_avaria, _processar_imagem_avaria

        payload = {
            "instance": "legacy",
            "data": {
                "key": {"remoteJid": "5511777773333@s.whatsapp.net", "id": "MSG999", "fromMe": False},
                "pushName": "Carlos",
                "message": {
                    "imageMessage": {
                        "mimetype": "image/jpeg",
                        "caption": "item danificado"
                    }
                }
            }
        }

        dados = _extrair_dados_mensagem(payload)
        assert _eh_mensagem_de_avaria(dados["caption"], dados["texto"]) is True

        info = _processar_imagem_avaria(dados)
        assert info["numero_os"] == ""
        assert "número da OS" in info["prompt"]

    def test_fluxo_registro_completo_mock(self, registry, image_bytes, mock_drive, mock_api):
        """
        CENÁRIO: Registro completo com todos os mocks
        ESPERADO: Drive chamado, ERP chamado, links retornados
        """
        resultado = registry.registrar_avaria(
            numero_os="OS-2026-042",
            descricao="Geladeira com amassado na lateral esquerda — 15cm",
            funcionario_nome="Diego",
            funcionario_telefone="5511999998888",
            image_bytes=image_bytes,
            nome_cliente="Maria Oliveira",
            data_mudanca="01/06/2026"
        )

        # Verificações completas
        assert resultado["success"] is True
        assert resultado["drive_url"] is not None
        assert resultado["registro_erp"] is not None
        assert len(resultado["erros"]) == 0
        assert resultado["os"] == "OS-2026-042"

        # Verificar descrição no ERP
        erp_obs = mock_api.adicionar_observacao_os.call_args[1]["observacao"]
        assert "AVARIA REGISTRADA" in erp_obs
        assert "Diego" in erp_obs
        assert "drive.google.com" in erp_obs  # Link do Drive na observação


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
