from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class SaveFinder:
    # Ordem explícita dos diretórios prioritários solicitados.
    def __init__(self) -> None:
        user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        app_data = Path(os.environ.get("APPDATA", user_profile / "AppData" / "Roaming"))
        local_app_data = Path(os.environ.get("LOCALAPPDATA", user_profile / "AppData" / "Local"))
        self.search_roots: List[Path] = [
            user_profile / "Documents" / "FC 26" / "settings",
            app_data / "EA Sports" / "FC 26",
            local_app_data / "EA Sports" / "FC 26",
            local_app_data / "EA SPORTS FC 26",
            local_app_data / "EA SPORTS FC 26" / "settings",
        ]
        self.locked_save_name = "CmMgrC20260325175348749"

    def _candidate_files_from_root(self, root: Path) -> List[Path]:
        if not root.exists() or not root.is_dir():
            return []
        candidates: List[Path] = []
        for ext in ("*.db", "*.sav", "CmMgrC*"):
            for path in root.rglob(ext):
                try:
                    if path.is_file() and path.stat().st_size > 1024 * 1024:
                        candidates.append(path)
                except OSError:
                    continue
        return candidates

    def _looks_like_career(self, path: Path) -> bool:
        name = path.name.lower()
        return ("career" in name) or name.startswith("cmmgrc")

    def find_career_save(self) -> Optional[Path]:
        # Trava temporária: forçar um save específico enquanto validamos a integração.
        for root in self.search_roots:
            locked_candidate = root / self.locked_save_name
            if locked_candidate.exists() and locked_candidate.is_file():
                return locked_candidate

        # Estratégia híbrida: prioriza naming de carreira e depois maior .db.
        all_candidates: List[Path] = []
        for root in self.search_roots:
            all_candidates.extend(self._candidate_files_from_root(root))

        if not all_candidates:
            return None

        career_named = [p for p in all_candidates if self._looks_like_career(p)]
        if career_named:
            return max(career_named, key=lambda p: p.stat().st_mtime)

        db_candidates = [p for p in all_candidates if p.suffix.lower() == ".db"]
        if db_candidates:
            biggest_db = max(db_candidates, key=lambda p: p.stat().st_size)
            same_dir = [p for p in db_candidates if p.parent == biggest_db.parent]
            if same_dir:
                return max(same_dir, key=lambda p: p.stat().st_mtime)
            return biggest_db

        return max(all_candidates, key=lambda p: p.stat().st_mtime)

    def get_save_metadata(self, path: Path) -> Dict[str, object]:
        stat = path.stat()
        return {
            "size_mb": round(stat.st_size / (1024 * 1024), 3),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "path": str(path),
        }

    def watch_for_changes(self, callback: Callable[[Path], None]) -> Optional[Observer]:
        save_path = self.find_career_save()
        if save_path is None:
            return None

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                if Path(event.src_path).resolve() == save_path.resolve():
                    callback(save_path)

            def on_moved(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                if Path(event.dest_path).resolve() == save_path.resolve():
                    callback(save_path)

        observer = Observer()
        observer.schedule(_Handler(), str(save_path.parent), recursive=False)
        observer.start()
        return observer
