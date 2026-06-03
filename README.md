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
- Drive: salvar e buscar arquivos por descricao (Google Drive)
- Analytics Proativos: insights automaticos de financeiro, operacional, leads
- Multi-usuario: contexto individual, preferencias e historico por usuario

## Stack

- Python 3.11 + Flask
- Anthropic Claude 3.5 Sonnet (tool use)
- Evolution API (WhatsApp self-hosted)
- SQLite (historico de conversas)
- Google Calendar API (sincronizacao de agenda)
- Google Drive API (armazenamento inteligente de arquivos)
- APScheduler (jobs automaticos)
- Deploy: Railway

## Arquitetura

```
agent/
  core.py          — Orquestrador principal (Claude + tools + memoria + perfis)
  tools.py         — Todas as ferramentas (Fases 1-4)
  prompts.py       — System prompts personalizados por role
  profiles.py      — Perfis de usuario por numero WhatsApp
  memory.py        — Historico de conversas por usuario
  notifications.py — Templates e motor de notificacoes
  vision.py        — Analise de imagens (comprovantes, avarias)
  analytics.py     — Analises proativas e insights (Fase 3)
  user_context.py  — Contexto individual por usuario (Fase 4)

integrations/
  evolution.py        — Evolution API (WhatsApp)
  google_calendar.py  — Google Calendar API
  google_drive.py     — Google Drive API (Fase 3)
  legacy_api.py       — ERP Legacy Moving

utils/
  scheduler.py   — Jobs automaticos (resumo diario, lembretes, analytics)
  audio.py       — Transcricao de audio (Whisper)
  formatter.py   — Formatacao de mensagens WhatsApp
  logger.py      — Logger estruturado
```

## Roadmap

- [x] Fase 1 - Estrutura base + ferramentas principais
- [x] Fase 2 - Notificacoes automaticas + Google Agenda
- [x] Fase 3 - Drive inteligente + Analises proativas
- [x] Fase 4 - Multi-usuario com contexto individual

## Variaveis de Ambiente

Copie `.env.example` para `.env` e preencha:

| Variavel | Descricao | Obrigatoria |
|---|---|---|
| ANTHROPIC_API_KEY | Chave API Anthropic | Sim |
| LEGACY_API_URL | URL do ERP Legacy Moving | Sim |
| LEGACY_JWT_TOKEN | Token JWT admin do ERP | Sim |
| EVOLUTION_API_URL | URL Evolution API | Sim (producao) |
| EVOLUTION_API_KEY | Chave Evolution API | Sim (producao) |
| EVOLUTION_INSTANCE | Nome da instancia WA | Sim (producao) |
| OPENAI_API_KEY | Chave OpenAI (Whisper) | Opcional |
| GOOGLE_CALENDAR_ID | ID do Google Calendar | Opcional |
| GOOGLE_CREDENTIALS_JSON | Credenciais Service Account | Opcional |
| DRIVE_ROOT_FOLDER_ID | Pasta raiz no Drive | Opcional |
| USER_CONTEXT_FILE | Arquivo de contexto usuarios | Opcional |

## Deploy no Railway

Ver guia completo em `DEPLOY.md`.

---
v4.0.0 — Todas as fases implementadas
