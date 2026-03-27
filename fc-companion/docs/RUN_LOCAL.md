# Rodar localmente (Backend + Watcher + Frontend)

## 1) Backend

Instale dependências:

```bash
cd fc-companion/backend
pip install -r requirements.txt
```

Suba a API:

```bash
uvicorn main:app --reload --port 8000
```

Healthcheck:

- `http://localhost:8000/health`

## 2) Watcher (state.json)

Em outro terminal:

```bash
cd fc-companion/backend
python watcher.py
```

O Watcher monitora o arquivo:

- `C:\Users\<SEU_USUARIO>\Desktop\fc_companion\state.json`

## 3) Live Editor (Lua extractor)

No Live Editor, execute:

- [companion_export.lua](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/extractor/companion_export.lua)

## 4) Frontend

```bash
cd fc-companion/frontend
npm install
npm run dev
```

## 5) Validar rapidamente

1. Garanta que o `state.json` está atualizando (Lua).
2. Veja logs do Watcher emitindo eventos para `POST /internal/event`.
3. Consulte:
   - `GET /events/recent`
   - `GET /feed/recent`

## 6) Documentos úteis

- Regras do Motor: [FOOTBALL_ENGINE_MANIFESTO.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/FOOTBALL_ENGINE_MANIFESTO.md)
- Variáveis de ambiente: [ENV.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/docs/ENV.md)
- Gemini: [AI_GEMINI.md](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/docs/AI_GEMINI.md)
