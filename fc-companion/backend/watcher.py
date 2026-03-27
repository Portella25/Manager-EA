from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from database import init_db, save_event, save_snapshot_if_new_day
from engine.event_dispatcher import EventDispatcher
from events import EventDetector
from external_ingestion import ExternalIngestion
from merger import StateMerger
from models import GameState
from save_reader import SaveFinder, SaveParser, SaveWatcher


BASE_DIR = Path.home() / "Desktop" / "fc_companion"
STATE_LUA_PATH = BASE_DIR / "state_lua.json"
SAVE_DATA_PATH = BASE_DIR / "save_data.json"
STATE_PATH = BASE_DIR / "state.json"
BACKEND_EVENT_URL = "http://localhost:8000/internal/event"
POLL_SECONDS = 2
READ_RETRIES = 8
READ_RETRY_DELAY = 0.25


class StateProcessor:
    # Núcleo do watcher: mescla fontes, roda detectores e despacha eventos sem bloquear.
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.detector = EventDetector()
        self.external_ingestion = ExternalIngestion(base_dir)
        self.merger = StateMerger(base_dir)
        self.previous_state: Optional[Dict[str, Any]] = None
        self.queue: "queue.Queue[tuple[str, Path]]" = queue.Queue()
        self.lock = threading.Lock()
        self.running = True

    def enqueue(self, reason: str, path: Path) -> None:
        self.queue.put((reason, path))

    def stop(self) -> None:
        self.running = False

    def _log(self, message: str) -> None:
        print(f"[{datetime.now().isoformat()}] {message}")

    def _read_state_with_retry(self, state_path: Path) -> Optional[Dict[str, Any]]:
        for attempt in range(READ_RETRIES):
            try:
                raw = state_path.read_text(encoding="utf-8")
                if not raw.strip():
                    raise ValueError("state.json vazio")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("state.json inválido (não é objeto)")
                return data
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                self._log(
                    f"Leitura parcial/indisponível de {state_path.name} "
                    f"(tentativa {attempt + 1}/{READ_RETRIES}): {exc}"
                )
                time.sleep(READ_RETRY_DELAY)
        self._log(f"Falha ao ler {state_path.name} após tentativas de retry.")
        return None

    def _send_event_to_backend(
        self,
        event_type: str,
        payload: Dict[str, Any],
        timestamp: datetime,
        save_uid: Optional[str],
        severity: int = 3,
    ) -> None:
        body = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": timestamp.isoformat(),
            "save_uid": save_uid,
            "severity": severity,
        }
        try:
            response = requests.post(BACKEND_EVENT_URL, json=body, timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            self._log(f"Falha no POST {BACKEND_EVENT_URL}: {exc}")

    def _merge_state(self) -> Optional[Dict[str, Any]]:
        self.merger.merge_and_save(STATE_PATH)
        return self._read_state_with_retry(STATE_PATH)

    def process_once(self, reason: str, source_path: Path) -> None:
        state = self._merge_state()
        if state is None:
            return

        with self.lock:
            old_state = self.previous_state
            events = self.detector.detect(old_state, state)

            try:
                old_game_state = GameState(**old_state) if old_state else None
                new_game_state = GameState(**state)
                dispatcher = EventDispatcher(old_game_state, new_game_state)
                hybrid_events = dispatcher.dispatch()

                hybrid_types = [e.event_type for e in hybrid_events]
                filtered_events = []
                for e in events:
                    if e.event_type == "MATCH_COMPLETED" and any(
                        x in hybrid_types for x in ["match_won", "match_lost", "match_drawn"]
                    ):
                        continue
                    if e.event_type == "PLAYER_INJURED" and "player_injured" in hybrid_types:
                        continue
                    if e.event_type == "BUDGET_CHANGED" and "board_budget_cut" in hybrid_types:
                        continue
                    filtered_events.append(e)

                events = filtered_events
                events.extend(hybrid_events)
            except Exception as exc:
                self._log(f"Erro ao rodar Motor Híbrido: {exc}")

            self.previous_state = state

        save_uid = ((state.get("meta") or {}).get("save_uid"))
        self.external_ingestion.ingest_all(save_uid)
        save_snapshot_if_new_day(save_uid=save_uid, state_data=state)

        self._log(
            f"state.json atualizado ({reason}) | origem={source_path.name} | save_uid={save_uid} | "
            f"time={((state.get('club') or {}).get('team_name'))} | "
            f"budget={((state.get('club') or {}).get('transfer_budget'))}"
        )

        for event in events:
            save_event(event.event_type, event.payload, event.save_uid)
            severity = getattr(event, "severity", 3)
            if severity is None:
                severity = 3
            self._send_event_to_backend(
                event_type=event.event_type,
                payload=event.payload,
                timestamp=event.timestamp,
                save_uid=event.save_uid,
                severity=severity,
            )
            self._log(f"EVENTO {event.event_type} | payload={event.payload} | severity={severity}")

    def worker_loop(self) -> None:
        while self.running:
            try:
                reason, path = self.queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self.process_once(reason, path)
            except Exception as exc:
                self._log(f"Erro inesperado no processamento: {exc}")
            finally:
                self.queue.task_done()


class SourceFileHandler(FileSystemEventHandler):
    # Handler único para os dois artefatos de entrada da mesclagem.
    def __init__(self, processor: StateProcessor):
        self.processor = processor

    def _is_source_file(self, path: str) -> bool:
        name = Path(path).name
        return name in {"state_lua.json", "save_data.json"}

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_source_file(event.src_path):
            self.processor.enqueue("created", Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_source_file(event.src_path):
            self.processor.enqueue("modified", Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_source_file(event.dest_path):
            self.processor.enqueue("moved", Path(event.dest_path))


def wait_for_first_source(base_dir: Path) -> None:
    print(f"[Watcher] Aguardando state_lua.json ou save_data.json em {base_dir}")
    while True:
        if (base_dir / "state_lua.json").exists() or (base_dir / "save_data.json").exists():
            return
        time.sleep(POLL_SECONDS)


def main() -> None:
    init_db()
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    processor = StateProcessor(BASE_DIR)
    finder = SaveFinder()
    parser = SaveParser()

    # team_id vem do último state_lua disponível para sincronizar o parser com a carreira ativa.
    def get_user_team_id() -> int:
        try:
            if not STATE_LUA_PATH.exists():
                return 0
            data = json.loads(STATE_LUA_PATH.read_text(encoding="utf-8"))
            return int(((data.get("club") or {}).get("team_id")) or 0)
        except Exception:
            return 0

    save_watcher: Optional[SaveWatcher] = None
    save_path = finder.find_career_save()
    if save_path is not None:
        print(f"[Watcher] Save encontrado: {save_path}")
        save_watcher = SaveWatcher(save_path=save_path, parser=parser, get_user_team_id=get_user_team_id, output_dir=BASE_DIR)
        save_watcher.start()
    else:
        print("[Watcher] Save de carreira não encontrado no bootstrap.")

    wait_for_first_source(BASE_DIR)
    processor.enqueue("bootstrap", STATE_LUA_PATH if STATE_LUA_PATH.exists() else SAVE_DATA_PATH)

    worker = threading.Thread(target=processor.worker_loop, daemon=True, name="state-processor")
    worker.start()

    observer = Observer()
    handler = SourceFileHandler(processor)
    observer.schedule(handler, str(BASE_DIR), recursive=False)
    observer.start()

    print(f"[Watcher] Monitorando fontes em: {BASE_DIR}")
    print("[Watcher] Fluxo: state_lua.json + save_data.json -> state.json")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Watcher] Encerrando...")
    finally:
        processor.stop()
        observer.stop()
        observer.join()
        if save_watcher is not None:
            save_watcher.stop()
        parser.close()


if __name__ == "__main__":
    main()
