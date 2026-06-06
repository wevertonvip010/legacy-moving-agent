"""
integrations/google_drive.py
Fase 3 — Drive inteligente: salvar, buscar e organizar arquivos no Google Drive
Suporta upload por URL, busca semantica por descricao e organizacao por categoria/OS
"""

import os
import json
import logging
import io
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID", "")

# Categorias de pasta no Drive
DRIVE_FOLDERS = {
    "avarias":      "Avarias",
    "contratos":    "Contratos",
    "comprovantes": "Comprovantes",
    "fotos_os":     "Fotos_OS",
    "orcamentos":   "Orcamentos",
    "relatorios":   "Relatorios",
    "outros":       "Outros",
}

_drive_service = None
_folder_cache: dict = {}


def _get_service():
    """Inicializa o servico Google Drive (lazy)."""
    global _drive_service
    if _drive_service is not None:
        return _drive_service
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        if not GOOGLE_CREDENTIALS_JSON:
            raise ValueError("GOOGLE_CREDENTIALS_JSON nao configurado no .env")
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        _drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("[Drive] Servico inicializado")
        return _drive_service
    except ImportError:
        raise ImportError("Instale: pip install google-api-python-client google-auth")
    except Exception as e:
        logger.error(f"[Drive] Erro ao inicializar: {e}")
        raise


def is_available() -> bool:
    try:
        _get_service()
        return True
    except Exception:
        return False


def _get_or_create_folder(folder_name: str, parent_id: Optional[str] = None) -> str:
    """Busca ou cria uma pasta no Drive. Retorna o ID da pasta."""
    cache_key = f"{parent_id or 'root'}:{folder_name}"
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]
    service = _get_service()
    parent = parent_id or DRIVE_ROOT_FOLDER_ID or "root"
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent}' in parents and trashed=false"
    )
    resp = service.files().list(q=query, fields="files(id,name)").execute()
    files = resp.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent],
        }
        folder = service.files().create(body=meta, fields="id").execute()
        folder_id = folder["id"]
        logger.info(f"[Drive] Pasta criada: {folder_name} ({folder_id})")
    _folder_cache[cache_key] = folder_id
    return folder_id


def _get_categoria_folder(categoria: str) -> str:
    """Retorna ID da pasta de categoria, criando se necessario."""
    nome_pasta = DRIVE_FOLDERS.get(categoria, "Outros")
    if DRIVE_ROOT_FOLDER_ID:
        root_id = DRIVE_ROOT_FOLDER_ID
    else:
        root_id = _get_or_create_folder("LegacyMoving-Agent")
    return _get_or_create_folder(nome_pasta, parent_id=root_id)


def upload_from_bytes(
    filename: str,
    content_bytes: bytes,
    mime_type: str = "application/octet-stream",
    categoria: str = "outros",
    descricao: str = "",
    os_id: Optional[int] = None,
    tags: Optional[list] = None,
) -> dict:
    """Envia bytes para o Google Drive na pasta correta."""
    service = _get_service()
    folder_id = _get_categoria_folder(categoria)
    ts = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M")
    meta_desc = descricao or filename
    if os_id:
        meta_desc = f"OS#{os_id} | {meta_desc}"
    if tags:
        meta_desc += f" | Tags: {', '.join(tags)}"
    meta_desc += f" | {ts}"
    file_meta = {
        "name": filename,
        "description": meta_desc,
        "parents": [folder_id],
    }
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id,name,webViewLink,mimeType,size,createdTime",
    ).execute()
    file_id = uploaded["id"]
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()
    result = {
        "id": file_id,
        "nome": uploaded.get("name"),
        "url": uploaded.get("webViewLink"),
        "categoria": categoria,
        "descricao": meta_desc,
        "tamanho": uploaded.get("size"),
        "criado_em": uploaded.get("createdTime"),
    }
    logger.info(f"[Drive] Arquivo salvo: {filename} ({file_id})")
    return result


def upload_from_url(
    url: str,
    filename: str,
    categoria: str = "outros",
    descricao: str = "",
    os_id: Optional[int] = None,
    tags: Optional[list] = None,
) -> dict:
    """Baixa arquivo de uma URL e envia para o Drive."""
    import requests
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0]
        return upload_from_bytes(
            filename=filename,
            content_bytes=resp.content,
            mime_type=content_type,
            categoria=categoria,
            descricao=descricao,
            os_id=os_id,
            tags=tags,
        )
    except Exception as e:
        logger.error(f"[Drive] Erro ao fazer upload de URL: {e}")
        return {"erro": str(e)}


def buscar_arquivos(
    query_texto: str = "",
    categoria: Optional[str] = None,
    os_id: Optional[int] = None,
    limite: int = 10,
) -> list:
    """Busca arquivos no Drive por texto livre, categoria ou OS."""
    service = _get_service()
    conditions = ["trashed=false"]
    if categoria:
        try:
            folder_id = _get_categoria_folder(categoria)
            conditions.append(f"'{folder_id}' in parents")
        except Exception:
            pass
    if os_id:
        conditions.append(f"fullText contains 'OS#{os_id}'")
    elif query_texto:
        safe_q = query_texto.replace("'", "\\'")
        conditions.append(f"fullText contains '{safe_q}'")
    q = " and ".join(conditions)
    fields = "files(id,name,description,webViewLink,mimeType,size,createdTime,modifiedTime)"
    try:
        resp = service.files().list(
            q=q,
            fields=fields,
            pageSize=limite,
            orderBy="modifiedTime desc",
        ).execute()
        files = resp.get("files", [])
        return [_format_file(f) for f in files]
    except Exception as e:
        logger.error(f"[Drive] Erro na busca: {e}")
        return []


def listar_arquivos_os(os_id: int) -> list:
    """Lista todos os arquivos relacionados a uma OS."""
    return buscar_arquivos(os_id=os_id, limite=20)


def listar_por_categoria(categoria: str, limite: int = 20) -> list:
    """Lista arquivos de uma categoria especifica."""
    return buscar_arquivos(categoria=categoria, limite=limite)


def obter_arquivo(file_id: str) -> dict:
    """Obtem detalhes de um arquivo pelo ID."""
    service = _get_service()
    try:
        f = service.files().get(
            fileId=file_id,
            fields="id,name,description,webViewLink,mimeType,size,createdTime",
        ).execute()
        return _format_file(f)
    except Exception as e:
        logger.error(f"[Drive] Erro ao obter arquivo {file_id}: {e}")
        return {"erro": str(e)}


def deletar_arquivo(file_id: str) -> dict:
    """Move arquivo para lixeira no Drive."""
    service = _get_service()
    try:
        service.files().update(fileId=file_id, body={"trashed": True}).execute()
        logger.info(f"[Drive] Arquivo {file_id} movido para lixeira")
        return {"ok": True, "id": file_id}
    except Exception as e:
        logger.error(f"[Drive] Erro ao deletar {file_id}: {e}")
        return {"erro": str(e)}


def _format_file(f: dict) -> dict:
    size_bytes = int(f.get("size", 0) or 0)
    size_label = _human_size(size_bytes) if size_bytes else ""
    return {
        "id": f.get("id"),
        "nome": f.get("name"),
        "descricao": f.get("description", ""),
        "url": f.get("webViewLink"),
        "tipo": f.get("mimeType", ""),
        "tamanho": size_label,
        "criado_em": _format_dt(f.get("createdTime", "")),
        "modificado_em": _format_dt(f.get("modifiedTime", "")),
    }


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _format_dt(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_local = dt.astimezone(ZoneInfo(TIMEZONE))
        return dt_local.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str


def formatar_arquivos_whatsapp(arquivos: list, titulo: str = "Arquivos") -> str:
    """Formata lista de arquivos para exibicao no WhatsApp."""
    if not arquivos:
        return "_Nenhum arquivo encontrado._"
    linhas = [f"*{titulo}* ({len(arquivos)})", ""]
    for arq in arquivos:
        linhas.append(f"\U0001F4C4 *{arq['nome']}*")
        if arq.get("descricao"):
            linhas.append(f"   _{arq['descricao'][:80]}_")
        if arq.get("tamanho"):
            linhas.append(f"   Tamanho: {arq['tamanho']}")
        linhas.append(f"   \U0001F4CE {arq.get('url', 'sem link')}")
        linhas.append("")
    return "\n".join(linhas)


# ─────────────────────────────────────────────────────────
# CLASSE WRAPPER — compatibilidade com main.py e tools.py
# ─────────────────────────────────────────────────────────

class GoogleDriveIntegration:
    """Wrapper OO sobre as funcoes de modulo do Google Drive."""

    def is_available(self) -> bool:
        return is_available()

    def upload_file(self, nome: str, conteudo_bytes: bytes,
                    categoria: str = "relatorios", numero_os: str = "",
                    descricao: str = "", nome_cliente: str = "",
                    funcionario_nome: str = "") -> dict:
        """Alias upload_file -> upload_from_bytes (compatibilidade tools.py)."""
        return upload_from_bytes(
            nome=nome, conteudo=conteudo_bytes, categoria=categoria,
            numero_os=numero_os, descricao=descricao,
            nome_cliente=nome_cliente, funcionario_nome=funcionario_nome)

    def upload_from_bytes(self, nome: str, conteudo: bytes,
                          categoria: str = "relatorios", **kwargs) -> dict:
        return upload_from_bytes(nome=nome, conteudo=conteudo,
                                 categoria=categoria, **kwargs)

    def search_files(self, query: str = "", numero_os: str = "",
                     categoria: str = "") -> list:
        """Alias search_files -> buscar_arquivos (compatibilidade tools.py)."""
        return buscar_arquivos(query=query, numero_os=numero_os,
                               categoria=categoria)

    def buscar_arquivos(self, query: str = "", numero_os: str = "",
                        categoria: str = "") -> list:
        return buscar_arquivos(query=query, numero_os=numero_os,
                               categoria=categoria)

    def listar_arquivos_os(self, numero_os: str) -> list:
        return listar_arquivos_os(numero_os=numero_os)

    def listar_por_categoria(self, categoria: str, limite: int = 20) -> list:
        return listar_por_categoria(categoria=categoria, limite=limite)

    def obter_arquivo(self, file_id: str) -> dict:
        return obter_arquivo(file_id=file_id)

    def formatar_arquivos_whatsapp(self, arquivos: list,
                                   titulo: str = "Arquivos") -> str:
        return formatar_arquivos_whatsapp(arquivos=arquivos, titulo=titulo)


# Singleton global — inicializado em main.py via init_google_drive()
google_drive: "GoogleDriveIntegration" = None


def init_google_drive() -> GoogleDriveIntegration:
    """Inicializa a instancia global do GoogleDriveIntegration."""
    global google_drive
    google_drive = GoogleDriveIntegration()
    logger.info("GoogleDriveIntegration inicializado.")
    return google_drive
