"""
utils/formatter.py
Formatador de mensagens para WhatsApp
Converte texto em formato compatível com WhatsApp markdown
"""

from datetime import datetime
from typing import Optional


# ──────────────────────────────────────────
# FORMATAÇÃO BÁSICA
# ──────────────────────────────────────────

def bold(text: str) -> str:
    """Texto em negrito: *texto*"""
    return f"*{text}*"


def italic(text: str) -> str:
    """Texto em itálico: _texto_"""
    return f"_{text}_"


def strike(text: str) -> str:
    """Texto riscado: ~texto~"""
    return f"~{text}~"


def code_inline(text: str) -> str:
    """Código inline: `texto`"""
    return f"`{text}`"


def code_block(text: str) -> str:
    """Bloco de código: ```texto```"""
    return f"```{text}```"


# ──────────────────────────────────────────
# COMPONENTES PRONTOS
# ──────────────────────────────────────────

def header(title: str, emoji: str = "") -> str:
    """Cabeçalho de mensagem com separador."""
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}{bold(title.upper())}"


def separator() -> str:
    """Linha separadora."""
    return "─" * 25


def bullet_list(items: list, emoji: str = "•") -> str:
    """Lista com marcadores."""
    lines = [f"{emoji} {item}" for item in items]
    return "\n".join(lines)


def numbered_list(items: list) -> str:
    """Lista numerada."""
    lines = [f"{i+1}. {item}" for i, item in enumerate(items)]
    return "\n".join(lines)


def key_value(key: str, value: str, emoji: str = "") -> str:
    """Par chave: valor formatado."""
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}{bold(key + ':')} {value}"


def money(value: float, prefix: str = "R$") -> str:
    """Formata valor monetário."""
    return f"{prefix} {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def date_br(dt: Optional[datetime] = None) -> str:
    """Formata data no padrão brasileiro."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d/%m/%Y")


def datetime_br(dt: Optional[datetime] = None) -> str:
    """Formata data e hora no padrão brasileiro."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d/%m/%Y %H:%M")


# ──────────────────────────────────────────
# MENSAGENS PRÉ-MONTADAS
# ──────────────────────────────────────────

def success_message(title: str, details: str = "") -> str:
    """Mensagem de sucesso padronizada."""
    lines = [f"✅ {bold(title)}"]
    if details:
        lines.append(details)
    return "\n".join(lines)


def error_message(title: str, details: str = "") -> str:
    """Mensagem de erro padronizada."""
    lines = [f"❌ {bold(title)}"]
    if details:
        lines.append(details)
    return "\n".join(lines)


def warning_message(title: str, details: str = "") -> str:
    """Mensagem de aviso padronizada."""
    lines = [f"⚠️ {bold(title)}"]
    if details:
        lines.append(details)
    return "\n".join(lines)


def info_message(title: str, details: str = "") -> str:
    """Mensagem informativa padronizada."""
    lines = [f"ℹ️ {bold(title)}"]
    if details:
        lines.append(details)
    return "\n".join(lines)


def expense_card(
    descricao: str,
    valor: float,
    categoria: str,
    data: Optional[str] = None,
    responsavel: Optional[str] = None,
) -> str:
    """Card formatado para exibir uma despesa."""
    lines = [
        f"💸 {bold('DESPESA REGISTRADA')}",
        separator(),
        key_value("Descrição", descricao, "📝"),
        key_value("Valor", money(valor), "💰"),
        key_value("Categoria", categoria, "🏷️"),
    ]
    if data:
        lines.append(key_value("Data", data, "📅"))
    if responsavel:
        lines.append(key_value("Registrado por", responsavel, "👤"))
    return "\n".join(lines)


def os_card(
    numero: str,
    cliente: str,
    tipo: str,
    status: str,
    data: Optional[str] = None,
    motorista: Optional[str] = None,
) -> str:
    """Card formatado para exibir uma Ordem de Serviço."""
    status_emoji = {
        "pendente": "🟡",
        "em_andamento": "🔵",
        "concluida": "✅",
        "cancelada": "❌",
    }.get(status.lower(), "⚪")

    lines = [
        f"📋 {bold('ORDEM DE SERVIÇO')}",
        separator(),
        key_value("OS Nº", numero, "🔢"),
        key_value("Cliente", cliente, "👤"),
        key_value("Tipo", tipo, "🚚"),
        key_value("Status", f"{status_emoji} {status.capitalize()}"),
    ]
    if data:
        lines.append(key_value("Data", data, "📅"))
    if motorista:
        lines.append(key_value("Motorista", motorista, "🚗"))
    return "\n".join(lines)


def summary_card(title: str, items: dict, emoji: str = "📊") -> str:
    """Card de resumo com múltiplos itens."""
    lines = [
        f"{emoji} {bold(title.upper())}",
        separator(),
    ]
    for key, value in items.items():
        lines.append(f"• {bold(key + ':')} {value}")
    return "\n".join(lines)


def paginated_list(
    title: str,
    items: list,
    page: int = 1,
    per_page: int = 10,
    emoji: str = "📋",
) -> str:
    """Lista paginada para quando há muitos itens."""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    total_pages = (total + per_page - 1) // per_page

    lines = [
        f"{emoji} {bold(title.upper())}",
        separator(),
    ]
    for i, item in enumerate(page_items, start=start + 1):
        lines.append(f"{i}. {item}")

    if total_pages > 1:
        lines.append(separator())
        lines.append(f"_Página {page}/{total_pages} — {total} itens no total_")

    return "\n".join(lines)


def help_menu(role: str) -> str:
    """Menu de ajuda personalizado por cargo."""
    base_commands = [
        "• _registrar despesa_ — Registra uma despesa",
        "• _minha agenda_ — Ver compromissos do dia",
        "• _tarefas pendentes_ — Ver suas tarefas",
        "• _ajuda_ — Exibe este menu",
    ]

    admin_commands = [
        "• _cadastrar [número] [nome] [cargo]_ — Cadastrar usuário",
        "• _listar usuários_ — Ver todos os usuários",
        "• _remover [número]_ — Remover usuário",
        "• _relatório financeiro_ — Resumo financeiro",
        "• _listar despesas_ — Ver todas as despesas",
    ]

    lines = [
        f"🤖 {bold('COMANDOS DISPONÍVEIS')}",
        separator(),
    ]
    lines.extend(base_commands)

    if role == "admin":
        lines.append("")
        lines.append(f"🔐 {bold('COMANDOS ADMIN')}")
        lines.extend(admin_commands)

    lines.append(separator())
    lines.append("_Ou simplesmente escreva o que precisa!_")
    return "\n".join(lines)


def welcome_message(name: str, role: str) -> str:
    """Mensagem de boas-vindas personalizada."""
    role_emoji = {
        "admin": "👑",
        "supervisor": "🎯",
        "motorista": "🚗",
        "operacional": "🔧",
        "comercial": "💼",
        "financeiro": "💰",
    }.get(role, "👤")

    return (
        f"Olá, {bold(name)}! {role_emoji}\n"
        f"Sou o agente da {bold('Legacy Moving')}.\n"
        f"Como posso te ajudar hoje?\n\n"
        f'_Digite {italic("ajuda")} para ver os comandos disponíveis._'
    )


def not_authorized_message() -> str:
    """Mensagem para usuário não cadastrado."""
    return (
        f"🚫 {bold('Acesso não autorizado')}\n\n"
        "Seu número não está cadastrado no sistema.\n"
        "Fale com o administrador para liberar seu acesso."
    )
