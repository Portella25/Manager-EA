from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from database import insert_external_event_log, upsert_external_artifact


class ExternalIngestion:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path.home() / "Desktop" / "fc_companion")
        self._events_offset = 0

    def _read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def ingest_json_artifact(self, save_uid: str, filename: str, artifact_type: str) -> Optional[int]:
        if save_uid == "unknown_save":
            file_path = self.base_dir / filename
        else:
            file_path = self.base_dir / save_uid / filename
            
        payload = self._read_json(file_path)
        if payload is None:
            return None
        artifact_save_uid = payload.get("meta", {}).get("save_uid") or payload.get("save_uid") or save_uid
        if not artifact_save_uid:
            return None
        return upsert_external_artifact(
            save_uid=str(artifact_save_uid),
            artifact_type=artifact_type,
            payload=payload,
            source_path=str(file_path),
        )

    def ingest_events_jsonl(self, save_uid: str) -> int:
        if save_uid == "unknown_save":
            file_path = self.base_dir / "events.jsonl"
        else:
            file_path = self.base_dir / save_uid / "events.jsonl"
            
        if not file_path.exists():
            return 0
        inserted = 0
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                handle.seek(self._events_offset)
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_raw = payload.get("timestamp")
                    if isinstance(ts_raw, (int, float)):
                        ts = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc).replace(tzinfo=None)
                    else:
                        ts = datetime.utcnow()
                    event_save_uid = payload.get("save_uid") or save_uid
                    if not event_save_uid:
                        continue
                    insert_external_event_log(
                        save_uid=str(event_save_uid),
                        timestamp=ts,
                        payload=payload,
                        event_id_raw=payload.get("event_id"),
                        event_name_raw=payload.get("event_name"),
                        category=payload.get("category"),
                        importance=payload.get("importance"),
                    )
                    inserted += 1
                self._events_offset = handle.tell()
        except Exception:
            return inserted
        return inserted

    def ingest_all(self, save_uid: Optional[str]) -> None:
        if not save_uid:
            return
        self.ingest_json_artifact(save_uid, "schema.json", "schema")
        self.ingest_json_artifact(save_uid, "reference_data.json", "reference_data")
        self.ingest_json_artifact(save_uid, "season_stats.json", "season_stats")
        self.ingest_json_artifact(save_uid, "transfer_history.json", "transfer_history")
        self.ingest_events_jsonl(save_uid)
