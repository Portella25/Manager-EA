from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from save_reader.save_parser import SaveParser


class SaveWatcher(FileSystemEventHandler):
    # Watcher dedicado ao save para manter parsing fora do loop principal do app.
    def __init__(
        self,
        save_path: Path,
        parser: SaveParser,
        get_user_team_id: Callable[[], int],
        output_dir: Optional[Path] = None,
    ) -> None:
        self.save_path = save_path
        self.parser = parser
        self.get_user_team_id = get_user_team_id
        self.output_dir = output_dir or (Path.home() / "Desktop" / "fc_companion")
        self.save_data_tmp = self.output_dir / "save_data.tmp"
        self.save_data_json = self.output_dir / "save_data.json"
        self.unresolved_ids_tmp = self.output_dir / "unresolved_player_ids.tmp"
        self.unresolved_ids_json = self.output_dir / "unresolved_player_ids.json"
        self.observer: Optional[Observer] = None
        self._lock = threading.Lock()
        self._running = False

    def _log(self, message: str) -> None:
        print(f"[SaveWatcher] {message}")

    def _write_atomic(self, payload: dict) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_data_tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if self.save_data_json.exists():
            self.save_data_json.unlink()
        self.save_data_tmp.replace(self.save_data_json)

    def _write_unresolved_ids(self, payload: dict) -> None:
        unresolved = payload.get("unresolved_name_player_ids")
        if not isinstance(unresolved, list):
            unresolved = []
        normalized = []
        seen = set()
        for value in unresolved:
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid in seen:
                continue
            seen.add(pid)
            normalized.append(pid)
        self.unresolved_ids_tmp.write_text(json.dumps(normalized), encoding="utf-8")
        if self.unresolved_ids_json.exists():
            self.unresolved_ids_json.unlink()
        self.unresolved_ids_tmp.replace(self.unresolved_ids_json)

    def _handle_change(self) -> None:
        # Delay curto para o jogo terminar a escrita do arquivo.
        time.sleep(2)
        with self._lock:
            if not self.parser.connect(self.save_path):
                self._log("Falha ao conectar no save. save_data.json não foi atualizado.")
                return
            user_team_id = int(self.get_user_team_id() or 0)
            payload = self.parser.extract_all(user_team_id=user_team_id)
            squad = payload.get("squad") if isinstance(payload, dict) else []
            manager = payload.get("manager") if isinstance(payload, dict) else {}
            manager_team_id = 0
            if isinstance(manager, dict):
                try:
                    manager_team_id = int(manager.get("clubteamid") or 0)
                except (TypeError, ValueError):
                    manager_team_id = 0
            if (not isinstance(squad, list) or len(squad) == 0) and manager_team_id > 0 and manager_team_id != user_team_id:
                payload = self.parser.extract_all(user_team_id=manager_team_id)
                if isinstance(payload, dict):
                    payload["resolved_user_team_id"] = manager_team_id
                    payload["requested_user_team_id"] = user_team_id
            self._write_atomic(payload)
            self._write_unresolved_ids(payload)
            self._log("Save file atualizado → save_data.json gerado")

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if Path(event.src_path).resolve() != self.save_path.resolve():
            return
        threading.Thread(target=self._handle_change, daemon=True, name="save-change-handler").start()

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if Path(event.dest_path).resolve() != self.save_path.resolve():
            return
        threading.Thread(target=self._handle_change, daemon=True, name="save-change-handler").start()

    def start(self) -> None:
        if self._running:
            return
        self.observer = Observer()
        self.observer.schedule(self, str(self.save_path.parent), recursive=False)
        self.observer.start()
        self._running = True
        self._log(f"Monitorando save: {self.save_path}")
        threading.Thread(target=self._handle_change, daemon=True, name="save-bootstrap-handler").start()

    def stop(self) -> None:
        if not self._running:
            return
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
        self._running = False
        self._log("Watcher de save encerrado.")
