# Legacy Moving Agent v5.2

**Assessor operacional via WhatsApp com IA — Legacy Moving**
Contato: legacymovingbr@gmail.com

---

## O que é

Agente de WhatsApp com IA (Claude/Anthropic) integrado ao ERP Legacy Moving.
Funciona como assessor operacional interno: recebe mensagens dos funcionários,
consulta o sistema, registra informações e responde com inteligência.

> **Não atende clientes.** Apenas a equipe interna da Legacy Moving.

---

## Funcionalidades

### ✅ Fase 1 — Estrutura base
- Webhook WhatsApp via Evolution API
- Integração com Claude (Anthropic) com tool use
- Sistema de perfis por número de telefone (admin, supervisor, motorista, operacional, comercial, financeiro)
- Histórico de conversa por usuário
- Consulta de OS e leads no ERP

### ✅ Fase 2 — Notificações automáticas + Google Agenda
- Resumo diário automático às 7h para admin/supervisor
- Lembretes de OS 24h antes para a equipe
- Alertas de estoque mínimo e tarefas vencidas
- Criação de eventos no Google Calendar

### ✅ Fase 3 — Drive inteligente + Análises proativas
- Upload de arquivos no Google Drive, organizado por categoria/OS
- Análises financeiras, operacionais e de leads com insights automáticos
- Relatório proativo semanal

### ✅ Fase 4 — Multi-usuário com contexto individual
- Preferências por usuário (alertas, modo verboso, idioma)
- Histórico de ações individuais
- Estado de conversa persistente (OS em foco, cliente em foco)

### ✅ Fase 5 — Sistema de Avarias
- Funcionário envia foto via WhatsApp → agente detecta automaticamente
- Foto baixada da Evolution API e salva no Google Drive (pasta do cliente/OS)
- Registro da avaria no ERP como observação interna da OS
- Documentação 100% interna — nunca compartilhada com o cliente
- Relatório de avarias por OS

### ✅ Handler de Áudio
- Mensagens de voz transcritas automaticamente via OpenAI Whisper
- Processadas como texto pelo agente

---

## Arquitetura

```
legacy-moving-agent/
├── agent/
│   ├── core.py          # Núcleo: orquestra Claude + ferramentas + perfis
│   ├── tools.py         # Definição e execução das ferramentas do agente
│   ├── prompts.py       # System prompt personalizado por perfil
│   ├── profiles.py      # Perfis de acesso por número de WhatsApp
│   ├── memory.py        # Histórico de conversa (SQLite + fallback /tmp)
│   ├── user_context.py  # Contexto individual e preferências
│   ├── notifications.py # Templates e roteamento de notificações
│   ├── analytics.py     # Análises proativas e insights
│   └── vision.py        # Análise de imagens via Claude Vision
├── integrations/
│   ├── evolution.py         # Cliente Evolution API (WhatsApp)
│   ├── legacy_api.py        # Cliente ERP Legacy Moving
│   ├── google_calendar.py   # Google Calendar via Service Account
│   ├── google_drive.py      # Google Drive via Service Account
│   └── damage_registry.py   # Registro de avarias (foto + Drive + ERP)
├── webhooks/
│   ├── whatsapp.py      # Webhook Evolution API (msgs de texto, imagem, áudio)
│   └── admin.py         # API REST de administração (protegida por token)
├── utils/
│   ├── database.py      # SQLite/PostgreSQL via SQLAlchemy
│   ├── scheduler.py     # APScheduler (resumo diário, lembretes)
│   ├── audio.py         # Transcrição Whisper
│   ├── formatter.py     # Formatação de mensagens WhatsApp
│   └── logger.py        # Logger estruturado
├── tests/
│   └── test_damage_registry.py  # Testes do sistema de avarias
├── main.py              # Ponto de entrada Flask v5.2
├── Procfile             # gunicorn para Railway
├── requirements.txt     # Dependências
├── .env.example         # Variáveis de ambiente documentadas
└── DEPLOY.md            # Guia de deploy passo a passo
```

---

## Tecnologias

- **IA:** Claude (Anthropic) — Sonnet para conversação, Haiku para visão
- **WhatsApp:** Evolution API (open-source)
- **Backend:** Flask + Gunicorn
- **Banco de dados:** SQLite (local) / PostgreSQL (produção)
- **Google:** Calendar API + Drive API via Service Account
- **Áudio:** OpenAI Whisper
- **Deploy:** Railway
- **Testes:** pytest

---

## Segurança

- `AGENT_SECRET` protege todas as rotas `/admin/*`
- `WEBHOOK_SECRET` valida que eventos vêm da Evolution API (anti-injection)
- Rate limiting: máx 10 mensagens/min por usuário
- Comparação de tokens via `hmac.compare_digest` (anti timing-attack)
- Repositório privado — credenciais nunca no código

---

## Deploy rápido

Veja o **[DEPLOY.md](./DEPLOY.md)** para o guia completo passo a passo.

```bash
# Saúde da aplicação
curl https://sua-url.railway.app/status

# Cadastrar primeiro admin
curl -X POST https://sua-url.railway.app/admin/usuarios \
  -H "X-Admin-Token: SEU_AGENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"phone":"5511999998888","nome":"Weverton","role":"admin"}'
```

---

## Versão

**v5.2** — 73+ commits | Todas as 5 fases implementadas e testadas
legacymovingbr@gmail.com
