# 🚀 Guia de Deploy — Legacy Moving Agent

Guia completo para colocar o agente em produção no Railway.

---

## 📋 Pré-requisitos

- [ ] Conta no [Railway](https://railway.app)
- [ ] Conta no [GitHub](https://github.com) com o repositório `legacy-moving-agent`
- [ ] Chave de API da [Anthropic](https://console.anthropic.com) (Claude)
- [ ] JWT Token do sistema Legacy Moving (gerado no backend)
- [ ] Chip de celular para WhatsApp (número dedicado)

---

## Parte 1 — Deploy da Evolution API

A Evolution API é o gateway que conecta seu servidor ao WhatsApp.

### 1.1 Criar serviço no Railway

1. Acesse [railway.app](https://railway.app) e faça login
2. Clique em **New Project** → **Deploy from Docker Image**
3. Cole a imagem: `atendai/evolution-api:latest`
4. Clique em **Deploy**

### 1.2 Configurar variáveis de ambiente da Evolution API

No painel do serviço, vá em **Variables** e adicione:

| Variável | Valor |
|---|---|
| `AUTHENTICATION_TYPE` | `apikey` |
| `AUTHENTICATION_API_KEY` | Crie uma chave forte (ex: `legacy-evo-2024-xkj`) |
| `DATABASE_ENABLED` | `true` |
| `DATABASE_PROVIDER` | `postgresql` |
| `DATABASE_CONNECTION_URI` | URI do Postgres (veja 1.3) |
| `QRCODE_LIMIT` | `30` |
| `DEL_INSTANCE` | `false` |
| `PORT` | `8080` |

### 1.3 Adicionar banco de dados PostgreSQL

1. No mesmo projeto, clique em **+ New** → **Database** → **PostgreSQL**
2. Aguarde criação do banco
3. Copie a `DATABASE_URL` e cole como `DATABASE_CONNECTION_URI` na Evolution API

### 1.4 Gerar domínio público para a Evolution API

1. No serviço Evolution API, vá em **Settings** → **Networking**
2. Clique em **Generate Domain**
3. Anote a URL gerada, ex: `https://evolution-api-production-xxxx.up.railway.app`

### 1.5 Criar a instância WhatsApp

Após o deploy (aguarde ~2 minutos), acesse via curl ou Insomnia:

```bash
curl -X POST https://SEU-DOMINIO-EVOLUTION/instance/create \
  -H "apikey: SUA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"instanceName": "legacy-moving", "qrcode": true}'
```

### 1.6 Conectar o WhatsApp (QR Code)

```bash
curl https://SEU-DOMINIO-EVOLUTION/instance/connect/legacy-moving \
  -H "apikey: SUA_API_KEY"
```

A resposta retorna um QR Code em base64. Decodifique e escaneie com o celular dedicado.

> ⚠️ **Use um chip exclusivo para o agente.** Nunca use seu WhatsApp pessoal.

---

## Parte 2 — Deploy do Agente (este repositório)

### 2.1 Criar serviço no Railway

1. No mesmo projeto Railway, clique em **+ New** → **GitHub Repo**
2. Selecione `wevertonvip010/legacy-moving-agent`
3. Railway detectará o `Procfile` e fará o build automaticamente

### 2.2 Configurar variáveis de ambiente do agente

No serviço do agente, vá em **Variables** e adicione:

| Variável | Valor | Obrigatório |
|---|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-... | ✅ |
| `LEGACY_API_URL` | URL do backend Legacy Moving | ✅ |
| `LEGACY_JWT_TOKEN` | Token JWT do sistema | ✅ |
| `EVOLUTION_API_URL` | URL da Evolution API (Parte 1) | ✅ |
| `EVOLUTION_API_KEY` | Chave criada na Parte 1 | ✅ |
| `EVOLUTION_INSTANCE` | `legacy-moving` | ✅ |
| `AGENT_SECRET` | Senha para validar webhooks (crie uma forte) | ✅ |
| `LOG_LEVEL` | `INFO` | ⬜ |
| `LOG_FORMAT` | `json` (recomendado para Railway) | ⬜ |

### 2.3 Gerar domínio público para o agente

1. No serviço do agente, vá em **Settings** → **Networking**
2. Clique em **Generate Domain**
3. Anote a URL, ex: `https://legacy-moving-agent-production.up.railway.app`

### 2.4 Configurar Webhook da Evolution API

Agora que o agente tem uma URL pública, configure o webhook:

```bash
curl -X POST https://SEU-DOMINIO-EVOLUTION/webhook/set/legacy-moving \
  -H "apikey: SUA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://SEU-DOMINIO-AGENTE/webhook/whatsapp",
    "webhook_by_events": false,
    "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
  }'
```

---

## Parte 3 — Primeiro Teste

### 3.1 Verificar saúde do agente

```bash
curl https://SEU-DOMINIO-AGENTE/health
```

Resposta esperada:
```json
{"status": "ok", "agent": "Legacy Moving Agent", "version": "1.0.0"}
```

### 3.2 Verificar conexão com WhatsApp

```bash
curl https://SEU-DOMINIO-EVOLUTION/instance/connectionState/legacy-moving \
  -H "apikey: SUA_API_KEY"
```

Resposta esperada:
```json
{"instance": {"instanceName": "legacy-moving", "state": "open"}}
```

### 3.3 Teste de mensagem

1. Cadastre seu número como admin primeiro. Via API diretamente no banco de dados ou editando `agent/profiles.py` temporariamente
2. Envie uma mensagem para o número do chip pelo WhatsApp
3. O agente deve responder!

---

## Parte 4 — Administração

### Cadastrar primeiro usuário (admin)

Após o deploy, acesse o banco de dados do agente pelo Railway e insira:

```sql
INSERT INTO user_profiles (phone_number, name, role, active, created_at)
VALUES ('5511999999999', 'Seu Nome', 'admin', true, NOW());
```

Ou via API administrativa (endpoint protegido):

```bash
curl -X POST https://SEU-DOMINIO-AGENTE/admin/users \
  -H "Authorization: Bearer SEU_AGENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"phone": "5511999999999", "name": "Seu Nome", "role": "admin"}'
```

### Comandos via WhatsApp (apenas admin)

Após estar cadastrado como admin, pelo próprio WhatsApp:

- `cadastrar 5511988888888 Diego motorista` — cadastra novo usuário
- `listar usuários` — vê todos os usuários
- `remover 5511988888888` — remove usuário

---

## Parte 5 — Monitoramento

### Logs no Railway

No painel do Railway, clique no serviço → **Logs** para ver os logs em tempo real.

Filtros úteis:
- `[MSG_IN]` — mensagens recebidas
- `[MSG_OUT]` — mensagens enviadas  
- `[TOOL]` — ferramentas chamadas
- `[ERROR]` — erros

### Redeploy automático

O Railway redeploya automaticamente quando você faz push para o branch `main`.

---

## 🆘 Solução de Problemas

| Problema | Causa | Solução |
|---|---|---|
| QR Code não aparece | Instance não criada | Verifique se a Evolution API está rodando e crie a instância |
| WhatsApp desconecta | Sessão expirou | Reconecte via `/instance/connect/legacy-moving` |
| Agente não responde | Webhook não configurado | Verifique a URL do webhook na Evolution API |
| Erro 401 | JWT Token expirado | Gere um novo token no sistema Legacy Moving |
| Timeout no Claude | Contexto muito longo | Reduza o histórico em `agent/memory.py` |

---

## 📦 Estrutura de Custos Estimada (Railway)

| Serviço | Plano | Custo Estimado |
|---|---|---|
| Evolution API | Hobby | ~$5/mês |
| PostgreSQL | Hobby | ~$5/mês |
| Agente (este repo) | Hobby | ~$5/mês |
| **Total** | | **~$15/mês** |

> Os custos da API Anthropic (Claude) são separados e variam conforme o uso.
> Estimativa: ~$10-30/mês para uso moderado com time de 10 pessoas.

---

*Dúvidas? Abra uma issue no repositório.*
