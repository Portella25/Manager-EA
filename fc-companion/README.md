# FC Companion — Fases 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 e 14

Companion app para o modo Carreira do EA FC 26 (PC), com extração em tempo real via Live Editor, detecção de eventos em Python, geração de narrativa, feed multicanal, reputação dinâmica, objetivos da diretoria, mercado vivo, agenda editorial, arcos de crise, arcos sazonais de longo prazo, payoff de temporada, legado multi-temporada, Hall da Fama, conquistas permanentes e meta-conquistas em API REST com FastAPI.

## Pré-requisitos

- Windows 10/11
- EA FC 26 (PC)
- FC 26 Live Editor 26.2.8 (xAranaktu)
- Python 3.11+
- Modo Carreira carregado no jogo

## Estrutura do projeto

```text
fc-companion/
├── extractor/
│   └── companion_export.lua
├── backend/
│   ├── save_reader/
│   │   ├── __init__.py
│   │   ├── save_finder.py
│   │   ├── save_parser.py
│   │   └── save_watcher.py
│   ├── merger.py
│   ├── main.py
│   ├── watcher.py
│   ├── diagnose_save.py
│   ├── models.py
│   ├── database.py
│   ├── events.py
│   ├── narrative_engine.py
│   └── requirements.txt
└── README.md
```

## Nova arquitetura híbrida (Fase 1 refatorada)

```text
Live Editor Lua (ponteiros de memória, leve)
        │
        └── state_lua.json
Save file EA FC 26 (SQLite no disco)
        │
        └── save_data.json
state_lua.json + save_data.json
        │
        └── StateMerger (backend/merger.py)
                │
                └── state.json unificado
                        │
                        ├── watcher.py (detecção de eventos)
                        ├── FastAPI (main.py)
                        └── PWA / frontend
```

- O Lua não usa varredura pesada de tabelas DB e exporta somente dados de memória direta para `state_lua.json`.
- O backend lê o save diretamente do disco em modo read-only e gera `save_data.json`.
- O `StateMerger` unifica as duas fontes sem falhar quando uma delas está ausente.

## Instalação

No terminal, dentro da pasta `fc-companion/backend`:

```bash
pip install -r requirements.txt
```

## Como rodar o script Lua no Live Editor

1. Abra o EA FC 26 via Live Editor.
2. Entre no save do modo Carreira de Treinador.
3. Abra o Lua Engine do Live Editor.
4. Cole o conteúdo de `extractor/companion_export.lua`.
5. Execute o script.

Saída esperada:

- O script escreve o estado parcial em `C:\Users\<SEU_USUARIO>\Desktop\fc_companion\state_lua.json`.
- A gravação é atômica: primeiro `state_lua.tmp`, depois rename para `state_lua.json`.
- O console do Live Editor mostra logs de atualização do `state_lua.json`.

## Localização automática do save

O backend procura o save de carreira nesta ordem:

1. `%USERPROFILE%\Documents\FC 26\settings\`
2. `%APPDATA%\EA Sports\FC 26\`
3. `%LOCALAPPDATA%\EA Sports\FC 26\`
4. Subpastas com arquivos `.db` ou `.sav` acima de 1MB

Regras:

- Prioriza arquivos com `"career"` no nome.
- Se não houver, usa o maior `.db` da pasta e desempata por modificação mais recente.
- O `save_watcher.py` monitora mudanças e regenera `save_data.json`.

## Como iniciar o backend

Use dois terminais dentro de `fc-companion/backend`.

### Terminal 1 — API FastAPI

```bash
uvicorn main:app --reload --port 8000
```

### Terminal 2 — Watcher

```bash
python watcher.py
```

## Como validar rapidamente

1. Com jogo + Lua rodando, verifique `state_lua.json`.
2. Inicie `watcher.py` e confirme geração de `save_data.json` e `state.json`.
3. Inicie `uvicorn`.
4. Acesse:

```text
http://localhost:8000/health
```

## Diagnóstico de save (SQLite)

Use o script de diagnóstico para validar as tabelas disponíveis no save:

```bash
cd fc-companion/backend
python diagnose_save.py
```

Ele:

- localiza automaticamente o save de carreira;
- lista as tabelas SQLite encontradas;
- imprime as 3 primeiras linhas de tabelas relevantes.

## Fluxo completo de dados

```text
Lua (memória direta) -> state_lua.json
Save EA FC 26 -> save_data.json
state_lua.json + save_data.json -> merger.py -> state.json
state.json -> watcher.py -> FastAPI -> PWA
```

## Como validar rapidamente (completo)

1. Com jogo + Lua rodando, verifique `state_lua.json`.
2. Inicie `uvicorn`.
3. Inicie `watcher.py`.
4. Confirme `save_data.json` e `state.json` no Desktop `fc_companion`.
5. Acesse:

```text
http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "last_update": "2026-03-24T21:32:10.123456"
}
```

## Endpoints disponíveis

- `GET /state`
- `GET /state/club`
- `GET /state/fixtures?completed=true|false`
- `GET /state/standings`
- `GET /state/squad`
- `GET /events/recent?limit=20`
- `GET /events/type/{event_type}`
- `POST /internal/event`
- `GET /narratives/recent?limit=20`
- `GET /narratives/event/{event_type}`
- `POST /narratives/generate`
- `GET /feed/recent?limit=30&save_uid=<id>&channel=imprensa|presidente|torcida`
- `GET /feed/channel/{channel}?limit=30`
- `GET /companion/overview`
- `GET /profile/coach?save_uid=<id>`
- `GET /torcida/sentimento?save_uid=<id>`
- `POST /press-conference/respond`
- `GET /press-conference/recent?limit=20&save_uid=<id>`
- `GET /board/challenges/active?save_uid=<id>`
- `GET /board/challenges/recent?limit=20&save_uid=<id>`
- `GET /market/rumors/recent?limit=20&save_uid=<id>&trigger_event=<tipo>`
- `POST /market/rumors/generate`
- `GET /timeline/recent?limit=30&save_uid=<id>&phase=<fase>&source_event=<evento>`
- `POST /timeline/generate`
- `GET /crisis/active?save_uid=<id>`
- `GET /crisis/recent?limit=20&save_uid=<id>`
- `POST /crisis/trigger`
- `GET /season-arc/active?save_uid=<id>`
- `GET /season-arc/recent?limit=20&save_uid=<id>`
- `POST /season-arc/trigger`
- `POST /season-arc/memory`
- `GET /season-arc/payoff/recent?limit=10&save_uid=<id>`
- `POST /season-arc/payoff/generate`
- `GET /legacy/profile?save_uid=<id>`
- `POST /legacy/rebuild?save_uid=<id>`
- `GET /hall-of-fame/profile?save_uid=<id>`
- `GET /hall-of-fame/entries?limit=30&save_uid=<id>`
- `POST /hall-of-fame/rebuild?save_uid=<id>`
- `GET /achievements/profile?save_uid=<id>`
- `GET /achievements/recent?limit=30&save_uid=<id>`
- `POST /achievements/rebuild?save_uid=<id>`
- `GET /meta-achievements/profile?save_uid=<id>`
- `GET /meta-achievements/recent?limit=30&save_uid=<id>`
- `POST /meta-achievements/rebuild?save_uid=<id>`
- `GET /health`

## Eventos detectados pelo watcher

- `MATCH_COMPLETED`
- `match_won`
- `match_lost`
- `match_drawn`
- `PLAYER_INJURED`
- `player_injured`
- `PLAYER_RECOVERED`
- `TRANSFER_OFFER_RECEIVED`
- `BUDGET_CHANGED`
- `board_budget_cut`
- `SEASON_CHANGED`
- `MORALE_DROP`
- `DATE_ADVANCED`

Cada evento é:

1. Persistido em SQLite (`events`).
2. Enviado via `POST` para `http://localhost:8000/internal/event`.
3. Logado no console com timestamp.

## Fase 2 — Camada de narrativa

A Fase 2 adiciona geração de conteúdo narrativo para cada evento:

- Tabela `narratives` no SQLite.
- Geração automática ao receber `POST /internal/event`.
- Endpoint para geração manual (`POST /narratives/generate`).
- Leitura por feed (`GET /narratives/recent`) e por tipo (`GET /narratives/event/{event_type}`).

### Modo de geração

Por padrão, o backend usa templates locais (zero dependência de chave externa).

O Motor Híbrido do futebol usa templates para eventos comuns e pode chamar o Gemini 2.0 Flash para eventos de alta severidade.

Configuração local recomendada via `.env` (não versionado):

- Copie `.env.example` para `.env` e preencha:
  - `GEMINI_API_KEY=`

Também é possível usar provedor OpenAI compatível via variáveis de ambiente:

```bash
set FC_COMPANION_AI_PROVIDER=openai
set OPENAI_API_KEY=sua_chave
set OPENAI_MODEL=gpt-4o-mini
set OPENAI_BASE_URL=https://api.openai.com/v1
```

Se a chamada externa falhar, o sistema faz fallback automático para templates locais.

## Documentação

- Regras do Motor Híbrido: [FOOTBALL_ENGINE_MANIFESTO.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/FOOTBALL_ENGINE_MANIFESTO.md)
- Variáveis de ambiente: [docs/ENV.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/docs/ENV.md)
- Gemini (setup e teste ao vivo): [docs/AI_GEMINI.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/docs/AI_GEMINI.md)
- Rodar localmente: [docs/RUN_LOCAL.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/docs/RUN_LOCAL.md)

## Fase 3 — Feed multicanal

A Fase 3 cria cards de conteúdo por canal em cada evento:

- `imprensa` para manchetes e análise editorial.
- `presidente` para tom institucional e cobrança de metas.
- `torcida` para reação social e sentimento da base.

No `POST /internal/event`, o backend:

1. Salva o evento.
2. Gera narrativa principal.
3. Gera um bundle com 3 cards por canal.
4. Persiste tudo em `feed_items`.

Você pode consumir o feed pronto para frontend com:

- `GET /feed/recent`
- `GET /feed/channel/{channel}`
- `GET /companion/overview`

## Fase 4 — Reputação dinâmica e coletiva interativa

A Fase 4 adiciona evolução gerencial contínua por save:

- Perfil do técnico com reputação (0-100), rótulo de reputação e estilo.
- Memória de sentimento da torcida (0-100) com classificação textual.
- Atualização automática desses indicadores sempre que um evento é processado.

Também inclui coletiva de imprensa interativa:

- `POST /press-conference/respond` recebe pergunta e resposta do técnico.
- O backend detecta tom (confiante, neutro, evasivo, agressivo).
- Gera consequências para reputação e moral percebida.
- Persiste histórico no banco para consumo do frontend.

## Fase 5 — Ultimato e objetivos dinâmicos da diretoria

A Fase 5 implementa o sistema de pressão contextual:

- Analisa sequência recente de resultados.
- Dispara ultimato automático quando há desempenho crítico.
- Cria objetivo de recuperação com meta de pontos em jogos restantes.
- Atualiza status do objetivo a cada novo `MATCH_COMPLETED` (active/completed/failed).
- Gera eventos narrativos derivados:
  - `BOARD_ULTIMATUM_CREATED`
  - `BOARD_ULTIMATUM_UPDATED`

Esses eventos entram no mesmo pipeline de narrativa e feed multicanal.

## Fase 6 — Mercado de transferências vivo

A Fase 6 introduz camada de rumores contextuais:

- Geração automática de rumor quando eventos críticos acontecem.
- Rumores com nível de confiança e perfil de alvo de mercado.
- Personalização pelo estilo/reputação do técnico.

Eventos que podem disparar rumor automaticamente:

- `MATCH_COMPLETED`
- `BUDGET_CHANGED`
- `TRANSFER_OFFER_RECEIVED`
- `BOARD_ULTIMATUM_CREATED`
- `BOARD_ULTIMATUM_UPDATED`

## Fase 7 — Agenda editorial automática

A Fase 7 adiciona timeline narrativa para transformar eventos em sequência editorial:

- Geração automática de entradas de timeline em eventos relevantes.
- Fases editoriais como `pre_match`, `post_match`, `fan_reaction`, `board_note`, `calendar`.
- Priorização por importância para facilitar ranking e destaque no frontend.
- Geração manual disponível para testes e curadoria de conteúdo.

## Fase 8 — Simulação de crise e recuperação

A Fase 8 adiciona arco narrativo de 3-5 passos com estado persistente:

- Início automático de crise em cenários de pressão (diretoria/desempenho/sentimento).
- Progressão por etapas conforme novos eventos chegam.
- Resolução por recuperação de indicadores ou colapso quando a reação falha.
- Emissão de eventos derivados:
  - `CRISIS_STARTED`
  - `CRISIS_UPDATED`

## Fase 9 — Arcos narrativos de temporada

A Fase 9 adiciona memória de longo prazo por temporada:

- Criação automática ou manual de arco sazonal.
- Marcos progressivos (milestones) com desfecho `resolved` ou `failed`.
- Memória persistida de decisões e acontecimentos relevantes.
- Eventos derivados:
  - `SEASON_ARC_STARTED`
  - `SEASON_ARC_UPDATED`

## Fase 10 — Payoff de fim de temporada

A Fase 10 fecha o ciclo narrativo com epílogo final:

- Cálculo de score final baseado em reputação, torcida, marcos e memória acumulada.
- Classificação por nota (`A+` até `E`) e texto de epílogo.
- Geração automática quando o arco sazonal termina.
- Geração manual para testes e ajustes editoriais.
- Evento derivado:
  - `SEASON_ARC_PAYOFF`

## Fase 11 — Legado multi-temporada

A Fase 11 consolida o histórico do técnico em visão de carreira longa:

- Agregação de payoffs de várias temporadas.
- Cálculo de ranking histórico de legado.
- Resumo narrativo consolidado da trajetória.
- Evento derivado:
  - `LEGACY_UPDATED`

## Fase 12 — Hall da Fama da carreira

A Fase 12 consolida marcos emblemáticos em uma camada histórica:

- Entradas do Hall da Fama geradas a partir de payoffs sazonais.
- Perfil agregado com tier histórico (aspirante → imortal).
- Rebuild manual para recalcular o acervo em saves antigos.
- Evento derivado:
  - `HOF_UPDATED`

## Fase 13 — Conquistas icônicas permanentes

A Fase 13 adiciona sistema de conquistas de carreira:

- Desbloqueio automático baseado em payoff sazonal, legado e Hall da Fama.
- Perfil de conquistas com nível de carreira e pontuação acumulada.
- Rebuild manual para recalcular conquistas em saves antigos.
- Eventos derivados:
  - `ACHIEVEMENT_UNLOCKED`
  - `ACHIEVEMENTS_UPDATED`

## Fase 14 — Meta-conquistas e coleções

A Fase 14 adiciona conquistas de coleção e títulos compostos:

- Desbloqueio por combinação de conquistas já obtidas.
- Perfil de meta-conquistas com progresso por coleção.
- Prestígio de coleção (bronze → platinum).
- Eventos derivados:
  - `META_ACHIEVEMENT_UNLOCKED`
  - `META_ACHIEVEMENTS_UPDATED`

## Banco de dados

Arquivo SQLite criado automaticamente em:

```text
fc-companion/backend/fc_companion.db
```

Tabelas:

- `events`
- `game_snapshots`
- `narratives`
- `feed_items`
- `coach_profile_state`
- `press_conferences`
- `board_challenges`
- `market_rumors`
- `editorial_timeline`
- `crisis_arcs`
- `season_arcs`
- `season_payoffs`
- `legacy_profiles`
- `hall_of_fame_entries`
- `hall_of_fame_profiles`
- `career_achievements`
- `achievement_profiles`
- `meta_achievements`
- `meta_achievement_profiles`

## Exemplo real de state.json

```json
{
  "status": "ok",
  "is_career_mode": true,
  "save_uid": "577fb2770ca5495ca67d812ebb67690",
  "system_time": "2026-03-23 18:46:14",
  "game_date": null,
  "date_source": "not_exposed_in_v26.2.8",
  "team": {
    "id": 111592,
    "name": "Passes Livres"
  },
  "transfer_budget": 38869562,
  "top_players": [
    {
      "id": 246067,
      "name": "Henry Vaca",
      "morale": null
    },
    {
      "id": 180561,
      "name": "Hassan Al Haydos",
      "morale": null
    },
    {
      "id": 246406,
      "name": "Xavier Arreaga",
      "morale": null
    }
  ]
}
```

Observação: a Fase 1 atual já suporta o formato completo definido no `companion_export.lua`; o exemplo acima é um snapshot real inicial usado na validação do pipeline.
