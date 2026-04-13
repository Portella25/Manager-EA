# FC Companion

![FC Companion Prévia]([Documentos/CapturaPWA.png](https://github.com/Portella25/Manager-EA/issues/1)

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

```text
EA FC 26 (save + runtime)
        │
        ├── Live Editor / Lua ───────────────► Desktop/fc_companion/state_lua.json
        │                                      └─ name resolution, live roles, finance_live
        │
        └── Save de carreira (.db) ─► save_reader/ ─► Desktop/fc_companion/save_data.json
                                         │              └─ transfer_history / season stats / squad
                                         └─ save_watcher.py + node_fbparser/

state_lua.json + save_data.json
        │
        ▼
watcher.py
        ├── StateMerger ─────────────► Desktop/fc_companion/state.json
        ├── EventDetector ───────────► eventos brutos
        ├── EventDispatcher ─────────► eventos híbridos
        └── ExternalIngestion ───────► schema / reference_data / season_stats / transfer_history

state.json + eventos + artefatos
        │
        ▼
FastAPI (backend/main.py)
        ├── database.py / SQLite (fc_companion.db)
        ├── *_engine.py (narrativa, reputação, mercado, crise, legado, conquistas...)
        ├── front_read_models.py (payloads agregados para a SPA)
        └── uploads/ (troféus e escudos)

FastAPI
        │
        ▼
React PWA (frontend/src)
        ├── App.tsx + Layout
        ├── pages/
        ├── components/
        ├── store/
        └── lib/api.ts
```

1. O **script Lua** (Live Editor) exporta dados de memória do jogo para `state_lua.json`.
2. O **save reader** lê o save em disco e complementa com `save_data.json`, incluindo histórico de transferências e estatísticas.
3. O **watcher** combina as fontes, detecta mudanças, gera eventos e envia o resultado para a API.
4. A **API (FastAPI)** orquestra os motores de domínio, persiste em SQLite e expõe os payloads consumidos pela SPA.
5. O **frontend (React PWA)** lê a API e apresenta o painel web, inclusive nos ecrãs premium.

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
├── extractor/
│   ├── companion_export.lua       # Script Lua principal para o Live Editor
│   └── explore_cm_feed_managers.lua
├── backend/
│   ├── main.py                    # API FastAPI e orquestração dos motores
│   ├── watcher.py                 # Monitoramento e despacho de eventos
│   ├── merger.py                  # Unificação das fontes de dados
│   ├── database.py                # Persistência SQLite
│   ├── events.py                  # Detecção de eventos no estado mesclado
│   ├── models.py                  # Schemas de entrada da API
│   ├── front_read_models.py       # Payloads agregados para o frontend
│   ├── external_ingestion.py      # Ingestão de artefatos auxiliares
│   ├── competition_stats.py       # Estatísticas de competições
│   ├── *_engine.py                # Motores de domínio (narrativa, mercado, legado...)
│   ├── internal_comms_*.py        # Fluxos de comunicação interna
│   ├── press_*.py                 # Press conference e fallout narrativo
│   ├── legacy_*.py                # Hub de legado e perfil histórico
│   ├── save_reader/
│   │   ├── save_finder.py
│   │   ├── save_parser.py
│   │   ├── save_watcher.py
│   │   ├── transfer_history_from_save.py
│   │   └── node_fbparser/
│   │       ├── parse_fbchunks.js
│   │       ├── package.json
│   │       └── package-lock.json
│   └── uploads/
│       ├── clubs/
│       └── trophies/
├── frontend/
│   ├── public/favicon.svg
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── Layout.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── BottomNav.tsx
│   │   │   ├── Empty.tsx
│   │   │   ├── NotificationBell.tsx
│   │   │   └── premium/
│   │   │       ├── ArticleReader.tsx
│   │   │       ├── NewsStoryCard.tsx
│   │   │       ├── SectionHeader.tsx
│   │   │       └── SignalRadarCard.tsx
│   │   ├── hooks/useTheme.ts
│   │   ├── lib/api.ts
│   │   ├── lib/utils.ts
│   │   ├── pages/
│   │   │   ├── Feed.tsx
│   │   │   ├── Home.tsx
│   │   │   ├── Plantel.tsx
│   │   │   ├── Carreira.tsx
│   │   │   ├── Legado.tsx
│   │   │   ├── Conquistas.tsx
│   │   │   ├── Configuracoes.tsx
│   │   │   ├── Mercado.tsx
│   │   │   ├── Social.tsx
│   │   │   ├── NewsArticle.tsx
│   │   │   ├── Conference.tsx
│   │   │   ├── Financas.tsx
│   │   │   ├── StatusFisico.tsx
│   │   │   └── Estatisticas.tsx
│   │   └── store/
│   │       ├── index.ts
│   │       ├── useGameStore.ts
│   │       ├── useFinanceStore.ts
│   │       ├── useCareerHubStore.ts
│   │       └── useNotificationsStore.ts
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── dist/                     # Build gerado pelo Vite/FastAPI
├── launcher/
│   ├── run_companion.py          # Script de arranque
│   ├── run_companion.bat
│   ├── FCCompanion.spec          # Spec PyInstaller
│   └── BUILD_EXE.md
├── docs/
│   ├── AI_GEMINI.md
│   ├── CAREER_PREMIUM_FRONT_BLUEPRINT.md
│   ├── CM_FEED_ARCHITECTURE.md
│   ├── ENV.md
│   ├── HALL_OF_FAME_SYNC.md
│   ├── LIVE_EDITOR_DATA_CONTRACT.md
│   └── RUN_LOCAL.md
└── README.md
```

---

## Ficheiros gerados localmente

| Ficheiro | Descrição |
|----------|-----------|
| `Desktop/fc_companion/state_lua.json` | Dados exportados pelo Lua |
| `Desktop/fc_companion/save_data.json` | Dados lidos do save em disco |
| `Desktop/fc_companion/state.json` | Estado unificado (fonte da API) |
| `Desktop/fc_companion/save_probe/` | Dumps auxiliares do parser do save |
| `Desktop/fc_companion/<save_uid>/transfer_history.json` | Histórico de transferências ingerido pelo backend |
| `backend/fc_companion.db` | Histórico, eventos, perfis e narrativas (SQLite) |
| `backend/uploads/` | Imagens enviadas para troféus e clubes |

---

## Variáveis de ambiente

Cria um ficheiro `.env` dentro de `backend/`:

```env
# IA (opcional — usa templates por padrão se não configurado)
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

# Provider de narrativa: "template" | "openai" | "gemini" | "ollama"
PROMANAGER_AI_PROVIDER=template
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
