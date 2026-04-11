"""Agrega estatísticas de jogadores por competição (Lua + save híbrido)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

COMPANION_DIR = Path.home() / "Desktop" / "fc_companion"


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _is_gk(player: Dict[str, Any]) -> bool:
    pos = str(player.get("position_label") or player.get("position") or "").upper()
    if "GOL" in pos or "GK" in pos or "GOLEIRO" in pos:
        return True
    pp = _safe_int(player.get("preferredposition1"), -1)
    return pp == 0


def _normalize_rating(raw: float) -> float:
    """Converte nota do save (0–99 ou 0–10) para escala ~0–10 com 1 decimal."""
    if raw <= 0:
        return 0.0
    if raw > 20:
        return round(raw / 10.0, 1)
    if raw <= 10.5:
        return round(raw, 1)
    return round(raw / 10.0, 1)


def _squad_maps(squad: List[Dict[str, Any]]) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, str]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    names: Dict[int, str] = {}
    for p in squad or []:
        pid = _safe_int(p.get("playerid"), 0)
        if pid <= 0:
            continue
        by_id[pid] = p
        for key in ("player_name", "commonname", "name"):
            v = str(p.get(key) or "").strip()
            if v and not v.isdigit():
                names[pid] = v
                break
        if pid not in names:
            first = str(p.get("firstname") or "").strip()
            last = str(p.get("lastname") or "").strip()
            names[pid] = f"{first} {last}".strip() or f"#{pid}"
    return by_id, names


TOP_RANKING_N = 10
LIST_CAP_CLUB = TOP_RANKING_N
LIST_CAP_GENERAL = TOP_RANKING_N
MERGED_COMPETITION_ID = -1


def _cap_rankings(payload: Dict[str, Any], cap: int) -> None:
    """Garante no máximo `cap` itens em cada ranking (sempre corta com [:cap])."""
    cap = max(1, min(cap, TOP_RANKING_N))
    for key in (
        "scorers",
        "assisters",
        "yellow_cards",
        "red_cards",
        "avg_rating",
        "clean_sheets_goalkeepers",
    ):
        lst = payload.get(key)
        if isinstance(lst, list):
            payload[key] = lst[:cap]
        else:
            payload[key] = []
    der = payload.get("derived")
    if isinstance(der, dict):
        for dk in ("offensive_contribution", "goals_per_90", "discipline_hot"):
            lst = der.get(dk)
            if isinstance(lst, list):
                der[dk] = lst[:cap]
            else:
                der[dk] = []


def _merge_raw_player_rows(all_comps: List[Dict[str, Any]], *, general: bool) -> List[Dict[str, Any]]:
    """Agrega linhas de todas as competições: um jogador (clube) ou jogador+clube (geral) com totais somados."""
    acc: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for comp in all_comps:
        if not isinstance(comp, dict):
            continue
        for row in comp.get("players") or []:
            if not isinstance(row, dict):
                continue
            pid = _safe_int(row.get("playerid"), 0)
            if pid <= 0:
                continue
            if general:
                tid = _safe_int(row.get("teamid"), 0)
                key: Tuple[Any, ...] = (pid, tid)
            else:
                key = (pid,)
            ap = _safe_int(row.get("appearances"), 0)
            g = _safe_int(row.get("goals"), 0)
            ast = _safe_int(row.get("assists"), 0)
            cs = _safe_int(row.get("clean_sheets"), 0)
            y = _safe_int(row.get("yellow_cards"), 0)
            red = _safe_int(row.get("red_cards"), 0)
            raw_r = _safe_float(row.get("avg_rating_raw"), 0.0)

            if key not in acc:
                acc[key] = {
                    "playerid": pid,
                    "goals": 0,
                    "assists": 0,
                    "appearances": 0,
                    "clean_sheets": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "_rating_num": 0.0,
                    "_rating_den": 0,
                }
                if general:
                    acc[key]["teamid"] = tid
                    acc[key]["team_name"] = str(row.get("team_name") or "").strip()
                    acc[key]["player_name"] = str(row.get("player_name") or "").strip()
                    acc[key]["position"] = str(row.get("position") or "").strip()
            b = acc[key]
            b["goals"] += g
            b["assists"] += ast
            b["appearances"] += ap
            b["clean_sheets"] += cs
            b["yellow_cards"] += y
            b["red_cards"] += red
            if ap > 0 and raw_r > 0:
                b["_rating_num"] += raw_r * ap
                b["_rating_den"] += ap
            if general:
                tn = str(row.get("team_name") or "").strip()
                if tn:
                    b["team_name"] = tn
                pn = str(row.get("player_name") or "").strip()
                if pn:
                    b["player_name"] = pn
                pos = str(row.get("position") or "").strip()
                if pos:
                    b["position"] = pos

    out: List[Dict[str, Any]] = []
    for b in acc.values():
        rd = _safe_int(b.pop("_rating_den", 0), 0)
        rn = _safe_float(b.pop("_rating_num", 0.0), 0.0)
        if rd > 0:
            b["avg_rating_raw"] = round(rn / rd, 4)
        else:
            b["avg_rating_raw"] = 0.0
        out.append(b)
    return out


def _enrich_row(
    row: Dict[str, Any],
    squad_by_id: Dict[int, Dict[str, Any]],
    name_fallback: Dict[int, str],
) -> Dict[str, Any]:
    pid = _safe_int(row.get("playerid"), 0)
    sp = squad_by_id.get(pid, {})
    goals = _safe_int(row.get("goals"), 0)
    assists = _safe_int(row.get("assists"), 0)
    apps = _safe_int(row.get("appearances"), 0)
    y = _safe_int(row.get("yellow_cards"), 0)
    red = _safe_int(row.get("red_cards"), 0)
    cs = _safe_int(row.get("clean_sheets"), 0)
    raw_r = _safe_float(row.get("avg_rating_raw") or row.get("avg_rating") or 0)
    rating = _normalize_rating(raw_r)
    position = str(sp.get("position_label") or sp.get("position") or row.get("position") or "")
    overall = _safe_int(sp.get("overallrating") or sp.get("overall") or row.get("overall"), 0)
    return {
        "playerid": pid,
        "name": name_fallback.get(pid, f"#{pid}"),
        "position": position,
        "overall": overall,
        "goals": goals,
        "assists": assists,
        "appearances": apps,
        "clean_sheets": cs,
        "yellow_cards": y,
        "red_cards": red,
        "avg_rating": rating,
        "is_goalkeeper": _is_gk(sp) if sp else False,
        "goals_plus_assists": goals + assists,
        "goals_per_90": round(goals * 90.0 / max(apps, 1), 2) if apps > 0 else 0.0,
        "cards_per_90": round((y + 3 * red) * 90.0 / max(apps, 1), 2) if apps > 0 else 0.0,
        "clean_sheet_rate": round(cs / max(apps, 1), 3) if apps > 0 else 0.0,
        "team_name": "",
    }


def _enrich_row_general(
    row: Dict[str, Any],
    squad_by_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    pid = _safe_int(row.get("playerid"), 0)
    sp = squad_by_id.get(pid, {})
    goals = _safe_int(row.get("goals"), 0)
    assists = _safe_int(row.get("assists"), 0)
    apps = _safe_int(row.get("appearances"), 0)
    y = _safe_int(row.get("yellow_cards"), 0)
    red = _safe_int(row.get("red_cards"), 0)
    cs = _safe_int(row.get("clean_sheets"), 0)
    raw_r = _safe_float(row.get("avg_rating_raw") or row.get("avg_rating") or 0)
    rating = _normalize_rating(raw_r)
    pos = str(row.get("position") or "").strip()
    pname = str(row.get("player_name") or "").strip()
    if not pname or pname.lower() == "unknown":
        pname = f"Jogador #{pid}" if pid else "—"
    tname = str(row.get("team_name") or "").strip()
    if not tname or tname.lower() == "unknown":
        tname = "—"
    is_gk = _is_gk(sp) if sp else bool(pos and ("GOL" in pos.upper() or "GK" in pos.upper() or "GOAL" in pos.upper()))
    ovr_src = row.get("overall")
    if ovr_src is None and sp:
        ovr_src = sp.get("overallrating") or sp.get("overall")
    overall = _safe_int(ovr_src, 0)
    return {
        "playerid": pid,
        "name": pname,
        "position": pos,
        "overall": overall,
        "goals": goals,
        "assists": assists,
        "appearances": apps,
        "clean_sheets": cs,
        "yellow_cards": y,
        "red_cards": red,
        "avg_rating": rating,
        "is_goalkeeper": is_gk,
        "goals_plus_assists": goals + assists,
        "goals_per_90": round(goals * 90.0 / max(apps, 1), 2) if apps > 0 else 0.0,
        "cards_per_90": round((y + 3 * red) * 90.0 / max(apps, 1), 2) if apps > 0 else 0.0,
        "clean_sheet_rate": round(cs / max(apps, 1), 3) if apps > 0 else 0.0,
        "team_name": tname,
    }


def _sort_nonempty(items: List[Dict[str, Any]], key_fn, reverse: bool = True) -> List[Dict[str, Any]]:
    return sorted(items, key=key_fn, reverse=reverse)


def _build_one_competition(
    comp: Dict[str, Any],
    squad_by_id: Dict[int, Dict[str, Any]],
    names: Dict[int, str],
    *,
    general: bool = False,
    list_cap: int = LIST_CAP_CLUB,
) -> Dict[str, Any]:
    cid = _safe_int(comp.get("competition_id"), 0)
    cname = str(comp.get("competition_name") or f"Competição {cid}")
    raw_players = comp.get("players") if isinstance(comp.get("players"), list) else []
    if general:
        enriched = [_enrich_row_general(r, squad_by_id) for r in raw_players if isinstance(r, dict)]
    else:
        enriched = [_enrich_row(r, squad_by_id, names) for r in raw_players if isinstance(r, dict)]

    scorers = _sort_nonempty([p for p in enriched if p["goals"] > 0], lambda x: (x["goals"], x["assists"]))
    assisters = _sort_nonempty([p for p in enriched if p["assists"] > 0], lambda x: (x["assists"], x["goals"]))
    yellows = _sort_nonempty([p for p in enriched if p["yellow_cards"] > 0], lambda x: x["yellow_cards"])
    reds = _sort_nonempty([p for p in enriched if p["red_cards"] > 0], lambda x: x["red_cards"])
    ratings = _sort_nonempty(
        [p for p in enriched if p["avg_rating"] > 0 and p["appearances"] > 0],
        lambda x: (x["avg_rating"], x["appearances"]),
    )
    gk_cs = _sort_nonempty(
        [p for p in enriched if p["is_goalkeeper"] and p["clean_sheets"] > 0],
        lambda x: (x["clean_sheets"], x["appearances"]),
    )

    offensive = _sort_nonempty(
        [p for p in enriched if p["goals_plus_assists"] > 0],
        lambda x: (x["goals_plus_assists"], x["goals"]),
    )
    clinical = _sort_nonempty(
        [p for p in enriched if p["goals"] > 0 and p["appearances"] > 0],
        lambda x: (x["goals_per_90"], x["goals"]),
    )
    discipline = sorted(
        [p for p in enriched if p["appearances"] > 0 and (p["yellow_cards"] + p["red_cards"]) > 0],
        key=lambda x: (x["cards_per_90"], x["yellow_cards"] + 3 * x["red_cards"]),
        reverse=True,
    )

    has_any = any(
        [
            scorers,
            assisters,
            yellows,
            reds,
            ratings,
            gk_cs,
            offensive,
            clinical,
            discipline,
        ]
    )

    out = {
        "competition_id": cid,
        "competition_name": cname,
        "has_player_stats": has_any,
        "scorers": scorers,
        "assisters": assisters,
        "yellow_cards": yellows,
        "red_cards": reds,
        "avg_rating": ratings,
        "clean_sheets_goalkeepers": gk_cs,
        "derived": {
            "offensive_contribution": offensive,
            "goals_per_90": clinical,
            "discipline_hot": discipline,
        },
    }
    _cap_rankings(out, list_cap)
    return out


def load_lua_competition_block() -> Dict[str, Any]:
    path = COMPANION_DIR / "state_lua.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_bytes())
    except Exception:
        return {}
    block = data.get("competition_player_stats")
    return block if isinstance(block, dict) else {}


def build_competition_stats_response(squad: List[Dict[str, Any]], lua_block: Dict[str, Any]) -> Dict[str, Any]:
    squad_by_id, names = _squad_maps(squad)
    comps_club = (
        lua_block.get("competitions_club")
        if isinstance(lua_block.get("competitions_club"), list)
        else lua_block.get("competitions")
    )
    if not isinstance(comps_club, list):
        comps_club = []
    comps_gen = lua_block.get("competitions_general")
    if not isinstance(comps_gen, list):
        comps_gen = []

    merged_club_rows = _merge_raw_player_rows([c for c in comps_club if isinstance(c, dict)], general=False)
    merged_gen_rows = _merge_raw_player_rows([c for c in comps_gen if isinstance(c, dict)], general=True)

    club_list: List[Dict[str, Any]] = []
    if merged_club_rows:
        club_list.append(
            _build_one_competition(
                {
                    "competition_id": MERGED_COMPETITION_ID,
                    "competition_name": "Todas as competições (total)",
                    "players": merged_club_rows,
                },
                squad_by_id,
                names,
                general=False,
                list_cap=LIST_CAP_CLUB,
            )
        )
    club_list.extend(
        _build_one_competition(c, squad_by_id, names, general=False, list_cap=LIST_CAP_CLUB)
        for c in comps_club
        if isinstance(c, dict)
    )

    gen_list: List[Dict[str, Any]] = []
    if merged_gen_rows:
        gen_list.append(
            _build_one_competition(
                {
                    "competition_id": MERGED_COMPETITION_ID,
                    "competition_name": "Todas as competições (total)",
                    "players": merged_gen_rows,
                },
                squad_by_id,
                names,
                general=True,
                list_cap=LIST_CAP_GENERAL,
            )
        )
    gen_list.extend(
        _build_one_competition(c, squad_by_id, names, general=True, list_cap=LIST_CAP_GENERAL)
        for c in comps_gen
        if isinstance(c, dict)
    )

    club_list.sort(key=lambda x: (0 if _safe_int(x.get("competition_id"), 0) == MERGED_COMPETITION_ID else 1, str(x.get("competition_name") or "")))
    gen_list.sort(key=lambda x: (0 if _safe_int(x.get("competition_id"), 0) == MERGED_COMPETITION_ID else 1, str(x.get("competition_name") or "")))
    return {
        "club": {
            "competitions": club_list,
            "source": str(lua_block.get("source_club") or lua_block.get("source") or "lua"),
        },
        "general": {
            "competitions": gen_list,
            "source": str(lua_block.get("source_general") or lua_block.get("source") or "lua"),
        },
        "competitions": club_list,
        "source": str(lua_block.get("source") or "lua"),
    }


def competition_stats_from_save_probe(squad: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fallback: lê save_probe mais recente (export manual) se tiver career_playerstats."""
    probe = COMPANION_DIR / "save_probe"
    if not probe.is_dir():
        return None
    dirs = [d for d in probe.iterdir() if d.is_dir()]
    if not dirs:
        return None
    latest = max(dirs, key=lambda d: d.stat().st_mtime)
    stats_path = latest / "db_0" / "career_playerstats.json"
    cu_path = latest / "db_0" / "career_users.json"
    cp_path = latest / "db_0" / "career_competitionprogress.json"
    if not stats_path.exists() or not cu_path.exists() or not cp_path.exists():
        return None
    try:
        user_team = _safe_int((json.loads(cu_path.read_bytes())[0] or {}).get("clubteamid"), 0)
        progress = json.loads(cp_path.read_bytes())
        comp_names: Dict[int, str] = {}
        for row in progress:
            if _safe_int(row.get("teamid"), -1) != user_team:
                continue
            cid = _safe_int(row.get("compobjid"), 0)
            if cid <= 0:
                continue
            sn = str(row.get("compshortname") or "").strip()
            if sn:
                comp_names[cid] = sn
            elif cid not in comp_names:
                comp_names[cid] = f"Competição {cid}"
        squad_ids = {_safe_int(p.get("playerid"), 0) for p in squad or []}
        squad_ids.discard(0)
        rows = json.loads(stats_path.read_bytes())
        by_c: Dict[int, List[Dict[str, Any]]] = {cid: [] for cid in comp_names}
        for r in rows:
            cid = _safe_int(r.get("compobjid") or r.get("compobjId") or r.get("competitionid"), 0)
            pid = _safe_int(r.get("playerid"), 0)
            if cid not in comp_names or pid not in squad_ids:
                continue
            by_c[cid].append(
                {
                    "playerid": pid,
                    "goals": _safe_int(r.get("goals") or r.get("leaguegoals"), 0),
                    "assists": _safe_int(r.get("assists") or r.get("leagueassists"), 0),
                    "appearances": _safe_int(
                        r.get("appearances") or r.get("gamesplayed") or r.get("leaguegames"), 0
                    ),
                    "clean_sheets": _safe_int(r.get("cleansheets") or r.get("leaguecleansheets"), 0),
                    "yellow_cards": _safe_int(r.get("yellows") or r.get("yellowcards"), 0),
                    "red_cards": _safe_int(r.get("reds") or r.get("redcards"), 0),
                    "avg_rating_raw": _safe_float(
                        r.get("avgmatchrating") or r.get("rating") or r.get("avgrating") or 0
                    ),
                }
            )
        lua_block = {
            "competitions": [
                {"competition_id": cid, "competition_name": comp_names[cid], "players": by_c.get(cid, [])}
                for cid in sorted(comp_names.keys(), key=lambda x: comp_names[x])
            ],
            "source": "save_probe",
        }
        base = build_competition_stats_response(squad, lua_block)
        base["general"] = {"competitions": [], "source": "save_probe_no_general"}
        return base
    except Exception:
        return None
