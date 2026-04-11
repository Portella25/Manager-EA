from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import (
    get_match_events,
    get_match_results,
    get_or_create_career_management_state,
    upsert_match_result_from_match_event,
)


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


def _club_team_id(state: Dict[str, Any]) -> int:
    return _to_int(((state.get("club") or {}).get("team_id")), 0)


def _fixture_to_match_row(fixture: Dict[str, Any], user_team_id: int, club_name: str) -> Optional[Dict[str, Any]]:
    """Converte um fixture concluído do state (Lua) para o mesmo formato usado em match_results."""
    if not fixture.get("is_completed"):
        return None
    home_id = _to_int(fixture.get("home_team_id"), 0)
    away_id = _to_int(fixture.get("away_team_id"), 0)
    if user_team_id <= 0 or user_team_id not in (home_id, away_id):
        return None
    is_home = user_team_id == home_id
    hs = fixture.get("home_score")
    aws = fixture.get("away_score")
    if hs is None or aws is None:
        return None
    my_score = _to_int(hs if is_home else aws, 0)
    opp_score = _to_int(aws if is_home else hs, 0)
    if my_score > opp_score:
        outcome, points = "W", 3
    elif my_score < opp_score:
        outcome, points = "L", 0
    else:
        outcome, points = "D", 1
    opponent_name = str(
        (fixture.get("away_team_name") if is_home else fixture.get("home_team_name")) or ""
    ).strip()
    dr = str(fixture.get("date_raw") or "")
    occurred_at = f"{dr}T12:00:00" if dr else datetime.utcnow().isoformat()
    return {
        "occurred_at": occurred_at,
        "date_raw": dr,
        "competition_id": _to_int(fixture.get("competition_id"), 0),
        "competition_name": str(fixture.get("competition_name") or ""),
        "club_name": club_name,
        "opponent_name": opponent_name,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "is_home": is_home,
        "my_score": my_score,
        "opp_score": opp_score,
        "goal_diff": my_score - opp_score,
        "outcome": outcome,
        "points": points,
    }


def _match_identity_key(m: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        str(m.get("date_raw") or ""),
        int(m.get("competition_id") or 0),
        int(m.get("home_team_id") or 0),
        int(m.get("away_team_id") or 0),
        int(m.get("my_score") or 0),
        int(m.get("opp_score") or 0),
    )


def _matches_from_state_fixtures(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    uid = _club_team_id(state)
    if uid <= 0:
        return []
    club_name = _safe_str(((state.get("club") or {}).get("team_name")))
    rows: List[Dict[str, Any]] = []
    for fx in state.get("fixtures") or []:
        if not isinstance(fx, dict):
            continue
        row = _fixture_to_match_row(fx, uid, club_name)
        if row:
            rows.append(row)
    rows.sort(key=lambda m: str(m.get("occurred_at") or ""))
    return rows


def _merge_match_sources(
    db_rows: List[Dict[str, Any]], state_rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], str]:
    """Une calendário ao vivo (state) com histórico persistido (SQLite), sem duplicar a mesma partida."""
    if not state_rows:
        return list(db_rows), "database"
    if not db_rows:
        return list(state_rows), "state"
    seen = {_match_identity_key(m) for m in state_rows}
    merged = list(state_rows)
    for m in db_rows:
        k = _match_identity_key(m)
        if k not in seen:
            merged.append(m)
            seen.add(k)
    merged.sort(key=lambda m: str(m.get("occurred_at") or ""))
    return merged, "merged"


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


def _calc_clubs_history(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calcula stats por clube onde o treinador atuou."""
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for m in matches:
        club = _safe_str(m.get("club_name")).strip()
        if not club:
            continue
        buckets.setdefault(club, []).append(m)
    clubs: List[Dict[str, Any]] = []
    for club_name, club_matches in buckets.items():
        stats = _calc_aproveitamento(club_matches)
        clubs.append({
            "club_name": club_name,
            "games": stats["games"],
            "wins": stats["wins"],
            "draws": stats["draws"],
            "losses": stats["losses"],
            "points": stats["points"],
            "aproveitamento_pct": stats["pct"],
        })
    clubs.sort(key=lambda c: (-c["games"], c["club_name"]))
    return clubs


def _calc_current_club_stats(matches: List[Dict[str, Any]], current_club: str) -> Optional[Dict[str, Any]]:
    """Stats do treinador no clube atual."""
    if not current_club:
        return None
    club_matches = [m for m in matches if _safe_str(m.get("club_name")).strip() == current_club]
    if not club_matches:
        return None
    stats = _calc_aproveitamento(club_matches)
    streaks = _calc_streaks(club_matches)
    records = _calc_records(club_matches)
    return {
        "club_name": current_club,
        **stats,
        "streaks": streaks,
        "records": records,
    }


FORMATION_MAP: Dict[int, str] = {
    0: "4-4-2", 1: "4-1-2-1-2", 2: "4-2-3-1", 3: "4-3-3", 4: "4-5-1",
    5: "4-3-2-1", 6: "4-3-1-2", 7: "4-2-2-2", 8: "4-1-2-1-2 (2)",
    9: "4-2-4", 10: "4-1-4-1", 11: "4-4-1-1", 12: "3-5-2",
    13: "3-4-3", 14: "3-4-2-1", 15: "3-4-1-2", 16: "5-3-2",
    17: "5-4-1", 18: "5-2-1-2", 19: "5-2-3", 20: "5-1-2-2",
    21: "4-2-3-1 (2)", 22: "4-3-3 (2)", 23: "4-3-3 (3)",
    24: "4-3-3 (4)", 25: "4-3-3 (5)", 26: "4-4-2 (2)",
    27: "3-1-4-2", 28: "3-5-1-1", 29: "4-1-3-2",
    30: "4-2-1-3", 31: "3-4-3 (2)", 32: "4-1-3-2 (2)",
    33: "4-1-2-3", 34: "3-2-3-2", 35: "3-3-4",
    # EAFC 25/26 high IDs
    200: "4-3-3 Ataque", 201: "4-4-2 Defesa", 202: "4-2-3-1 Largo",
    203: "3-5-2 Ala", 204: "4-1-4-1 Contra", 205: "4-3-3 Falso 9",
    206: "4-2-2-2 Losango", 207: "4-1-2-1-2 Estreito",
    208: "5-3-2 Defensivo", 209: "3-4-3 Ofensivo", 210: "4-3-2-1 Variante",
    211: "4-2-3-1 Estreito", 212: "4-4-1-1 Ataque",
    213: "4-3-3 Equilibrado", 214: "3-4-2-1 Ofensivo",
}


def _build_manager_profile(state: Dict[str, Any], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Perfil do treinador com dados do save."""
    manager = dict(state.get("manager") or {})
    manager_history = dict(manager.get("manager_history") or {})
    manager_pref = dict(manager.get("manager_pref") or {})
    club = dict(state.get("club") or {})

    total_games = len(matches) if matches else _to_int(manager_history.get("games_played"), 0)
    total_wins = sum(1 for m in matches if m.get("outcome") == "W") if matches else _to_int(manager_history.get("wins"), 0)
    total_draws = sum(1 for m in matches if m.get("outcome") == "D") if matches else _to_int(manager_history.get("draws"), 0)
    total_losses = sum(1 for m in matches if m.get("outcome") == "L") if matches else _to_int(manager_history.get("losses"), 0)

    total_pts = total_wins * 3 + total_draws
    total_possible = total_games * 3
    pct = round((total_pts / total_possible) * 100, 2) if total_possible > 0 else 0.0

    clubs_managed = set()
    for m in matches:
        c = _safe_str(m.get("club_name")).strip()
        if c:
            clubs_managed.add(c)

    from front_read_models import _career_season_number
    seasons = _career_season_number(state)

    domestic_cup_trophies = _to_int(manager_history.get("domesticcuptrophies"), 0)
    continental_trophies = _to_int(manager_history.get("continentalcuptrophies"), 0)
    league_trophies_raw = _to_int(manager_history.get("leaguetrophies"), 0)
    league_trophies = league_trophies_raw if league_trophies_raw < 100 else 0

    total_trophies = league_trophies + domestic_cup_trophies + continental_trophies

    formation_id = _to_int(manager_pref.get("clubformation1"), -1)
    favorite_formation = FORMATION_MAP.get(formation_id, f"ID {formation_id}" if formation_id >= 0 else "Desconhecida")

    goals_for = _to_int(manager_history.get("goals_for"), 0)
    goals_against = _to_int(manager_history.get("goals_against"), 0)

    return {
        "total_games": total_games,
        "total_wins": total_wins,
        "total_draws": total_draws,
        "total_losses": total_losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "aproveitamento_pct": pct,
        "clubs_managed_count": max(len(clubs_managed), 1),
        "clubs_managed": sorted(clubs_managed),
        "seasons": seasons,
        "current_club": _safe_str(club.get("team_name")),
        "trophies": {
            "league": league_trophies,
            "domestic_cup": domestic_cup_trophies,
            "continental": continental_trophies,
            "total": total_trophies,
        },
        "favorite_formation": favorite_formation,
        "biggest_buy": _safe_str(manager_history.get("bigbuyplayername")),
        "biggest_sell": _safe_str(manager_history.get("bigsellplayername")),
    }


def build_legacy_hub(save_uid: str, state: Dict[str, Any]) -> Dict[str, Any]:
    if not save_uid:
        return {
            "save_uid": "",
            "generated_at": datetime.utcnow().isoformat(),
            "aproveitamento": _calc_aproveitamento([]),
            "aproveitamento_meta": {"source": "empty", "count_state": 0, "count_database": 0, "count_merged": 0},
            "records": {"biggest_win": None, "worst_loss": None},
            "streaks": {"longest_win_streak": {"count": 0, "from": None, "to": None}, "current_win_streak": {"count": 0, "since": None}},
            "club_most_games": None,
            "best_xi": _best_xi_from_state(state),
        }

    db_matches = get_match_results(save_uid)
    if not db_matches:
        events = get_match_events(save_uid)
        fallback_club = _safe_str(((state.get("club") or {}).get("team_name")) or "")
        for ev in events:
            payload = dict(ev.get("payload") or {})
            if not payload.get("club_name") and fallback_club:
                payload["club_name"] = fallback_club
            occurred_at = ev.get("timestamp")
            if isinstance(occurred_at, datetime):
                upsert_match_result_from_match_event(save_uid, payload, occurred_at)
        db_matches = get_match_results(save_uid)

    state_matches = _matches_from_state_fixtures(state)
    matches, merge_source = _merge_match_sources(db_matches, state_matches)

    aproveitamento = _calc_aproveitamento(matches)
    aproveitamento_meta = {
        "source": merge_source,
        "count_state": len(state_matches),
        "count_database": len(db_matches),
        "count_merged": len(matches),
    }
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

    current_club_name = _safe_str((state.get("club") or {}).get("team_name"))
    clubs_history = _calc_clubs_history(matches)
    current_club_stats = _calc_current_club_stats(matches, current_club_name)
    manager_profile = _build_manager_profile(state, matches)

    management_state = get_or_create_career_management_state(save_uid) if save_uid else {}
    tactical = dict(management_state.get("tactical") or {})
    locker = dict(management_state.get("locker_room") or {})

    manager_morale = {
        "cohesion": locker.get("cohesion"),
        "low_morale_count": _to_int(locker.get("low_morale_count"), 0),
        "tactical_stability": tactical.get("stability"),
    }

    return {
        "save_uid": save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "aproveitamento": aproveitamento,
        "aproveitamento_meta": aproveitamento_meta,
        "records": records,
        "streaks": streaks,
        "club_most_games": club_most_games,
        "best_xi": best_xi,
        "cards": cards,
        "manager_profile": manager_profile,
        "clubs_history": clubs_history,
        "current_club_stats": current_club_stats,
        "manager_morale": manager_morale,
    }

