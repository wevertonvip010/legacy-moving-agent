# Legacy Moving Agent

Agente WhatsApp com IA (Claude/Anthropic) integrado ao ERP Legacy Moving.
Funciona como assessor operacional completo via WhatsApp.

## Funcionalidades

- Controle operacional: consultar/criar OS, verificar mudancas, registrar avarias
- Financeiro: registrar despesas/receitas por audio ou texto, consultar resumo
- Agenda: programacao do dia, disponibilidade de equipe, sync Google Agenda
- Leads e Clientes: criar lead por mensagem, converter, consultar historico
- Estoque: consultar nivel, alertas de estoque baixo/critico
- Equipe: disponibilidade, alocacao em OS, ranking gamificacao
- Notificacoes: confirmacao de mudanca, alertas de avaria, lembretes
- Drive: salvar e buscar arquivos por descricao

## Stack

- Python 3.11 + Flask
- Anthropic Claude 3.5 Sonnet (tool use)
- Evolution API (WhatsApp self-hosted)
- SQLite (historico de conversas)
- Deploy: Railway

## Roadmap

- [x] Fase 1 - Estrutura base + ferramentas principais
- [ ] Fase 2 - Notificacoes automaticas + Google Agenda
- [ ] Fase 3 - Drive inteligente + Analises proativas
- [ ] Fase 4 - Multi-usuario com contexto individual
