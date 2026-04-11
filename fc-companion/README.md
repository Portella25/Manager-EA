# FC Companion

> Companion de mesa para o **Modo Carreira do EA FC 26 (PC)**.  
> Lê o teu save e o estado em memória via Live Editor, detecta eventos em tempo real e alimenta uma **API REST + PWA** com narrativa, jornal esportivo, diretoria, mercado, conquistas e muito mais.

> ⚠️ Projeto independente. Não é afiliado à Electronic Arts nem ao EA FC.

---

## O que é?

O FC Companion transforma os dados do teu Modo Carreira numa **experiência paralela ao jogo**: um painel web que acompanha cada resultado, lesão, transferência e marco da tua temporada — com narrativa gerada por IA, jornal esportivo, coletivas de imprensa, diretoria reagindo às tuas decisões e muito mais.

Funciona **100% local** no teu PC. Nenhum dado sai da tua máquina sem a tua permissão.

---

## Funcionalidades

- 📰 **Jornal esportivo** — feed diário com notícias geradas a partir dos eventos da tua carreira
- 🏆 **Sala de troféus** — histórico de conquistas com destaque narrativo por temporada
- 🧑‍💼 **Perfil do treinador** — biografia, reputação e evolução ao longo da carreira
- 🎙️ **Coletivas de imprensa** — contexto pré e pós-jogo com dados reais do save
- 💬 **Negociações** — diálogos com jogadores (contratos, crises, conselhos)
- 📊 **Dashboard da temporada** — classificação, finanças, plantel e moral
- 🧬 **Arcos narrativos** — crises, momentos de virada e epílogos de temporada
- 🏅 **Conquistas e Hall da Fama** — desbloqueadas por marcos reais da carreira

---

## Como funciona

```
EA FC 26 (save em disco)
        │
        ▼
  save_data.json ──┐
                   ├──► merger.py ──► state.json ──► watcher.py ──► FastAPI ──► React PWA
  state_lua.json ──┘
  (Live Editor)
```

1. O **script Lua** (Live Editor) exporta dados de memória do jogo a cada 5 segundos.
2. O **leitor de save** (Python) complementa com dados do ficheiro `.db` do jogo.
3. O **merger** unifica tudo num `state.json` estável.
4. O **watcher** detecta mudanças, gera eventos e envia para a API.
5. A **API (FastAPI)** processa eventos com motores de narrativa, reputação, mercado, etc.
6. O **frontend (React PWA)** exibe tudo num painel acessível também no telemóvel.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Extrator | Lua (FC 26 Live Editor) |
| Backend | Python 3.11+, FastAPI, SQLite, Watchdog |
| Frontend | React + TypeScript + Tailwind CSS + Vite (PWA) |
| IA | Gemini 2.0 Flash / Ollama (local) / OpenAI-compatible |

---

## Requisitos

- Windows 10/11
- EA FC 26 (PC) com save de Modo Carreira
- [FC 26 Live Editor](https://github.com/xAranaktu/FC-26-Live-Editor) com Lua Engine ativo
- Python 3.11 ou 3.12
- Node.js 18+

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/fc-companion.git
cd fc-companion
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
npm run build
```

---

## Como usar

### Passo 1 — Live Editor (Lua)

1. Abre o EA FC 26 e carrega a tua carreira.
2. No Live Editor, abre o **Lua Engine**.
3. Cola o conteúdo de `extractor/companion_export.lua` e executa.

O script vai criar a pasta `%USERPROFILE%\Desktop\fc_companion\` com o ficheiro `state_lua.json`.

### Passo 2 — API

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

Acessa a documentação em: [http://localhost:8000/docs](http://localhost:8000/docs)

### Passo 3 — Watcher

Num segundo terminal:

```bash
cd backend
python watcher.py
```

### Passo 4 — Frontend (desenvolvimento)

```bash
cd frontend
npm run dev
```

Ou acessa diretamente via `http://localhost:8000` se já tiveres feito o build.

---

## Estrutura do projeto

```
fc-companion/
├── .env.example                  # Modelo de variáveis (raiz; ver também backend/.env)
├── .gitignore
├── FOOTBALL_ENGINE_MANIFESTO.md  # Notas de desenho do “motor” futebolístico
├── README.md
│
├── docs/                         # Documentação técnica e contratos
│   ├── AI_GEMINI.md
│   ├── CAREER_PREMIUM_FRONT_BLUEPRINT.md
│   ├── CM_FEED_ARCHITECTURE.md
│   ├── ENV.md
│   ├── LIVE_EDITOR_DATA_CONTRACT.md
│   └── RUN_LOCAL.md
│
├── extractor/                    # Scripts Lua (Live Editor)
│   ├── companion_export.lua      # Export principal → state_lua.json
│   └── explore_cm_feed_managers.lua
│
├── backend/
│   ├── main.py                   # FastAPI: rotas, SPA, uploads
│   ├── watcher.py                # Watchdog + merge + eventos → API
│   ├── merger.py                 # StateMerger → state.json
│   ├── events.py                 # EventDetector (diff de estado)
│   ├── database.py               # SQLAlchemy / SQLite
│   ├── models.py                 # Pydantic / GameState
│   ├── front_read_models.py      # Hubs JSON (home, social, finanças, jornal, …)
│   ├── legacy_hub.py             # Agregação para o ecrã Legado
│   ├── competition_stats.py      # Stats de competição / blocos Lua
│   ├── external_ingestion.py     # Import de artefactos / eventos externos
│   ├── player_relation_press.py  # Relação treinador–jogador + coletiva
│   ├── press_narrative.py
│   ├── press_theme_templates.py
│   ├── internal_comms_engine.py
│   ├── internal_comms_coach_banks.py
│   ├── internal_comms_lock.py
│   ├── diagnose_save.py          # CLI: inspecionar save
│   ├── debug_standings.py        # Debug de classificações
│   ├── requirements.txt
│   ├── fc_companion.db           # SQLite (gerado em runtime; não versionar)
│   │
│   ├── achievements_engine.py
│   ├── board_engine.py
│   ├── career_dynamics_engine.py
│   ├── crisis_engine.py
│   ├── editorial_engine.py
│   ├── hall_of_fame_engine.py
│   ├── legacy_engine.py
│   ├── market_engine.py
│   ├── meta_achievements_engine.py
│   ├── narrative_engine.py
│   ├── payoff_engine.py
│   ├── reputation_engine.py
│   ├── season_arc_engine.py
│   │
│   ├── engine/
│   │   ├── analyzer.py           # FootballAnalyzer (pressão, momentum, …)
│   │   ├── content_generator.py  # Conteúdo híbrido para narrativa
│   │   ├── event_dispatcher.py   # EventDispatcher + severidades
│   │   └── llm_client.py
│   │
│   ├── save_reader/
│   │   ├── save_finder.py
│   │   ├── save_parser.py
│   │   ├── save_watcher.py
│   │   ├── transfer_history_from_save.py
│   │   └── node_fbparser/        # Node: parse_fbchunks.js (+ package.json)
│   │
│   ├── uploads/                  # Imagens servidas em /uploads
│   │   ├── clubs/
│   │   └── trophies/
│   │
│   └── test_*.py                 # unittest (engine, legado, carreira, gemini live)
│
├── frontend/                     # React 18 + Vite + TypeScript + Tailwind + PWA
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── eslint.config.js
│   ├── tsconfig.json
│   ├── package.json
│   ├── public/
│   ├── dist/                     # Build de produção (npm run build; servido pelo FastAPI)
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── vite-env.d.ts
│       ├── assets/               # SVG / estáticos do Vite
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── Header.tsx
│       │   ├── BottomNav.tsx
│       │   ├── Empty.tsx
│       │   └── premium/          # ArticleReader, NewsStoryCard, SectionHeader, SignalRadarCard
│       ├── pages/
│       │   ├── Feed.tsx
│       │   ├── Home.tsx
│       │   ├── Plantel.tsx
│       │   ├── Mercado.tsx
│       │   ├── Social.tsx
│       │   ├── NewsArticle.tsx
│       │   ├── Conference.tsx
│       │   ├── Financas.tsx
│       │   ├── StatusFisico.tsx
│       │   ├── Estatisticas.tsx
│       │   ├── Carreira.tsx
│       │   ├── Legado.tsx
│       │   ├── Conquistas.tsx
│       │   └── Configuracoes.tsx
│       ├── lib/                  # api.ts, utils.ts
│       ├── store/                # Zustand (useGameStore, useCareerHubStore, useFinanceStore, …)
│       └── hooks/                # ex.: useTheme.ts
│
└── launcher/                     # Arranque Windows + PyInstaller
    ├── run_companion.py
    ├── run_companion.bat
    ├── BUILD_EXE.md
    ├── FCCompanion.spec
    ├── dist/
    │   └── FCCompanion.exe       # Executável (quando gerado)
    └── build/                    # Cache PyInstaller (opcional; regenerável — ver .gitignore)
```

> **Nota:** `frontend/node_modules/`, `backend/__pycache__/`, `save_reader/node_fbparser/node_modules/` e ficheiros `.env` locais não estão listados — são dependências ou artefactos gerados. O `launcher/build/` pode existir após build do `.exe` e é ignorado no Git.

---

## Ficheiros gerados localmente

| Ficheiro | Descrição |
|----------|-----------|
| `Desktop/fc_companion/state_lua.json` | Dados exportados pelo Lua |
| `Desktop/fc_companion/save_data.json` | Dados lidos do save em disco |
| `Desktop/fc_companion/state.json` | Estado unificado (fonte da API) |
| `backend/fc_companion.db` | Histórico, eventos, perfis (SQLite) |

---

## Variáveis de ambiente

Cria um ficheiro `.env` dentro de `backend/`:

```env
# IA (opcional — usa templates por padrão se não configurado)
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

# Provider de narrativa: "template" | "openai" | "gemini" | "ollama"
FC_COMPANION_AI_PROVIDER=template
```

---

## Gerar executável Windows (.exe)

```bash
cd launcher
pip install pyinstaller
pyinstaller FCCompanion.spec
```

O executável será gerado em `launcher/dist/`. Consulta `BUILD_EXE.md` para detalhes.

---

## Diagnóstico

| Script | Uso |
|--------|-----|
| `backend/diagnose_save.py` | Inspeciona a estrutura do save |
| `backend/debug_standings.py` | Depura classificações |

---

## Testes

```bash
cd backend
python -m unittest discover -p "test_*.py"
```

---

## Contribuir

Pull requests são bem-vindos! Se encontrares um bug ou tiveres uma ideia, abre uma **issue** primeiro para discutirmos.

---

## Licença

MIT — livre para uso pessoal e educacional.

> EA FC é marca registada da Electronic Arts. Este projeto não é endossado nem afiliado à EA. Faz sempre backup dos teus saves antes de usar ferramentas de terceiros.