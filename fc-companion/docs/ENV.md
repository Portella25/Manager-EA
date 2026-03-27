# Variáveis de Ambiente e `.env`

O backend lê configurações via variáveis de ambiente. Em desenvolvimento local, você pode usar um arquivo `.env` na pasta `fc-companion/` (o backend carrega automaticamente via `python-dotenv`).

## Como usar

1. Copie o template:

   - Copie [.env.example](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/.env.example) para `fc-companion/.env`

2. Preencha apenas o que você precisa no seu ambiente local.

## Variáveis suportadas

- `FC_COMPANION_AI_PROVIDER`
  - `template` (padrão): usa templates locais.
  - `openai`: usa provedor OpenAI compatível (ex.: OpenAI / gateways compatíveis).
  - Observação: o Motor Híbrido usa templates/LLM conforme severidade para eventos do futebol.

- `OPENAI_API_KEY`
  - Obrigatória apenas se `FC_COMPANION_AI_PROVIDER=openai`.

- `OPENAI_MODEL`
  - Ex.: `gpt-4o-mini`.

- `OPENAI_BASE_URL`
  - Ex.: `https://api.openai.com/v1`.

- `GEMINI_API_KEY`
  - Obrigatória apenas para habilitar chamadas reais ao Gemini quando o Motor Híbrido decidir usar LLM (eventos com severidade alta).

- `GEMINI_MIN_INTERVAL_SECONDS`
  - Intervalo mínimo entre chamadas reais à API (padrão: `20`).

- `GEMINI_COOLDOWN_SECONDS`
  - Tempo de cooldown local após erro de quota 429 (padrão: `120`).

- `GEMINI_MAX_CALLS_PER_PROCESS`
  - Limite de chamadas reais por processo do backend (padrão: `5`).

- `GEMINI_STRICT_LIVE_TEST`
  - Se `1`, o teste live exige resposta real da API (sem fallback).

## Regras de segurança

- Nunca commite `.env` no repositório.
- Use `.env.example` como referência (sem segredos).
