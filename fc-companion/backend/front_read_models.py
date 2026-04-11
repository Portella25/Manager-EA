from __future__ import annotations

import hashlib
import json
import re
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
    upsert_career_management_state,
    replace_career_facts,
    replace_news_daily_package,
)


STATE_PATH = Path.home() / "Desktop" / "fc_companion" / "state.json"
SAVE_DATA_PATH = Path.home() / "Desktop" / "fc_companion" / "save_data.json"
COMPANION_ROOT_PATH = Path.home() / "Desktop" / "fc_companion"
SLOT_ORDER = ["destaque", "bastidores", "análise", "mercado", "contexto"]

SLOT_LABEL_PT: Dict[str, str] = {
    "destaque": "Destaque",
    "bastidores": "Bastidores",
    "análise": "Análise",
    "mercado": "Mercado",
    "contexto": "Contexto",
}

# Rubrica curta por tipo de facto — evita rótulo genérico duplicado (ex.: análise_2) e dá cara de coluna esportiva BR
FACT_TYPE_SLOT_RUBRIC_PT: Dict[str, str] = {
    "league_table_shift": "Tabela",
    "positive_streak": "Embalada",
    "winless_streak": "Fase irregular",
    "top_scorer_update": "Artilharia",
    "top_assister_update": "Garçons",
    "young_talent_rise": "Base",
    "important_win": "Rodada",
    "big_win": "Rodada",
    "draw_frustration": "Rodada",
    "important_loss": "Rodada",
    "key_player_in_form": "Elenco",
    "calendar_congestion": "Calendário",
    "rival_highlight": "Concorrência",
    "surprise_league_position": "Tabela",
    "tactical_identity_shift": "Esquema",
    "external_narrative": "Radar",
    "press_conference_fallout": "Coletiva",
    "board_pressure_active": "Diretoria",
    "board_ultimatum_active": "Diretoria",
    "season_arc_milestone": "Temporada",
    "reserve_frustrated": "Vestiário",
    "critical_injury": "DM",
    "return_from_injury": "DM",
    "market_offer_strong": "Mercado",
    "market_rumor_hot": "Mercado",
    "transfer_completed": "Mercado",
    "locker_room_tension": "Vestiário",
    "upcoming_derby": "Clássico",
}


def _normalize_news_slot_key(slot: str) -> str:
    s = (slot or "").strip()
    if not s:
        return "contexto"
    for prefix in ("destaque", "bastidores", "análise", "mercado", "contexto"):
        if s == prefix or s.startswith(prefix + "_"):
            return prefix
    return re.sub(r"_\d+$", "", s) or "contexto"


def _compute_slot_label(slot: str, fact_type: str) -> str:
    base = _normalize_news_slot_key(slot)
    label = SLOT_LABEL_PT.get(base, base.replace("_", " ").title())
    rubric = FACT_TYPE_SLOT_RUBRIC_PT.get((fact_type or "").strip())
    if rubric:
        return f"{label} · {rubric}"
    return label


def enrich_news_story_for_client(story: Dict[str, Any]) -> Dict[str, Any]:
    """Garante slot_label legível (nunca análise_2) e coerente com o tipo de matéria."""
    out = dict(story)
    sf = (out.get("source_facts") or [{}])[0] if isinstance(out.get("source_facts"), list) else {}
    ft = str((sf or {}).get("fact_type") or "")
    out["slot_label"] = _compute_slot_label(str(out.get("slot") or ""), ft)
    return out

IMPACT_LABEL_PT: Dict[str, str] = {
    "high": "Alto",
    "medium": "Médio",
    "low": "Baixo",
}
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
        "intocavel": "Intocável",
        "intocável": "Intocável",
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


CONFERENCE_QUESTION_CORE_VARIANTS: Dict[str, List[str]] = {
    "match": [
        "Depois do contexto recente, o que este momento diz sobre a competitividade real da equipe?",
        "Os últimos jogos mudam a leitura sobre equilíbrio entre ataque e defesa?",
        "O que o recorte recente de resultados revela sobre o teto real do time?",
    ],
    "form": [
        "O desempenho recente já permite falar em tendência consolidada ou ainda exige cautela?",
        "Dá para projetar uma sequência positiva ou o cenário ainda é frágil?",
        "Como você avalia a regularidade do grupo nas últimas rodadas?",
    ],
    "locker_room": [
        "Como você responde aos sinais de tensão e à leitura de desgaste no ambiente interno?",
        "O clima do vestiário interfere diretamente nas decisões para a sequência?",
        "Há ruídos internos que precisam ser endereçados publicamente?",
    ],
    "board": [
        "A cobrança institucional altera a forma como você prepara o grupo para os próximos compromissos?",
        "A relação com a diretoria pesa na liberdade de escolhas técnicas?",
        "Como equilibra expectativa da cúpula e rotina do dia a dia no CT?",
    ],
    "market": [
        "O mercado já interfere nas decisões esportivas imediatas do elenco?",
        "Rumores e janela mudam o foco do grupo na reta decisiva?",
        "Como a especulação afeta o vestiário neste momento?",
    ],
    "medical": [
        "Como o aspecto físico influencia as escolhas para a sequência de jogos?",
        "O departamento médico condiciona escalação e minutos neste calendário?",
        "Desgaste e recuperação aparecem como limitadores táticos agora?",
    ],
    "player": [
        "O rendimento individual recente muda a hierarquia e o discurso do treinador?",
        "Algum nome específico força repensar titularidade ou funções?",
        "Como você lida com a exposição de um jogador em destaque ou em crise?",
    ],
    "season": [
        "Esse momento altera o rumo do arco da temporada e o peso das próximas decisões?",
        "Objetivos da temporada entram em revisão após o que vimos recentemente?",
        "O que está em jogo além do próximo apito inicial?",
    ],
}

CONFERENCE_SLOT_FRAMING_PRIORITY: Dict[int, Tuple[str, ...]] = {
    1: ("vespera", "ultimo_jogo", "tabela", "calendario_saude", "bare"),
    2: ("ultimo_jogo", "tabela", "calendario_saude", "vespera", "bare"),
    3: ("tabela", "calendario_saude", "ultimo_jogo", "vespera", "bare"),
    4: ("calendario_saude", "competicao_objetivo", "ultimo_jogo", "vespera", "bare"),
    5: ("bare", "vespera", "ultimo_jogo", "tabela", "calendario_saude"),
    6: ("competicao_objetivo", "tabela", "vespera", "bare", "calendario_saude"),
}


def _pick_conference_question_core(topic_type: str, topic_id: Any, slot: int) -> str:
    tt = str(topic_type or "season").lower()
    variants = CONFERENCE_QUESTION_CORE_VARIANTS.get(tt) or CONFERENCE_QUESTION_CORE_VARIANTS["season"]
    if not variants:
        return CONFERENCE_QUESTION_CORE_VARIANTS["season"][0]
    h = hashlib.md5(f"{topic_id}:{slot}".encode("utf-8")).hexdigest()
    return variants[int(h[:8], 16) % len(variants)]


def _conference_framing_vespera(core: str, next_fixture: Optional[Dict[str, Any]]) -> Optional[str]:
    if not next_fixture:
        return None
    hn = str(next_fixture.get("home_team_name") or "")
    an = str(next_fixture.get("away_team_name") or "")
    if not hn or not an or len(core) < 2:
        return None
    return f"À véspera de {hn} x {an}, {core[0].lower()}{core[1:]}"


def _conference_framing_ultimo_jogo(
    core: str,
    last_fixture: Optional[Dict[str, Any]],
    user_team_id: int,
) -> Optional[str]:
    if not last_fixture or last_fixture.get("home_score") is None:
        return None
    letter = _result_letter(last_fixture, user_team_id) or ""
    label = {"W": "a vitória", "D": "o empate", "L": "a derrota"}.get(letter)
    if not label or len(core) < 2:
        return None
    sc = f"{last_fixture.get('home_score')} x {last_fixture.get('away_score')}"
    comp = str(last_fixture.get("competition_name") or "").strip()
    mid = f" na {comp}" if comp else ""
    return f"Após {label}{mid} ({sc}), {core[0].lower()}{core[1:]}"


def _conference_framing_tabela(core: str, club_name: str, table: Optional[Dict[str, Any]]) -> Optional[str]:
    if not table or len(core) < 2:
        return None
    comp = str(table.get("competition_name") or "competição")
    rank = table.get("rank")
    pts = table.get("points")
    if rank is None or pts is None:
        return None
    return f"Na tabela da {comp}, com o {club_name} na {rank}ª posição ({pts} pontos), {core[0].lower()}{core[1:]}"


def _conference_framing_calendario_saude(core: str, medical: Dict[str, Any]) -> Optional[str]:
    if len(core) < 2:
        return None
    inj = _to_int(medical.get("injured_count"), 0)
    cong = _to_int(medical.get("congestion_index"), 0)
    fat = _to_float(medical.get("fatigue_index"), 0.0)
    risk = _to_int(medical.get("injury_risk_index"), 0)
    if inj >= 2 or cong >= 4:
        prefix = f"Com {inj} desfalque(s) e calendário exigente (congestão {cong}/10), "
    elif risk >= 55 or fat >= 58.0:
        prefix = f"Com risco físico elevado no grupo (desgaste e departamento médico no radar), "
    elif cong >= 2:
        prefix = "Com sequência densa de jogos pela frente, "
    else:
        prefix = "Pensando em físico, recuperação e rodízio no elenco, "
    return f"{prefix}{core[0].lower()}{core[1:]}"


def _conference_framing_competicao_objetivo(
    core: str,
    club_name: str,
    next_fixture: Optional[Dict[str, Any]],
    table: Optional[Dict[str, Any]],
) -> Optional[str]:
    if len(core) < 2:
        return None
    comp = ""
    if next_fixture:
        comp = str(next_fixture.get("competition_name") or "").strip()
    if not comp and table:
        comp = str(table.get("competition_name") or "").strip()
    if not comp:
        return None
    return f"Dentro da {comp}, com o que o {club_name} ainda pode alcançar na temporada, {core[0].lower()}{core[1:]}"


def _conference_framing_bare(core: str, club_name: str) -> Optional[str]:
    if len(core) < 2:
        return None
    return f"Sobre o momento do {club_name}, {core[0].lower()}{core[1:]}"


def _build_framed_conference_question(
    slot: int,
    core: str,
    club_name: str,
    next_fixture: Optional[Dict[str, Any]],
    last_fixture: Optional[Dict[str, Any]],
    user_team_id: int,
    table: Optional[Dict[str, Any]],
    medical: Dict[str, Any],
) -> Tuple[str, str]:
    order = CONFERENCE_SLOT_FRAMING_PRIORITY.get(slot) or CONFERENCE_SLOT_FRAMING_PRIORITY[1]
    for kind in order:
        if kind == "vespera":
            out = _conference_framing_vespera(core, next_fixture)
        elif kind == "ultimo_jogo":
            out = _conference_framing_ultimo_jogo(core, last_fixture, user_team_id)
        elif kind == "tabela":
            out = _conference_framing_tabela(core, club_name, table)
        elif kind == "calendario_saude":
            out = _conference_framing_calendario_saude(core, medical)
        elif kind == "competicao_objetivo":
            out = _conference_framing_competicao_objetivo(core, club_name, next_fixture, table)
        else:
            out = _conference_framing_bare(core, club_name)
        if out:
            return out, kind
    return core, "bare"


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


def _career_season_number(state: Dict[str, Any]) -> int:
    """Temporada da carreira derivada da game_date.
    EAFC 26 inicia na temporada 25/26 (jul 2025). Cada temporada começa em julho.
    Jul 2025 – Jun 2026 = temporada 1, Jul 2026 – Jun 2027 = temporada 2, etc."""
    gd = _game_date_obj(state)
    if gd is None:
        return 1
    base_year = 2025
    if gd.month >= 7:
        season = gd.year - base_year + 1
    else:
        season = gd.year - base_year
    return max(season, 1)


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
        "career_season": _career_season_number(current_state),
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
        if str(current_player.get("overallrating_source") or "") == "lua_le_db":
            base_overall_source = "lua_le_db"
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
        position_source = "save_preferredposition1"
        if str(current_player.get("preferredposition_source") or "") == "lua_le_db":
            position_source = "lua_le_db"
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
                "preferredposition_source": position_source,
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


def build_press_fallout_career_facts(
    save_uid: str,
    game_date: str,
    *,
    conference_id: int,
    headline: str,
    board_reaction: str,
    locker_room_reaction: str,
    fan_reaction: str,
    audience: Optional[str],
    focus_player_name: Optional[str],
    linked_headline: Optional[str],
    detected_tone: str,
    reputation_delta: int,
    morale_delta: int,
) -> List[Dict[str, Any]]:
    """Factos editoriais derivados da coletiva — alimentam o jornal do dia seguinte e contexto da próxima edição."""
    aud = (audience or "midia").lower()
    club_line = str(board_reaction or "").strip()
    locker = str(locker_room_reaction or "").strip()
    fan = str(fan_reaction or "").strip()
    parts = [club_line, locker]
    if fan:
        parts.append(fan)
    summary = " ".join(p for p in parts if p)[:900]

    fp = (focus_player_name or "").strip()
    player_names = [fp] if fp else []

    imp = 52 + min(18, max(abs(int(reputation_delta)), abs(int(morale_delta))) * 3)

    facts: List[Dict[str, Any]] = [
        _build_fact(
            save_uid=save_uid,
            game_date=game_date,
            fact_type="press_conference_fallout",
            category="press",
            title=str(headline or "Coletiva: repercussão interna")[:160],
            summary=summary or str(headline or ""),
            importance=int(imp),
            confidence=0.82,
            entities={
                "player_names": player_names,
                "club_names": [],
                "linked_headline": (linked_headline or "")[:200],
                "audience_focus": aud,
            },
            source_refs=[{"source": "press_conference", "ref_id": str(conference_id)}],
            signals={
                "tone": detected_tone,
                "reputation_delta": int(reputation_delta),
                "morale_delta": int(morale_delta),
                "audience": aud,
            },
            dedupe_group=f"press_fallout_{conference_id}",
            eligible_for_news=True,
            eligible_for_home=True,
            eligible_for_conference=True,
        )
    ]

    leakish = any(
        x in fan.lower()
        for x in ("rumor", "rumores", "colunistas", "vaz", "vazamento", "bastidor")
    )
    if leakish and fp:
        facts.append(
            _build_fact(
                save_uid=save_uid,
                game_date=game_date,
                fact_type="locker_room_tension",
                category="locker_room",
                title=f"Bastidor: clima em volta de {fp} após exposição na mídia",
                summary="Nos corredores, a leitura é de ruído extra em momento sensível; o grupo monitora o clima interno.",
                importance=min(88, int(imp) + 8),
                confidence=0.55,
                entities={"player_names": [fp], "club_names": []},
                source_refs=[{"source": "press_conference", "ref_id": str(conference_id), "kind": "leak_echo"}],
                signals={"press_echo": True, "player": fp},
                dedupe_group=f"press_leak_echo_{conference_id}",
                eligible_for_news=True,
                eligible_for_home=False,
                eligible_for_conference=True,
            )
        )
    return facts


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
        "important_win": "destaque",
        "important_loss": "destaque",
        "big_win": "destaque",
        "draw_frustration": "destaque",
        "positive_streak": "análise",
        "winless_streak": "destaque",
        "board_pressure_active": "contexto",
        "board_ultimatum_active": "contexto",
        "key_player_in_form": "análise",
        "top_scorer_update": "análise",
        "top_assister_update": "análise",
        "young_talent_rise": "análise",
        "reserve_frustrated": "bastidores",
        "critical_injury": "bastidores",
        "return_from_injury": "bastidores",
        "market_offer_strong": "mercado",
        "market_rumor_hot": "mercado",
        "transfer_completed": "mercado",
        "locker_room_tension": "bastidores",
        "tactical_identity_shift": "análise",
        "season_arc_milestone": "contexto",
        "upcoming_derby": "destaque",
        "calendar_congestion": "análise",
        "league_table_shift": "análise",
        "rival_highlight": "contexto",
        "external_narrative": "contexto",
        "surprise_league_position": "destaque",
        "press_conference_fallout": "contexto",
    }
    return mapping.get(str(fact.get("fact_type") or ""), "contexto")


def _article_kind_for_slot(slot: str) -> str:
    if slot == "análise":
        return "analysis"
    if slot == "mercado":
        return "rumor"
    if slot == "bastidores":
        return "internal_note"
    if slot == "contexto":
        return "press_echo"
    return "news"


def _pick_variant_by_seed(variants: List[str], seed: str) -> str:
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % max(len(variants), 1)
    return variants[idx] if variants else ""


def _aproveitamento_pct(pts: int, played: int) -> int:
    if played <= 0:
        return 0
    return int(round(100.0 * float(pts) / float(played * 3)))


def _render_article_from_fact(fact: Dict[str, Any]) -> Dict[str, Any]:
    slot = _slot_for_fact(fact)
    raw_impact = _impact_from_importance(_to_int(fact.get("importance"), 50))
    impact = IMPACT_LABEL_PT.get(raw_impact, raw_impact)
    title = str(fact.get("title") or "")
    summary = str(fact.get("summary") or "")
    category = str(fact.get("category") or "")
    fact_type = str(fact.get("fact_type") or "")
    signals = dict(fact.get("signals") or {})
    entities = dict(fact.get("entities") or {})
    pnames = list(entities.get("player_names") or [])
    cnames = list(entities.get("competition_names") or [])
    club_names = list(entities.get("club_names") or [])
    team = club_names[0] if club_names else "Clube"
    seed = f"{fact_type}:{fact.get('game_date', '')}:{title}"

    tags: List[str] = []
    CATEGORY_TAGS: Dict[str, List[str]] = {
        "match": ["Partida", "Competição"],
        "form": ["Forma", "Desempenho"],
        "market": ["Mercado"],
        "board": ["Diretoria"],
        "locker_room": ["Vestiário"],
        "medical": ["Departamento Médico"],
        "player": ["Jogador"],
        "calendar": ["Calendário"],
        "table": ["Classificação"],
        "season": ["Temporada"],
        "transfer": ["Transferência"],
        "external": ["Contexto"],
        "press": ["Coletiva", "Mídia"],
    }
    tags = list(CATEGORY_TAGS.get(category, ["Geral"]))

    body = [summary]
    lead = summary
    subheadline = summary
    why_it_matters = "Acompanhe os desdobramentos ao longo da temporada."
    club_effects = ["Pode influenciar as próximas decisões do treinador."]

    if fact_type == "important_win":
        score = signals.get("score", "")
        opponent = signals.get("opponent", "")
        lead = _pick_variant_by_seed(
            [
                f"{team} cumpriu tabela com vitória sobre {opponent} — resultado que vale mais que três pontos no bolso.",
                f"Vitória de ofício: {team} fez o dever de casa contra {opponent} e respira na briga do calendário.",
                f"No rescaldo da rodada, {team} confirmou que a prioridade era somar — e somou com vitória sobre {opponent}.",
                f"Triunfo para tirar ruído: {team} bate {opponent} e muda o clima em volta do trabalho da comissão.",
            ],
            seed + ":iw:lead",
        )
        subheadline = _pick_variant_by_seed(
            [
                f"Placar {score}: jogo decidido nos detalhes, com vitória que pesa na confiança do elenco.",
                f"O {score} fecha a conta do dia e posiciona {team} melhor na conversa com a torcida e com a imprensa.",
                f"Com {score} no placar, o debate sai do ‘como jogou’ e vai para ‘o que isso libera no vestiário’.",
            ],
            seed + ":iw:sub",
        )
        body_variants = [
            [
                f"O jogo terminou {score}. A leitura é de controle: {team} administrou momentos-chave, evitou susto e carimbo os três pontos contra {opponent}.",
                f"Não foi passeio, mas foi eficiente. A equipe encontrou caminho para desequilibrar — e o placar reflete isso sem precisar de discurso exagerado.",
                f"Na prática, a vitória mexe no humor do CT e adia qualquer crise de curto prazo; o foco agora é manter padrão nas próximas rodadas.",
            ],
            [
                f"Foi {score}. {team} soube quando acelerar e quando segurar o jogo, algo que times candidatos a coisa grande precisam mostrar com regularidade.",
                f"Contra {opponent}, o triunfo também serve como resposta silenciosa para quem cobrava reação — ainda que o campeonato cobre consistência, não um jogo só.",
                f"O calendário não espera: o próximo desafio já desloca a conversa do ‘alívio’ para ‘confirmar’.",
            ],
            [
                f"Placar {score}. O que chama atenção é a sensação de que {team} jogou com roteiro — mesmo quando o adversário esboçou reação.",
                f"A vitória sobre {opponent} entra no pacote de ‘resultados que constroem narrativa’: torcida celebra, mídia amplia e a diretoria ganha oxigênio.",
                f"O treinador ganha tempo para trabalhar ideias sem barulho externo; o elenco, confiança para repetir intensidade.",
            ],
            [
                f"{score} no placar e três pontos na conta. Para {team}, o triunfo sobre {opponent} é aquele tipo de resultado que fecha semana com sensação de dever cumprido.",
                f"Ofensivamente, houve clareza nos lances decisivos; defensivamente, o time evitou o drama até o apito final.",
                f"O efeito colateral é moral alta no grupo — útil quando a tabela aperta e cada rodada vira prova.",
            ],
        ]
        body = _pick_variant_by_seed(body_variants, seed + ":iw:body")
        why_it_matters = _pick_variant_by_seed(
            [
                "No futebol brasileiro, ‘rodada boa’ vira pauta rápida: vitória limpa narrativa, muda manchete e altera tom de coletiva.",
                "Vitórias isoladas não garantem título, mas mudam o clima — e o clima muda cobrança, escalação e até mercado.",
            ],
            seed + ":iw:wim",
        )
        club_effects = [
            _pick_variant_by_seed(
                ["Ambiente interno mais leve nos treinos imediatamente após o resultado.", "Menos ruído nas bancadas e mais crédito para o comando técnico."],
                seed + ":iw:ce1",
            ),
            _pick_variant_by_seed(
                ["Discurso de ‘time em construção’ ganha um resultado para embalar a próxima sequência.", "Pressão externa diminui até o próximo tropeço."],
                seed + ":iw:ce2",
            ),
        ]

    elif fact_type == "important_loss":
        score = signals.get("score", "")
        opponent = signals.get("opponent", "")
        body_variants = [
            [f"A derrota por {score} para o {opponent} aumenta a pressão e coloca o treinador em posição delicada.",
             "A equipe precisará de uma resposta imediata para evitar que a crise se instale."],
            [f"Revés por {score} diante do {opponent}. O clima nos bastidores é de cobrança e a torcida pede reação.",
             "A diretoria acompanha com atenção e espera sinais de recuperação nos próximos jogos."],
            [f"Com o resultado negativo contra {opponent}, {team} vê a situação se complicar na tabela.",
             "O treinador terá que encontrar soluções rápidas para reverter o momento."],
            [f"Derrota por {score} que frustra e preocupa. {team} não conseguiu impor seu jogo contra {opponent}.",
             "A cobrança cresce e o próximo jogo ganha peso de decisão."],
            [f"{team} cai para {opponent} por {score} e a pressão se intensifica sobre o comando técnico.",
             "O vestiário precisa se reerguer rapidamente para não deixar a sequência escapar."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Derrotas consecutivas podem acelerar crises e mudar o rumo da temporada."
        club_effects = ["Eleva a cobrança sobre o treinador.", "Pode afetar o moral do elenco."]

    elif fact_type == "big_win":
        score = signals.get("score", "")
        opponent = signals.get("opponent", "")
        lead = _pick_variant_by_seed(
            [
                f"{team} passou o rolo compressor em {opponent}: o tipo de tarde que vira highlight no celular de torcedor e de rival.",
                f"Quem buscava ‘prova de fase’ encontrou no placar — jogo contra {opponent} virou show coletivo e estatística inflada.",
                f"No rescaldo da rodada, o que ficou foi sensação de domínio: {opponent} até tentou reagir, mas o ritmo foi unilateral.",
            ],
            seed + ":bw:lead",
        )
        subheadline = _pick_variant_by_seed(
            [
                f"Placar {score}: resultado que fecha debate sobre quem impôs o jogo — e abre debate sobre teto ofensivo do time.",
                f"O {score} entra para a galeria de goleadas da temporada e muda o tom da cobertura por alguns dias.",
                f"Vitória com números largos: além do placar, o recado é psicológico para o restante do calendário.",
            ],
            seed + ":bw:sub",
        )
        body_variants = [
            [
                f"Fechou {score}. {team} acelerou transições, castigou erro de {opponent} e transformou chances em gol com frieza de time embalado.",
                f"A leitura tática é simples: quando o adversário abre, o time soube finalizar — e finalizar muito.",
                f"Na imprensa e nas redes, o assunto deixa de ser ‘vitória’ e vira ‘pauta de candidato a fase arrasadora’ — com todo o cuidado que isso exige na próxima rodada.",
            ],
            [
                f"O placar de {score} espelha um roteiro de pressão alta e eficiência na área. {opponent} viu o jogo escapar cedo e não encontrou antídoto.",
                f"Para o torcedor, é aquele jogo que enche timeline; para o técnico, é material para corrigir detalhes mesmo com vitória folgada.",
                f"Efeito prático: moral alta, concorrentes diretos anotam o recado e a expectativa externa sobe — às vezes mais rápido do que o próprio elenco quer.",
            ],
            [
                f"Vitória elástica ({score}). O que impressiona é a regularidade do acerto: não foi um gol isolado, foi sequência de situações bem resolvidas.",
                f"{opponent} saiu derrotado e com a sensação de ter encontrado um time em dia inspirado — ruim para confiança do adversário, ótimo para {team}.",
                f"No Brasileirão, goleada vira conversa de mesa redonda: aparece em programa esportivo, vira meme e empurra o clube para o centro do noticiário.",
            ],
        ]
        body = _pick_variant_by_seed(body_variants, seed + ":bw:body")
        why_it_matters = _pick_variant_by_seed(
            [
                "Goleada não é só número: no calendário apertado, ela vira ânimo interno, medo externo nos rivais e narrativa de ‘time perigoso’.",
                "Placar largo muda percepção — e no Brasil, percepção vira cobrança quando o time não repete o nível na sequência.",
            ],
            seed + ":bw:wim",
        )
        club_effects = [
            _pick_variant_by_seed(
                [
                    f"Moral alta no elenco; treinos ganham clima de ‘semana boa’ — com cuidado para não cair em acomodação.",
                    "Vitrine positiva para quem busca afirmar peças ofensivas e encaixe tático.",
                ],
                seed + ":bw:ce1",
            ),
            _pick_variant_by_seed(
                [
                    "Mídia esportiva amplia cobertura; rival direto passa a estudar mais o time.",
                    "Expectativa da torcida sobe — e com ela, a exigência no próximo jogo.",
                ],
                seed + ":bw:ce2",
            ),
        ]

    elif fact_type == "draw_frustration":
        score = signals.get("score", "")
        opponent = signals.get("opponent", "")
        body_variants = [
            [f"Empate em {score} contra {opponent}. {team} teve oportunidades mas não conseguiu converter.",
             "O resultado de empate em casa frustra e mantém a equipe estagnada na classificação."],
            [f"{team} fica no {score} com {opponent} e perde a chance de subir na tabela.",
             "A falta de eficiência ofensiva preocupa e vira pauta para os próximos treinos."],
            [f"Mais um empate. O {score} contra {opponent} mostra que {team} precisa ser mais decisivo.",
             "Pontos escapam e o cenário na classificação fica cada vez mais apertado."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Empates em sequência podem comprometer objetivos a longo prazo."
        club_effects = ["Gera frustração no vestiário.", "Mantém pressão por eficiência."]

    elif fact_type == "positive_streak":
        count = _to_int(signals.get("streak_count"), 3)
        body_variants = [
            [f"{team} emplacou {count} vitórias seguidas e vive o melhor momento da temporada.",
             "A regularidade impressiona e coloca a equipe como candidata séria aos objetivos do ano."],
            [f"Sequência de {count} vitórias consecutivas! {team} mostra consistência rara nesta temporada.",
             "O trabalho da comissão técnica começa a dar frutos visíveis na tabela e no vestiário."],
            [f"Com {count} vitórias em sequência, {team} escala posições e muda o patamar competitivo.",
             "A confiança do grupo está em alta e os resultados refletem a evolução tática."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Sequências positivas mudam narrativa, moral e posição na tabela."
        club_effects = ["Fortalece a posição do treinador.", "Eleva a confiança do elenco."]
        tags.append("Sequência")

    elif fact_type == "winless_streak":
        body_variants = [
            [summary, "A ausência de vitórias pesa no moral e aumenta a urgência por uma reação imediata."],
            [summary, "Sem vencer há vários jogos, a pressão sobre o treinador cresce a cada rodada."],
            [summary, "A seca de vitórias se reflete na postura tímida em campo e no descontentamento da torcida."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Fase sem vitórias gera crise de confiança e pode precipitar mudanças."
        club_effects = ["Aumenta risco de crise.", "Pressão por mudanças imediatas."]

    elif fact_type == "top_scorer_update":
        player = pnames[0] if pnames else "Atacante"
        goals = _to_int(signals.get("goals"), 0)
        comp = cnames[0] if cnames else "campeonato"
        body_variants = [
            [f"{player} chegou a {goals} gols e é o artilheiro de {team} na temporada.",
             f"A fase goleadora reforça sua importância tática e o coloca no debate como destaque de {comp}."],
            [f"Com {goals} gols, {player} lidera a artilharia e se firma como referência ofensiva de {team}.",
             "Cada jogo reforça a dependência da equipe no seu camisa de gol."],
            [f"{player} não para de marcar! {goals} gols na temporada colocam o jogador no radar da artilharia de {comp}.",
             "O treinador sabe que tem em mãos um diferencial que poucos rivais conseguem neutralizar."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Artilheiros definem temporadas e atraem atenção de mercado."
        club_effects = ["Valorização do jogador.", "Dependência ofensiva pode ser risco."]
        tags.append("Artilharia")

    elif fact_type == "top_assister_update":
        player = pnames[0] if pnames else "Meia"
        assists = _to_int(signals.get("assists"), 0)
        body_variants = [
            [f"{player} soma {assists} assistências e lidera a criação de jogadas em {team}.",
             "O garçom da equipe tem sido fundamental nas principais jogadas de gol da temporada."],
            [f"Com {assists} passes decisivos, {player} se consolida como cérebro criativo do time.",
             "A capacidade de decisão nos últimos metros faz diferença em jogos equilibrados."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Criadores de jogo são peça-chave em equipes com ambição."
        club_effects = ["Reforça importância no esquema tático.", "Atrai interesse de outros clubes."]
        tags.append("Assistências")

    elif fact_type == "young_talent_rise":
        player = pnames[0] if pnames else "Jovem promessa"
        ovr = _to_int(signals.get("overall"), 0)
        pot = _to_int(signals.get("potential"), 0)
        body = [
            f"{player} (OVR {ovr}, potencial {pot}) está em ascensão e chama atenção nas categorias de base.",
            "O jovem talento pode ser peça importante no futuro do clube ou gerar retorno financeiro significativo.",
        ]
        why_it_matters = "Revelar talentos é parte essencial do projeto esportivo."
        club_effects = ["Possível valorização de ativo.", "Opção interna para o treinador."]
        tags.append("Base")

    elif fact_type in {"reserve_frustrated", "locker_room_tension"}:
        body_variants = [
            [summary, "A situação no vestiário exige cuidado e pode afetar a harmonia do grupo."],
            [summary, "Os bastidores aquecem e o treinador precisa gerenciar egos e expectativas."],
            [summary, "A gestão do elenco entra em fase delicada que pode impactar resultados."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Problemas internos se refletem em campo quando não tratados a tempo."
        club_effects = ["Risco de queda no desempenho.", "Pode afetar coesão do grupo."]

    elif fact_type in {"market_offer_strong", "market_rumor_hot"}:
        body_variants = [
            [summary, "O mercado se movimenta e o planejamento esportivo precisa se adaptar às circunstâncias."],
            [summary, "Bastidores agitados: as negociações podem alterar o perfil do elenco para a sequência."],
            [summary, "A janela de transferências ganha novo capítulo e pode mudar peças importantes do tabuleiro."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Movimentações de mercado redefinem elenco e expectativas."
        club_effects = ["Pode mudar dinâmica do grupo.", "Impacto financeiro nas contas do clube."]

    elif fact_type == "transfer_completed":
        player = pnames[0] if pnames else "Jogador"
        direction = signals.get("direction", "")
        fee = signals.get("fee", "")
        if direction == "in":
            body = [
                f"{player} é o novo reforço de {team}! A contratação movimenta o mercado e traz novas opções ao treinador.",
                f"Com o valor de {fee}, a diretoria aposta na chegada para qualificar o elenco.",
            ]
            tags.append("Reforço")
        else:
            body = [
                f"{team} confirma a saída de {player}. A negociação rende {fee} e abre espaço no elenco.",
                "A diretoria já trabalha em alternativas para repor a posição.",
            ]
            tags.append("Saída")
        why_it_matters = "Transferências mudam a cara do time e as possibilidades táticas."
        club_effects = ["Redefine opções do treinador.", "Impacto no orçamento."]

    elif fact_type in {"critical_injury", "return_from_injury"}:
        player = pnames[0] if pnames else "Jogador"
        if fact_type == "critical_injury":
            body_variants = [
                [f"{player} se lesionou e desfalca {team}. O departamento médico avalia o tempo de recuperação.",
                 "A ausência pesa na escalação e obriga o treinador a buscar alternativas."],
                [f"Baixa no elenco: {player} vai ao departamento médico e vira dúvida para os próximos compromissos.",
                 "A gestão física do elenco volta ao centro do debate técnico."],
            ]
        else:
            body_variants = [
                [f"Boa notícia: {player} está de volta e fica à disposição do treinador.",
                 "O retorno reforça o elenco e traz mais opções para as decisões de escalação."],
                [f"{player} recebe alta médica e pode ser relacionado. O elenco ganha fôlego com o retorno.",
                 "A volta do jogador pode mudar a dinâmica da equipe nos próximos jogos."],
            ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "A disponibilidade do elenco impacta diretamente nos resultados."
        club_effects = ["Muda opções de escalação.", "Altera gestão de minutagem."]

    elif fact_type in {"board_pressure_active", "board_ultimatum_active", "season_arc_milestone"}:
        body_variants = [
            [summary, "O peso institucional do momento redefine prioridades e coloca a carreira sob análise."],
            [summary, "Diretoria e imprensa acompanham de perto: o próximo passo será decisivo."],
            [summary, "A pressão institucional cresce e cada resultado ganha peso dobrado."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Pressão da diretoria pode antecipar decisões e mudar o rumo da carreira."
        club_effects = ["Aumenta urgência por resultados.", "Decisões ganham peso simbólico."]

    elif fact_type == "key_player_in_form":
        player = pnames[0] if pnames else "Destaque"
        body_variants = [
            [f"{player} vive grande fase e é o nome mais comentado nos treinos e na imprensa.",
             "O rendimento individual sustenta boa parte do desempenho coletivo da equipe."],
            [f"A boa fase de {player} não passa despercebida. O jogador é peça central no esquema do treinador.",
             "Enquanto mantiver esse nível, a equipe tem um diferencial competitivo claro."],
            [f"{player} segue em excelente momento e já é apontado como um dos melhores em atividade no campeonato.",
             "O treinador conta com o jogador como trunfo principal para os desafios que vêm pela frente."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Jogadores em alta são o motor de qualquer campanha bem-sucedida."
        club_effects = ["Valorização do jogador.", "Expectativa alta da torcida."]

    elif fact_type == "upcoming_derby":
        opponent = signals.get("opponent", "Rival")
        comp = cnames[0] if cnames else "campeonato"
        body_variants = [
            [f"Clássico à vista! {team} enfrenta {opponent} pelo {comp} e a tensão já toma conta.",
             "Derbys carregam peso emocional e podem definir temporadas inteiras."],
            [f"A cidade se divide: {team} x {opponent} promete ser o jogo da semana.",
             f"O confronto pelo {comp} vale mais do que pontos — vale moral e posicionamento."],
            [f"Clássico imperdível: {team} e {opponent} se enfrentam com tudo em jogo.",
             "A rivalidade histórica dá ao jogo uma dimensão que vai além do tático."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Clássicos definem lideranças, moral e narrativa da temporada."
        club_effects = ["Eleva a pressão emocional.", "Resultado impacta torcida diretamente."]
        tags.append("Clássico")

    elif fact_type == "calendar_congestion":
        games = _to_int(signals.get("games_in_period"), 0)
        body = [
            f"{team} enfrenta {games} jogos em período curto. A gestão física será determinante.",
            "A sequência apertada obriga rotação e pode revelar profundidade — ou fragilidade — do elenco.",
        ]
        why_it_matters = "Congestionamento de jogos é quando elencos profundos fazem a diferença."
        club_effects = ["Obriga rotação.", "Aumenta risco de lesões."]
        tags.append("Calendário")

    elif fact_type == "league_table_shift":
        rank = _to_int(signals.get("rank"), 0)
        pts = _to_int(signals.get("points"), 0)
        played = _to_int(signals.get("played"), 0)
        gd = _to_int(signals.get("goal_difference"), 0)
        team_count = _to_int(signals.get("team_count"), 0)
        comp = cnames[0] if cnames else "campeonato"
        ap_pct = _aproveitamento_pct(pts, played)
        z4 = team_count > 0 and rank > team_count - 4

        lead = _pick_variant_by_seed(
            [
                f"No {comp}, a tabela não mente: {team} aparece na posição que define o tom da cobrança — e da festa.",
                f"Panorama de classificação: {team} está no trecho da tabela onde cada rodada vira manchete, não só resultado.",
                f"Campeonato de pontos corridos pede regularidade; {team} mostra onde está no retrato do momento.",
            ],
            seed + ":lt:lead",
        )
        subheadline = _pick_variant_by_seed(
            [
                f"{rank}º lugar, {pts} pontos em {played} jogos — aproveitamento de {ap_pct}% dos pontos disputados.",
                f"Números da campanha até aqui: {pts} pts, saldo de {gd:+d}, com {team} na {rank}ª posição.",
                f"Leitura rápida: {rank}º colocado com {pts} pontos; o saldo ({gd:+d}) ajuda a contar a história ofensiva e defensiva.",
            ],
            seed + ":lt:sub",
        )

        if rank == 1:
            body_variants = [
                [
                    f"Ficha: {team} lidera o {comp} com {pts} pontos em {played} rodadas, saldo de {gd:+d} e aproveitamento de {ap_pct}% — números de quem manda no ritmo da competição.",
                    f"Estar na ponta muda o discurso: de ‘buscar reação’ para ‘confirmar favoritismo’. Holofote aumenta, e a torcida cobra constância como se fosse obrigação.",
                    f"O detalhe brasileiro: liderança cedo no campeonato vira debate de programa esportivo — às vezes mais do que o próprio jogo da rodada.",
                ],
                [
                    f"{team} aparece no 1º lugar com {pts} pontos e {played} jogos. O saldo ({gd:+d}) sugere time com produção regular — ainda que o calendário castigue quem tropeçar.",
                    f"Na prática, o grupo herda uma pressão boa: todo mundo quer derrubar quem está no topo.",
                    f"Para o treinador, o desafio vira gestão de elenco e de expectativa — porque no Brasil, ‘primeiro colocado’ vira título provisório até o próximo empate.",
                ],
            ]
            why_it_matters = _pick_variant_by_seed(
                [
                    "No pontos corridos, liderança é narrativa diária: muda manchete, muda tom de coletiva e até muda mercado de especulação.",
                    "Topo da tabela atrai atenção da mídia e dos rivais — o time deixa de ser ‘surpresa’ e passa a ser referência.",
                ],
                seed + ":lt:wim:1",
            )
            club_effects = [
                "Discurso interno ganha ambiente de ‘candidato’; cobrança por título ou G-4 fica mais explícita.",
                "Crédito alto para o comando técnico — até o próximo tropeço virar pauta.",
            ]
        elif rank <= 4:
            body_variants = [
                [
                    f"Ficha: {team} é o {rank}º colocado no {comp}, com {pts} pontos em {played} jogos e saldo {gd:+d}. Está no G-4 — faixa que, em ano de Libertadores/Sul-Americana, vira obsessão de torcida.",
                    f"O recorte é de campanha viva: não dá para cravar nada ainda, mas dá para discutir se o time está no grupo dos que ‘estão na conversa’.",
                    f"Cada empate dói mais quando a tabela está densa; cada vitória vira passo enorme porque o pelotão do meio não perdoa.",
                ],
                [
                    f"{team} aparece em {rank}º com {pts} pontos. O aproveitamento ({ap_pct}%) ajuda a explicar se o time está ‘no ritmo’ dos primeiros ou se precisa de sequência para consolidar.",
                    f"No Brasil, G-4 vira palavra de ordem cedo: torcida compara com rival, mídia projeta cenário e diretoria observa o desgaste do calendário.",
                    f"O próximo ciclo de jogos costuma dizer se dá para sonhar alto ou se o realismo pede regularidade antes de promessa.",
                ],
            ]
            why_it_matters = _pick_variant_by_seed(
                [
                    "Posição no topo da tabela redefine prioridades: treinos, rotação e até comunicação — tudo vira gestão de expectativa.",
                    "No G-4, o debate público muda: menos ‘reconstrução’, mais ‘aproveitar janela’.",
                ],
                seed + ":lt:wim:g4",
            )
            club_effects = [
                "Expectativa da torcida sobe; cobrança por vaga internacional fica mais explícita.",
                "Comissão técnica ganha argumentos — mas também ganha pressão para não desperdiçar posição.",
            ]
        elif rank <= 10:
            body_variants = [
                [
                    f"Ficha: {team} está na {rank}ª posição, com {pts} pontos em {played} jogos e saldo {gd:+d}. É o tal meio de tabela: nem segurança de topo, nem drama de Z-4 — mas com pouco margem para oscilar.",
                    f"A leitura comum é de time que precisa de sequência: uma semana boa empurra para o pelotão de cima; uma semana ruim aproxima do nervosismo.",
                    f"No noticiário, meio de tabela vira ‘zona de empate’: ponto até ajuda, mas vitória vira urgência quando o calendário aperta.",
                ],
                [
                    f"{team} soma {pts} pontos e aparece em {rank}º. O aproveitamento de {ap_pct}% mostra campanha inconsistente ou calendário difícil — dependendo do olhar.",
                    f"Para torcedor, é fase de paciência curta: empate vira crise rápida; vitória vira ‘hora de subir’.",
                    f"O treinador costuma ouvir dois barulhos ao mesmo tempo: calendário pedindo rotação e tabela pedindo resultado.",
                ],
            ]
            why_it_matters = _pick_variant_by_seed(
                [
                    "Meio de tabela é janela de virada: quem engrena sequência salta; quem oscila vira alvo de cobrança rápida.",
                    "No contexto do Brasileirão, posição intermediária mexe na pauta de reforço e no discurso da diretoria.",
                ],
                seed + ":lt:wim:mid",
            )
            club_effects = [
                "Ambiente pode alternar entre ‘tranquilo’ e ‘alarme’ com dois resultados seguidos.",
                "Planejamento de elenco fica sensível: uma janela mal usada pode custar posição.",
            ]
        elif z4:
            body_variants = [
                [
                    f"Alerta de tabela: {team} está na {rank}ª posição com {pts} pontos em {played} jogos (saldo {gd:+d}). É o trecho em que a palavra ‘Z-4’ aparece em capa mesmo com vitória na última rodada.",
                    f"A pressão muda de tom: menos ‘projeto’, mais ‘ponto a qualquer custo’. Torcida cobra, mídia amplia e cada empate dói em dobro.",
                    f"O time precisa de regularidade defensiva e eficiência ofensiva ao mesmo tempo — senão o calendário consome moral rápido.",
                ],
                [
                    f"{team} aparece na parte de baixo ({rank}º) com {pts} pontos. Aproveitamento de {ap_pct}% explica parte da história; a outra parte é detalhe de jogo que decide pontos.",
                    f"No Brasil, zona de rebaixamento vira conteúdo diário: programa esportivo, rádio e grupo de torcedor tratam cada rodada como final.",
                    f"A diretoria entra no modo ‘curto prazo’: resultado manda, e decisões podem antecipar.",
                ],
            ]
            why_it_matters = _pick_variant_by_seed(
                [
                    "Zona de rebaixamento altera tudo: pauta interna, especulação de mercado e até minutagem de jovens — tudo fica mais conservador.",
                    "No calendário apertado, um ciclo ruim derruba confiança mais rápido do que estatística explica.",
                ],
                seed + ":lt:wim:z4",
            )
            club_effects = [
                "Cobrança intensa da torcida e da imprensa; clima de urgência no CT.",
                "Risco de mudanças forçadas (técnico, esquema ou peças) se a sequência não melhorar.",
            ]
        else:
            body_variants = [
                [
                    f"Ficha: {team} está na {rank}ª posição do {comp}, com {pts} pontos em {played} jogos e saldo {gd:+d} (aproveitamento {ap_pct}%).",
                    f"O cenário é de construção: dá para subir com sequência, mas também dá para perder posição se o time não fechar jogos.",
                    f"No ritmo do campeonato brasileiro, a tabela muda rápido — e a narrativa muda junto.",
                ],
                [
                    f"{team} soma {pts} pontos e aparece em {rank}º. Não é nem o pelotão de cima nem o fundo — é a faixa onde detalhe decide se a semana foi boa ou ruim.",
                    f"Para torcedor, vira jogo de paciência; para treinador, vira gestão de elenco e resultado ao mesmo tempo.",
                    f"A imprensa costuma rotular como ‘time irregular’ — rótulo que some com três vitórias seguidas.",
                ],
            ]
            why_it_matters = _pick_variant_by_seed(
                [
                    "Classificação é o espelho mais honesto: muda discurso, muda cobrança e muda prioridade de reforço.",
                    "No Brasileirão, posição na tabela vira assunto diário — mesmo quando o time não entra em campo.",
                ],
                seed + ":lt:wim:else",
            )
            club_effects = [
                "Percepção pública oscila com sequências curtas; estabilidade vira ativo raro.",
                "Objetivos da temporada podem ser revisados cedo se a distância para o G-4 ou para o Z-4 mudar rápido.",
            ]
        body = _pick_variant_by_seed(body_variants, seed + ":lt:body")
        tags.append("Tabela")

    elif fact_type == "surprise_league_position":
        rival = signals.get("rival_name", "Equipe surpresa")
        rival_rank = _to_int(signals.get("rival_rank"), 0)
        comp = cnames[0] if cnames else "campeonato"
        body_variants = [
            [f"Surpresa na tabela: {rival} aparece na {rival_rank}ª posição do {comp}.",
             "A campanha inesperada chama atenção e pode alterar a dinâmica da competição."],
            [f"{rival} surpreende e ocupa a {rival_rank}ª colocação no {comp}. Poucos apostavam nessa campanha.",
             "O equilíbrio do campeonato ganha novo capítulo com esse desempenho inesperado."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Equipes surpresa mudam a dinâmica da competição e impactam adversários diretos."
        club_effects = [f"Pode afetar objetivos de {team}.", "Novo adversário na disputa."]

    elif fact_type == "rival_highlight":
        rival = signals.get("rival_name", "Rival")
        body_variants = [
            [f"De olho no adversário: {rival} vem se fortalecendo e pode ser obstáculo direto.",
             "A movimentação do rival exige atenção e pode influenciar a estratégia do treinador."],
            [f"{rival} faz campanha forte e se consolida como concorrente direto na briga da temporada.",
             "O desempenho do adversário eleva o nível de exigência para os próximos compromissos."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "Acompanhar rivais é essencial para definir estratégias competitivas."
        club_effects = ["Eleva padrão de exigência.", "Pode mudar metas de curto prazo."]

    elif fact_type == "external_narrative":
        body = [summary]
        if signals.get("narrative_extra"):
            body.append(str(signals["narrative_extra"]))
        why_it_matters = "Eventos externos criam contexto e profundidade na experiência da temporada."
        club_effects = ["Contexto narrativo para a carreira."]

    elif fact_type == "press_conference_fallout":
        aud = str(signals.get("audience") or entities.get("audience_focus") or "")
        body = [summary]
        if pnames:
            body.append(f"Leitura em torno de {pnames[0]}: a comunicação pública vira referência interna nos próximos dias.")
        why_it_matters = "Coletivas moldam expectativa da diretoria, do elenco e da torcida na edição seguinte."
        club_effects = [
            f"Tom percebido ({signals.get('tone', '—')}) com delta de reputação {signals.get('reputation_delta', 0)}.",
            f"Repercussão no vestiário (moral {signals.get('morale_delta', 0)}). Audiência foco: {aud or 'geral'}.",
        ]
        tags.extend(["Comunicação", "Coletiva"])

    elif fact_type == "tactical_identity_shift":
        body_variants = [
            [summary, "A busca por uma nova identidade tática pode ser o ponto de virada da temporada."],
            [summary, "Mudanças no estilo de jogo dividem opiniões mas podem trazer resultados."],
            [summary, "O treinador tenta encontrar o equilíbrio certo entre risco e segurança."],
        ]
        body = _pick_variant_by_seed(body_variants, seed)
        why_it_matters = "A identidade tática define como a equipe compete e é percebida."
        club_effects = ["Período de adaptação.", "Resultados podem oscilar."]

    return {
        "slot": slot,
        "slot_label": _compute_slot_label(slot, fact_type),
        "kind": _article_kind_for_slot(slot),
        "priority": _to_int(fact.get("importance"), 50),
        "impact": impact,
        "headline": title,
        "subheadline": subheadline,
        "lead": lead,
        "body": body,
        "why_it_matters": why_it_matters,
        "club_effects": club_effects,
        "tags": tags,
        "entities": {
            "club": club_names,
            "players": pnames,
            "staff": entities.get("staff_labels") or [],
            "competitions": cnames,
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
    max_stories = min(limit, 7)
    ranked = sorted(
        [fact for fact in facts if bool((fact.get("editorial_flags") or {}).get("eligible_for_news"))],
        key=lambda item: (-_to_int(item.get("importance"), 0), -int(_to_float(item.get("confidence"), 0) * 1000)),
    )
    used_groups: set = set()
    stories: List[Dict[str, Any]] = []
    slot_candidates = {slot: [] for slot in SLOT_ORDER}
    for fact in ranked:
        slot_candidates.setdefault(_slot_for_fact(fact), []).append(fact)
    for slot in SLOT_ORDER:
        for fact in slot_candidates.get(slot, []):
            dedupe_group = str((fact.get("editorial_flags") or {}).get("dedupe_group") or fact.get("dedupe_group") or "")
            if dedupe_group in used_groups:
                continue
            used_groups.add(dedupe_group)
            stories.append(_render_article_from_fact(fact))
            break
    if len(stories) < max_stories:
        for fact in ranked:
            dedupe_group = str((fact.get("editorial_flags") or {}).get("dedupe_group") or fact.get("dedupe_group") or "")
            if dedupe_group in used_groups:
                continue
            used_groups.add(dedupe_group)
            stories.append(_render_article_from_fact(fact))
            if len(stories) >= max_stories:
                break
    return stories[:max_stories]


def _fact_dedupe_key(fact: Dict[str, Any]) -> str:
    ed = dict(fact.get("editorial_flags") or {})
    dg = str(ed.get("dedupe_group") or fact.get("dedupe_group") or "").strip()
    return dg or f"_anon_{hash(json.dumps(fact, sort_keys=True, default=str))}"


def _extract_press_career_facts(save_uid: str, game_date: str) -> List[Dict[str, Any]]:
    """Factos gerados após coletivas — reaplicados após rebuild do jornal para não serem apagados."""
    out: List[Dict[str, Any]] = []
    for pf in get_career_facts(save_uid=save_uid, game_date=game_date, limit=500):
        refs = pf.get("source_refs") or []
        if any(isinstance(r, dict) and r.get("source") == "press_conference" for r in refs):
            out.append({k: v for k, v in pf.items() if k != "id"})
    return out


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
    force_rebuild: bool = False,
) -> List[Dict[str, Any]]:
    if not force_rebuild:
        existing = get_career_facts(save_uid=save_uid, game_date=game_date)
        if existing:
            return existing

    user_team_id = _user_team_id(state)
    club = dict(state.get("club") or {})
    fixtures = list(state.get("fixtures") or [])
    squad = list(state.get("squad") or [])
    injuries = list(state.get("injuries") or [])
    standings = list(state.get("standings") or [])
    transfer_history = list(state.get("transfer_history") or [])
    tactical = dict((management_state.get("tactical") or {}))
    locker = dict((management_state.get("locker_room") or {}))
    medical = dict((management_state.get("medical") or {}))
    competition_names = _competition_name_index(save_uid)
    current_game_date_raw = _game_date_value(state)
    results = _recent_results(fixtures, user_team_id, limit=8, game_date_raw=current_game_date_raw)
    last_fixture = _decorate_fixture(_last_completed_fixture(fixtures, user_team_id), user_team_id, competition_names)
    next_fix = _decorate_fixture(
        _next_fixture(fixtures, user_team_id, game_date_raw=current_game_date_raw),
        user_team_id,
        competition_names,
    )
    primary_table = _select_primary_league_table(state, user_team_id, next_fix, competition_names)
    season_stats = dict(club.get("season_stats") or {})

    facts: List[Dict[str, Any]] = []
    team_name = str(club.get("team_name") or "Clube")
    competition_name = str((last_fixture or {}).get("competition_name") or (primary_table or {}).get("competition_name") or "")
    seed_base = f"{save_uid}:{game_date}"

    def _ent(extra_players: Optional[List] = None, extra_comps: Optional[List] = None, **kw: Any) -> Dict[str, Any]:
        e: Dict[str, Any] = {
            "club_ids": [user_team_id],
            "club_names": [team_name],
            "player_ids": [],
            "player_names": extra_players or [],
            "staff_labels": ["manager"],
            "competition_ids": [],
            "competition_names": extra_comps or ([competition_name] if competition_name else []),
        }
        e.update(kw)
        return e

    # --- 1. ÚLTIMO RESULTADO ---
    if last_fixture:
        letter = _result_letter(last_fixture, user_team_id)
        opponent_name = str(
            last_fixture.get("away_team_name") if _to_int(last_fixture.get("home_team_id"), -1) == user_team_id else last_fixture.get("home_team_name")
        )
        hs = _to_int(last_fixture.get("home_score"), 0)
        aws = _to_int(last_fixture.get("away_score"), 0)
        score = f"{hs} x {aws}"
        goal_diff = abs(hs - aws)
        is_user_home = _to_int(last_fixture.get("home_team_id"), -1) == user_team_id
        user_goals = hs if is_user_home else aws

        title_variants_win = [
            f"{team_name} vence {opponent_name} e embala na temporada",
            f"Vitória sobre {opponent_name} reforça confiança em {team_name}",
            f"{team_name} bate {opponent_name} por {score} e respira",
            f"Triunfo por {score}! {team_name} supera {opponent_name}",
            f"{team_name} despacha {opponent_name} e ganha fôlego",
        ]
        title_variants_loss = [
            f"{team_name} cai diante de {opponent_name} e pressão cresce",
            f"Derrota para {opponent_name} liga o alerta em {team_name}",
            f"{opponent_name} vence e {team_name} entra em alerta",
            f"Revés por {score}: {team_name} perde para {opponent_name}",
            f"{team_name} tropeça contra {opponent_name} e vê pressão subir",
        ]
        title_variants_draw = [
            f"Empate em {score}: {team_name} fica no zero a zero com {opponent_name}" if hs == 0 else f"Empate em {score} entre {team_name} e {opponent_name}",
            f"{team_name} não passa de empate com {opponent_name}",
            f"Igualdade em {score} frustra {team_name} contra {opponent_name}",
        ]

        if letter == "W":
            ft = "big_win" if goal_diff >= 3 else "important_win"
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type=ft, category="match",
                title=_pick_variant_by_seed(title_variants_win, f"{seed_base}:win"),
                summary=f"Resultado em {score} contra {opponent_name}. {team_name} soma mais 3 pontos.",
                importance=90 if goal_diff >= 3 else 88, confidence=0.95,
                entities=_ent(),
                source_refs=[{"source": "state.fixtures", "ref_id": str(last_fixture.get("id") or "")}],
                signals={"trend": "positive", "score": score, "opponent": opponent_name, "goal_diff": goal_diff},
                dedupe_group=f"last_match_{game_date}",
            ))
        elif letter == "L":
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="important_loss", category="match",
                title=_pick_variant_by_seed(title_variants_loss, f"{seed_base}:loss"),
                summary=f"Derrota por {score} contra {opponent_name} aumenta a pressão.",
                importance=90, confidence=0.95,
                entities=_ent(),
                source_refs=[{"source": "state.fixtures", "ref_id": str(last_fixture.get("id") or "")}],
                signals={"trend": "negative", "score": score, "opponent": opponent_name},
                dedupe_group=f"last_match_{game_date}",
            ))
        elif letter == "D":
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="draw_frustration", category="match",
                title=_pick_variant_by_seed(title_variants_draw, f"{seed_base}:draw"),
                summary=f"Empate em {score} com {opponent_name}. Pontos divididos.",
                importance=72, confidence=0.92,
                entities=_ent(),
                source_refs=[{"source": "state.fixtures", "ref_id": str(last_fixture.get("id") or "")}],
                signals={"trend": "neutral", "score": score, "opponent": opponent_name},
                dedupe_group=f"last_match_{game_date}",
            ))

    # --- 2. SEQUÊNCIA (positiva ou negativa) ---
    streak_w = 0
    for r in results:
        if r == "W":
            streak_w += 1
        else:
            break
    streak_nw = 0
    for r in results:
        if r != "W":
            streak_nw += 1
        else:
            break

    if streak_w >= 3:
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="positive_streak", category="form",
            title=_pick_variant_by_seed([
                f"{team_name} emplacou {streak_w} vitórias seguidas!",
                f"Fase de ouro: {team_name} vence {streak_w} partidas consecutivas",
                f"Sequência invicta! {streak_w} vitórias de {team_name}",
            ], f"{seed_base}:streak_w"),
            summary=f"A série de {streak_w} vitórias consolida o bom momento e melhora a posição na tabela.",
            importance=80, confidence=0.9,
            entities=_ent(),
            source_refs=[{"source": "state.fixtures", "ref_id": "recent_form"}],
            signals={"trend": "positive", "last_5": results[:5], "streak_count": streak_w},
            dedupe_group="recent_form",
        ))
    elif streak_nw >= 4:
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="winless_streak", category="form",
            title=_pick_variant_by_seed([
                f"{team_name} não vence há {streak_nw} jogos e pressão cresce",
                f"Seca de vitórias: {team_name} sem vencer há {streak_nw} partidas",
                f"Fase difícil de {team_name}: {streak_nw} jogos sem vitória",
            ], f"{seed_base}:streak_nw"),
            summary="A ausência de vitórias pesa no moral e eleva a cobrança por reação.",
            importance=86, confidence=0.92,
            entities=_ent(),
            source_refs=[{"source": "state.fixtures", "ref_id": "recent_form"}],
            signals={"trend": "negative", "last_5": results[:5], "streak_count": streak_nw},
            dedupe_group="recent_form",
        ))

    # --- 3. CLASSIFICAÇÃO E TABELA ---
    if primary_table:
        rank = _to_int(primary_table.get("rank"), 0)
        pts = _to_int(primary_table.get("points"), 0)
        played = _to_int(primary_table.get("played"), 0)
        team_count = _to_int(primary_table.get("team_count"), 0)
        comp = primary_table.get("competition_name") or competition_name
        gd = _to_int(primary_table.get("goal_difference"), 0)

        if rank > 0 and played > 0:
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="league_table_shift", category="table",
                title=_pick_variant_by_seed([
                    f"{team_name} ocupa a {rank}ª posição com {pts} pontos",
                    f"Classificação: {team_name} em {rank}º no {comp}",
                    f"{rank}º lugar para {team_name} após {played} rodadas",
                    f"{team_name} é o {rank}º colocado com saldo de {gd:+d} gols",
                    f"Panorama da tabela: {team_name} na {rank}ª colocação",
                ], f"{seed_base}:table"),
                summary=f"{team_name} soma {pts} pontos em {played} jogos e ocupa a {rank}ª posição entre {team_count} equipes no {comp}.",
                importance=74 if rank <= 4 else 65, confidence=0.95,
                entities=_ent(extra_comps=[comp] if comp else None),
                source_refs=[{"source": "state.standings", "ref_id": f"rank_{rank}"}],
                signals={"rank": rank, "points": pts, "played": played, "goal_difference": gd, "team_count": team_count},
                dedupe_group="table_position",
            ))

        # Equipe surpresa no topo ou perto
        all_rows_comp = [r for r in standings if _to_int(r.get("competition_id"), 0) == _to_int(primary_table.get("competition_id"), 0)]
        sorted_standings = sorted(all_rows_comp, key=_standings_sort_key)
        if len(sorted_standings) >= 5 and rank > 0:
            for idx, row in enumerate(sorted_standings[:5]):
                rival_id = _to_int(row.get("team_id"), 0)
                if rival_id != user_team_id and rival_id > 0:
                    rival_name = str(row.get("team_name") or f"Time {rival_id}")
                    rival_rank = idx + 1
                    rival_pts = _to_int((row.get("total") or {}).get("points"), 0)
                    facts.append(_build_fact(
                        save_uid=save_uid, game_date=game_date,
                        fact_type="rival_highlight", category="table",
                        title=_pick_variant_by_seed([
                            f"{rival_name} é o {rival_rank}º colocado e briga pelo topo",
                            f"De olho no rival: {rival_name} aparece forte no {comp}",
                            f"{rival_name} soma {rival_pts} pontos e pressiona na tabela",
                        ], f"{seed_base}:rival:{rival_id}"),
                        summary=f"{rival_name} está na {rival_rank}ª posição com {rival_pts} pontos e disputa diretamente com {team_name}.",
                        importance=60, confidence=0.88,
                        entities=_ent(extra_comps=[comp] if comp else None),
                        source_refs=[{"source": "state.standings", "ref_id": f"rival_{rival_id}"}],
                        signals={"rival_name": rival_name, "rival_rank": rival_rank, "rival_points": rival_pts},
                        dedupe_group=f"rival_{rival_id}",
                    ))
                    break

    # --- 4. ARTILHEIRO E GARÇOM DO ELENCO ---
    top_scorer_info = season_stats.get("top_scorer")
    if top_scorer_info:
        ts_pid = _to_int(top_scorer_info.get("playerid"), 0)
        ts_goals = _to_int(top_scorer_info.get("total_goals"), 0)
        ts_player = next((p for p in squad if _to_int(p.get("playerid"), 0) == ts_pid), None)
        ts_name = _player_name(ts_player) if ts_player else f"Jogador #{ts_pid}"
        if ts_goals >= 3:
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="top_scorer_update", category="player",
                title=_pick_variant_by_seed([
                    f"{ts_name}: {ts_goals} gols e artilheiro de {team_name}",
                    f"Artilharia: {ts_name} lidera com {ts_goals} gols",
                    f"{ts_name} chega a {ts_goals} gols e é referência ofensiva",
                    f"Gol é com {ts_name}: {ts_goals} na temporada",
                    f"Artilheiro! {ts_name} marca {ts_goals} e puxa a fila de {team_name}",
                ], f"{seed_base}:scorer"),
                summary=f"{ts_name} lidera a artilharia de {team_name} com {ts_goals} gols na temporada.",
                importance=72, confidence=0.9,
                entities=_ent(extra_players=[ts_name]),
                source_refs=[{"source": "season_stats", "ref_id": f"scorer_{ts_pid}"}],
                signals={"goals": ts_goals, "playerid": ts_pid},
                dedupe_group="top_scorer",
            ))

    top_assist_info = season_stats.get("top_assist")
    if top_assist_info:
        ta_pid = _to_int(top_assist_info.get("playerid"), 0)
        ta_assists = _to_int(top_assist_info.get("total_assists"), 0)
        ta_player = next((p for p in squad if _to_int(p.get("playerid"), 0) == ta_pid), None)
        ta_name = _player_name(ta_player) if ta_player else f"Jogador #{ta_pid}"
        if ta_assists >= 2:
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="top_assister_update", category="player",
                title=_pick_variant_by_seed([
                    f"{ta_name}: {ta_assists} assistências e garçom da equipe",
                    f"Garçom: {ta_name} soma {ta_assists} passes decisivos",
                    f"{ta_name} distribui jogo com {ta_assists} assistências",
                ], f"{seed_base}:assist"),
                summary=f"{ta_name} é o líder em assistências de {team_name} com {ta_assists} passes para gol.",
                importance=68, confidence=0.88,
                entities=_ent(extra_players=[ta_name]),
                source_refs=[{"source": "season_stats", "ref_id": f"assist_{ta_pid}"}],
                signals={"assists": ta_assists, "playerid": ta_pid},
                dedupe_group="top_assister",
            ))

    # --- 5. JOGADOR EM FORMA / JOVEM PROMESSA ---
    squad_sorted = sorted(
        squad,
        key=lambda item: (_to_int(item.get("form"), -1), _to_float(item.get("overall_live"), _to_float(item.get("overallrating"), 0))),
        reverse=True,
    )
    if squad_sorted and _to_int(squad_sorted[0].get("form"), -1) >= 3:
        top_p = dict(squad_sorted[0])
        tp_name = _player_name(top_p)
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="key_player_in_form", category="player",
            title=_pick_variant_by_seed([
                f"{tp_name} vive grande fase e é destaque de {team_name}",
                f"Brilho individual: {tp_name} em excelente momento",
                f"{tp_name} sustenta o bom momento com atuações decisivas",
                f"Forma excepcional: {tp_name} é arma principal do treinador",
                f"{tp_name} empilha boas atuações e chama atenção",
            ], f"{seed_base}:form"),
            summary=f"{tp_name} está no melhor momento e é peça-chave nas decisões do treinador.",
            importance=70, confidence=0.84,
            entities=_ent(extra_players=[tp_name]),
            source_refs=[{"source": "state.squad", "ref_id": str(top_p.get("playerid") or "")}],
            signals={"trend": "positive"},
            dedupe_group="player_form_primary",
        ))

    young_talents = [
        p for p in squad
        if _to_int(p.get("age"), 30) <= 21
        and _to_int(p.get("potential"), 0) >= 80
        and _to_int(p.get("potential"), 0) - _to_int(p.get("overallrating"), 0) >= 8
    ]
    if young_talents:
        young_talents.sort(key=lambda p: _to_int(p.get("potential"), 0), reverse=True)
        yt = young_talents[0]
        yt_name = _player_name(yt)
        yt_ovr = _to_int(yt.get("overallrating"), 0)
        yt_pot = _to_int(yt.get("potential"), 0)
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="young_talent_rise", category="player",
            title=_pick_variant_by_seed([
                f"Joia da base: {yt_name} tem potencial para ser estrela",
                f"{yt_name} ({_to_int(yt.get('age'), 0)} anos) cresce e atrai olhares",
                f"Promessa: {yt_name} evolui e pode ganhar espaço no elenco",
            ], f"{seed_base}:youth"),
            summary=f"{yt_name} tem {_to_int(yt.get('age'), 0)} anos, overall {yt_ovr} e potencial de {yt_pot}.",
            importance=62, confidence=0.82,
            entities=_ent(extra_players=[yt_name]),
            source_refs=[{"source": "state.squad", "ref_id": str(yt.get("playerid") or "")}],
            signals={"overall": yt_ovr, "potential": yt_pot, "age": _to_int(yt.get("age"), 0)},
            dedupe_group="young_talent",
        ))

    # --- 6. PRÓXIMO JOGO / CLÁSSICO ---
    if next_fix:
        next_opp = str(
            next_fix.get("away_team_name") if _to_int(next_fix.get("home_team_id"), -1) == user_team_id else next_fix.get("home_team_name")
        )
        next_comp = str(next_fix.get("competition_name") or competition_name)
        next_date_label = str(next_fix.get("date_label") or "")
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="upcoming_derby", category="calendar",
            title=_pick_variant_by_seed([
                f"Próximo desafio: {team_name} x {next_opp}",
                f"{team_name} se prepara para enfrentar {next_opp}",
                f"Calendário: {next_opp} é o próximo adversário",
                f"Foco total: {team_name} mira o duelo com {next_opp}",
                f"Preparação em curso para {team_name} x {next_opp}",
            ], f"{seed_base}:next"),
            summary=f"{team_name} enfrenta {next_opp} pelo {next_comp}. {('Jogo em ' + next_date_label + '.') if next_date_label else ''}",
            importance=70, confidence=0.95,
            entities=_ent(extra_comps=[next_comp] if next_comp else None),
            source_refs=[{"source": "state.fixtures", "ref_id": str(next_fix.get("id") or "")}],
            signals={"opponent": next_opp, "competition": next_comp},
            dedupe_group="upcoming_match",
        ))

    # Congestionamento de calendário
    user_upcoming = sorted(
        [f for f in fixtures if _is_user_fixture(f, user_team_id) and not f.get("is_completed")],
        key=_fixture_sort_key,
    )
    if len(user_upcoming) >= 4:
        first_raw = _to_int(user_upcoming[0].get("date_raw"), 0)
        fourth_raw = _to_int(user_upcoming[3].get("date_raw"), 0)
        if fourth_raw > 0 and first_raw > 0 and (fourth_raw - first_raw) <= 14:
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="calendar_congestion", category="calendar",
                title=_pick_variant_by_seed([
                    f"Maratona à vista: {team_name} tem 4 jogos em período curto",
                    f"Calendário apertado cobra gestão física de {team_name}",
                    f"Sequência intensa: 4 partidas em poucos dias para {team_name}",
                ], f"{seed_base}:calendar"),
                summary="A densidade do calendário exige rotação inteligente e gestão cuidadosa do elenco.",
                importance=64, confidence=0.88,
                entities=_ent(),
                source_refs=[{"source": "state.fixtures", "ref_id": "calendar"}],
                signals={"games_in_period": 4},
                dedupe_group="calendar_congestion",
            ))

    # --- 7. TRANSFERÊNCIAS RECENTES ---
    if transfer_history:
        recent_transfers = sorted(
            transfer_history,
            key=lambda t: _to_int(t.get("signed_date") or t.get("completed_date"), 0),
            reverse=True,
        )[:3]
        for i, tx in enumerate(recent_transfers):
            tx_player = str(tx.get("player_name") or "Jogador")
            tx_direction = str(tx.get("direction") or tx.get("type") or "")
            tx_fee = tx.get("fee") or tx.get("amount") or 0
            fee_label = f"€{_to_int(tx_fee, 0):,}" if tx_fee else "valor não divulgado"
            if tx_direction in ("in", "buy"):
                title_t = f"Reforço: {tx_player} chega a {team_name}"
                dir_signal = "in"
            else:
                title_t = f"{tx_player} deixa {team_name}"
                dir_signal = "out"
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="transfer_completed", category="transfer",
                title=title_t,
                summary=f"Negociação de {tx_player} por {fee_label}.",
                importance=68 - (i * 4), confidence=0.92,
                entities=_ent(extra_players=[tx_player]),
                source_refs=[{"source": "state.transfer_history", "ref_id": str(tx.get("id") or "")}],
                signals={"direction": dir_signal, "fee": fee_label, "playerid": _to_int(tx.get("player_id"), 0)},
                dedupe_group=f"transfer_{tx.get('id', i)}",
            ))
            if i == 0:
                break

    # --- 8. LESÕES ---
    if injuries:
        injury = dict(injuries[0] or {})
        injury_name = _player_name(injury)
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="critical_injury", category="medical",
            title=_pick_variant_by_seed([
                f"{injury_name} no departamento médico: preocupação em {team_name}",
                f"Lesão de {injury_name} tira o sono da comissão técnica",
                f"{injury_name} se machuca e desfalca {team_name}",
            ], f"{seed_base}:injury"),
            summary=f"{injury_name} está no departamento médico e pode ser desfalque nos próximos jogos.",
            importance=78, confidence=0.92,
            entities=_ent(extra_players=[injury_name]),
            source_refs=[{"source": "state.injuries", "ref_id": str(injury.get("playerid") or "")}],
            signals={"injury_risk": _to_int(medical.get("injury_risk_index"), 50)},
            dedupe_group="medical_primary",
        ))

    # --- 9. DIRETORIA E PRESSÃO ---
    if board_active and str(board_active.get("status") or "") == "active":
        ft = "board_ultimatum_active" if str(board_active.get("challenge_type") or "") == "ULTIMATUM" else "board_pressure_active"
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type=ft, category="board",
            title=str(board_active.get("title") or "Diretoria aumenta a pressão"),
            summary=str(board_active.get("description") or "A diretoria elevou o nível de cobrança."),
            importance=92, confidence=0.98,
            entities=_ent(staff_labels=["board", "manager"]),
            source_refs=[{"source": "board_active_challenge", "ref_id": str(board_active.get("id") or "")}],
            signals={"pressure_delta": 18},
            dedupe_group="board_pressure",
        ))

    if crisis_active and str(crisis_active.get("status") or "") == "active":
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="board_pressure_active", category="season",
            title="Crise em curso redefine o contexto da carreira",
            summary=str(crisis_active.get("summary") or "O ambiente do clube exige reação imediata."),
            importance=93, confidence=0.95,
            entities=_ent(staff_labels=["manager", "board"]),
            source_refs=[{"source": "crisis_active_arc", "ref_id": str(crisis_active.get("id") or "")}],
            signals={"pressure_delta": 22},
            dedupe_group="crisis_context",
        ))

    # --- 10. MERCADO ---
    if market_rumors:
        strongest_rumor = max(market_rumors, key=lambda item: _to_int(item.get("confidence_level"), 0))
        if _to_int(strongest_rumor.get("confidence_level"), 0) >= 70:
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="market_rumor_hot", category="market",
                title=str(strongest_rumor.get("headline") or "Mercado ganha força nos bastidores"),
                summary=str(strongest_rumor.get("content") or "A movimentação de mercado ganhou tração nos bastidores."),
                importance=max(70, _to_int(strongest_rumor.get("confidence_level"), 70)),
                confidence=min(0.99, _to_int(strongest_rumor.get("confidence_level"), 70) / 100.0),
                entities=_ent(),
                source_refs=[{"source": "market_rumors_recent", "ref_id": str(strongest_rumor.get("id") or "")}],
                signals={"media_heat": _to_int(strongest_rumor.get("confidence_level"), 70)},
                dedupe_group="market_primary",
            ))

    # --- 11. VESTIÁRIO ---
    frustrated = next(
        (row for row in player_relations
         if _to_int(row.get("frustration"), 0) >= 45 or str(row.get("status_label") or "") in {"insatisfeito", "frustrado"}),
        None,
    )
    if frustrated:
        fr_name = str(frustrated.get("player_name") or "Jogador do elenco")
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="reserve_frustrated", category="locker_room",
            title=_pick_variant_by_seed([
                f"Insatisfação: {fr_name} quer mais espaço em {team_name}",
                f"{fr_name} demonstra frustração nos bastidores",
                f"Vestiário em alerta: {fr_name} pode pedir para sair",
            ], f"{seed_base}:frustrated"),
            summary=f"{fr_name} está insatisfeito e a situação exige gestão cuidadosa.",
            importance=76, confidence=0.88,
            entities=_ent(extra_players=[fr_name]),
            source_refs=[{"source": "player_relations_recent", "ref_id": str(frustrated.get("id") or "")}],
            signals={"morale_delta": -8},
            dedupe_group="locker_room_primary",
        ))

    cohesion = locker.get("cohesion")
    low_morale_count = _to_int(locker.get("low_morale_count"), 0)
    if (_to_int(cohesion, 55) <= 45) or low_morale_count >= 3:
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="locker_room_tension", category="locker_room",
            title=_pick_variant_by_seed([
                f"Clima tenso no vestiário de {team_name}",
                f"Bastidores aquecem: moral em baixa no elenco",
                f"Vestiário de {team_name} pede atenção do treinador",
            ], f"{seed_base}:locker"),
            summary="Os sinais internos indicam necessidade de gestão mais cuidadosa de confiança e papéis.",
            importance=80, confidence=0.9,
            entities=_ent(),
            source_refs=[{"source": "career_management_state", "ref_id": "locker_room"}],
            signals={"morale_delta": -6},
            dedupe_group="locker_room_tension",
        ))

    # --- 12. TÁTICA ---
    stability = _to_int(tactical.get("stability"), 55)
    if stability <= 45:
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="tactical_identity_shift", category="season",
            title=_pick_variant_by_seed([
                f"Identidade tática de {team_name} está em construção",
                f"Treinador busca modelo de jogo ideal para {team_name}",
                f"Mudanças táticas marcam fase de transição de {team_name}",
            ], f"{seed_base}:tactic"),
            summary="A equipe passa por fase de ajustes que pode definir o rumo da temporada.",
            importance=68, confidence=0.82,
            entities=_ent(),
            source_refs=[{"source": "career_management_state", "ref_id": "tactical"}],
            signals={"trend": "neutral", "stability": stability},
            dedupe_group="tactical_shift",
        ))

    # --- 13. ARCO DA TEMPORADA ---
    if season_arc_active and _to_int(season_arc_active.get("current_milestone"), 1) > 1:
        facts.append(_build_fact(
            save_uid=save_uid, game_date=game_date,
            fact_type="season_arc_milestone", category="season",
            title=str(season_arc_active.get("title") or "Momento decisivo da temporada"),
            summary=str(season_arc_active.get("theme") or "A temporada ganhou novo peso narrativo."),
            importance=72, confidence=0.88,
            entities=_ent(),
            source_refs=[{"source": "season_arc_active", "ref_id": str(season_arc_active.get("id") or "")}],
            signals={"milestone": _to_int(season_arc_active.get("current_milestone"), 1)},
            dedupe_group="season_arc_primary",
        ))

    # --- 14. NARRATIVA EXTERNA (contextual) ---
    gd_obj = _game_date_obj(state)
    if gd_obj:
        month = gd_obj.month
        narrative_pool = []
        if month in (1, 2):
            narrative_pool = [
                ("Janela de transferências agita o mercado", "O período de negociações traz especulações e pode alterar elencos."),
                ("Fase final do mercado de inverno", "Clubes correm para fechar reforços antes do prazo final."),
            ]
        elif month in (3, 4):
            narrative_pool = [
                ("Reta decisiva dos campeonatos se aproxima", "As últimas rodadas vão definir campeões, rebaixados e classificados."),
                ("Temporada entra na fase crucial", "Cada ponto vale ouro na disputa pelo título e contra o rebaixamento."),
            ]
        elif month in (5, 6):
            narrative_pool = [
                ("Final de temporada: hora de balanço", "Clubes começam a planejar a próxima janela e avaliar o elenco."),
                ("Férias se aproximam, mas antes as decisões finais", "Os últimos jogos podem definir o futuro de treinadores e jogadores."),
            ]
        elif month in (7, 8):
            narrative_pool = [
                ("Nova temporada! Expectativas renovadas", "O início da temporada traz esperança e novas contratações."),
                ("Pré-temporada define os rumos do ano", "Amistosos e treinos moldam a equipe para os desafios que vêm."),
            ]
        elif month in (9, 10):
            narrative_pool = [
                ("Campeonatos ganham forma e favoritos aparecem", "As primeiras rodadas já desenham o cenário competitivo."),
                ("Início de temporada: quem são os candidatos ao título?", "Os resultados iniciais começam a separar pretendentes de coadjuvantes."),
            ]
        elif month in (11, 12):
            narrative_pool = [
                ("Reta final do primeiro turno agita a competição", "A tabela começa a ganhar forma e pressiona quem está abaixo."),
                ("Virada de turno se aproxima com surpresas", "Equipes inesperadas aparecem na parte de cima da tabela."),
            ]
        if narrative_pool:
            pick = _pick_variant_by_seed(narrative_pool, f"{seed_base}:ext")
            facts.append(_build_fact(
                save_uid=save_uid, game_date=game_date,
                fact_type="external_narrative", category="external",
                title=pick[0],
                summary=pick[1],
                importance=55, confidence=0.8,
                entities=_ent(),
                source_refs=[{"source": "contextual_narrative", "ref_id": f"month_{month}"}],
                signals={"month": month, "narrative_extra": pick[1]},
                dedupe_group="external_narrative",
            ))

    prior_press = _extract_press_career_facts(save_uid, game_date)
    if prior_press:
        by_dg: Dict[str, Dict[str, Any]] = {}
        for f in facts:
            by_dg[_fact_dedupe_key(f)] = f
        for pf in prior_press:
            by_dg[_fact_dedupe_key(pf)] = pf
        facts = list(by_dg.values())

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
            force_rebuild=rebuild,
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
    stories_payload = list(package.get("stories") or [])[: min(limit, 7)]
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


def build_news_feed_daily(save_uid: str, date: Optional[str] = None, limit: int = 7) -> Dict[str, Any]:
    state = _read_state()
    game_date = date or _iso_game_date(state)
    return _build_news_feed_daily_internal(save_uid=save_uid, game_date=game_date, limit=limit, rebuild=False)


def rebuild_news_feed_daily(save_uid: str, date: Optional[str] = None, limit: int = 7) -> Dict[str, Any]:
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

    def seed_from_ui_images(team_name: str) -> Optional[Dict[str, Any]]:
        if str(team_name or "").strip().lower() != "botafogo":
            return None
        return {
            "source": "ui_images_v1",
            "captured_at": "2026-03-27",
            "overview": {
                "lucro": -77_360_000.0,
                "receitas": 50_510_000.0,
                "despesas": 127_860_000.0,
                "club_value": 705_980_000.0,
                "projection": 728_380_000.0,
            },
            "receitas_breakdown": [
                {"label": "Produtos", "amount": 24_780_000.0},
                {"label": "Prêmios em dinheiro", "amount": 10_050_000.0},
                {"label": "Transferências", "amount": 9_150_000.0},
                {"label": "Sócio torcedor", "amount": 3_280_000.0},
                {"label": "Ingressos", "amount": 3_240_000.0},
            ],
            "despesas_breakdown": [
                {"label": "Transferências", "amount": 100_800_000.0},
                {"label": "Salários de atletas", "amount": 23_530_000.0},
                {"label": "Reserva bônus atleta", "amount": 2_500_000.0},
                {"label": "Salários auxiliares técnicos", "amount": 493_910.0},
                {"label": "Manutenção estádio", "amount": 275_000.0},
                {"label": "Custos de viagens", "amount": 196_000.0},
                {"label": "Instalações da base", "amount": 70_000.0},
            ],
            "budget": {
                "current": 46_933_044.0,
                "weekly_allowance": 1_173_326.0,
                "season_flow": {
                    "income": [
                        {"label": "Verba inicial", "amount": 63_469_124.0},
                        {"label": "Prêmio em dinheiro", "amount": 10_050_000.0},
                        {"label": "Venda de ingressos", "amount": 6_523_620.0},
                        {"label": "Cortes salariais", "amount": 2_586_000.0},
                        {"label": "Venda de atletas", "amount": 9_150_000.0},
                    ],
                    "expense": [
                        {"label": "Aumentos salariais", "amount": 22_502_000.0},
                        {"label": "Compra de atletas", "amount": 100_800_000.0},
                    ],
                    "variation_pct": -27,
                },
            },
        }

    ui_seed = finance_state.get("ui_seed_finance_v1")
    if not isinstance(ui_seed, dict) or not ui_seed:
        suggested = seed_from_ui_images(club.get("team_name") or "")
        if suggested:
            ui_seed = suggested
            finance_state["ui_seed_finance_v1"] = ui_seed
            try:
                seed_budget = dict(ui_seed.get("budget") or {})
                if "cash_balance" not in finance_state or finance_state.get("cash_balance") in (None, 0, 0.0):
                    finance_state["cash_balance"] = float(seed_budget.get("current") or 0.0)
                if "transfer_budget" not in finance_state or finance_state.get("transfer_budget") in (None, 0, 0.0):
                    finance_state["transfer_budget"] = float(seed_budget.get("current") or 0.0)
            except Exception:
                pass
            upsert_career_management_state(
                save_uid=effective_save_uid,
                locker_room=dict((management_state.get("locker_room") or {})),
                finance=finance_state,
                tactical=dict((management_state.get("tactical") or {})),
                academy=dict((management_state.get("academy") or {})),
                medical=dict((management_state.get("medical") or {})),
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
    seed_overview = dict((ui_seed or {}).get("overview") or {}) if isinstance(ui_seed, dict) else {}
    if overview_lucro is None and "lucro" in seed_overview:
        overview_lucro = _to_float(seed_overview.get("lucro"), 0.0)
    if overview_receitas is None and "receitas" in seed_overview:
        overview_receitas = _to_float(seed_overview.get("receitas"), 0.0)
    if overview_despesas is None and "despesas" in seed_overview:
        overview_despesas = _to_float(seed_overview.get("despesas"), 0.0)
    if overview_club_value is None and "club_value" in seed_overview:
        overview_club_value = _to_float(seed_overview.get("club_value"), 0.0)
    if overview_projection is None and "projection" in seed_overview:
        overview_projection = _to_float(seed_overview.get("projection"), 0.0)

    seed_receitas_breakdown = (ui_seed or {}).get("receitas_breakdown") if isinstance(ui_seed, dict) else None
    if isinstance(seed_receitas_breakdown, list) and seed_receitas_breakdown:
        receitas_breakdown = [
            {"label": str(item.get("label") or ""), "amount": _to_float(item.get("amount"), 0.0)}
            for item in seed_receitas_breakdown
            if str(item.get("label") or "").strip() and _to_float(item.get("amount"), 0.0) > 0
        ]
        receitas_breakdown.sort(key=lambda row: _to_float(row.get("amount"), 0.0), reverse=True)

    seed_despesas_breakdown = (ui_seed or {}).get("despesas_breakdown") if isinstance(ui_seed, dict) else None
    if isinstance(seed_despesas_breakdown, list) and seed_despesas_breakdown:
        despesas_breakdown = [
            {"label": str(item.get("label") or ""), "amount": _to_float(item.get("amount"), 0.0)}
            for item in seed_despesas_breakdown
            if str(item.get("label") or "").strip() and _to_float(item.get("amount"), 0.0) > 0
        ]
        despesas_breakdown.sort(key=lambda row: _to_float(row.get("amount"), 0.0), reverse=True)

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

    if overview_receitas is not None and "Sócio torcedor" in unavailable_topics["receitas"]:
        if any(str(item.get("label") or "") == "Sócio torcedor" for item in receitas_breakdown):
            unavailable_topics["receitas"].remove("Sócio torcedor")
    if overview_receitas is not None and "Ingressos" in unavailable_topics["receitas"]:
        if any(str(item.get("label") or "") == "Ingressos" for item in receitas_breakdown):
            unavailable_topics["receitas"].remove("Ingressos")
    if overview_receitas is not None and "Produtos" in unavailable_topics["receitas"]:
        if any(str(item.get("label") or "") == "Produtos" for item in receitas_breakdown):
            unavailable_topics["receitas"].remove("Produtos")
    for topic in ["Manutenção estádio", "Custos de viagens", "Instalações da base"]:
        if topic in unavailable_topics["despesas"] and any(str(item.get("label") or "") == topic for item in despesas_breakdown):
            unavailable_topics["despesas"].remove(topic)

    weekly_allowance_display = weekly_allowance
    seed_budget = dict((ui_seed or {}).get("budget") or {}) if isinstance(ui_seed, dict) else {}
    if _to_float(seed_budget.get("weekly_allowance"), 0.0) > 0:
        weekly_allowance_display = round(_to_float(seed_budget.get("weekly_allowance"), 0.0), 2)
    season_flow = seed_budget.get("season_flow") if isinstance(seed_budget.get("season_flow"), dict) else None
    start_transfer_budget_display = transfer_budget_start
    if isinstance(season_flow, dict):
        income_items = list(season_flow.get("income") or [])
        for item in income_items:
            if str(item.get("label") or "").strip().lower() == "verba inicial":
                start_transfer_budget_display = round(_to_float(item.get("amount"), transfer_budget_start), 2)
                break

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
            "reliability": "strict_real_only" if not ui_seed else "assumed_ui_seed_v1",
            "unavailable_metrics": unavailable_overview,
        },
        "receitas": {
            "total": overview_receitas,
            "breakdown": receitas_breakdown,
            "unavailable_topics": unavailable_topics["receitas"],
        },
        "despesas": {
            "total": overview_despesas,
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
            "weekly_allowance": weekly_allowance_display,
            "monthly_chart": monthly_chart,
            "season_baseline": {
                "start_transfer_budget": start_transfer_budget_display,
                "start_wage_budget": wage_budget_start,
                "current_transfer_budget": transfer_budget,
                "current_wage_budget": wage_budget,
            },
            "season_flow": season_flow,
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
            "overview_policy": "strict_real_only (sem estimativa para métricas sem fonte direta)" if not ui_seed else "assumed_ui_seed_v1 (valores preenchidos manualmente a partir do UI)",
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
            "ui_seed_finance_v1": ui_seed or None,
        },
    }


def _audience_for_topic_type(topic_type: str) -> str:
    if topic_type in {"board", "season"}:
        return "board"
    if topic_type in {"locker_room", "player"}:
        return "players"
    return "staff"


def _lower_first_sentence(q: str) -> str:
    s = (q or "").strip()
    if len(s) <= 1:
        return s
    return s[0].lower() + s[1:]


def _month_proactive_quota(save_uid: str, ym: str) -> int:
    """2 ou 3 convites proativos por mês de jogo, estável para o mesmo save."""
    if not save_uid:
        return 2
    h = int(hashlib.md5(f"{save_uid}|proactive|{ym}".encode("utf-8")).hexdigest()[:8], 16)
    return 2 + (h % 2)


def _build_interaction_touchpoints(
    state: Dict[str, Any],
    news_stories: List[Dict[str, Any]],
    market_rumors: List[Dict[str, Any]],
    player_relations: List[Dict[str, Any]],
    club_name: str,
    *,
    save_uid: str = "",
    game_date: str = "",
) -> List[Dict[str, Any]]:
    """Ganchos para conversa 1:1 ou foco — notícias, rumor, forma, relação e convites proativos (2–3/mês)."""
    out: List[Dict[str, Any]] = []
    seen_pid = set()
    squad = [p for p in (state.get("squad") or []) if isinstance(p, dict)]

    def _register(tp: Dict[str, Any]) -> None:
        pid = _to_int(tp.get("player_id"), 0)
        if pid <= 0 or pid in seen_pid:
            return
        seen_pid.add(pid)
        out.append(tp)

    ym = (game_date or "")[:7] or "1970-01"
    proactive_cap = _month_proactive_quota(save_uid, ym)
    proactive_n = 0

    def _captain_player() -> Optional[Dict[str, Any]]:
        if not squad:
            return None
        return max(
            squad,
            key=lambda p: (_to_float(p.get("overall_live") or p.get("overallrating"), 0.0), _to_int(p.get("form"), 0)),
        )

    if proactive_cap > 0 and save_uid:
        cand_lines: List[Dict[str, Any]] = []
        cap = _captain_player()
        if cap:
            cpid = _to_int(cap.get("playerid"), 0)
            if cpid > 0:
                cnm = str(cap.get("player_name") or cap.get("commonname") or "Grupo")
                cand_lines.append(
                    {
                        "player_id": cpid,
                        "player_name": cnm,
                        "hook_type": "proactive_seek",
                        "hook_label": "Capitão pediu um papo",
                        "context": (
                            f"Quer alinhar liderança e clima com o treinador antes do próximo desafio — "
                            f"contexto de temporada com o {club_name}."
                        ),
                        "article_id": None,
                        "suggested_prompt": (
                            f"Ouvir {cnm} com calma e fechar mensagem única pro vestiário, sem ruído externo."
                        ),
                    }
                )
        for rel in sorted(player_relations, key=lambda r: -_to_int(r.get("frustration"), 0)):
            rpid = _to_int(rel.get("playerid"), 0)
            if rpid <= 0:
                continue
            fr = _to_int(rel.get("frustration"), 0)
            if fr < 40:
                continue
            rnm = str(rel.get("player_name") or "Jogador")
            cand_lines.append(
                {
                    "player_id": rpid,
                    "player_name": rnm,
                    "hook_type": "proactive_seek",
                    "hook_label": "Quer clareza com você",
                    "context": (
                        f"Situação delicada (frustração alta). Busca conversa direta no CT — "
                        f"sem querer estourar na mídia ainda."
                    ),
                    "article_id": None,
                    "suggested_prompt": (
                        f"Dar caminho honesto a {rnm} sobre minutos e papel, reduzindo tensão interna."
                    ),
                }
            )
            break
        shuffled = sorted(
            squad,
            key=lambda p: int(hashlib.md5(f"{save_uid}|{ym}|{_to_int(p.get('playerid'), 0)}".encode("utf-8")).hexdigest()[:8], 16),
        )
        for p in shuffled:
            pid = _to_int(p.get("playerid"), 0)
            if pid <= 0:
                continue
            nm = str(p.get("player_name") or p.get("commonname") or "Atleta")
            cand_lines.append(
                {
                    "player_id": pid,
                    "player_name": nm,
                    "hook_type": "proactive_seek",
                    "hook_label": "Bateu na sua porta",
                    "context": (
                        f"Contexto da temporada com o {club_name}: quer um minuto com o treinador para alinhar expectativa."
                    ),
                    "article_id": None,
                    "suggested_prompt": ("Reforçar vínculo profissional e papel no grupo sem prometer o impossível."),
                }
            )
            if len(cand_lines) >= proactive_cap + 4:
                break
        for item in cand_lines:
            if proactive_n >= proactive_cap or len(out) >= 8:
                break
            pid = _to_int(item.get("player_id"), 0)
            if pid <= 0 or pid in seen_pid:
                continue
            before = len(out)
            _register(item)
            if len(out) > before:
                proactive_n += 1

    def _match_player_in_text(text: str) -> Optional[tuple[int, str]]:
        low = (text or "").lower()
        for p in squad:
            pid = _to_int(p.get("playerid"), 0)
            if pid <= 0:
                continue
            nm = str(p.get("player_name") or p.get("commonname") or "").strip()
            if len(nm) < 3:
                continue
            nlow = nm.lower()
            if nlow in low:
                return (pid, nm)
            for part in nm.split():
                if len(part) > 3 and part.lower() in low:
                    return (pid, nm)
        return None

    for story in news_stories[:6]:
        hl = str(story.get("headline") or "")
        aid = story.get("article_id")
        hit = _match_player_in_text(hl)
        if hit:
            pid, pname = hit
            _register(
                {
                    "player_id": pid,
                    "player_name": pname,
                    "hook_type": "news_mention",
                    "hook_label": "Citado na edição do dia",
                    "context": hl[:200],
                    "article_id": aid,
                    "suggested_prompt": (
                        f"Como abordar com o grupo o que a imprensa publicou envolvendo {pname}, sem perder controle da narrativa?"
                    ),
                }
            )

    rated = sorted(
        squad,
        key=lambda x: _to_float(x.get("overall_live") or x.get("overallrating"), 0.0),
        reverse=True,
    )
    for p in rated[:2]:
        pid = _to_int(p.get("playerid"), 0)
        if pid <= 0:
            continue
        nm = str(p.get("player_name") or p.get("commonname") or "Jogador")
        ov = _to_float(p.get("overall_live") or p.get("overallrating"), 0.0)
        _register(
            {
                "player_id": pid,
                "player_name": nm,
                "hook_type": "form_peak",
                "hook_label": "Destaque no plantel",
                "context": f"Referência técnica atual (overall {ov:.1f})." if ov else "Peça-chave no elenco.",
                "article_id": None,
                "suggested_prompt": (
                    f"Como reconhecer publicamente o momento de {nm} sem criar hierarquia tóxica no vestiário?"
                ),
            }
        )

    for rel in player_relations[:12]:
        pid = _to_int(rel.get("playerid"), 0)
        if pid <= 0 or pid in seen_pid:
            continue
        fr = _to_int(rel.get("frustration"), 0)
        trust = _to_int(rel.get("trust"), 60)
        st = str(rel.get("status_label") or "").lower()
        if fr < 45 and trust > 55 and "tenso" not in st and "frio" not in st:
            continue
        nm = str(rel.get("player_name") or "Jogador")
        _register(
            {
                "player_id": pid,
                "player_name": nm,
                "hook_type": "relationship_strain",
                "hook_label": "Relação tensa / cobrança",
                "context": f"Confiança {trust}, frustração {fr}. {st or 'clima delicado'}.",
                "article_id": None,
                "suggested_prompt": (
                    f"Como puxar {nm} para uma conversa honesta sobre expectativa e minutos, sem escalar o ruído interno?"
                ),
            }
        )
        if len(out) >= 8:
            break

    for rumor in market_rumors[:4]:
        hl = str(rumor.get("headline") or rumor.get("content") or "")[:300]
        hit = _match_player_in_text(hl)
        if hit:
            pid, pname = hit
            _register(
                {
                    "player_id": pid,
                    "player_name": pname,
                    "hook_type": "market_rumor",
                    "hook_label": "Rumor de mercado",
                    "context": hl[:200],
                    "article_id": None,
                    "suggested_prompt": (
                        f"Como responder à especulação em torno de {pname} sem comprometer o grupo nem a diretoria?"
                    ),
                }
            )
        if len(out) >= 8:
            break

    return out[:8]


def _build_interaction_prompts(
    questions: List[Dict[str, Any]],
    *,
    club_name: str,
    board_active: Optional[Dict[str, Any]],
    crisis_active: Optional[Dict[str, Any]],
    effective_mode: str,
    next_fixture: Optional[Dict[str, Any]],
    last_fixture: Optional[Dict[str, Any]],
    primary_table: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Perguntas dedicadas por audiência (diretoria / elenco / comissão) para a aba Social."""
    prompts: Dict[str, Any] = {"board": None, "players": None, "staff": None}
    for q in questions:
        tt = str(q.get("topic_type") or "")
        aud = _audience_for_topic_type(tt)
        if prompts.get(aud) is None:
            prompts[aud] = {**q, "audience": aud, "label": {"board": "Diretoria", "players": "Elenco", "staff": "Comissão técnica"}[aud]}

    stakes = "alta pressão" if (board_active or crisis_active) else "ritmo normal"
    tbl = primary_table or {}
    rk = tbl.get("rank")
    pts = tbl.get("points")
    tnm = str(tbl.get("competition_name") or "")
    table_bits = ""
    if rk is not None and pts is not None and tnm:
        table_bits = f" Na {tnm}, o {club_name} está na {rk}ª posição com {pts} pontos."

    if prompts["board"] is None:
        ult = " Com ultimato explícito da presidência, cada ponto pesa no orçamento e na continuidade do projeto." if board_active else ""
        prompts["board"] = {
            "question_id": "fallback:board",
            "slot": 0,
            "topic_type": "board",
            "question": (
                f"Que compromissos mensuráveis o projeto esportivo do {club_name} apresenta à diretoria neste ciclo "
                f"(metas financeiras, desportivas e prazo de avaliação){ult}?{table_bits}"
            ),
            "intent": "negociação institucional e alinhamento de KPIs com o conselho",
            "why_now": f"Pauta de conselho / leitura de governança ({stakes}) — linguagem de resultado e risco.",
            "entities": [],
            "predicted_effects": {"reputation_risk": "medium", "morale_risk": "low", "board_sensitivity": "high", "fan_sensitivity": "medium"},
            "audience": "board",
            "label": "Diretoria",
            "voice_note": "Tom corporativo: metas, transparência, trade-offs. Evita linguagem de vestiário.",
        }
    if prompts["players"] is None:
        prompts["players"] = {
            "question_id": "fallback:players",
            "slot": 0,
            "topic_type": "locker_room",
            "question": (
                f"Como o {club_name} traduz confiança e cobrança no dia a dia do vestiário — "
                f"liderança técnica, hierarquia de minutos e clima entre titulares e reservas?"
            ),
            "intent": "grupo, hierarquia e energia emocional",
            "why_now": "Elenco sente resultado e discurso do treinador de forma coletiva; não é reunião de conselho.",
            "entities": [],
            "predicted_effects": {"reputation_risk": "low", "morale_risk": "high", "board_sensitivity": "medium", "fan_sensitivity": "medium"},
            "audience": "players",
            "label": "Elenco",
            "voice_note": "Tom de capitão: energia, respeito, confronto saudável. Não misturar com planilha da diretoria.",
        }
    if prompts["staff"] is None:
        comp = str((next_fixture or {}).get("competition_name") or "calendário")
        prompts["staff"] = {
            "question_id": "fallback:staff",
            "slot": 0,
            "topic_type": "match",
            "question": (
                f"Como a comissão técnica prioriza cargas, vídeo-tática e critério médico para o bloco de treinos "
                f"que antecede a sequência na {comp} — onde entra o trade-off físico x resultado?"
            ),
            "intent": "processo de treino, DM e análise de adversário",
            "why_now": f"Modo {effective_mode}: linguagem de staff — microciclo, indisponíveis e plano de jogo.",
            "entities": [],
            "predicted_effects": {"reputation_risk": "medium", "morale_risk": "medium", "board_sensitivity": "medium", "fan_sensitivity": "high"},
            "audience": "staff",
            "label": "Comissão técnica",
            "voice_note": "Tom técnico: treino, dados, lesão, vídeo. Distinto de diretoria e de motivational speech.",
        }

    if effective_mode == "pre_match" and next_fixture:
        h = str(next_fixture.get("home_team_name") or "")
        a = str(next_fixture.get("away_team_name") or "")
        if h and a:
            if isinstance(prompts.get("board"), dict) and str(prompts["board"].get("question_id") or "").startswith("fallback"):
                q = str(prompts["board"].get("question") or "")
                prompts["board"]["question"] = (
                    f"Antes de {h} x {a}, em reunião com a diretoria: {_lower_first_sentence(q)}"
                )
            if isinstance(prompts.get("players"), dict) and str(prompts["players"].get("question_id") or "").startswith("fallback"):
                q = str(prompts["players"].get("question") or "")
                prompts["players"]["question"] = (
                    f"No pré-jogo de {h} x {a}, no vestiário: {_lower_first_sentence(q)}"
                )
            if isinstance(prompts.get("staff"), dict) and str(prompts["staff"].get("question_id") or "").startswith("fallback"):
                q = str(prompts["staff"].get("question") or "")
                prompts["staff"]["question"] = (
                    f"Na véspera de {h} x {a}, em reunião de staff no CT: {_lower_first_sentence(q)}"
                )
    elif effective_mode == "post_match" and last_fixture:
        sc = f"{last_fixture.get('home_score')} x {last_fixture.get('away_score')}"
        if isinstance(prompts.get("board"), dict) and str(prompts["board"].get("question_id") or "").startswith("fallback"):
            q = str(prompts["board"].get("question") or "")
            prompts["board"]["question"] = f"Após {sc}, na leitura com a diretoria: {_lower_first_sentence(q)}"
        if isinstance(prompts.get("players"), dict) and str(prompts["players"].get("question_id") or "").startswith("fallback"):
            q = str(prompts["players"].get("question") or "")
            prompts["players"]["question"] = f"Depois do placar {sc}, com o elenco: {_lower_first_sentence(q)}"
        if isinstance(prompts.get("staff"), dict) and str(prompts["staff"].get("question_id") or "").startswith("fallback"):
            q = str(prompts["staff"].get("question") or "")
            prompts["staff"]["question"] = f"Pós-{sc}, em balanço técnico com a comissão: {_lower_first_sentence(q)}"

    return prompts


def _is_match_day(fixtures: Sequence[Dict[str, Any]], user_team_id: int, game_date_raw: Optional[int]) -> bool:
    if not game_date_raw or not user_team_id:
        return False
    for f in fixtures:
        if not _is_user_fixture(f, user_team_id):
            continue
        if _to_int(f.get("date_raw"), 0) == game_date_raw:
            return True
    return False


def _match_day_completed_fixture(fixtures: Sequence[Dict[str, Any]], user_team_id: int, game_date_raw: Optional[int]) -> Optional[Dict[str, Any]]:
    if not game_date_raw or not user_team_id:
        return None
    for f in fixtures:
        if not _is_user_fixture(f, user_team_id):
            continue
        if _to_int(f.get("date_raw"), 0) == game_date_raw and f.get("is_completed"):
            return dict(f)
    return None


def build_conference_context(
    save_uid: str,
    mode: Optional[str] = None,
    questions_limit: int = 4,
) -> Dict[str, Any]:
    from database import count_press_conferences_for_game_date
    state = _read_state()
    game_date = _iso_game_date(state)
    manager = dict(state.get("manager") or {})
    club = dict(state.get("club") or {})
    user_team_id = _user_team_id(state)
    current_game_date_raw = _game_date_value(state)
    fixtures_raw = list(state.get("fixtures") or [])
    match_day = _is_match_day(fixtures_raw, user_team_id, current_game_date_raw)
    match_day_completed = _match_day_completed_fixture(fixtures_raw, user_team_id, current_game_date_raw)
    today_count = count_press_conferences_for_game_date(save_uid, game_date) if game_date else 0
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
    club_name_str = str(club.get("team_name") or "Clube")
    primary_table = (
        _select_primary_league_table(state, user_team_id, next_fixture, competition_names)
        if user_team_id
        else None
    )
    questions = []
    for index, topic in enumerate(hot_topics[: max(3, min(questions_limit, 6))], start=1):
        topic_type = str(topic.get("topic_type") or "season")
        qcore = _pick_conference_question_core(topic_type, topic.get("topic_id"), index)
        qtext, framing_kind = _build_framed_conference_question(
            index,
            qcore,
            club_name_str,
            next_fixture,
            last_fixture,
            user_team_id,
            primary_table,
            medical,
        )
        questions.append(
            {
                "question_id": f"{topic.get('topic_id')}:{index}",
                "slot": index,
                "topic_type": topic_type,
                "question": qtext,
                "question_framing": framing_kind,
                "intent": f"explorar o tema {topic_type} ({framing_kind})",
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
    stories_for_touch = list((news_payload.get("stories") or []))[:10]
    player_touchpoints = _build_interaction_touchpoints(
        state,
        stories_for_touch,
        list(market_rumors or []),
        list(player_relations or []),
        str(club.get("team_name") or "Clube"),
        save_uid=save_uid,
        game_date=game_date or "",
    )
    news_discussion_hooks = [
        {
            "article_id": s.get("article_id"),
            "headline": s.get("headline"),
            "lead": str(s.get("lead") or s.get("summary") or "")[:220],
        }
        for s in stories_for_touch[:5]
        if s.get("headline")
    ]
    interaction_prompts = _build_interaction_prompts(
        questions,
        club_name=str(club.get("team_name") or "Clube"),
        board_active=board_active,
        crisis_active=crisis_active,
        effective_mode=effective_mode,
        next_fixture=next_fixture,
        last_fixture=last_fixture,
        primary_table=primary_table,
    )
    match_day_result = None
    if match_day_completed:
        md = _decorate_fixture(match_day_completed, user_team_id, competition_names) or {}
        md_letter = _result_letter(md, user_team_id) or ""
        match_day_result = {
            "home_team_name": md.get("home_team_name"),
            "away_team_name": md.get("away_team_name"),
            "home_score": md.get("home_score"),
            "away_score": md.get("away_score"),
            "competition_name": md.get("competition_name"),
            "result_letter": md_letter,
            "result_label": {"W": "vitória", "D": "empate", "L": "derrota"}.get(md_letter, None),
        }
    return {
        "contract_version": 2,
        "save_uid": save_uid,
        "generated_at": datetime.utcnow().isoformat(),
        "mode": effective_mode,
        "is_match_day": match_day,
        "match_day_completed": match_day_result,
        "conference_today_count": today_count,
        "conference_locked": today_count >= 4,
        "context_snapshot": {
            "game_date": game_date,
            "club_name": str(club.get("team_name") or "Clube"),
            "manager_name": _manager_name(manager),
            "table_summary": (
                {
                    "competition_name": primary_table.get("competition_name"),
                    "rank": primary_table.get("rank"),
                    "points": primary_table.get("points"),
                    "played": primary_table.get("played"),
                    "goal_difference": primary_table.get("goal_difference"),
                }
                if primary_table
                else None
            ),
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
        "interaction_prompts": interaction_prompts,
        "player_touchpoints": player_touchpoints,
        "news_discussion_hooks": news_discussion_hooks,
        "interaction_sim_meta": {
            "players_one_on_one_enabled": True,
            "cross_links": ["news_feed_daily", "market_rumors", "player_relations", "squad"],
        },
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


# --- Apresentação PT-BR para o endpoint /companion/overview ---

_TIMELINE_PHASE_LABELS_PT: Dict[str, str] = {
    "season_arc": "Arco da temporada",
    "season_arc_start": "Início do arco sazonal",
    "season_arc_payoff": "Desfecho do arco",
    "crisis_step": "Momento da crise",
    "crisis_start": "Crise iniciada",
    "calendar": "Calendário",
    "pre_match": "Pré-jogo",
    "post_match": "Pós-jogo",
    "fan_reaction": "Torcida",
    "board_note": "Diretoria",
    "market_watch": "Mercado",
    "achievement": "Conquista",
    "legacy": "Legado",
}

_COACH_STYLE_DISPLAY: Dict[str, str] = {
    "equilibrado": "Equilibrado",
    "ofensivo": "Ofensivo",
    "ambicioso": "Ambicioso",
    "pragmático": "Pragmático",
    "contenção": "Contenção",
    "pressionado": "Pressionado",
    "instável": "Instável",
    "resiliente": "Resiliente",
    "estrategista": "Estrategista",
    "visionário": "Visionário",
    "em_risco": "Em risco",
    "elite": "Elite",
    "respeitado": "Respeitado",
    "estável": "Estável",
    "questionado": "Questionado",
}


def _format_coach_style_display(raw: str) -> str:
    s = raw.strip()
    if not s:
        return s
    key = s.lower()
    return _COACH_STYLE_DISPLAY.get(key, s[:1].upper() + s[1:] if len(s) > 1 else s.upper())


def _normalize_status_relation_display(raw: str) -> str:
    key = raw.strip().lower()
    mapping = {
        "neutro": "Neutro",
        "frustrado": "Frustrado",
        "insatisfeito": "Insatisfeito",
        "motivado": "Motivado",
    }
    return mapping.get(key, raw[:1].upper() + raw[1:] if raw else raw)


def _season_arc_title_for_ui(title: str) -> str:
    t = str(title or "").strip()
    if not t:
        return t
    t = re.sub(r"\bcurrent\b", "atual", t, flags=re.IGNORECASE)
    return t


def _season_arc_theme_for_ui(theme: str) -> str:
    t = str(theme or "").strip()
    if not t:
        return t
    t = re.sub(r"equilibrio", "equilíbrio", t, flags=re.IGNORECASE)
    return t


def _normalize_season_arc_for_ui(arc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not arc:
        return arc
    out = dict(arc)
    out["title"] = _season_arc_title_for_ui(str(out.get("title") or ""))
    out["theme"] = _season_arc_theme_for_ui(str(out.get("theme") or ""))
    return out


def _timeline_phase_label(phase: str) -> str:
    key = str(phase or "").strip().lower()
    if not key:
        return "Momento"
    return _TIMELINE_PHASE_LABELS_PT.get(key, key.replace("_", " ").strip().title())


def _normalize_timeline_entry_for_ui(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entry)
    phase = str(out.get("phase") or "")
    out["phase_label"] = _timeline_phase_label(phase)
    return out


def _player_name_from_state_squad(state: Dict[str, Any], playerid: int) -> Optional[str]:
    for p in state.get("squad") or []:
        if _to_int((p or {}).get("playerid"), 0) == playerid:
            return _player_name(p)
    return None


def _relation_needs_name_fix(name: str) -> bool:
    n = name.strip()
    if not n:
        return True
    if n.startswith("#") and n[1:].isdigit():
        return True
    if n.upper().startswith("ID "):
        return True
    return False


def _normalize_player_relation_for_ui(row: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    pid = _to_int(out.get("playerid"), 0)
    raw_name = str(out.get("player_name") or "").strip()
    if pid and _relation_needs_name_fix(raw_name):
        resolved = _player_name_from_state_squad(state, pid)
        if resolved and not resolved.startswith("ID "):
            if resolved.strip() == f"#{pid}" and raw_name.startswith("#"):
                out["player_name"] = f"Jogador #{pid}"
            else:
                out["player_name"] = resolved
        elif raw_name.startswith("#"):
            out["player_name"] = f"Jogador #{pid}"
    rl = _normalize_relation_role_label(out.get("role_label"))
    if rl:
        out["role_label"] = rl
    elif out.get("role_label"):
        out["role_label"] = str(out.get("role_label"))
    sl = _normalize_status_relation_display(str(out.get("status_label") or ""))
    if sl:
        out["status_label"] = sl
    return out


def enrich_companion_overview_payload(payload: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Ajusta textos da visão geral para apresentação ao usuário (PT-BR), in-place."""
    if payload.get("season_arc_active"):
        payload["season_arc_active"] = _normalize_season_arc_for_ui(payload["season_arc_active"])
    if payload.get("timeline_recent"):
        payload["timeline_recent"] = [_normalize_timeline_entry_for_ui(e) for e in payload["timeline_recent"]]
    if payload.get("player_relations_recent"):
        payload["player_relations_recent"] = [_normalize_player_relation_for_ui(r, state) for r in payload["player_relations_recent"]]
    cms = payload.get("career_management_state")
    if isinstance(cms, dict):
        tactical = dict(cms.get("tactical") or {})
        cs = tactical.get("coach_style")
        if isinstance(cs, str) and cs.strip():
            tactical["coach_style"] = _format_coach_style_display(cs)
        ident = tactical.get("identity_label")
        if isinstance(ident, str) and ident.strip():
            tactical["identity_label"] = _format_coach_style_display(ident)
        cms["tactical"] = tactical
        payload["career_management_state"] = cms
