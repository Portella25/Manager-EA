from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from database import (
    get_active_board_challenge,
    get_active_crisis_arc,
    get_active_season_arc,
    get_career_facts,
    get_external_artifact,
    get_news_daily_package,
    get_or_create_career_management_state,
    get_or_create_coach_profile,
    get_player_relations,
    get_recent_events,
    get_recent_finance_ledger,
    get_recent_external_event_logs,
    get_recent_market_rumors,
    get_recent_timeline_entries,
    replace_career_facts,
    replace_news_daily_package,
)


STATE_PATH = Path.home() / "Desktop" / "fc_companion" / "state.json"
SAVE_DATA_PATH = Path.home() / "Desktop" / "fc_companion" / "save_data.json"
COMPANION_ROOT_PATH = Path.home() / "Desktop" / "fc_companion"
SLOT_ORDER = ["lead", "backstage", "analysis", "market", "environment"]
REFERENCE_BIRTHDATE_EPOCH = date(1582, 10, 14)
POSITION_LABELS = {
    0: "GOL",
    1: "ALA-D",
    2: "LD",
    3: "ZAG-D",
    4: "ZAG",
    5: "ZAG-E",
    6: "LE",
    7: "ALA-E",
    8: "VOL",
    9: "VOL-D",
    10: "VOL-E",
    11: "MD",
    12: "MC-D",
    13: "MC",
    14: "MC-E",
    15: "ME",
    16: "MAT-D",
    17: "MEI",
    18: "MAT-E",
    19: "PD",
    20: "SA-D",
    21: "ATA",
    22: "SA-E",
    23: "PE",
    24: "ATA-D",
    25: "CA",
    26: "ATA-E",
    27: "ATA",
}
PLAYER_ROLE_LABELS = {
    1: "Crucial",
    2: "Importante",
    3: "Rodízio",
    4: "Esporádico",
    5: "Promessa",
    0: "Base",
}
COMPETITION_NAME_HINTS = {
    651: "Mundial de Clubes",
    1364: "CONMEBOL Libertadores",
    1663: "Brasileirão",
    1665: "Brasileirão",
    1841: "Cariocão",
}


def _read_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_save_data() -> Dict[str, Any]:
    if not SAVE_DATA_PATH.exists():
        return {}
    try:
        data = json.loads(SAVE_DATA_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_transfer_history(save_uid: str) -> Dict[str, Any]:
    if not save_uid:
        return {}
    path = COMPANION_ROOT_PATH / save_uid / "transfer_history.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _label_from_kind(kind: str) -> str:
    labels = {
        "bonus_resultado": "Prêmios em dinheiro",
        "penalidade_resultado": "Penalidades esportivas",
        "folha_salarial": "Salários de atletas",
        "amortizacao": "Amortização de transferências",
        "bonus_metas": "Bônus por metas",
    }
    return labels.get(kind, kind.replace("_", " ").title())


def _extract_period_month(period: str) -> int:
    if len(period) >= 7 and period[4] == "-":
        return _to_int(period[5:7], 0)
    return 0


def _sum_values(values: Sequence[Any]) -> float:
    return round(sum(_to_float(value, 0.0) for value in values), 2)


def _normalize_transfer_items(raw_items: Sequence[Dict[str, Any]], user_team_name: str = "") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_items):
        row = dict(item or {})
        amount = abs(
            _to_float(
                row.get("amount")
                or row.get("fee")
                or row.get("value")
                or row.get("price")
                or row.get("transfer_fee"),
                0.0,
            )
        )
        if amount <= 0:
            continue
        raw_direction = str(
            row.get("direction")
            or row.get("movement")
            or row.get("type")
            or row.get("side")
            or ""
        ).lower()
        is_sell = raw_direction in ("out", "sell", "sale", "saida", "saída")
        if not raw_direction:
            to_team = str(row.get("to_team_name") or row.get("to_team") or "").lower()
            from_team = str(row.get("from_team_name") or row.get("from_team") or "").lower()
            user_name = str(user_team_name or "").strip().lower()
            if user_name and to_team and user_name in to_team:
                is_sell = False
            elif user_name and from_team and user_name in from_team:
                is_sell = True
        player_name = str(row.get("player_name") or row.get("player") or row.get("name") or "Jogador")
        period = str(row.get("period") or row.get("date") or row.get("transfer_date") or "")
        out.append(
            {
                "id": row.get("id") or f"transfer:{idx}",
                "period": period,
                "label": "Transferências",
                "kind": "transfer_sell" if is_sell else "transfer_buy",
                "description": ("Venda: " if is_sell else "Compra: ") + player_name,
                "amount": round(amount if is_sell else -amount, 2),
                "direction": "in" if is_sell else "out",
                "occurred_at": row.get("occurred_at") or row.get("timestamp"),
                "source": row.get("source") or "transfer_history_json",
            }
        )
    return out


def _normalize_manager_amount(value: Any) -> float:
    raw = _to_float(value, 0.0)
    if raw == 0:
        return 0.0
    if abs(raw) < 1000:
        return round(raw * 1_000_000.0, 2)
    return round(raw, 2)


def _pick_team_finance_row(club_name: str, teams: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    name = str(club_name or "").strip().lower()
    if not name:
        return {}
    for team in teams:
        team_name = str(team.get("teamname") or team.get("team_name") or "").strip().lower()
        if team_name and team_name == name:
            return dict(team)
    return {}


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(value)))


def _manager_name(manager: Dict[str, Any]) -> str:
    common = str(manager.get("commonname") or "").strip()
    if common:
        return common
    first = str(manager.get("firstname") or "").strip()
    last = str(manager.get("surname") or "").strip()
    merged = f"{first} {last}".strip()
    return merged or "Treinador"


def _player_name(player: Dict[str, Any]) -> str:
    name = str(player.get("player_name") or "").strip()
    if name and not name.startswith("ID "):
        return name
    common = str(player.get("commonname") or "").strip()
    if common:
        return common
    first = str(player.get("firstname") or "").strip()
    last = str(player.get("lastname") or "").strip()
    merged = f"{first} {last}".strip()
    return merged or f"#{player.get('playerid')}"


def _iso_game_date(state: Dict[str, Any]) -> str:
    raw = ((state.get("meta") or {}).get("game_date")) or {}
    try:
        return date(int(raw.get("year")), int(raw.get("month")), int(raw.get("day"))).isoformat()
    except (TypeError, ValueError):
        return date.today().isoformat()


def _label_game_date(game_date: str) -> str:
    try:
        parsed = date.fromisoformat(game_date)
        return parsed.strftime("%d %b %Y")
    except ValueError:
        return game_date


def _game_date_obj(state: Dict[str, Any]) -> Optional[date]:
    raw = ((state.get("meta") or {}).get("game_date")) or {}
    try:
        return date(int(raw.get("year")), int(raw.get("month")), int(raw.get("day")))
    except (TypeError, ValueError):
        return None


def _game_date_value(state: Dict[str, Any]) -> int:
    current = _game_date_obj(state)
    if current is None:
        return 0
    return (current.year * 10000) + (current.month * 100) + current.day


def _parse_date_raw(value: Any) -> Optional[date]:
    raw = _to_int(value, 0)
    if raw <= 0:
        return None
    year = raw // 10000
    month = (raw // 100) % 100
    day = raw % 100
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _fixture_sort_key(fixture: Dict[str, Any]) -> Tuple[int, int, int]:
    raw_date = _to_int(fixture.get("date_raw"), 0)
    raw_time = _to_int(fixture.get("time_raw"), 0)
    fixture_id = _to_int(fixture.get("id"), 0)
    return raw_date, raw_time, fixture_id


def _user_team_id(state: Dict[str, Any]) -> int:
    return _to_int(((state.get("club") or {}).get("team_id")), 0)


def _format_time_raw(value: Any) -> Optional[str]:
    raw = _to_int(value, 0)
    if raw <= 0:
        return None
    hours = raw // 100
    minutes = raw % 100
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def _format_date_raw(value: Any) -> Optional[str]:
    parsed = _parse_date_raw(value)
    if parsed is None:
        return None
    return parsed.strftime("%d %b %Y")


def _birthdate_from_serial(value: Any) -> Optional[date]:
    raw = _to_int(value, 0)
    if raw <= 0:
        return None
    try:
        return REFERENCE_BIRTHDATE_EPOCH + timedelta(days=raw)
    except OverflowError:
        return None


def _age_from_birthdate_serial(value: Any, current_date: Optional[date]) -> Optional[int]:
    birth_date = _birthdate_from_serial(value)
    if birth_date is None or current_date is None:
        return None
    age = current_date.year - birth_date.year - ((current_date.month, current_date.day) < (birth_date.month, birth_date.day))
    if age < 0 or age > 60:
        return None
    return age


def _position_label_from_id(value: Any) -> Optional[str]:
    pos_id = _to_int(value, -1)
    if pos_id < 0:
        return None
    return POSITION_LABELS.get(pos_id, f"POS {pos_id}")


def _position_group_from_id(value: Any) -> str:
    pos_id = _to_int(value, -1)
    if pos_id == 0:
        return "GK"
    if 1 <= pos_id <= 7:
        return "DEF"
    if 8 <= pos_id <= 18:
        return "MID"
    if 19 <= pos_id <= 27:
        return "ATT"
    return "RES"


def _contract_until_label(value: Any) -> Optional[str]:
    raw = _to_int(value, 0)
    if raw <= 0:
        return None
    if 19000101 <= raw <= 22001231:
        return _format_date_raw(raw)
    if 1900 <= raw <= 2200:
        return str(raw)
    return None


def _player_role_label(value: Any) -> Optional[str]:
    role_id = _to_int(value, -1)
    if role_id >= 256:
        role_id = role_id % 256
    if role_id < 0:
        return "Não definido"
    return PLAYER_ROLE_LABELS.get(role_id, f"Papel {role_id}")


def _normalize_relation_role_label(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    mapping = {
        "crucial": "Crucial",
        "importante": "Importante",
        "important": "Importante",
        "rotacao": "Rodízio",
        "rotação": "Rodízio",
        "rodizio": "Rodízio",
        "rodízio": "Rodízio",
        "esporadico": "Esporádico",
        "esporádico": "Esporádico",
        "promessa": "Promessa",
        "base": "Base",
    }
    return mapping.get(raw)


def _infer_role_from_profile(overall: Optional[int], age: Optional[int], wage: Optional[float]) -> str:
    ovr = _to_int(overall, 0)
    years = _to_int(age, 0)
    salary = _to_float(wage, 0.0)
    if ovr >= 77 and salary >= 78000:
        return "Crucial"
    if ovr <= 63:
        return "Promessa"
    if ovr <= 67 and years <= 19 and salary <= 20000:
        return "Promessa"
    if (ovr >= 75 and salary >= 25000) or (ovr >= 73 and salary >= 38000 and years >= 23):
        return "Importante"
    if (ovr <= 70 and salary < 40000 and years <= 24) or (ovr <= 68 and salary < 24000):
        return "Esporádico"
    return "Rodízio"


def _external_payload(save_uid: str, artifact_type: str) -> Dict[str, Any]:
    artifact = get_external_artifact(save_uid, artifact_type)
    if not artifact:
        return {}
    payload = artifact.get("payload")
    if isinstance(payload, dict):
        return payload
    return {}


def _reference_dataset(save_uid: str) -> Dict[str, Any]:
    payload = _external_payload(save_uid, "reference_data")
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def _season_stats_items(save_uid: str) -> List[Dict[str, Any]]:
    payload = _external_payload(save_uid, "season_stats")
    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _reference_players_by_id(save_uid: str) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}
    for player in _reference_dataset(save_uid).get("players") or []:
        pid = _to_int((player or {}).get("playerid"), 0)
        if pid > 0 and pid not in indexed:
            indexed[pid] = dict(player)
    return indexed


def _competition_name_index(save_uid: str) -> Dict[int, str]:
    names: Dict[int, str] = {}
    for item in _season_stats_items(save_uid):
        comp_id = _to_int(item.get("competition_id"), 0)
        comp_name = str(item.get("competition_name") or "").strip()
        if comp_id > 0 and comp_name:
            names.setdefault(comp_id, comp_name)
    for comp_id, comp_name in COMPETITION_NAME_HINTS.items():
        names.setdefault(comp_id, comp_name)
    return names


def _decorate_fixture(
    fixture: Optional[Dict[str, Any]],
    user_team_id: int,
    competition_names: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    if not fixture:
        return None
    decorated = dict(fixture)
    competition_id = _to_int(decorated.get("competition_id"), 0)
    competition_name = str(decorated.get("competition_name") or "").strip() or competition_names.get(competition_id)
    if competition_name:
        decorated["competition_name"] = competition_name
    decorated["date_label"] = _format_date_raw(decorated.get("date_raw"))
    decorated["time_label"] = _format_time_raw(decorated.get("time_raw"))
    home_team_id = _to_int(decorated.get("home_team_id"), -1)
    if home_team_id == user_team_id:
        decorated["opponent_team_id"] = decorated.get("away_team_id")
        decorated["opponent_name"] = decorated.get("away_team_name")
        decorated["home_away"] = "home"
    else:
        decorated["opponent_team_id"] = decorated.get("home_team_id")
        decorated["opponent_name"] = decorated.get("home_team_name")
        decorated["home_away"] = "away"
    return decorated


def _standings_points(row: Dict[str, Any]) -> int:
    total = dict(row.get("total") or {})
    wins = _to_int(total.get("wins"), 0)
    draws = _to_int(total.get("draws"), 0)
    stored_points = _to_int(total.get("points"), 0)
    calculated_points = (wins * 3) + draws
    return stored_points if stored_points > 0 else calculated_points


def _standings_sort_key(row: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
    total = dict(row.get("total") or {})
    wins = _to_int(total.get("wins"), 0)
    goals_for = _to_int(total.get("goals_for"), 0)
    goals_against = _to_int(total.get("goals_against"), 0)
    return (
        -_standings_points(row),
        -wins,
        -(goals_for - goals_against),
        -goals_for,
        str(row.get("team_name") or ""),
    )


def _select_primary_league_table(
    state: Dict[str, Any],
    user_team_id: int,
    next_fixture: Optional[Dict[str, Any]],
    competition_names: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in state.get("standings") or []:
        comp_id = _to_int((row or {}).get("competition_id"), 0)
        if comp_id > 0:
            grouped.setdefault(comp_id, []).append(dict(row))
    next_comp_id = _to_int((next_fixture or {}).get("competition_id"), 0)
    ranked_candidates: List[Tuple[int, int, int, List[Dict[str, Any]], Dict[str, Any]]] = []
    for comp_id, rows in grouped.items():
        mine = next((row for row in rows if _to_int(row.get("team_id"), 0) == user_team_id), None)
        if mine is None:
            continue
        team_count = len(rows)
        score = (
            (150 if team_count >= 10 else 0)
            + (80 if next_comp_id > 0 and comp_id == next_comp_id and team_count >= 10 else 0)
            + (team_count * 3)
            + _standings_points(mine)
        )
        ranked_candidates.append((score, comp_id, team_count, rows, mine))
    if not ranked_candidates:
        return None
    ranked_candidates.sort(key=lambda item: (item[0], item[2], _standings_points(item[4])), reverse=True)
    _, competition_id, team_count, rows, mine = ranked_candidates[0]
    sorted_rows = sorted(rows, key=_standings_sort_key)
    rank = next(
        (index + 1 for index, row in enumerate(sorted_rows) if _to_int(row.get("team_id"), 0) == user_team_id),
        None,
    )
    total = dict(mine.get("total") or {})
    competition_name = competition_names.get(competition_id) or str((next_fixture or {}).get("competition_name") or "").strip() or None
    played = _to_int(total.get("wins"), 0) + _to_int(total.get("draws"), 0) + _to_int(total.get("losses"), 0)
    return {
        "competition_id": competition_id,
        "competition_name": competition_name,
        "rank": rank,
        "team_count": team_count,
        "points": _standings_points(mine),
        "played": played,
        "wins": _to_int(total.get("wins"), 0),
        "draws": _to_int(total.get("draws"), 0),
        "losses": _to_int(total.get("losses"), 0),
        "goals_for": _to_int(total.get("goals_for"), 0),
        "goals_against": _to_int(total.get("goals_against"), 0),
        "goal_difference": _to_int(total.get("goals_for"), 0) - _to_int(total.get("goals_against"), 0),
    }


def _is_user_fixture(fixture: Dict[str, Any], user_team_id: int) -> bool:
    return _to_int(fixture.get("home_team_id"), -1) == user_team_id or _to_int(fixture.get("away_team_id"), -1) == user_team_id


def _result_letter(fixture: Dict[str, Any], user_team_id: int) -> Optional[str]:
    if not fixture.get("is_completed"):
        return None
    home_id = _to_int(fixture.get("home_team_id"), -1)
    away_id = _to_int(fixture.get("away_team_id"), -1)
    home_score = fixture.get("home_score")
    away_score = fixture.get("away_score")
    if home_score is None or away_score is None:
        return None
    if home_id != user_team_id and away_id != user_team_id:
        return None
    my_score = _to_int(home_score if home_id == user_team_id else away_score, 0)
    opp_score = _to_int(away_score if home_id == user_team_id else home_score, 0)
    if my_score > opp_score:
        return "W"
    if my_score < opp_score:
        return "L"
    return "D"


def _recent_results(
    fixtures: Sequence[Dict[str, Any]],
    user_team_id: int,
    limit: int = 5,
    game_date_raw: Optional[int] = None,
) -> List[str]:
    completed = [f for f in fixtures if _is_user_fixture(f, user_team_id) and f.get("is_completed")]
    if game_date_raw:
        completed = [f for f in completed if _to_int(f.get("date_raw"), 0) <= game_date_raw]
    completed.sort(key=_fixture_sort_key, reverse=True)
    results: List[str] = []
    for fixture in completed:
        letter = _result_letter(fixture, user_team_id)
        if letter:
            results.append(letter)
        if len(results) >= limit:
            break
    return results


def _next_fixture(
    fixtures: Sequence[Dict[str, Any]],
    user_team_id: int,
    game_date_raw: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    upcoming = [f for f in fixtures if _is_user_fixture(f, user_team_id) and not f.get("is_completed")]
    if game_date_raw:
        filtered = [f for f in upcoming if _to_int(f.get("date_raw"), 0) >= game_date_raw]
        if filtered:
            upcoming = filtered
    upcoming.sort(key=_fixture_sort_key)
    if not upcoming:
        return None
    return dict(upcoming[0])


def build_season_context(save_uid: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    current_state = state or _read_state()
    current_game_date = _game_date_obj(current_state)
    current_game_date_raw = _game_date_value(current_state)
    user_team_id = _user_team_id(current_state)
    competition_names = _competition_name_index(save_uid)
    fixtures = list(current_state.get("fixtures") or [])
    next_fixture = _decorate_fixture(
        _next_fixture(fixtures, user_team_id, current_game_date_raw),
        user_team_id,
        competition_names,
    )
    last_fixture = _decorate_fixture(
        _last_completed_fixture(fixtures, user_team_id),
        user_team_id,
        competition_names,
    )
    recent_form = _recent_results(fixtures, user_team_id, limit=5, game_date_raw=current_game_date_raw)
    league_table = _select_primary_league_table(current_state, user_team_id, next_fixture, competition_names)
    game_date_iso = _iso_game_date(current_state)
    return {
        "game_date": {
            "iso": game_date_iso,
            "label": _label_game_date(game_date_iso),
            "day": current_game_date.day if current_game_date else None,
            "month": current_game_date.month if current_game_date else None,
            "year": current_game_date.year if current_game_date else None,
        },
        "next_fixture": next_fixture,
        "last_fixture": last_fixture,
        "recent_form": {
            "last_5": recent_form,
            "points_last_5": _points_from_results(recent_form),
            "trend_label": "positivo" if _points_from_results(recent_form) >= 7 else ("instável" if _points_from_results(recent_form) >= 4 else "pressionado"),
        },
        "league_table": league_table,
    }


def build_squad_overview(save_uid: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    current_state = state or _read_state()
    effective_save_uid = save_uid or str(((current_state.get("meta") or {}).get("save_uid")) or "")
    current_game_date = _game_date_obj(current_state)
    reference_players = _reference_players_by_id(effective_save_uid) if effective_save_uid else {}
    relations = get_player_relations(effective_save_uid, limit=200) if effective_save_uid else []
    relation_by_pid = {_to_int(item.get("playerid"), 0): item for item in relations if _to_int(item.get("playerid"), 0) > 0}
    injuries = {_to_int(item.get("playerid"), 0): item for item in (current_state.get("injuries") or []) if _to_int(item.get("playerid"), 0) > 0}
    transfer_offers_by_pid: Dict[int, List[Dict[str, Any]]] = {}
    for offer in current_state.get("transfer_offers") or []:
        pid = _to_int((offer or {}).get("playerid"), 0)
        if pid > 0:
            transfer_offers_by_pid.setdefault(pid, []).append(dict(offer))
    enriched: List[Dict[str, Any]] = []
    for player in current_state.get("squad") or []:
        current_player = dict(player)
        pid = _to_int(current_player.get("playerid"), 0)
        reference = reference_players.get(pid, {})
        relation = relation_by_pid.get(pid, {})
        overall_rating = current_player.get("overallrating")
        reference_overall = reference.get("overallrating")
        overall_live = current_player.get("overall_live")
        base_overall_source = "save_overallrating"
        base_overall = _to_int(overall_rating, 0)
        if base_overall <= 0:
            base_overall = _to_int(reference_overall, 0)
            base_overall_source = "reference_players_overallrating"
        if base_overall <= 0:
            overall_live_float = _to_float(overall_live, 0.0)
            base_overall = int(overall_live_float + 0.5) if overall_live_float > 0 else 0
            base_overall_source = "save_squadranking_curroverall"
        overall_prev = current_player.get("overall_prev")
        overall_live_snapshot = int(_to_float(overall_live, 0.0) + 0.5) if _to_float(overall_live, 0.0) > 0 else None
        overall_prev_snapshot = int(_to_float(overall_prev, 0.0) + 0.5) if _to_float(overall_prev, 0.0) > 0 else None
        overall_delta = 0
        if overall_live is not None and overall_prev is not None:
            overall_delta = int(round(_to_float(overall_live, 0.0) - _to_float(overall_prev, 0.0)))
        overall = base_overall if base_overall > 0 else None
        overall_source = base_overall_source
        potential = current_player.get("potential")
        if potential is None:
            potential = reference.get("potential")
        position_id = current_player.get("preferredposition1")
        if position_id is None:
            position_id = reference.get("preferredposition1")
        birthdate_raw = current_player.get("birthdate")
        if birthdate_raw is None:
            birthdate_raw = reference.get("birthdate")
        age = current_player.get("age")
        if age is None:
            age = _age_from_birthdate_serial(birthdate_raw, current_game_date)
        birthdate_value = _birthdate_from_serial(birthdate_raw)
        contract_until = current_player.get("contractvaliduntil")
        wage_value = current_player.get("wage")
        contract_wage = current_player.get("contract_wage")
        player_role = current_player.get("playerrole")
        player_role_source = str(current_player.get("playerrole_source") or "save_playerrole")
        injury = injuries.get(pid)
        role_label = _player_role_label(player_role)
        role_source = player_role_source
        if role_label == "Não definido":
            role_label = _infer_role_from_profile(overall, age, _to_float(wage_value, _to_float(contract_wage, 0.0)))
            role_source = "inferred_profile_rules"
        enriched.append(
            {
                **current_player,
                "overall_base": base_overall if base_overall > 0 else None,
                "overall_delta": overall_delta,
                "overall_delta_label": f"{overall_delta:+d}" if overall_delta else None,
                "overall_live_snapshot": overall_live_snapshot,
                "overall_prev_snapshot": overall_prev_snapshot,
                "overall": overall if overall and overall > 0 else None,
                "overall_source": overall_source if overall and overall > 0 else None,
                "potential": _to_int(potential, 0) or None,
                "age": _to_int(age, 0) or None,
                "birthdate_label": birthdate_value.isoformat() if birthdate_value else None,
                "position_id": _to_int(position_id, -1) if position_id is not None else None,
                "position_label": _position_label_from_id(position_id),
                "position_group": _position_group_from_id(position_id),
                "wage_effective": _to_float(wage_value, _to_float(contract_wage, 0.0)) or None,
                "contract_until_label": _contract_until_label(contract_until),
                "injury_status": injury,
                "transfer_interest_count": len(transfer_offers_by_pid.get(pid, [])),
                "trust": relation.get("trust"),
                "role_id": (_to_int(player_role, -1) % 256) if player_role is not None and _to_int(player_role, -1) >= 256 else (_to_int(player_role, -1) if player_role is not None else None),
                "role_label": role_label,
                "role_source": role_source,
                "status_label": relation.get("status_label"),
                "frustration": relation.get("frustration"),
            }
        )
    enriched.sort(
        key=lambda item: (
            item.get("overall") is None,
            -_to_int(item.get("overall"), 0),
            -_to_float(item.get("contract_wage"), 0.0),
            _player_name(item),
        )
    )
    return enriched


def _last_completed_fixture(fixtures: Sequence[Dict[str, Any]], user_team_id: int) -> Optional[Dict[str, Any]]:
    completed = [f for f in fixtures if _is_user_fixture(f, user_team_id) and f.get("is_completed")]
    completed.sort(key=_fixture_sort_key, reverse=True)
    if not completed:
        return None
    return dict(completed[0])


def _points_from_results(results: Sequence[str]) -> int:
    mapping = {"W": 3, "D": 1, "L": 0}
    return sum(mapping.get(item, 0) for item in results)


def _impact_from_importance(importance: int) -> str:
    if importance >= 85:
        return "high"
    if importance >= 60:
        return "medium"
    return "low"


def _score_label(score: Optional[int], positive_high: bool = True) -> str:
    if score is None:
        return "indefinido"
    if positive_high:
        if score >= 75:
            return "forte"
        if score >= 55:
            return "estável"
        if score >= 35:
            return "atento"
        return "crítico"
    if score <= 25:
        return "leve"
    if score <= 50:
        return "moderada"
    if score <= 75:
        return "alta"
    return "crítica"


def _build_fact(
    save_uid: str,
    game_date: str,
    fact_type: str,
    category: str,
    title: str,
    summary: str,
    importance: int,
    confidence: float,
    entities: Dict[str, Any],
    source_refs: List[Dict[str, Any]],
    signals: Dict[str, Any],
    dedupe_group: str,
    eligible_for_news: bool = True,
    eligible_for_home: bool = True,
    eligible_for_conference: bool = True,
) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "fact_id": f"{save_uid}:{game_date}:{dedupe_group}",
        "save_uid": save_uid,
        "game_date": game_date,
        "fact_type": fact_type,
        "category": category,
        "title": title,
        "summary": summary,
        "importance": int(importance),
        "confidence": float(confidence),
        "status": "active",
        "entities": entities,
        "source_refs": source_refs,
        "signals": signals,
        "editorial_flags": {
            "eligible_for_news": eligible_for_news,
            "eligible_for_home": eligible_for_home,
            "eligible_for_conference": eligible_for_conference,
            "dedupe_group": dedupe_group,
        },
        "created_at": now,
        "updated_at": now,
    }


def _slot_for_fact(fact: Dict[str, Any]) -> str:
    mapping = {
        "important_win": "lead",
        "important_loss": "lead",
        "positive_streak": "analysis",
        "winless_streak": "lead",
        "board_pressure_active": "environment",
        "board_ultimatum_active": "environment",
        "key_player_in_form": "analysis",
        "reserve_frustrated": "backstage",
        "critical_injury": "backstage",
        "return_from_injury": "backstage",
        "market_offer_strong": "market",
        "market_rumor_hot": "market",
        "locker_room_tension": "backstage",
        "tactical_identity_shift": "analysis",
        "season_arc_milestone": "environment",
    }
    return mapping.get(str(fact.get("fact_type") or ""), "environment")


def _article_kind_for_slot(slot: str) -> str:
    if slot == "analysis":
        return "analysis"
    if slot == "market":
        return "rumor"
    if slot == "backstage":
        return "internal_note"
    if slot == "environment":
        return "press_echo"
    return "news"


def _render_article_from_fact(fact: Dict[str, Any]) -> Dict[str, Any]:
    slot = _slot_for_fact(fact)
    impact = _impact_from_importance(_to_int(fact.get("importance"), 50))
    title = str(fact.get("title") or "")
    summary = str(fact.get("summary") or "")
    category = str(fact.get("category") or "")
    fact_type = str(fact.get("fact_type") or "")
    body = [
        summary,
        "O movimento altera a leitura do momento da carreira e entra no radar das próximas decisões.",
    ]
    why_it_matters = "O tema afeta diretamente a percepção pública e a margem de decisão do treinador."
    club_effects = ["Aumenta o peso do próximo ciclo de decisões no clube."]
    tags = []
    if category == "match":
        tags.extend(["Partida", "Competição"])
    if category == "market":
        tags.append("Mercado")
    if category == "board":
        tags.append("Diretoria")
    if category == "locker_room":
        tags.append("Vestiário")
    if category == "medical":
        tags.append("Lesão")
    if fact_type == "important_win":
        body = [
            "A vitória recente fortalece a leitura de recuperação e aumenta a margem de confiança no projeto técnico.",
            "O resultado também reposiciona a equipe no debate público sobre competitividade e consistência.",
        ]
        why_it_matters = "Sequências positivas alteram pressão, expectativa da torcida e narrativa da temporada."
        club_effects = ["Melhora o ambiente interno.", "Reduz pressão imediata sobre o comando técnico."]
    elif fact_type == "important_loss":
        body = [
            "A derrota amplia o debate sobre estabilidade esportiva e força respostas no curto prazo.",
            "A comissão passa a operar sob leitura pública mais dura nas próximas partidas.",
        ]
        why_it_matters = "Resultados negativos próximos um do outro aceleram pressão institucional e editorial."
        club_effects = ["Eleva a cobrança externa.", "Aumenta sensibilidade da próxima coletiva."]
    elif fact_type in {"positive_streak", "winless_streak"}:
        body = [
            summary,
            "A sequência recente passa a definir a interpretação central do momento competitivo da equipe.",
        ]
        why_it_matters = "A forma recente orienta expectativas, críticas e decisões de gestão."
        club_effects = ["Muda o tom da cobertura.", "Redefine urgências técnicas e institucionais."]
    elif fact_type in {"reserve_frustrated", "locker_room_tension"}:
        body = [
            summary,
            "Nos bastidores, o tema afeta confiança, comunicação interna e leitura de meritocracia.",
        ]
        why_it_matters = "Questões de vestiário costumam transbordar rapidamente para clima de elenco e coletiva."
        club_effects = ["Aumenta risco de ruído interno.", "Pode afetar moral e confiança."]
    elif fact_type in {"market_offer_strong", "market_rumor_hot"}:
        body = [
            summary,
            "A movimentação de mercado pressiona o planejamento e pode alterar prioridades esportivas no elenco.",
        ]
        why_it_matters = "Mercado mexe com continuidade técnica, reposição e percepção pública do planejamento."
        club_effects = ["Reabre discussões sobre reposição.", "Eleva atenção em posições sensíveis."]
    elif fact_type in {"critical_injury", "return_from_injury"}:
        body = [
            summary,
            "A disponibilidade do elenco volta ao centro da discussão técnica e do planejamento imediato.",
        ]
        why_it_matters = "Lesões e retornos mudam escalação, carga física e leitura de risco competitivo."
        club_effects = ["Afeta gestão de minutos.", "Muda pressão sobre profundidade do elenco."]
    elif fact_type in {"board_pressure_active", "board_ultimatum_active", "season_arc_milestone"}:
        body = [
            summary,
            "O tema amplia o peso institucional do momento e redefine o enquadramento narrativo da carreira.",
        ]
        why_it_matters = "Pressão e marcos de temporada são gatilhos fortes para home, feed e coletiva."
        club_effects = ["Eleva o valor simbólico da próxima decisão.", "Aumenta sensibilidade da imprensa."]
    elif fact_type == "key_player_in_form":
        body = [
            summary,
            "O rendimento individual passa a sustentar parte importante do debate técnico e das escolhas do treinador.",
        ]
        why_it_matters = "Jogadores em alta costumam puxar expectativa, cobrança por minutos e narrativa pública."
        club_effects = ["Reforça opções de escalação.", "Cria pauta natural para imprensa e torcida."]
    entities = dict(fact.get("entities") or {})
    return {
        "slot": slot,
        "kind": _article_kind_for_slot(slot),
        "priority": _to_int(fact.get("importance"), 50),
        "impact": impact,
        "headline": title,
        "subheadline": summary,
        "lead": summary,
        "body": body,
        "why_it_matters": why_it_matters,
        "club_effects": club_effects,
        "tags": tags,
        "entities": {
            "club": entities.get("club_names") or [],
            "players": entities.get("player_names") or [],
            "staff": entities.get("staff_labels") or [],
            "competitions": entities.get("competition_names") or [],
        },
        "source_facts": [
            {
                "fact_type": fact.get("fact_type"),
                "source": (fact.get("source_refs") or [{}])[0].get("source", "career_facts"),
                "confidence": fact.get("confidence"),
            }
        ],
        "cover_image_url": None,
        "published_at": datetime.utcnow().isoformat(),
    }


def _select_editorial_stories(facts: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    ranked = sorted(
        [fact for fact in facts if bool((fact.get("editorial_flags") or {}).get("eligible_for_news"))],
        key=lambda item: (-_to_int(item.get("importance"), 0), -int(_to_float(item.get("confidence"), 0) * 1000)),
    )
    used_groups = set()
    stories: List[Dict[str, Any]] = []
    slot_candidates = {slot: [] for slot in SLOT_ORDER}
    for fact in ranked:
        slot_candidates[_slot_for_fact(fact)].append(fact)
    for slot in SLOT_ORDER:
        for fact in slot_candidates.get(slot, []):
            dedupe_group = str((fact.get("editorial_flags") or {}).get("dedupe_group") or fact.get("dedupe_group") or "")
            if dedupe_group in used_groups:
                continue
            used_groups.add(dedupe_group)
            stories.append(_render_article_from_fact(fact))
            break
    if len(stories) < min(limit, 5):
        for fact in ranked:
            dedupe_group = str((fact.get("editorial_flags") or {}).get("dedupe_group") or fact.get("dedupe_group") or "")
            if dedupe_group in used_groups:
                continue
            used_groups.add(dedupe_group)
            stories.append(_render_article_from_fact(fact))
            if len(stories) >= min(limit, 5):
                break
    return stories[: min(limit, 5)]


def _ensure_facts(
    save_uid: str,
    game_date: str,
    state: Dict[str, Any],
    coach_profile: Dict[str, Any],
    management_state: Dict[str, Any],
    board_active: Optional[Dict[str, Any]],
    crisis_active: Optional[Dict[str, Any]],
    season_arc_active: Optional[Dict[str, Any]],
    market_rumors: List[Dict[str, Any]],
    player_relations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    existing = get_career_facts(save_uid=save_uid, game_date=game_date)
    if existing:
        return existing
    user_team_id = _user_team_id(state)
    club = dict(state.get("club") or {})
    fixtures = list(state.get("fixtures") or [])
    squad = list(state.get("squad") or [])
    injuries = list(state.get("injuries") or [])
    tactical = dict((management_state.get("tactical") or {}))
    locker = dict((management_state.get("locker_room") or {}))
    medical = dict((management_state.get("medical") or {}))
    competition_names = _competition_name_index(save_uid)
    current_game_date_raw = _game_date_value(state)
    results = _recent_results(fixtures, user_team_id, limit=5, game_date_raw=current_game_date_raw)
    last_fixture = _decorate_fixture(_last_completed_fixture(fixtures, user_team_id), user_team_id, competition_names)
    facts: List[Dict[str, Any]] = []
    team_name = str(club.get("team_name") or "Clube")
    competition_name = str((last_fixture or {}).get("competition_name") or club.get("competition_name") or "")
    if last_fixture:
        letter = _result_letter(last_fixture, user_team_id)
        opponent_name = str(
            last_fixture.get("away_team_name") if _to_int(last_fixture.get("home_team_id"), -1) == user_team_id else last_fixture.get("home_team_name")
        )
        score = f"{last_fixture.get('home_score')} x {last_fixture.get('away_score')}"
        if letter == "W":
            facts.append(
                _build_fact(
                    save_uid=save_uid,
                    game_date=game_date,
                    fact_type="important_win",
                    category="match",
                    title=f"{team_name} vence e reforça o bom momento",
                    summary=f"Resultado em {score} contra {opponent_name} aumenta a confiança para a sequência.",
                    importance=88,
                    confidence=0.95,
                    entities={
                        "club_ids": [user_team_id],
                        "club_names": [team_name],
                        "player_ids": [],
                        "player_names": [],
                        "staff_labels": ["manager"],
                        "competition_ids": [_to_int(last_fixture.get("competition_id"), 0)],
                        "competition_names": [competition_name] if competition_name else [],
                    },
                    source_refs=[{"source": "state.fixtures", "ref_id": str(last_fixture.get("id") or "")}],
                    signals={"trend": "positive", "score": score},
                    dedupe_group=f"last_match_{game_date}",
                )
            )
        elif letter == "L":
            facts.append(
                _build_fact(
                    save_uid=save_uid,
                    game_date=game_date,
                    fact_type="important_loss",
                    category="match",
                    title=f"{team_name} entra sob cobrança após derrota",
                    summary=f"O revés em {score} contra {opponent_name} aumenta a pressão para a próxima resposta.",
                    importance=90,
                    confidence=0.95,
                    entities={
                        "club_ids": [user_team_id],
                        "club_names": [team_name],
                        "player_ids": [],
                        "player_names": [],
                        "staff_labels": ["manager"],
                        "competition_ids": [_to_int(last_fixture.get("competition_id"), 0)],
                        "competition_names": [competition_name] if competition_name else [],
                    },
                    source_refs=[{"source": "state.fixtures", "ref_id": str(last_fixture.get("id") or "")}],
                    signals={"trend": "negative", "score": score},
                    dedupe_group=f"last_match_{game_date}",
                )
            )
    if len(results) >= 3 and results[:3] == ["W", "W", "W"]:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="positive_streak",
                category="form",
                title=f"{team_name} vive sequência positiva",
                summary=f"A série recente de resultados sustenta uma leitura pública de crescimento competitivo.",
                importance=78,
                confidence=0.9,
                entities={"club_ids": [user_team_id], "club_names": [team_name]},
                source_refs=[{"source": "state.fixtures", "ref_id": "recent_form"}],
                signals={"trend": "positive", "last_5": results},
                dedupe_group="recent_form",
            )
        )
    if len(results) >= 4 and "W" not in results[:4]:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="winless_streak",
                category="form",
                title=f"{team_name} precisa reagir à sequência sem vencer",
                summary="A ausência de vitórias aumenta a cobrança institucional e o peso emocional do próximo jogo.",
                importance=86,
                confidence=0.92,
                entities={"club_ids": [user_team_id], "club_names": [team_name]},
                source_refs=[{"source": "state.fixtures", "ref_id": "recent_form"}],
                signals={"trend": "negative", "last_5": results},
                dedupe_group="recent_form",
            )
        )
    if board_active and str(board_active.get("status") or "") == "active":
        fact_type = "board_ultimatum_active" if str(board_active.get("challenge_type") or "") == "ULTIMATUM" else "board_pressure_active"
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type=fact_type,
                category="board",
                title=str(board_active.get("title") or "Diretoria aumenta a pressão"),
                summary=str(board_active.get("description") or "A diretoria elevou o nível de cobrança no curto prazo."),
                importance=92,
                confidence=0.98,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["board", "manager"]},
                source_refs=[{"source": "board_active_challenge", "ref_id": str(board_active.get("id") or "")}],
                signals={"pressure_delta": 18},
                dedupe_group="board_pressure",
            )
        )
    if crisis_active and str(crisis_active.get("status") or "") == "active":
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="board_pressure_active",
                category="season",
                title="Crise em curso redefine o contexto da carreira",
                summary=str(crisis_active.get("summary") or "O ambiente do clube exige reação imediata."),
                importance=93,
                confidence=0.95,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["manager", "board"]},
                source_refs=[{"source": "crisis_active_arc", "ref_id": str(crisis_active.get("id") or "")}],
                signals={"pressure_delta": 22},
                dedupe_group="crisis_context",
            )
        )
    if market_rumors:
        strongest_rumor = max(market_rumors, key=lambda item: _to_int(item.get("confidence_level"), 0))
        if _to_int(strongest_rumor.get("confidence_level"), 0) >= 70:
            facts.append(
                _build_fact(
                    save_uid=save_uid,
                    game_date=game_date,
                    fact_type="market_rumor_hot",
                    category="market",
                    title=str(strongest_rumor.get("headline") or "Mercado ganha força nos bastidores"),
                    summary=str(strongest_rumor.get("content") or "A movimentação de mercado ganhou tração nos bastidores."),
                    importance=max(70, _to_int(strongest_rumor.get("confidence_level"), 70)),
                    confidence=min(0.99, _to_int(strongest_rumor.get("confidence_level"), 70) / 100.0),
                    entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["manager"]},
                    source_refs=[{"source": "market_rumors_recent", "ref_id": str(strongest_rumor.get("id") or "")}],
                    signals={"media_heat": _to_int(strongest_rumor.get("confidence_level"), 70)},
                    dedupe_group="market_primary",
                )
            )
    if injuries:
        injury = dict(injuries[0] or {})
        injury_name = _player_name(injury)
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="critical_injury",
                category="medical",
                title=f"{injury_name} entra em alerta médico",
                summary="O departamento médico passa a ser parte central do planejamento imediato do elenco.",
                importance=82,
                confidence=0.92,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "player_ids": [_to_int(injury.get("playerid"), 0)], "player_names": [injury_name]},
                source_refs=[{"source": "state.injuries", "ref_id": str(injury.get("playerid") or "")}],
                signals={"injury_risk": _to_int(medical.get("injury_risk_index"), 50)},
                dedupe_group="medical_primary",
            )
        )
    frustrated = next(
        (
            row
            for row in player_relations
            if _to_int(row.get("frustration"), 0) >= 45 or str(row.get("status_label") or "") in {"insatisfeito", "frustrado"}
        ),
        None,
    )
    if frustrated:
        frustrated_name = str(frustrated.get("player_name") or "Jogador do elenco")
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="reserve_frustrated",
                category="locker_room",
                title=f"{frustrated_name} entra no radar dos bastidores",
                summary="A gestão de papéis e minutos passa a exigir mais cuidado no vestiário.",
                importance=76,
                confidence=0.88,
                entities={
                    "club_ids": [user_team_id],
                    "club_names": [team_name],
                    "player_ids": [_to_int(frustrated.get("playerid"), 0)],
                    "player_names": [frustrated_name],
                },
                source_refs=[{"source": "player_relations_recent", "ref_id": str(frustrated.get("id") or "")}],
                signals={"morale_delta": -8},
                dedupe_group="locker_room_primary",
            )
        )
    cohesion = locker.get("cohesion")
    low_morale_count = _to_int(locker.get("low_morale_count"), 0)
    if (_to_int(cohesion, 55) <= 45) or low_morale_count >= 3:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="locker_room_tension",
                category="locker_room",
                title="O clima interno pede atenção",
                summary="Os sinais do vestiário indicam necessidade de gestão mais fina de confiança e papéis.",
                importance=80,
                confidence=0.9,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["manager"]},
                source_refs=[{"source": "career_management_state", "ref_id": "locker_room"}],
                signals={"morale_delta": -6},
                dedupe_group="locker_room_primary",
            )
        )
    stability = _to_int(tactical.get("stability"), 55)
    if stability <= 45:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="tactical_identity_shift",
                category="season",
                title="A identidade tática entra em revisão",
                summary="A leitura do momento sugere ajustes de rota na forma como a equipe compete.",
                importance=68,
                confidence=0.82,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["manager"]},
                source_refs=[{"source": "career_management_state", "ref_id": "tactical"}],
                signals={"trend": "neutral"},
                dedupe_group="tactical_shift",
            )
        )
    if season_arc_active and _to_int(season_arc_active.get("current_milestone"), 1) > 1:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="season_arc_milestone",
                category="season",
                title=str(season_arc_active.get("title") or "Arco da temporada em andamento"),
                summary=str(season_arc_active.get("theme") or "A temporada ganhou novo peso narrativo e competitivo."),
                importance=72,
                confidence=0.88,
                entities={"club_ids": [user_team_id], "club_names": [team_name], "staff_labels": ["manager"]},
                source_refs=[{"source": "season_arc_active", "ref_id": str(season_arc_active.get("id") or "")}],
                signals={"milestone": _to_int(season_arc_active.get("current_milestone"), 1)},
                dedupe_group="season_arc_primary",
            )
        )
    squad_sorted = sorted(
        squad,
        key=lambda item: (_to_int(item.get("form"), -1), _to_float(item.get("overall_live"), _to_float(item.get("overallrating"), 0))),
        reverse=True,
    )
    if squad_sorted and _to_int(squad_sorted[0].get("form"), -1) >= 3:
        top_player = dict(squad_sorted[0])
        top_player_name = _player_name(top_player)
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="key_player_in_form",
                category="player",
                title=f"{top_player_name} sustenta o debate técnico",
                summary="O desempenho recente do jogador reforça sua centralidade nas próximas decisões de escalação.",
                importance=66,
                confidence=0.84,
                entities={
                    "club_ids": [user_team_id],
                    "club_names": [team_name],
                    "player_ids": [_to_int(top_player.get("playerid"), 0)],
                    "player_names": [top_player_name],
                },
                source_refs=[{"source": "state.squad", "ref_id": str(top_player.get("playerid") or "")}],
                signals={"trend": "positive"},
                dedupe_group="player_form_primary",
            )
        )
    return replace_career_facts(save_uid=save_uid, game_date=game_date, facts=facts)


def _build_news_feed_daily_internal(save_uid: str, game_date: str, limit: int, rebuild: bool) -> Dict[str, Any]:
    state = _read_state()
    package = None if rebuild else get_news_daily_package(save_uid=save_uid, game_date=game_date)
    coach_profile = get_or_create_coach_profile(save_uid)
    management_state = get_or_create_career_management_state(save_uid)
    board_active = get_active_board_challenge(save_uid, challenge_type="ULTIMATUM")
    crisis_active = get_active_crisis_arc(save_uid)
    season_arc_active = get_active_season_arc(save_uid)
    market_rumors = get_recent_market_rumors(limit=8, save_uid=save_uid)
    player_relations = get_player_relations(save_uid, limit=40)
    timeline_recent = get_recent_timeline_entries(limit=8, save_uid=save_uid)
    external_events = get_recent_external_event_logs(save_uid, limit=8)
    if package is None:
        facts = _ensure_facts(
            save_uid=save_uid,
            game_date=game_date,
            state=state,
            coach_profile=coach_profile,
            management_state=management_state,
            board_active=board_active,
            crisis_active=crisis_active,
            season_arc_active=season_arc_active,
            market_rumors=market_rumors,
            player_relations=player_relations,
        )
        stories = _select_editorial_stories(facts=facts, limit=limit)
        density_level = "full" if len(stories) >= 5 else ("medium" if len(stories) >= 3 else "light")
        lead_angle = stories[0]["headline"] if stories else "contexto diário"
        package = replace_news_daily_package(
            save_uid=save_uid,
            game_date=game_date,
            edition_label="Diário da Carreira",
            lead_angle=lead_angle,
            density_level=density_level,
            layout_hints={
                "stack_order": SLOT_ORDER,
                "fullscreen_default_article_id": None,
                "show_more_available": False,
            },
            stories=stories,
        )
    stories_payload = list(package.get("stories") or [])[: min(limit, 5)]
    if package.get("layout_hints") and stories_payload:
        package["layout_hints"]["fullscreen_default_article_id"] = stories_payload[0].get("article_id")
    secondary_modules = {
        "rumors": market_rumors[:3],
        "timeline_hooks": [
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "phase": row.get("phase"),
                "importance": row.get("importance"),
            }
            for row in timeline_recent[:3]
        ],
        "external_signals": [
            {
                "event_id_raw": row.get("event_id_raw"),
                "category": row.get("category"),
                "importance": row.get("importance"),
                "summary": str((row.get("payload") or {}).get("event_name") or row.get("event_name_raw") or "Sinal externo recente"),
            }
            for row in external_events[:3]
        ],
    }
    return {
        "contract_version": 1,
        "save_uid": save_uid,
        "game_date": game_date,
        "generated_at": datetime.utcnow().isoformat(),
        "editorial_package": {
            "package_id": package.get("package_id"),
            "edition_label": package.get("edition_label"),
            "lead_angle": package.get("lead_angle"),
            "density_level": package.get("density_level"),
            "stories_count": len(stories_payload),
        },
        "stories": stories_payload,
        "secondary_modules": secondary_modules,
        "layout_hints": package.get("layout_hints") or {
            "stack_order": SLOT_ORDER,
            "fullscreen_default_article_id": stories_payload[0].get("article_id") if stories_payload else None,
            "show_more_available": False,
        },
    }


def build_news_feed_daily(save_uid: str, date: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    state = _read_state()
    game_date = date or _iso_game_date(state)
    return _build_news_feed_daily_internal(save_uid=save_uid, game_date=game_date, limit=limit, rebuild=False)


def rebuild_news_feed_daily(save_uid: str, date: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    state = _read_state()
    game_date = date or _iso_game_date(state)
    return _build_news_feed_daily_internal(save_uid=save_uid, game_date=game_date, limit=limit, rebuild=True)


def _alert_item(severity: str, kind: str, title: str, message: str, cta_label: str, cta_target: str, source: str) -> Dict[str, Any]:
    return {
        "id": f"{kind}:{title}",
        "type": kind,
        "severity": severity,
        "title": title,
        "message": message,
        "cta_label": cta_label,
        "cta_target": cta_target,
        "source": source,
    }


def build_dashboard_home(
    save_uid: str,
    news_limit: int = 5,
    timeline_limit: int = 6,
    alerts_limit: int = 6,
) -> Dict[str, Any]:
    state = _read_state()
    game_date = _iso_game_date(state)
    manager = dict(state.get("manager") or {})
    club = dict(state.get("club") or {})
    fixtures = list(state.get("fixtures") or [])
    squad = list(state.get("squad") or [])
    injuries = list(state.get("injuries") or [])
    user_team_id = _user_team_id(state)
    coach_profile = get_or_create_coach_profile(save_uid)
    management_state = get_or_create_career_management_state(save_uid)
    board_active = get_active_board_challenge(save_uid, challenge_type="ULTIMATUM")
    crisis_active = get_active_crisis_arc(save_uid)
    season_arc_active = get_active_season_arc(save_uid)
    market_rumors = get_recent_market_rumors(limit=5, save_uid=save_uid)
    player_relations = get_player_relations(save_uid, limit=50)
    timeline_recent = get_recent_timeline_entries(limit=timeline_limit, save_uid=save_uid)
    news_payload = build_news_feed_daily(save_uid=save_uid, date=game_date, limit=min(news_limit, 5))
    season_context = build_season_context(save_uid=save_uid, state=state)
    next_fixture = season_context.get("next_fixture")
    recent_form = list(((season_context.get("recent_form") or {}).get("last_5")) or [])
    league_table = season_context.get("league_table")
    squad_overview = build_squad_overview(save_uid=save_uid, state=state)
    locker = dict((management_state.get("locker_room") or {}))
    finance = dict((management_state.get("finance") or {}))
    medical = dict((management_state.get("medical") or {}))
    hot_players = [
        _player_name(player)
        for player in sorted(squad_overview, key=lambda item: (_to_int(item.get("form"), 0), _to_int(item.get("overall"), 0)), reverse=True)[:3]
        if _to_int(player.get("form"), 0) >= 3
    ]
    fatigue_watch = [
        _player_name(player)
        for player in sorted(squad_overview, key=lambda item: _to_int(item.get("fitness"), 100))[:3]
        if player.get("fitness") is not None and _to_int(player.get("fitness"), 100) < 60
    ]
    contract_watch = [
        _player_name(player)
        for player in squad_overview
        if bool(player.get("contract_until_label")) and _to_int(player.get("age"), 0) > 0
    ][:3]
    unhappy_count = sum(1 for item in player_relations if _to_int(item.get("frustration"), 0) >= 45)
    board_confidence_score = _clamp(_to_int(coach_profile.get("reputation_score"), 50) - (18 if board_active else 0) - (20 if crisis_active else 0))
    injury_risk_score = _clamp(_to_int(medical.get("injury_risk_index"), len(injuries) * 15))
    financial_pressure_score = _clamp(_to_int(finance.get("cash_pressure_index"), 0))
    locker_room_score = _clamp(_to_int(locker.get("cohesion"), _to_int(locker.get("trust_avg"), 55)))
    fan_sentiment_score = _clamp(_to_int(coach_profile.get("fan_sentiment_score"), 50))
    alerts: List[Dict[str, Any]] = []
    if board_active:
        alerts.append(
            _alert_item(
                "critical" if str(board_active.get("challenge_type")) == "ULTIMATUM" else "high",
                "board",
                str(board_active.get("title") or "Diretoria em alerta"),
                str(board_active.get("description") or "A diretoria aumentou a cobrança."),
                "Abrir painel institucional",
                "/clube",
                "board_active_challenge",
            )
        )
    if crisis_active:
        alerts.append(
            _alert_item(
                "high",
                "match",
                "Crise em curso",
                str(crisis_active.get("summary") or "O ambiente competitivo exige reação imediata."),
                "Ver contexto completo",
                "/bastidores",
                "crisis_active_arc",
            )
        )
    if injury_risk_score >= 60:
        alerts.append(
            _alert_item(
                "high",
                "medical",
                "Carga física exige atenção",
                "Os indicadores médicos sugerem risco elevado para a sequência de jogos.",
                "Abrir status físico",
                "/elenco",
                "career_management_state.medical",
            )
        )
    if locker_room_score <= 45 or unhappy_count > 0:
        alerts.append(
            _alert_item(
                "medium",
                "locker_room",
                "Clima do elenco pede gestão fina",
                "Sinais de frustração e confiança irregular exigem controle de ambiente.",
                "Abrir bastidores",
                "/bastidores",
                "career_management_state.locker_room",
            )
        )
    if market_rumors and _to_int(market_rumors[0].get("confidence_level"), 0) >= 80:
        alerts.append(
            _alert_item(
                "medium",
                "market",
                str(market_rumors[0].get("headline") or "Mercado ganha força"),
                str(market_rumors[0].get("content") or "Há movimento relevante no planejamento de elenco."),
                "Abrir mercado",
                "/mercado",
                "market_rumors_recent",
            )
        )
    alerts = alerts[:alerts_limit]
    hero_state_label = "estavel"
    hero_state_tone = "neutral"
    if crisis_active:
        hero_state_label = "em_crise"
        hero_state_tone = "danger"
    elif board_active:
        hero_state_label = "pressionado"
        hero_state_tone = "warning"
    elif fan_sentiment_score >= 60 and _points_from_results(recent_form) >= 7:
        hero_state_label = "em_alta"
        hero_state_tone = "positive"
    strategic_primary = "proteger estabilidade do clube"
    strategic_secondary: Optional[str] = None
    why_now = "O contexto atual exige decisões coerentes entre desempenho, ambiente e narrativa pública."
    if board_active:
        strategic_primary = "responder pressão da diretoria"
        strategic_secondary = "evitar ampliação da crise"
        why_now = "Há cobrança institucional ativa e qualquer tropeço amplia a pressão."
    elif injury_risk_score >= 60:
        strategic_primary = "gerir desgaste do elenco"
        strategic_secondary = "preservar titulares-chave"
        why_now = "A carga física elevada pode afetar rendimento e disponibilidade."
    elif unhappy_count > 0:
        strategic_primary = "estabilizar o vestiário"
        strategic_secondary = "controlar papéis e minutos"
        why_now = "Sinais de frustração exigem resposta antes de virar ruído maior."
    return {
        "contract_version": 1,
        "save_uid": save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "snapshot": {
            "game_date": {
                "day": _to_int(((state.get("meta") or {}).get("game_date") or {}).get("day"), 0) or None,
                "month": _to_int(((state.get("meta") or {}).get("game_date") or {}).get("month"), 0) or None,
                "year": _to_int(((state.get("meta") or {}).get("game_date") or {}).get("year"), 0) or None,
                "label": _label_game_date(game_date),
            },
            "club": {
                "team_id": user_team_id,
                "team_name": str(club.get("team_name") or "Clube"),
                "manager_name": _manager_name(manager),
                "crest_url": None,
                "competition_focus": str((next_fixture or {}).get("competition_name") or (league_table or {}).get("competition_name") or ""),
                "league_position": (league_table or {}).get("rank"),
                "league_points": (league_table or {}).get("points"),
            },
            "hero": {
                "headline": f"{str(club.get('team_name') or 'O clube')} entra em novo ciclo de decisões",
                "subheadline": why_now,
                "state_label": hero_state_label,
                "state_tone": hero_state_tone,
            },
        },
        "hero_panel": {
            "next_fixture": {
                "fixture_id": next_fixture.get("id"),
                "competition_id": next_fixture.get("competition_id"),
                "competition_name": next_fixture.get("competition_name"),
                "home_team_id": next_fixture.get("home_team_id"),
                "home_team_name": next_fixture.get("home_team_name"),
                "away_team_id": next_fixture.get("away_team_id"),
                "away_team_name": next_fixture.get("away_team_name"),
                "date_raw": next_fixture.get("date_raw"),
                "time_raw": next_fixture.get("time_raw"),
                "date_label": next_fixture.get("date_label"),
                "time_label": next_fixture.get("time_label"),
                "opponent_name": next_fixture.get("opponent_name"),
                "home_away": next_fixture.get("home_away"),
                "is_user_team_fixture": True,
                "narrative_angle": "Próximo compromisso com potencial de redefinir o tom público da carreira.",
            } if next_fixture else None,
            "recent_form": {
                "last_5": recent_form,
                "points_last_5": _points_from_results(recent_form),
                "trend_label": "positivo" if _points_from_results(recent_form) >= 7 else ("instável" if _points_from_results(recent_form) >= 4 else "pressionado"),
            },
            "league_table": league_table,
            "club_health": {
                "locker_room_score": locker_room_score,
                "fan_sentiment_score": fan_sentiment_score,
                "board_confidence_score": board_confidence_score,
                "injury_risk_score": injury_risk_score,
                "financial_pressure_score": financial_pressure_score,
            },
            "strategic_focus": {
                "primary_decision": strategic_primary,
                "secondary_decision": strategic_secondary,
                "why_now": why_now,
            },
        },
        "cards": {
            "next_match": {
                "title": "Próximo jogo",
                "importance": 90 if next_fixture else 55,
                "summary": f"{next_fixture.get('home_team_name')} x {next_fixture.get('away_team_name')}" if next_fixture else "Sem próximo jogo identificado.",
                "meta": " • ".join([item for item in [next_fixture.get("date_label"), next_fixture.get("competition_name")] if item]) if next_fixture else None,
                "cta": "Ver análise da partida",
            },
            "squad": {
                "title": "Elenco",
                "highlights": {
                    "in_form_count": len(hot_players),
                    "fatigue_risk_count": len(fatigue_watch),
                    "unhappy_count": unhappy_count,
                    "injured_count": len(injuries),
                },
                "cta": "Abrir gestão do elenco",
            },
            "news": {
                "title": "Notícias do dia",
                "stories_count": len(news_payload.get("stories") or []),
                "lead_story_title": ((news_payload.get("stories") or [{}])[0]).get("headline") if news_payload.get("stories") else None,
                "cta": "Abrir feed completo",
            },
            "critical_alerts": {
                "title": "Alertas críticos",
                "count": len(alerts),
                "top_alert": alerts[0]["title"] if alerts else None,
                "cta": "Ver todos os alertas",
            },
            "league": {
                "title": "Liga",
                "rank": (league_table or {}).get("rank"),
                "points": (league_table or {}).get("points"),
                "competition_name": (league_table or {}).get("competition_name"),
                "cta": "Abrir tabela",
            },
        },
        "radars": {
            "squad": {
                "hot_players": hot_players,
                "fatigue_watch": fatigue_watch,
                "contract_watch": contract_watch,
                "market_interest": [str(item.get("headline") or "") for item in market_rumors[:2]],
            },
            "board": {
                "objective_label": str((board_active or {}).get("title") or "estabilidade institucional"),
                "status": str((board_active or {}).get("status") or "inactive"),
                "risk_level": _score_label(100 - board_confidence_score, positive_high=False),
                "message": str((board_active or {}).get("description") or "Sem objetivo institucional crítico ativo."),
            },
            "season": {
                "arc_title": str((season_arc_active or {}).get("title") or "Temporada em andamento"),
                "arc_status": str((season_arc_active or {}).get("status") or "inactive"),
                "phase_label": str((season_arc_active or {}).get("theme") or "regular"),
                "milestone_progress": f"{_to_int((season_arc_active or {}).get('current_milestone'), 0)}/{_to_int((season_arc_active or {}).get('max_milestones'), 0)}" if season_arc_active else "0/0",
            },
            "climate": {
                "locker_room_label": _score_label(locker_room_score, positive_high=True),
                "fan_mood_label": _score_label(_clamp(int((fan_sentiment_score * 0.65) + (_points_from_results(recent_form) * 5))), positive_high=True),
                "press_tone_label": "reativa" if alerts else "estável",
                "institutional_pressure_label": _score_label(100 - board_confidence_score, positive_high=False),
            },
        },
        "alerts": alerts,
        "daily_news_preview": [
            {
                "article_id": story.get("article_id"),
                "slot": story.get("slot"),
                "headline": story.get("headline"),
                "subheadline": story.get("subheadline"),
                "impact": story.get("impact"),
                "cover_image_url": story.get("cover_image_url"),
                "published_at": story.get("published_at"),
            }
            for story in (news_payload.get("stories") or [])[: min(news_limit, 5)]
        ],
        "timeline_preview": timeline_recent[:timeline_limit],
        "source_map": {
            "state": bool(state),
            "coach_profile": True,
            "career_management_state": True,
            "board_active_challenge": board_active is not None,
            "crisis_active_arc": crisis_active is not None,
            "season_arc_active": season_arc_active is not None,
            "news_feed_daily": True,
        },
    }


def build_finance_hub(
    save_uid: Optional[str] = None,
    ledger_limit: int = 80,
    transactions_limit: int = 40,
) -> Dict[str, Any]:
    state = _read_state()
    effective_save_uid = save_uid or str(((state.get("meta") or {}).get("save_uid")) or "default_save")
    save_data = _read_save_data()
    management_state = get_or_create_career_management_state(effective_save_uid)
    finance_state = dict((management_state.get("finance") or {}))
    club = dict(state.get("club") or {})
    game_date = ((state.get("meta") or {}).get("game_date")) or {}
    game_year = _to_int(game_date.get("year"), date.today().year)
    game_month = _to_int(game_date.get("month"), date.today().month)
    squad = list(state.get("squad") or save_data.get("squad") or [])
    ledger = get_recent_finance_ledger(limit=max(ledger_limit, transactions_limit), save_uid=effective_save_uid)
    manager = dict(save_data.get("manager") or {})
    finance_live = dict(state.get("finance_live") or {})
    manager_pref = dict(manager.get("manager_pref") or {})
    manager_pref.update(dict(finance_live.get("manager_pref") or {}))
    manager_info = dict(manager.get("manager_info") or {})
    manager_info.update(dict(finance_live.get("manager_info") or {}))
    manager_history = dict(manager.get("manager_history") or {})
    manager_history.update(dict(finance_live.get("manager_history") or {}))
    finance_live_functions = dict(finance_live.get("discovered_function_values") or {})
    finance_live_contract = dict(finance_live.get("contract_summary") or {})
    finance_live_transfer = dict(finance_live.get("transfer_summary") or {})
    teams = list(state.get("all_teams") or save_data.get("teams") or [])
    finance_candidates = list(save_data.get("finance_table_candidates") or [])
    transfer_history_payload = _read_transfer_history(effective_save_uid)
    transfer_history_items = _normalize_transfer_items(
        transfer_history_payload.get("items") or [],
        user_team_name=str(club.get("team_name") or ""),
    )
    if not transfer_history_items:
        transfer_history_items = _normalize_transfer_items(
            list(save_data.get("transfer_history") or []),
            user_team_name=str(club.get("team_name") or ""),
        )

    transfer_budget_lua = _normalize_manager_amount(club.get("transfer_budget"))
    wage_budget_lua = _normalize_manager_amount(club.get("wage_budget"))
    transfer_budget_save = _normalize_manager_amount(manager_pref.get("transferbudget"))
    transfer_budget_start = _normalize_manager_amount(manager_pref.get("startofseasontransferbudget"))
    wage_budget_save = _normalize_manager_amount(manager_pref.get("wagebudget"))
    wage_budget_start = _normalize_manager_amount(manager_pref.get("startofseasonwagebudget"))
    cash_balance_state = _to_float(finance_state.get("cash_balance"), 0.0)
    transfer_budget = transfer_budget_lua or _to_float(finance_state.get("transfer_budget"), 0.0) or transfer_budget_save or transfer_budget_start
    wage_budget = wage_budget_lua or _to_float(finance_state.get("wage_budget"), 0.0) or wage_budget_save or wage_budget_start
    cash_balance = cash_balance_state or transfer_budget
    if transfer_budget <= 0 and cash_balance > 0:
        transfer_budget = cash_balance
    if 0 < transfer_budget < 1_000_000 and cash_balance > 5_000_000:
        transfer_budget = cash_balance
    if transfer_budget > 0 and cash_balance > (transfer_budget * 3):
        transfer_budget = cash_balance
    team_finance_row = _pick_team_finance_row(str(club.get("team_name") or ""), teams)
    clubworth_raw = _to_float(team_finance_row.get("clubworth"), 0.0)
    clubworth = clubworth_raw * 1000.0 if 0 < clubworth_raw < 1_000_000 else clubworth_raw

    contract_wages_weekly = [_to_float(player.get("contract_wage"), 0.0) for player in squad]
    squad_wage_weekly = _sum_values(contract_wages_weekly)
    if _to_float(finance_live_contract.get("athletes_weekly_wages"), 0.0) > 0:
        squad_wage_weekly = _to_float(finance_live_contract.get("athletes_weekly_wages"), 0.0)
    squad_wage_annual = round(squad_wage_weekly * 52, 2)
    manager_wage_weekly = _to_float(manager.get("wage"), 0.0)
    commission_payroll_weekly = max(
        0.0,
        _to_float(manager_info.get("wage"), 0.0) - manager_wage_weekly,
    )
    wage_staff_annual = round(commission_payroll_weekly * 52, 2)
    total_wage_annual = round(squad_wage_annual + wage_staff_annual + (manager_wage_weekly * 52), 2)
    signon_bonus_total = _sum_values([player.get("signon_bonus") for player in squad])
    if _to_float(finance_live_contract.get("signon_bonus_total"), 0.0) > 0:
        signon_bonus_total = _to_float(finance_live_contract.get("signon_bonus_total"), 0.0)
    performance_bonus_total = 0.0
    for player in squad:
        bonus_value = _to_float(player.get("performancebonusvalue"), 0.0)
        bonus_count = max(0.0, _to_float(player.get("performancebonuscount"), 0.0))
        if bonus_value > 0 and bonus_count > 0:
            performance_bonus_total += bonus_value * bonus_count
    performance_bonus_total = round(performance_bonus_total, 2)
    if _to_float(finance_live_contract.get("performance_bonus_projection"), 0.0) > 0:
        performance_bonus_total = round(_to_float(finance_live_contract.get("performance_bonus_projection"), 0.0), 2)
    wage_utilization = _to_float(finance_state.get("wage_utilization"), 0.0)
    if wage_utilization <= 0 and wage_budget > 0 and total_wage_annual > 0:
        wage_utilization = round(total_wage_annual / wage_budget, 3)

    transfer_sales = round(
        sum(max(0.0, _to_float(item.get("amount"), 0.0)) for item in transfer_history_items if item.get("amount", 0) > 0),
        2,
    )
    transfer_buys = round(
        sum(abs(min(0.0, _to_float(item.get("amount"), 0.0))) for item in transfer_history_items if item.get("amount", 0) < 0),
        2,
    )
    if transfer_sales <= 0 and _to_float(finance_live_transfer.get("sells_total"), 0.0) > 0:
        transfer_sales = round(_to_float(finance_live_transfer.get("sells_total"), 0.0), 2)
    if transfer_buys <= 0 and _to_float(finance_live_transfer.get("buys_total"), 0.0) > 0:
        transfer_buys = round(_to_float(finance_live_transfer.get("buys_total"), 0.0), 2)
    prize_money = _to_float(manager_info.get("totalearnings"), 0.0)

    normalized_ledger: List[Dict[str, Any]] = []
    for entry in ledger:
        amount = _to_float(entry.get("amount"), 0.0)
        period = str(entry.get("period") or f"{game_year:04d}-{game_month:02d}")
        kind = str(entry.get("kind") or "movimento")
        normalized_ledger.append(
            {
                "id": entry.get("id"),
                "period": period,
                "kind": kind,
                "label": _label_from_kind(kind),
                "description": str(entry.get("description") or _label_from_kind(kind)),
                "amount": round(amount, 2),
                "direction": "in" if amount >= 0 else "out",
                "occurred_at": entry.get("created_at"),
            }
        )
    for item in transfer_history_items:
        normalized_ledger.insert(
            0,
            dict(item),
        )
    if not transfer_history_items and _normalize_manager_amount(manager_history.get("bigsellamount")) > 0:
        normalized_ledger.insert(
            0,
            {
                "id": "save:transfer_sale_fallback",
                "period": f"{game_year:04d}-{game_month:02d}",
                "kind": "venda_transferencia_save",
                "label": "Transferências",
                "description": f"Maior venda registrada: {manager_history.get('bigsellplayername') or 'jogador'}",
                "amount": round(_normalize_manager_amount(manager_history.get("bigsellamount")), 2),
                "direction": "in",
                "occurred_at": None,
                "source": "manager_history_fallback",
            },
        )
    if not transfer_history_items and _normalize_manager_amount(manager_history.get("bigbuyamount")) > 0:
        normalized_ledger.insert(
            0,
            {
                "id": "save:transfer_buy_fallback",
                "period": f"{game_year:04d}-{game_month:02d}",
                "kind": "compra_transferencia_save",
                "label": "Transferências",
                "description": f"Maior compra registrada: {manager_history.get('bigbuyplayername') or 'jogador'}",
                "amount": round(-abs(_normalize_manager_amount(manager_history.get("bigbuyamount"))), 2),
                "direction": "out",
                "occurred_at": None,
                "source": "manager_history_fallback",
            },
        )
    if prize_money > 0:
        normalized_ledger.insert(
            0,
            {
                "id": "save:total_earnings",
                "period": f"{game_year:04d}-{game_month:02d}",
                "kind": "premio_save",
                "label": "Prêmios em dinheiro",
                "description": "Acumulado registrado no save",
                "amount": round(prize_money, 2),
                "direction": "in",
                "occurred_at": None,
            },
        )
    if transfer_sales <= 0:
        transfer_sales = round(
            sum(max(0.0, _to_float(item.get("amount"), 0.0)) for item in normalized_ledger if str(item.get("label") or "") == "Transferências"),
            2,
        )
    if transfer_buys <= 0:
        transfer_buys = round(
            sum(abs(min(0.0, _to_float(item.get("amount"), 0.0))) for item in normalized_ledger if str(item.get("label") or "") == "Transferências"),
            2,
        )

    receitas_total = round(sum(item["amount"] for item in normalized_ledger if item["amount"] > 0), 2)
    despesas_total = round(abs(sum(item["amount"] for item in normalized_ledger if item["amount"] < 0)), 2)
    lucro = round(receitas_total - despesas_total, 2)

    receitas_map: Dict[str, float] = {
        "Transferências": round(max(0.0, transfer_sales), 2),
        "Prêmios em dinheiro": round(max(0.0, prize_money), 2),
        "Sócio torcedor": 0.0,
        "Ingressos": 0.0,
        "Produtos": 0.0,
    }
    despesas_map: Dict[str, float] = {
        "Transferências": round(max(0.0, transfer_buys), 2),
        "Salários de atletas": round(max(0.0, squad_wage_annual), 2),
        "Reserva bônus atleta": round(max(0.0, signon_bonus_total + performance_bonus_total), 2),
        "Salários auxiliares técnicos": round(max(0.0, wage_staff_annual), 2),
        "Manutenção estádio": 0.0,
        "Custos de viagens": 0.0,
        "Instalações da base": 0.0,
    }
    if sum(receitas_map.values()) <= 0:
        receitas_map["Verba inicial"] = round(max(0.0, transfer_budget_start), 2)

    receitas_breakdown = [
        {"label": label, "amount": amount}
        for label, amount in sorted(receitas_map.items(), key=lambda row: row[1], reverse=True)
        if amount > 0
    ]
    despesas_breakdown = [
        {"label": label, "amount": amount}
        for label, amount in sorted(despesas_map.items(), key=lambda row: row[1], reverse=True)
        if amount > 0
    ]

    period_buckets: Dict[str, Dict[str, Any]] = {}
    for item in normalized_ledger:
        period = str(item.get("period") or "")
        month_bucket = period_buckets.setdefault(period, {"period": period, "income": 0.0, "expense": 0.0, "net": 0.0})
        if item["amount"] >= 0:
            month_bucket["income"] = round(month_bucket["income"] + item["amount"], 2)
        else:
            month_bucket["expense"] = round(month_bucket["expense"] + abs(item["amount"]), 2)
        month_bucket["net"] = round(month_bucket["income"] - month_bucket["expense"], 2)

    month_labels = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    monthly_chart = []
    for month in range(1, 13):
        selected = None
        for period, values in period_buckets.items():
            if period.startswith(f"{game_year:04d}-") and _extract_period_month(period) == month:
                selected = values
                break
        monthly_chart.append(
            {
                "month": month_labels[month - 1],
                "income": round(_to_float((selected or {}).get("income"), 0.0), 2),
                "expense": round(_to_float((selected or {}).get("expense"), 0.0), 2),
                "net": round(_to_float((selected or {}).get("net"), 0.0), 2),
            }
        )

    weekly_allowance = round((cash_balance / 40.0), 2) if cash_balance > 0 else 0.0
    squad_value_total = _sum_values([player.get("value") for player in squad])
    club_value = round(clubworth if clubworth > 0 else (squad_value_total + max(cash_balance, 0.0)), 2)
    completed_months = [row for row in monthly_chart if abs(_to_float(row.get("net"), 0.0)) > 0]
    avg_month_net = (
        round(sum(_to_float(row.get("net"), 0.0) for row in completed_months) / len(completed_months), 2)
        if completed_months
        else 0.0
    )
    remaining_months = max(0, 12 - game_month)
    projected_operational_net = round(avg_month_net * remaining_months, 2)
    projected_transfer_net = round(max(0.0, transfer_sales - transfer_buys), 2)
    projected_club_value = round(club_value + projected_operational_net + projected_transfer_net, 2)
    transactions = normalized_ledger[:transactions_limit]
    unavailable_topics = {
        "receitas": ["Sócio torcedor", "Ingressos", "Produtos"],
        "despesas": ["Manutenção estádio", "Custos de viagens", "Instalações da base"],
    }
    if wage_staff_annual <= 0:
        unavailable_topics["despesas"].append("Salários auxiliares técnicos")
    unavailable_overview = [
        "Lucro",
        "Receitas",
        "Despesas",
        "Valor do clube",
        "Projeção de valor do clube",
    ]
    overview_lucro: Optional[float] = None
    overview_receitas: Optional[float] = None
    overview_despesas: Optional[float] = None
    overview_club_value: Optional[float] = None
    overview_projection: Optional[float] = None
    function_metric_map = {
        "GetFinanceProfit": "lucro",
        "GetFinanceRevenue": "receitas",
        "GetFinanceExpense": "despesas",
        "GetClubWorth": "club_value",
        "GetClubValue": "club_value",
        "GetProjectedClubWorth": "projection",
        "GetProjectedClubValue": "projection",
    }
    discovered_overview: Dict[str, float] = {}
    for fn_name, metric_name in function_metric_map.items():
        if fn_name in finance_live_functions:
            value = _to_float(finance_live_functions.get(fn_name), 0.0)
            if value > 0:
                discovered_overview[metric_name] = value
    overview_lucro = discovered_overview.get("lucro")
    overview_receitas = discovered_overview.get("receitas")
    overview_despesas = discovered_overview.get("despesas")
    overview_club_value = discovered_overview.get("club_value")
    overview_projection = discovered_overview.get("projection")
    if overview_lucro is not None and "Lucro" in unavailable_overview:
        unavailable_overview.remove("Lucro")
    if overview_receitas is not None and "Receitas" in unavailable_overview:
        unavailable_overview.remove("Receitas")
    if overview_despesas is not None and "Despesas" in unavailable_overview:
        unavailable_overview.remove("Despesas")
    if overview_club_value is not None and "Valor do clube" in unavailable_overview:
        unavailable_overview.remove("Valor do clube")
    if overview_projection is not None and "Projeção de valor do clube" in unavailable_overview:
        unavailable_overview.remove("Projeção de valor do clube")

    return {
        "contract_version": 1,
        "save_uid": effective_save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "overview": {
            "lucro": overview_lucro,
            "receitas": overview_receitas,
            "despesas": overview_despesas,
            "cash_balance": cash_balance,
            "club_value": overview_club_value,
            "projection": overview_projection,
            "wage_budget": wage_budget,
            "transfer_budget": transfer_budget,
            "wage_utilization": wage_utilization,
            "reliability": "strict_real_only",
            "unavailable_metrics": unavailable_overview,
        },
        "receitas": {
            "total": None,
            "breakdown": receitas_breakdown,
            "unavailable_topics": unavailable_topics["receitas"],
        },
        "despesas": {
            "total": None,
            "breakdown": despesas_breakdown,
            "wage_tracking": {
                "squad_weekly": squad_wage_weekly,
                "manager_weekly": commission_payroll_weekly,
                "squad_annual": squad_wage_annual,
                "staff_annual": wage_staff_annual,
                "total_annual": total_wage_annual,
            },
            "bonus_reserve": {
                "signon_bonus": signon_bonus_total,
                "performance_bonus_projection": performance_bonus_total,
            },
            "unavailable_topics": unavailable_topics["despesas"],
        },
        "transactions": {
            "total": len(normalized_ledger),
            "items": transactions,
        },
        "budget": {
            "current": cash_balance,
            "weekly_allowance": weekly_allowance,
            "monthly_chart": monthly_chart,
            "season_baseline": {
                "start_transfer_budget": transfer_budget_start,
                "start_wage_budget": wage_budget_start,
                "current_transfer_budget": transfer_budget,
                "current_wage_budget": wage_budget,
            },
        },
        "source_trace": {
            "club_transfer_budget_source": "state.club.transfer_budget (lua_memory)",
            "club_wage_budget_source": "state.club.wage_budget (lua_memory)",
            "cash_balance_source": "career_management_state.finance.cash_balance",
            "manager_pref_source": "save_data.manager.manager_pref (save_file)",
            "manager_info_source": "save_data.manager.manager_info (save_file)",
            "manager_history_source": "save_data.manager.manager_history (save_file)",
            "transfer_history_source": "Desktop/fc_companion/{save_uid}/transfer_history.json",
            "finance_live_source": "state.finance_live (lua_memory_live)",
            "squad_wages_source": "save_data.squad[].contract_wage (save_file)",
            "club_value_source": "save_data.teams[].clubworth por team_name",
            "projection_source": "club_value + média líquida mensal projetada + saldo transferências",
            "overview_policy": "strict_real_only (sem estimativa para métricas sem fonte direta)",
            "finance_table_candidates": finance_candidates[:12],
            "missing_critical_fields": [
                field
                for field, value in [
                    ("transfer_budget", transfer_budget),
                    ("wage_budget", wage_budget),
                    ("cash_balance", cash_balance),
                    ("squad_contract_wages", squad_wage_weekly),
                ]
                if _to_float(value, 0.0) <= 0
            ],
            "unavailable_topics": unavailable_topics,
            "unavailable_overview_metrics": unavailable_overview,
            "finance_live_discovered_functions": finance_live_functions,
            "finance_live_manager_samples": finance_live.get("manager_memory_samples") or {},
        },
    }


def build_conference_context(
    save_uid: str,
    mode: Optional[str] = None,
    questions_limit: int = 4,
) -> Dict[str, Any]:
    state = _read_state()
    game_date = _iso_game_date(state)
    manager = dict(state.get("manager") or {})
    club = dict(state.get("club") or {})
    user_team_id = _user_team_id(state)
    current_game_date_raw = _game_date_value(state)
    competition_names = _competition_name_index(save_uid)
    coach_profile = get_or_create_coach_profile(save_uid)
    management_state = get_or_create_career_management_state(save_uid)
    board_active = get_active_board_challenge(save_uid, challenge_type="ULTIMATUM")
    crisis_active = get_active_crisis_arc(save_uid)
    market_rumors = get_recent_market_rumors(limit=5, save_uid=save_uid)
    player_relations = get_player_relations(save_uid, limit=40)
    news_payload = build_news_feed_daily(save_uid=save_uid, date=game_date, limit=5)
    season_arc_active = get_active_season_arc(save_uid)
    facts = _ensure_facts(
        save_uid=save_uid,
        game_date=game_date,
        state=state,
        coach_profile=coach_profile,
        management_state=management_state,
        board_active=board_active,
        crisis_active=crisis_active,
        season_arc_active=season_arc_active,
        market_rumors=market_rumors,
        player_relations=player_relations,
    )
    conference_facts = [
        fact
        for fact in facts
        if bool((fact.get("editorial_flags") or {}).get("eligible_for_conference"))
    ]
    conference_facts.sort(key=lambda item: (-_to_int(item.get("importance"), 0), -int(_to_float(item.get("confidence"), 0) * 1000)))
    next_fixture = _decorate_fixture(_next_fixture(list(state.get("fixtures") or []), user_team_id, current_game_date_raw), user_team_id, competition_names)
    last_fixture = _decorate_fixture(_last_completed_fixture(list(state.get("fixtures") or []), user_team_id), user_team_id, competition_names)
    effective_mode = mode or ("pre_match" if next_fixture else ("post_match" if last_fixture else "generic"))
    locker = dict((management_state.get("locker_room") or {}))
    medical = dict((management_state.get("medical") or {}))
    board_score = _clamp(_to_int(coach_profile.get("reputation_score"), 50) - (18 if board_active else 0) - (20 if crisis_active else 0))
    fan_score = _clamp(_to_int(coach_profile.get("fan_sentiment_score"), 50))
    locker_score = _clamp(_to_int(locker.get("cohesion"), _to_int(locker.get("trust_avg"), 55)))
    media_score = _clamp(45 + (_to_int((news_payload.get("editorial_package") or {}).get("stories_count"), 0) * 6) + (10 if board_active else 0) + (12 if crisis_active else 0))
    hot_topics = []
    for fact in conference_facts[: max(questions_limit, 4)]:
        hot_topics.append(
            {
                "topic_id": fact.get("fact_id"),
                "topic_type": fact.get("category"),
                "title": fact.get("title"),
                "summary": fact.get("summary"),
                "importance": fact.get("importance"),
                "entities": (fact.get("entities") or {}).get("player_names") or (fact.get("entities") or {}).get("club_names") or [],
                "recommended_tone": "calmo" if _to_int(fact.get("importance"), 0) < 75 else "firme",
            }
        )
    question_templates = {
        "match": "Depois do contexto recente, o que este momento diz sobre a competitividade real da equipe?",
        "form": "O desempenho recente já permite falar em tendência consolidada ou ainda exige cautela?",
        "locker_room": "Como você responde aos sinais de tensão e à leitura de desgaste no ambiente interno?",
        "board": "A cobrança institucional altera a forma como você prepara o grupo para os próximos compromissos?",
        "market": "O mercado já interfere nas decisões esportivas imediatas do elenco?",
        "medical": "Como o aspecto físico influencia as escolhas para a sequência de jogos?",
        "player": "O rendimento individual recente muda a hierarquia e o discurso do treinador?",
        "season": "Esse momento altera o rumo do arco da temporada e o peso das próximas decisões?",
    }
    questions = []
    for index, topic in enumerate(hot_topics[: max(3, min(questions_limit, 6))], start=1):
        topic_type = str(topic.get("topic_type") or "season")
        questions.append(
            {
                "question_id": f"{topic.get('topic_id')}:{index}",
                "slot": index,
                "topic_type": topic_type,
                "question": question_templates.get(topic_type, question_templates["season"]),
                "intent": f"explorar o tema {topic_type} no contexto atual",
                "why_now": str(topic.get("summary") or ""),
                "entities": topic.get("entities") or [],
                "predicted_effects": {
                    "reputation_risk": "high" if _to_int(topic.get("importance"), 0) >= 85 else ("medium" if _to_int(topic.get("importance"), 0) >= 65 else "low"),
                    "morale_risk": "high" if topic_type in {"locker_room", "player"} else ("medium" if topic_type in {"board", "medical"} else "low"),
                    "board_sensitivity": "high" if topic_type in {"board", "season"} else "medium",
                    "fan_sensitivity": "high" if topic_type in {"match", "form"} else "medium",
                },
            }
        )
    safe_tone = "equilibrado"
    recommended_approach = "Reconhecer o contexto sem dramatizar e reforçar clareza de plano."
    if board_active:
        safe_tone = "firme"
        recommended_approach = "Reconhecer a pressão e transmitir controle sem abrir fissuras com a diretoria."
    elif crisis_active:
        safe_tone = "calmo"
        recommended_approach = "Evitar escalada emocional e reposicionar a narrativa em trabalho e reação."
    last_result_label = None
    last_result_score = None
    if last_fixture:
        last_result_label = {"W": "vitória", "D": "empate", "L": "derrota"}.get(_result_letter(last_fixture, user_team_id) or "", None)
        last_result_score = f"{last_fixture.get('home_score')} x {last_fixture.get('away_score')}"
    return {
        "contract_version": 1,
        "save_uid": save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "mode": effective_mode,
        "context_snapshot": {
            "game_date": game_date,
            "club_name": str(club.get("team_name") or "Clube"),
            "manager_name": _manager_name(manager),
            "next_fixture": {
                "fixture_id": next_fixture.get("id"),
                "competition_name": next_fixture.get("competition_name"),
                "home_team_name": next_fixture.get("home_team_name"),
                "away_team_name": next_fixture.get("away_team_name"),
                "is_rivalry": False,
                "stakes_label": "alta pressão" if board_active or crisis_active else "relevante",
            } if next_fixture else None,
            "last_result": {
                "label": last_result_label,
                "score": last_result_score,
                "narrative": "O resultado recente segue moldando a leitura pública do momento." if last_result_label else None,
            } if last_fixture else None,
        },
        "pressure_map": {
            "board": {
                "score": 100 - board_score,
                "label": _score_label(100 - board_score, positive_high=False),
                "reason": str((board_active or {}).get("description") or "Sem ultimato ativo, mas a reputação segue no radar institucional."),
            },
            "fans": {
                "score": fan_score,
                "label": _score_label(fan_score, positive_high=True),
                "reason": "A leitura da torcida acompanha forma recente, expectativa e ambiente.",
            },
            "locker_room": {
                "score": locker_score,
                "label": _score_label(locker_score, positive_high=True),
                "reason": "O clima interno reflete confiança, frustração e estabilidade de papéis.",
            },
            "media": {
                "score": media_score,
                "label": _score_label(media_score, positive_high=True),
                "reason": "A intensidade editorial cresce com resultados, pressão e temas quentes do dia.",
            },
        },
        "hot_topics": hot_topics,
        "questions": questions,
        "response_guidance": {
            "safe_tone": safe_tone,
            "recommended_approach": recommended_approach,
            "danger_zones": [
                "conflitar com diretoria" if board_active else "soar desconectado do momento",
                "expor jogador ou tensão interna",
                "minimizar sinais médicos" if _to_int(medical.get("injury_risk_index"), 0) >= 50 else "prometer além do cenário atual",
            ],
        },
        "expected_consequences": {
            "positive_path": [
                "Aumenta confiança pública no treinador.",
                "Reduz risco de ruído institucional no curto prazo.",
            ],
            "negative_path": [
                "Eleva desconforto interno e piora tom da imprensa.",
                "Amplia pressão sobre próximos resultados.",
            ],
        },
        "source_map": {
            "coach_profile": True,
            "board_active_challenge": board_active is not None,
            "crisis_active_arc": crisis_active is not None,
            "player_relations_recent": bool(player_relations),
            "career_management_state": True,
            "events_recent": bool(get_recent_events(limit=5, save_uid=save_uid)),
            "news_feed_daily": True,
        },
    }
