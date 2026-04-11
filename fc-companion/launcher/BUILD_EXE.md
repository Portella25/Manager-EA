## Companion Launcher (Windows) — `FCCompanion.exe`

### Save padronizado (Botafogo)
- Por defeito o sistema usa **`CmMgrC20260409141102584`** (`FC_COMPANION_LOCKED_SAVE` no `run_companion.bat` e no código do launcher).
- Para outro save: altere a linha `set "FC_COMPANION_LOCKED_SAVE=..."` no `run_companion.bat` ou a constante `LOCKED_SAVE_ID` em `run_companion.py`.

### Pré-requisitos
- **Python 3** no PATH (o `.exe` só orquestra; watcher e API correm com `python`).
- Dependências do backend já instaladas: `pip install -r fc-companion\backend\requirements.txt`
- **Node.js** apenas se precisar de gerar `frontend\dist` de novo (`npm run build`).

### Onde está o executável
Após o build: **`fc-companion\launcher\dist\FCCompanion.exe`**

Mantenha o `.exe` dentro da pasta do repositório (ex.: `launcher\dist\`), para o launcher encontrar `backend\main.py` e `frontend\dist`.

### Regenerar o `.exe`

```bat
cd fc-companion\frontend
npm run build

cd ..\launcher
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --name FCCompanion run_companion.py
```

### Atalho + ícone
- Clique direito em `FCCompanion.exe` → **Criar atalho**
- Propriedades do atalho → **Alterar ícone…**
