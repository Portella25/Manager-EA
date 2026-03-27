# Gemini 2.0 Flash (Motor Híbrido)

O Motor Híbrido gera 80% do conteúdo via templates e chama a LLM (Gemini) apenas para eventos de severidade alta.

## Como habilitar (local)

1. Crie `fc-companion/.env` (copiando do `.env.example`).
2. Preencha:

   - `GEMINI_API_KEY=`

3. Instale dependências do backend:

```bash
cd fc-companion/backend
pip install -r requirements.txt
```

## Como testar a chamada real (live test)

O teste ao vivo só roda se `GEMINI_API_KEY` estiver no ambiente (para não quebrar CI/testes offline).

- Arquivo: [test_gemini_live.py](file:///C:/Users/Ryzen%205%205600g/Documents/trae_projects/Eafc%2026/fc-companion/backend/test_gemini_live.py)

Rodar:

```bash
cd fc-companion/backend
python test_gemini_live.py
```

## Comportamento de fallback

Se a chave não estiver configurada, o backend retorna texto de fallback para eventos severos (mantém o app funcionando sem depender da LLM).
