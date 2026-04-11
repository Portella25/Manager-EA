"""Atualiza relação treinador–jogador após interações 1:1 persistidas (imprensa / comunicação interna)."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from database import get_player_relation, save_feed_item, upsert_player_relation


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def _status_from_scores(trust: int, frustration: int) -> str:
    if frustration >= 60:
        return "frustrado"
    if trust <= 35 or frustration >= 50:
        return "insatisfeito"
    if trust >= 72 and frustration < 38:
        return "alinhou"
    if frustration >= 40:
        return "tenso"
    return "neutro"


def apply_one_on_one_interaction_to_relation(
    save_uid: str,
    player_id: int,
    player_name: Optional[str],
    tone: str,
    reputation_delta: int,
    morale_delta: int,
) -> Optional[Dict[str, Any]]:
    """
    Ajusta trust/frustração conforme o tom percebido na resposta do treinador.
    Opcionalmente gera ruído na mídia se a relação estiver muito estressada.
    """
    if not save_uid or not player_id:
        return None
    existing = get_player_relation(save_uid, player_id)
    trust = _clamp(int(existing.get("trust") or 50) if existing else 50)
    frustration = _clamp(int(existing.get("frustration") or 0) if existing else 0)
    role_label = str((existing or {}).get("role_label") or "rotacao")
    notes = dict((existing or {}).get("notes") or {})

    t = (tone or "").strip().lower()
    if t == "confiante":
        trust = _clamp(trust + 2 + (1 if morale_delta > 0 else 0))
        frustration = _clamp(frustration - max(2, min(5, abs(morale_delta) or 2)))
    elif t == "agressivo":
        trust = _clamp(trust - 4 - (1 if reputation_delta < -1 else 0))
        frustration = _clamp(frustration + 5 + (2 if reputation_delta < -2 else 0))
    elif t == "evasivo":
        trust = _clamp(trust - 3)
        frustration = _clamp(frustration + 3)
    else:  # neutro
        trust = _clamp(trust + (1 if morale_delta > 0 else 0))
        frustration = _clamp(frustration + (1 if morale_delta < 0 else -1))

    status = _status_from_scores(trust, frustration)
    notes["last_press_tone"] = t
    notes["last_interaction_rep_delta"] = int(reputation_delta)
    media_hint = False
    if frustration >= 62 and trust <= 48:
        h = int(hashlib.md5(f"{save_uid}|media|{player_id}|{frustration}".encode()).hexdigest()[:8], 16)
        if h % 4 == 0:
            media_hint = True
            save_feed_item(
                event_type="LOCKER_ROOM_LEAK",
                channel="media",
                title=f"Ruído no ambiente: tensão entre treinador e {player_name or 'atleta'}",
                content=(
                    "Fontes próximas ao grupo indicam incômodo após conversas internas; "
                    "o clube tenta evitar exposição pública, mas a imprensa especula."
                ),
                tone="tension",
                source="player_relation",
                save_uid=save_uid,
            )

    saved = upsert_player_relation(
        save_uid=save_uid,
        playerid=int(player_id),
        player_name=player_name or (existing or {}).get("player_name"),
        trust=trust,
        role_label=role_label,
        status_label=status,
        frustration=frustration,
        notes={**notes, "last_media_rumor": media_hint},
    )
    return saved

