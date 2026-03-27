from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import get_match_events, get_match_results, upsert_match_result_from_match_event


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str:
    return str(value) if value is not None else ""


def _resolve_player_name(player: Dict[str, Any]) -> str:
    for key in ("player_name", "commonname", "name"):
        raw = _safe_str(player.get(key)).strip()
        if raw and not raw.isdigit():
            return raw
    first = _safe_str(player.get("firstname")).strip()
    last = _safe_str(player.get("lastname")).strip()
    full = (f"{first} {last}").strip()
    if full and not full.isdigit():
        return full
    pid = _to_int(player.get("playerid"), 0)
    return f"Jogador #{pid or '--'}"


def _scoreline(my_score: int, opp_score: int) -> str:
    return f"{my_score} x {opp_score}"


def _calc_aproveitamento(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = sum(1 for m in matches if m.get("outcome") == "W")
    draws = sum(1 for m in matches if m.get("outcome") == "D")
    losses = sum(1 for m in matches if m.get("outcome") == "L")
    games = len(matches)
    points = sum(_to_int(m.get("points"), 0) for m in matches)
    points_possible = games * 3
    pct = round((points / points_possible) * 100, 2) if points_possible > 0 else 0.0
    return {
        "games": games,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": points,
        "points_possible": points_possible,
        "pct": pct,
    }


def _calc_streaks(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    longest = 0
    longest_range: Tuple[Optional[str], Optional[str]] = (None, None)
    current = 0
    current_since: Optional[str] = None

    streak = 0
    streak_start: Optional[str] = None
    for m in matches:
        occurred_at = _safe_str(m.get("occurred_at"))
        if m.get("outcome") == "W":
            if streak == 0:
                streak_start = occurred_at
            streak += 1
            if streak >= longest:
                longest = streak
                longest_range = (streak_start, occurred_at)
        else:
            streak = 0
            streak_start = None

    for m in reversed(matches):
        if m.get("outcome") != "W":
            break
        current += 1
        current_since = _safe_str(m.get("occurred_at"))
    if current > 0:
        current_since = _safe_str(matches[-current].get("occurred_at"))

    return {
        "longest_win_streak": {
            "count": longest,
            "from": longest_range[0],
            "to": longest_range[1],
        },
        "current_win_streak": {
            "count": current,
            "since": current_since,
        },
    }


def _calc_records(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    biggest_win: Optional[Dict[str, Any]] = None
    worst_loss: Optional[Dict[str, Any]] = None
    for m in matches:
        diff = _to_int(m.get("goal_diff"), 0)
        if biggest_win is None or diff > _to_int(biggest_win.get("goal_diff"), -10_000):
            biggest_win = dict(m)
        if worst_loss is None or diff < _to_int(worst_loss.get("goal_diff"), 10_000):
            worst_loss = dict(m)

    def _normalize(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not record:
            return None
        my_score = _to_int(record.get("my_score"), 0)
        opp_score = _to_int(record.get("opp_score"), 0)
        return {
            "scoreline": _scoreline(my_score, opp_score),
            "goal_diff": _to_int(record.get("goal_diff"), 0),
            "opponent_name": record.get("opponent_name"),
            "club_name": record.get("club_name"),
            "competition_name": record.get("competition_name"),
            "occurred_at": record.get("occurred_at"),
            "date_raw": record.get("date_raw"),
        }

    return {
        "biggest_win": _normalize(biggest_win),
        "worst_loss": _normalize(worst_loss),
    }


def _calc_club_most_games(matches: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    buckets: Dict[str, int] = {}
    for m in matches:
        club = _safe_str(m.get("club_name")).strip()
        if not club:
            continue
        buckets[club] = buckets.get(club, 0) + 1
    if not buckets:
        return None
    club_name, games = max(buckets.items(), key=lambda item: item[1])
    return {"club_name": club_name, "games": games}


def _best_xi_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    squad = list(state.get("squad") or [])
    candidates: List[Dict[str, Any]] = []
    for p in squad:
        if not isinstance(p, dict):
            continue
        overall = p.get("overall")
        if overall is None:
            overall = p.get("overallrating")
        overall_i = _to_int(overall, 0)
        candidates.append(
            {
                "playerid": _to_int(p.get("playerid"), 0),
                "name": _resolve_player_name(p),
                "overall": overall_i,
                "position": _safe_str(p.get("position") or p.get("preferredposition")),
            }
        )
    candidates.sort(key=lambda item: (-_to_int(item.get("overall"), 0), item.get("name") or ""))
    players = candidates[:11]
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "players": players,
    }


def build_legacy_hub(save_uid: str, state: Dict[str, Any]) -> Dict[str, Any]:
    if not save_uid:
        return {
            "save_uid": "",
            "generated_at": datetime.utcnow().isoformat(),
            "aproveitamento": _calc_aproveitamento([]),
            "records": {"biggest_win": None, "worst_loss": None},
            "streaks": {"longest_win_streak": {"count": 0, "from": None, "to": None}, "current_win_streak": {"count": 0, "since": None}},
            "club_most_games": None,
            "best_xi": _best_xi_from_state(state),
        }

    matches = get_match_results(save_uid)
    if not matches:
        events = get_match_events(save_uid)
        fallback_club = _safe_str(((state.get("club") or {}).get("team_name")) or "")
        for ev in events:
            payload = dict(ev.get("payload") or {})
            if not payload.get("club_name") and fallback_club:
                payload["club_name"] = fallback_club
            occurred_at = ev.get("timestamp")
            if isinstance(occurred_at, datetime):
                upsert_match_result_from_match_event(save_uid, payload, occurred_at)
        matches = get_match_results(save_uid)

    aproveitamento = _calc_aproveitamento(matches)
    streaks = _calc_streaks(matches)
    records = _calc_records(matches)
    club_most_games = _calc_club_most_games(matches)
    best_xi = _best_xi_from_state(state)

    cards: List[Dict[str, Any]] = []
    cards.append(
        {
            "card_id": "kpi:aproveitamento",
            "type": "kpi",
            "title": "Aproveitamento",
            "value": f"{aproveitamento['pct']:.1f}%",
            "subtitle": f"{aproveitamento['wins']}V · {aproveitamento['draws']}E · {aproveitamento['losses']}D ({aproveitamento['games']} jogos)",
        }
    )
    if records.get("biggest_win"):
        rec = records["biggest_win"]
        cards.append(
            {
                "card_id": "record:biggest_win",
                "type": "record",
                "title": "Maior vitória",
                "value": rec.get("scoreline"),
                "subtitle": f"vs {rec.get('opponent_name') or '--'} · saldo +{rec.get('goal_diff')}",
                "meta": {
                    "competition_name": rec.get("competition_name"),
                    "date_raw": rec.get("date_raw"),
                    "occurred_at": rec.get("occurred_at"),
                },
            }
        )
    if records.get("worst_loss"):
        rec = records["worst_loss"]
        cards.append(
            {
                "card_id": "record:worst_loss",
                "type": "record",
                "title": "Pior derrota",
                "value": rec.get("scoreline"),
                "subtitle": f"vs {rec.get('opponent_name') or '--'} · saldo {rec.get('goal_diff')}",
                "meta": {
                    "competition_name": rec.get("competition_name"),
                    "date_raw": rec.get("date_raw"),
                    "occurred_at": rec.get("occurred_at"),
                },
            }
        )
    cards.append(
        {
            "card_id": "streak:longest_win",
            "type": "streak",
            "title": "Maior sequência de vitórias",
            "value": f"{_to_int((streaks.get('longest_win_streak') or {}).get('count'), 0)}",
            "subtitle": "na carreira",
        }
    )
    if club_most_games:
        cards.append(
            {
                "card_id": "club:most_games",
                "type": "club",
                "title": "Time com mais jogos",
                "value": f"{club_most_games.get('games')}",
                "subtitle": club_most_games.get("club_name") or "--",
            }
        )

    return {
        "save_uid": save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "aproveitamento": aproveitamento,
        "records": records,
        "streaks": streaks,
        "club_most_games": club_most_games,
        "best_xi": best_xi,
        "cards": cards,
        "missing_topics": [
            "titulos_conquistados",
            "titulo_mais_importante",
        ],
    }

