# DEPLOY — Legacy Moving Agent v5.2
**Contato:** legacymovingbr@gmail.com

---

## PRÉ-REQUISITOS

Antes de começar, tenha em mãos:
- Conta no [Railway](https://railway.app) (deploy)
- Conta Google com acesso ao Gmail `legacymovingbr@gmail.com`
- Evolution API rodando (pode ser no Railway também)
- Chave da API Anthropic: https://console.anthropic.com
- Chave da API OpenAI (opcional, para áudio): https://platform.openai.com

---

## PASSO 1 — Google Cloud: Service Account

> Uma Service Account é uma conta técnica que o agente usa para acessar Calendar e Drive sem expor sua senha.

1. Acesse https://console.cloud.google.com
2. Crie um projeto (ex: `legacy-moving-agent`)
3. Menu lateral → **APIs e Serviços** → **Ativar APIs**
   - Ativar `Google Calendar API`
   - Ativar `Google Drive API`
4. Menu lateral → **IAM e Admin** → **Contas de serviço**
5. Clicar em **Criar conta de serviço**
   - Nome: `legacy-moving-agent`
   - Clicar em **Concluído**
6. Clicar na conta criada → aba **Chaves** → **Adicionar chave** → **JSON**
7. Salvar o arquivo `.json` baixado — você vai precisar do conteúdo completo

### 1a. Compartilhar o Google Calendar

1. Abrir Google Calendar com `legacymovingbr@gmail.com`
2. Engrenagem → **Configurações** → clicar no calendário principal
3. Seção **Compartilhar com pessoas específicas**
4. Adicionar o e-mail da Service Account (termina em `@...iam.gserviceaccount.com`)
5. Permissão: **Fazer alterações em eventos**
6. Copiar o **ID do calendário** (em Integrar calendário): geralmente `legacymovingbr@gmail.com`

### 1b. Compartilhar o Google Drive

1. Abrir Google Drive com `legacymovingbr@gmail.com`
2. Criar uma pasta chamada `Legacy Moving Agent`
3. Clicar com botão direito → **Compartilhar**
4. Adicionar o e-mail da Service Account → permissão **Editor**
5. Copiar o **ID da pasta** (última parte da URL do Drive):
   `https://drive.google.com/drive/folders/[ID-AQUI]`

---

## PASSO 2 — Deploy no Railway

1. Acesse https://railway.app → **New Project** → **Deploy from GitHub repo**
2. Selecione o repositório `wevertonvip010/legacy-moving-agent`
3. Railway detecta o `Procfile` automaticamente
4. Vá em **Variables** e adicione **todas** as variáveis abaixo:

### Variáveis obrigatórias

```
# Empresa
COMPANY_NAME=Legacy Moving
COMPANY_EMAIL=legacymovingbr@gmail.com
COMPANY_WHATSAPP=5511999999999
COMPANY_TAGLINE=Legacy Moving — Cuidando do que é seu

# Anthropic (IA principal)
ANTHROPIC_API_KEY=sk-ant-api03-...    ← sua chave

# ERP Legacy Moving
LEGACY_API_URL=https://seu-erp.railway.app
LEGACY_JWT_TOKEN=eyJhbGci...          ← token JWT admin do ERP

# Evolution API (WhatsApp)
EVOLUTION_API_URL=https://sua-evolution.railway.app
EVOLUTION_API_KEY=sua-chave-evolution
EVOLUTION_INSTANCE=legacy-moving

# Segurança — OBRIGATÓRIO configurar antes de usar
AGENT_SECRET=gere-uma-senha-forte-aqui    ← para proteger rotas /admin/*
WEBHOOK_SECRET=outro-token-aleatorio-aqui ← configure igual na Evolution API

# Google Calendar
GOOGLE_CALENDAR_ID=legacymovingbr@gmail.com
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}  ← JSON completo em UMA linha
CALENDAR_TIMEZONE=America/Sao_Paulo

# Google Drive
DRIVE_ROOT_FOLDER_ID=1AbcDeFgHiJkLmNoP  ← ID da pasta "Legacy Moving Agent"

# Banco de dados (SQLite padrão, suficiente para início)
DATABASE_URL=sqlite:///agent_data.db

# Modelos de IA
CLAUDE_MODEL=claude-sonnet-4-5
VISION_MODEL=claude-haiku-4-5
```

### Variáveis opcionais

```
# Áudio (Whisper) — necessário para mensagens de voz
OPENAI_API_KEY=sk-...    ← sua chave OpenAI

# Scheduler
RESUMO_HORA=7
RESUMO_MINUTO=0
LEMBRETE_HORAS=24

# Rate limiting
RATE_MAX_CALLS=10
RATE_WINDOW_SEC=60

# Logs
LOG_LEVEL=INFO
PORT=5001
```

---

## PASSO 3 — Configurar webhook na Evolution API

Após o Railway gerar a URL do seu app (ex: `https://legacy-moving-agent-xxx.railway.app`):

1. Acesse o painel da Evolution API
2. Selecione a instância `legacy-moving`
3. Configure o webhook:
   - **URL:** `https://sua-url.railway.app/webhook/messages-upsert`
   - **Header:** `x-webhook-secret: [valor do WEBHOOK_SECRET]`
   - **Eventos:** `MESSAGES_UPSERT`, `MESSAGES_UPDATE`, `CONNECTION_UPDATE`
4. Salvar e testar a conexão

---

## PASSO 4 — Cadastrar o primeiro admin

Com o app rodando, cadastre seu número como administrador:

```bash
curl -X POST https://sua-url.railway.app/admin/usuarios \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: [valor do AGENT_SECRET]" \
  -d '{"phone":"5511999998888","nome":"Weverton","role":"admin"}'
```

> Substitua o telefone pelo seu número com DDI+DDD (sem +, sem espaço).

---

## PASSO 5 — Cadastrar a equipe

Use o mesmo endpoint para cada funcionário:

```bash
# Cadastrar motorista
curl -X POST https://sua-url.railway.app/admin/usuarios \
  -H "X-Admin-Token: [AGENT_SECRET]" \
  -H "Content-Type: application/json" \
  -d '{"phone":"5511888887777","nome":"Diego","role":"operacional"}'

# Roles disponíveis:
# admin | supervisor | motorista | operacional | comercial | financeiro
```

---

## PASSO 6 — Verificar se está funcionando

### Health check
```bash
curl https://sua-url.railway.app/status
# Deve retornar: {"status":"ok","version":"5.2.0","integrations":{...}}
```

### Teste de mensagem
1. Envie uma mensagem de WhatsApp para o número conectado na Evolution
2. Espere a resposta do agente
3. Verifique os logs no Railway (aba **Deployments** → **View Logs**)

### Teste de avaria
1. Envie uma foto com legenda: `"sofá arranhado OS 042"`
2. O agente deve responder confirmando o registro
3. Verifique se a foto apareceu no Google Drive → pasta Avarias

---

## SOLUÇÃO DE PROBLEMAS

| Sintoma | Causa provável | Solução |
|---|---|---|
| App não sobe | `ANTHROPIC_API_KEY` errada | Verificar chave no Railway |
| Webhook retorna 401 | `WEBHOOK_SECRET` diferente | Igualar na Evolution e Railway |
| Rotas /admin retornam 401 | `AGENT_SECRET` não configurado | Adicionar no Railway |
| Fotos não vão pro Drive | `GOOGLE_CREDENTIALS_JSON` inválido | Verificar JSON em uma linha |
| Calendar não cria eventos | SA não compartilhada no Calendar | Repetir passo 1a |
| Áudio não transcrito | `OPENAI_API_KEY` ausente | Adicionar chave ou ignorar |
| ERP indisponível | `LEGACY_API_URL` ou token errados | Verificar URL e token JWT |

---

## ATUALIZAR O SISTEMA

```bash
# Fazer push para main — Railway redeploya automaticamente
git push origin main
```

O banco SQLite é preservado entre deploys. Os dados de usuários e histórico não são perdidos.

---

## SEGURANÇA — CHECKLIST ANTES DE PRODUÇÃO

- [ ] `AGENT_SECRET` configurado com senha forte (mín. 32 caracteres)
- [ ] `WEBHOOK_SECRET` configurado e igual na Evolution API
- [ ] `ANTHROPIC_API_KEY` e `LEGACY_JWT_TOKEN` armazenados só no Railway (nunca no código)
- [ ] `GOOGLE_CREDENTIALS_JSON` armazenado só no Railway
- [ ] Repositório GitHub configurado como **Private**
- [ ] URL do Railway não compartilhada publicamente
- [ ] Arquivo `.env` local no `.gitignore`
