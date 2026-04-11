"""Histórico de transferências lido diretamente do save (SQLite), com cache por mtime."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from save_reader.save_finder import SaveFinder
from save_reader.save_parser import SaveParser

_lock = threading.Lock()
_cache_key: Optional[Tuple[str, float, int]] = None
_cache_rows: List[Dict[str, Any]] = []


def clear_transfer_history_cache() -> None:
    global _cache_key, _cache_rows
    with _lock:
        _cache_key = None
        _cache_rows = []


def get_transfer_history_from_career_save(team_id: int) -> List[Dict[str, Any]]:
    """
    Abre o save de carreira, lê career_presignedcontract e filtra pelo clube.
    Resultado em cache enquanto o ficheiro de save não mudar (mtime).
    """
    global _cache_key, _cache_rows
    if team_id <= 0:
        return []
    finder = SaveFinder()
    path = finder.find_career_save()
    if path is None or not path.exists():
        return []
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    key: Tuple[str, float, int] = (str(path.resolve()), mtime, team_id)
    with _lock:
        if _cache_key == key and _cache_rows is not None:
            return list(_cache_rows)
    parser = SaveParser()
    if not parser.connect(path):
        return []
    try:
        rows = parser.get_transfer_history(team_id)
        if not isinstance(rows, list):
            rows = []
    finally:
        parser.close()
    with _lock:
        _cache_key = key
        _cache_rows = list(rows)
    return list(rows)
