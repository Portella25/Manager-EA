"""Uma rodada de interação interna (Social) por data de jogo no save."""

from __future__ import annotations

from database import get_external_artifact, upsert_external_artifact

ARTIFACT_TYPE = "internal_comms_daily_lock"


def is_internal_comms_locked_for_date(save_uid: str, current_game_date: str) -> bool:
    if not save_uid or not (current_game_date or "").strip():
        return False
    art = get_external_artifact(save_uid, ARTIFACT_TYPE)
    if not art:
        return False
    done = (art.get("payload") or {}).get("completed_game_date")
    return bool(done and str(done) == str(current_game_date).strip())


def record_internal_comms_completed(save_uid: str, game_date: str) -> None:
    if not save_uid or not (game_date or "").strip():
        return
    upsert_external_artifact(save_uid, ARTIFACT_TYPE, {"completed_game_date": str(game_date).strip()})
