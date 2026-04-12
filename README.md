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
3. Cola o conteúdo de `extractor/fc_companion_export.lua` e executa.

O script vai criar a pasta `%USERPROFILE%\Desktop\fc-companion\` com o ficheiro `state_lua.json`.

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

Ou acessa diretamente via `http://localhost:5173` se já tiveres feito o build.

---

## Estrutura do projeto

```
fc-companion/
├── extractor/
│   └── fc_companion_export.lua     # Script Lua para o Live Editor
├── backend/
│   ├── main.py                     # API FastAPI
│   ├── watcher.py                  # Monitoramento de mudanças
│   ├── merger.py                   # Unificação das fontes de dados
│   ├── events.py                   # Detecção de eventos (diff de estado)
│   ├── database.py                 # Persistência SQLite
│   ├── *_engine.py                 # Motores de domínio (narrativa, mercado, etc.)
│   ├── engine/                     # Análise, dispatcher e cliente LLM
│   ├── save_reader/                # Leitura do save em disco
│   └── front_read_models.py        # Agregadores de dados para o frontend
├── frontend/
│   └── src/                        # React + TypeScript + Tailwind
├── launcher/
│   ├── run_fc_companion.py         # Script de arranque
│   └── FC Companion.spec           # Spec PyInstaller (gerar .exe)
└── README.md
```

---

## Ficheiros gerados localmente

| Ficheiro | Descrição |
|----------|-----------|
| `Desktop/fc-companion/state_lua.json` | Dados exportados pelo Lua |
| `Desktop/fc-companion/save_data.json` | Dados lidos do save em disco |
| `Desktop/fc-companion/state.json` | Estado unificado (fonte da API) |
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
pyinstaller "FC Companion.spec"
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
