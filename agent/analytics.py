"""
agent/analytics.py
Fase 3 -- Analises proativas: insights automaticos, tendencias e alertas inteligentes
O agente detecta padroes e envia alertas proativos sem precisar ser perguntado
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")


def _tz() -> ZoneInfo:
    return ZoneInfo(TIMEZONE)


def _now() -> datetime:
    return datetime.now(_tz())


# Analises Financeiras

def analisar_financeiro(legacy_api) -> dict:
    """Analisa o financeiro e retorna insights proativos."""
    try:
        agora = _now()
        mes_atual = legacy_api.obter_resumo_financeiro(mes=agora.month, ano=agora.year) or {}
        mes_anterior_dt = agora.replace(day=1) - timedelta(days=1)
        mes_anterior = legacy_api.obter_resumo_financeiro(
            mes=mes_anterior_dt.month, ano=mes_anterior_dt.year
        ) or {}

        receita = float(mes_atual.get("receita_total", 0))
        despesas = float(mes_atual.get("despesas_total", 0))
        lucro = receita - despesas
        receita_ant = float(mes_anterior.get("receita_total", 0))

        insights = []
        alertas = []

        if receita_ant > 0:
            delta_receita = ((receita - receita_ant) / receita_ant) * 100
            if delta_receita >= 10:
                insights.append(f"Receita subiu {delta_receita:.1f}% vs mes anterior")
            elif delta_receita <= -10:
                alertas.append(f"Receita caiu {abs(delta_receita):.1f}% vs mes anterior")

        if receita > 0:
            ratio = (despesas / receita) * 100
            if ratio > 80:
                alertas.append(f"Despesas em {ratio:.0f}% da receita -- margem critica!")
            elif ratio > 65:
                alertas.append(f"Despesas em {ratio:.0f}% da receita -- atencao")

        dia_do_mes = agora.day
        dias_no_mes = 30
        if dia_do_mes > 0 and receita > 0:
            projecao_receita = (receita / dia_do_mes) * dias_no_mes
            projecao_lucro = projecao_receita - (despesas / dia_do_mes) * dias_no_mes
            insights.append(
                f"Projecao do mes: receita R${projecao_receita:,.0f} / lucro R${projecao_lucro:,.0f}"
            )

        return {"receita": receita, "despesas": despesas, "lucro": lucro,
                "insights": insights, "alertas": alertas}
    except Exception as e:
        logger.error(f"[Analytics] Erro ao analisar financeiro: {e}")
        return {"erro": str(e)}


def gerar_insight_financeiro_texto(legacy_api) -> str:
    """Gera texto formatado para WhatsApp com insights financeiros."""
    dados = analisar_financeiro(legacy_api)
    if "erro" in dados:
        return f"_Nao foi possivel gerar analise: {dados['erro']}_"

    linhas = ["*Analise Financeira do Mes*", ""]
    linhas.append(f"Receita:  R$ {dados['receita']:>10,.2f}")
    linhas.append(f"Despesas: R$ {dados['despesas']:>10,.2f}")
    linhas.append(f"Lucro:    R$ {dados['lucro']:>10,.2f}")

    if dados.get("alertas"):
        linhas.append("")
        linhas.append("*Alertas:*")
        for a in dados["alertas"]:
            linhas.append(f"  - {a}")

    if dados.get("insights"):
        linhas.append("")
        linhas.append("*Insights:*")
        for i in dados["insights"]:
            linhas.append(f"  - {i}")

    return "\n".join(linhas)


# Analises Operacionais

def analisar_operacional(legacy_api) -> dict:
    """Analisa indicadores operacionais: OS sem motorista, sem equipe, avarias."""
    try:
        agora = _now()
        hoje = agora.strftime("%Y-%m-%d")
        amanha = (agora + timedelta(days=1)).strftime("%Y-%m-%d")

        os_hoje = legacy_api.listar_ordens_servico(data=hoje) or []
        os_amanha = legacy_api.listar_ordens_servico(data=amanha) or []

        alertas = []
        insights = []

        sem_motorista = [o for o in os_hoje if not o.get("motorista_id")]
        if sem_motorista:
            alertas.append(
                f"{len(sem_motorista)} OS(s) hoje sem motorista: "
                + ", ".join(f"#{o.get('numero','?')}" for o in sem_motorista)
            )

        sem_equipe = [o for o in os_amanha if not o.get("equipe_ids")]
        if sem_equipe:
            alertas.append(
                f"{len(sem_equipe)} OS(s) amanha sem equipe: "
                + ", ".join(f"#{o.get('numero','?')}" for o in sem_equipe)
            )

        if os_hoje:
            insights.append(f"Hoje: {len(os_hoje)} OS(s) programadas")
        if os_amanha:
            insights.append(f"Amanha: {len(os_amanha)} OS(s) programadas")

        try:
            avarias = legacy_api.listar_avarias(limite=5) or []
            if avarias:
                insights.append(f"{len(avarias)} avaria(s) registrada(s) recentemente")
        except Exception:
            pass

        return {"os_hoje": len(os_hoje), "os_amanha": len(os_amanha),
                "alertas": alertas, "insights": insights}
    except Exception as e:
        logger.error(f"[Analytics] Erro ao analisar operacional: {e}")
        return {"erro": str(e)}


# Analises de Leads

def analisar_leads(legacy_api) -> dict:
    """Analisa pipeline de leads: sem contato, taxa de conversao."""
    try:
        leads_novos = legacy_api.listar_leads(status="novo", limite=50) or []
        leads_em_contato = legacy_api.listar_leads(status="em_contato", limite=50) or []
        leads_convertidos = legacy_api.listar_leads(status="convertido", limite=50) or []

        agora = _now()
        alertas = []
        insights = []

        parados = []
        for lead in leads_novos:
            criado_str = lead.get("criado_em", "")
            if criado_str:
                try:
                    criado = datetime.fromisoformat(criado_str.replace("Z", "+00:00"))
                    if (agora - criado).days >= 2:
                        parados.append(lead)
                except Exception:
                    pass

        if parados:
            alertas.append(
                f"{len(parados)} lead(s) novo(s) sem contato ha 2+ dias: "
                + ", ".join(l.get("nome", "?")[:20] for l in parados[:3])
            )

        total_leads = len(leads_novos) + len(leads_em_contato) + len(leads_convertidos)
        if total_leads > 0 and leads_convertidos:
            taxa = (len(leads_convertidos) / total_leads) * 100
            insights.append(f"Taxa de conversao: {taxa:.0f}%")

        if leads_novos:
            insights.append(f"{len(leads_novos)} lead(s) aguardando primeiro contato")

        return {"leads_novos": len(leads_novos), "leads_em_contato": len(leads_em_contato),
                "leads_convertidos": len(leads_convertidos),
                "alertas": alertas, "insights": insights}
    except Exception as e:
        logger.error(f"[Analytics] Erro ao analisar leads: {e}")
        return {"erro": str(e)}


# Analises de Estoque

def analisar_estoque(legacy_api) -> dict:
    """Verifica itens em nivel critico ou abaixo do minimo."""
    try:
        estoque = legacy_api.listar_estoque() or []
        criticos = []
        baixos = []

        for item in estoque:
            qtd = int(item.get("quantidade", 0))
            minimo = int(item.get("quantidade_minima", 0))
            nome = item.get("nome", "?")

            if qtd <= 0:
                criticos.append(f"{nome}: SEM ESTOQUE")
            elif qtd < minimo:
                baixos.append(f"{nome}: {qtd} (min {minimo})")

        alertas = []
        if criticos:
            alertas.append("CRITICO -- Sem estoque: " + ", ".join(criticos))
        if baixos:
            alertas.append("Abaixo do minimo: " + ", ".join(baixos))

        return {"total_itens": len(estoque), "criticos": len(criticos),
                "baixos": len(baixos), "alertas": alertas}
    except Exception as e:
        logger.error(f"[Analytics] Erro ao analisar estoque: {e}")
        return {"erro": str(e)}


# Relatorio Consolidado

def gerar_relatorio_proativo(legacy_api) -> str:
    """
    Gera relatorio consolidado com todos os alertas e insights do dia.
    Usado pelo scheduler para enviar analise diaria proativa.
    """
    linhas = [
        f"*Relatorio Proativo -- {_now().strftime('%d/%m/%Y %H:%M')}*",
        "=" * 28,
        "",
    ]

    op = analisar_operacional(legacy_api)
    if not op.get("erro"):
        linhas.append("*Operacional*")
        for a in op.get("alertas", []):
            linhas.append(f"  [!] {a}")
        for i in op.get("insights", []):
            linhas.append(f"  -> {i}")
        linhas.append("")

    est = analisar_estoque(legacy_api)
    if not est.get("erro") and est.get("alertas"):
        linhas.append("*Estoque*")
        for a in est["alertas"]:
            linhas.append(f"  [!] {a}")
        linhas.append("")

    lds = analisar_leads(legacy_api)
    if not lds.get("erro") and (lds.get("alertas") or lds.get("insights")):
        linhas.append("*Comercial*")
        for a in lds.get("alertas", []):
            linhas.append(f"  [!] {a}")
        for i in lds.get("insights", []):
            linhas.append(f"  -> {i}")
        linhas.append("")

    fin = analisar_financeiro(legacy_api)
    if not fin.get("erro"):
        linhas.append("*Financeiro*")
        for a in fin.get("alertas", []):
            linhas.append(f"  [!] {a}")
        for i in fin.get("insights", []):
            linhas.append(f"  -> {i}")
        linhas.append("")

    total_alertas = (
        len(op.get("alertas", []))
        + len(est.get("alertas", []))
        + len(lds.get("alertas", []))
        + len(fin.get("alertas", []))
    )

    if total_alertas == 0:
        linhas.append("_Sem alertas criticos no momento._")

    return "\n".join(linhas)
