from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Save de carreira padronizado (Botafogo). Override: variável FC_COMPANION_LOCKED_SAVE.
LOCKED_SAVE_ID = "CmMgrC20260409141102584"


def _find_fc_companion_root() -> Path:
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent
    for p in [start, *start.parents]:
        if (p / "backend" / "main.py").is_file() and (p / "backend" / "watcher.py").is_file():
            return p
    raise RuntimeError(
        "Pasta do projeto não encontrada (falta backend/main.py). "
        "Mantenha o .exe em fc-companion/launcher/dist/ dentro do repositório."
    )


ROOT = _find_fc_companion_root()
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def _print(msg: str) -> None:
    print(f"[Launcher] {msg}", flush=True)


def _python_for_subprocess() -> str:
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python", "py"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "Python não encontrado no PATH. Instale Python 3 e marque 'Add to PATH', "
        "ou use run_companion.bat com o Python correto."
    )


def _run_checked(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Falhou: {' '.join(cmd)} (code={proc.returncode})")


def ensure_frontend_dist() -> None:
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return
    _print("Build do frontend não encontrado. Gerando `frontend/dist`…")
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm não encontrado no PATH. Instale Node.js e rode `npm run build` em frontend/.")
    _run_checked([npm, "install"], cwd=FRONTEND_DIR)
    _run_checked([npm, "run", "build"], cwd=FRONTEND_DIR)


def main() -> int:
    ensure_frontend_dist()

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["FC_COMPANION_LOCKED_SAVE"] = (env.get("FC_COMPANION_LOCKED_SAVE") or "").strip() or LOCKED_SAVE_ID

    py = _python_for_subprocess()
    procs: list[subprocess.Popen[bytes]] = []

    def spawn(name: str, cmd: list[str], cwd: Path) -> None:
        _print(f"Iniciando {name}…")
        procs.append(
            subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=None,
                stderr=None,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        )

    try:
        spawn("watcher", [py, "watcher.py"], cwd=BACKEND_DIR)
        spawn(
            "backend",
            [
                py,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=BACKEND_DIR,
        )

        url = "http://127.0.0.1:8000/"
        _print(f"Save travado: {env['FC_COMPANION_LOCKED_SAVE']}")
        _print("Aguardando backend responder…")
        time.sleep(1.2)
        webbrowser.open(url, new=1)
        _print(f"Aberto no browser: {url}")

        while True:
            alive = [p for p in procs if p.poll() is None]
            if not alive:
                _print("Processos encerraram. Saindo.")
                return 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        _print("Encerrando…")
        return 0
    finally:
        for p in procs:
            if p.poll() is not None:
                continue
            try:
                if os.name == "nt":
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    p.terminate()
            except Exception:
                pass
        time.sleep(0.8)
        for p in procs:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
