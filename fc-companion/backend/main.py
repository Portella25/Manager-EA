from __future__ import annotations

"""API FastAPI para expor estado atual do save e histórico de eventos."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(override=True)

from database import (
    create_crisis_arc,
    create_season_arc,
    create_board_challenge,
    get_events_by_type,
    get_active_board_challenge,
    get_active_crisis_arc,
    get_active_season_arc,
    get_recent_crisis_arcs,
    get_recent_board_challenges,
    get_recent_market_rumors,
    get_recent_match_event_payloads,
    get_recent_season_payoffs,
    get_recent_season_arcs,
    get_recent_timeline_entries,
    get_recent_hall_of_fame_entries,
    get_recent_achievements,
    get_recent_meta_achievements,
    get_achievement_profile,
    get_meta_achievement_profile,
    has_achievement,
    has_meta_achievement,
    get_hall_of_fame_profile,
    get_legacy_profile,
    get_or_create_coach_profile,
    get_recent_press_conferences,
    get_recent_feed,
    merge_career_facts,
    get_narratives_by_event_type,
    get_recent_events,
    get_recent_narratives,
    init_db,
    insert_event_with_timestamp,
    save_feed_item,
    save_market_rumor,
    save_narrative,
    save_season_payoff,
    save_press_conference,
    save_timeline_entry,
    save_hall_of_fame_entry,
    save_achievement,
    save_meta_achievement,
    upsert_achievement_profile,
    upsert_meta_achievement_profile,
    upsert_hall_of_fame_profile,
    upsert_legacy_profile,
    append_season_arc_memory,
    update_season_arc_progress,
    update_crisis_arc_progress,
    update_board_challenge_progress,
    update_coach_profile,
    get_or_create_career_management_state,
    upsert_career_management_state,
    get_player_relations,
    upsert_player_relation,
    save_finance_ledger_entry,
    get_recent_finance_ledger,
    get_external_artifact,
    get_recent_external_event_logs,
    upsert_match_result_from_match_event,
    count_press_conferences_for_game_date,
)
from board_engine import BoardEngine
from achievements_engine import AchievementsEngine
from meta_achievements_engine import MetaAchievementsEngine
from crisis_engine import CrisisEngine
from editorial_engine import EditorialEngine
from front_read_models import (
    _iso_game_date,
    _read_state,
    build_conference_context,
    build_dashboard_home,
    build_finance_hub,
    build_news_feed_daily,
    build_press_fallout_career_facts,
    build_season_context,
    build_squad_overview,
    enrich_companion_overview_payload,
    rebuild_news_feed_daily,
)
from market_engine import MarketEngine
from models import (
    CareerManagementPatchIn,
    CrisisTriggerIn,
    InternalCommsStepIn,
    InternalEventIn,
    MarketRumorIn,
    NarrativeIn,
    PlayerRelationPatchIn,
    PressConferenceIn,
    SeasonArcMemoryIn,
    SeasonArcTriggerIn,
    SeasonPayoffIn,
    TimelineEntryIn,
)
from hall_of_fame_engine import HallOfFameEngine
from legacy_engine import LegacyEngine
from legacy_hub import build_legacy_hub
from external_ingestion import ExternalIngestion
from payoff_engine import PayoffEngine
from narrative_engine import NarrativeEngine
from reputation_engine import ReputationEngine
from season_arc_engine import SeasonArcEngine
from career_dynamics_engine import CareerDynamicsEngine
from player_relation_press import apply_one_on_one_interaction_to_relation
from internal_comms_lock import record_internal_comms_completed
from competition_stats import (
    build_competition_stats_response,
    competition_stats_from_save_probe,
    load_lua_competition_block,
)
from save_reader.transfer_history_from_save import get_transfer_history_from_career_save


STATE_PATH = Path.home() / "Desktop" / "fc_companion" / "state.json"
COMPANION_DATA_DIR = Path.home() / "Desktop" / "fc_companion"


def _resolve_club_team_id_from_state(state: Dict[str, Any]) -> int:
    club = state.get("club") or {}
    try:
        tid = int(club.get("team_id") or 0)
    except (TypeError, ValueError):
        tid = 0
    if tid > 0:
        return tid
    mgr = state.get("manager") or {}
    try:
        return int(mgr.get("clubteamid") or 0)
    except (TypeError, ValueError):
        return 0


def _hydrate_state_club_from_lua(state: Dict[str, Any]) -> Dict[str, Any]:
    """Garante club.team_id para histórico do save quando state.json está incompleto."""
    if _resolve_club_team_id_from_state(state) > 0:
        return state
    lua_path = COMPANION_DATA_DIR / "state_lua.json"
    if not lua_path.exists():
        return state
    try:
        lua = json.loads(lua_path.read_text(encoding="utf-8"))
        c = lua.get("club")
        if isinstance(c, dict) and c.get("team_id"):
            merged = dict(state) if state else {}
            merged_club = {**(merged.get("club") or {}), **c}
            merged["club"] = merged_club
            return merged
    except Exception:
        pass
    return state


def _read_save_data_transfer_history_disk() -> List[Dict[str, Any]]:
    """Fallback quando state.json ainda não tem transfer_history do save (merge atrasado)."""
    path = COMPANION_DATA_DIR / "save_data.json"
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        th = data.get("transfer_history")
        return list(th) if isinstance(th, list) else []
    except Exception:
        return []


def _merge_market_live_club_history(
    th_payload: Dict[str, Any], state: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Prioridade: LE items → state.transfer_history → save_data.json em disco."""
    le_items = list(th_payload.get("items") or [])
    summary = dict(th_payload.get("summary") or {})
    summary["le_club_item_count"] = len(le_items)
    state_th = list(state.get("transfer_history") or [])
    disk_th = _read_save_data_transfer_history_disk()
    if le_items:
        summary["club_history_source"] = "live_editor"
        summary["count"] = len(le_items)
        return le_items, summary
    if state_th:
        summary["club_history_source"] = "state_merge"
        summary["count"] = len(state_th)
        return state_th, summary
    if disk_th:
        summary["club_history_source"] = "save_data_json"
        summary["count"] = len(disk_th)
        return disk_th, summary
    tid = _resolve_club_team_id_from_state(state)
    if tid > 0:
        try:
            sql_th = get_transfer_history_from_career_save(tid)
        except Exception:
            sql_th = []
        if sql_th:
            summary["club_history_source"] = "save_sqlite_direct"
            summary["count"] = len(sql_th)
            summary["club_team_id_used"] = tid
            return sql_th, summary
    summary["club_history_source"] = "empty"
    summary["count"] = 0
    return [], summary


app = FastAPI(title="FC Companion Backend", version="1.0.0")
narrative_engine = NarrativeEngine()
reputation_engine = ReputationEngine()
board_engine = BoardEngine()
market_engine = MarketEngine()
editorial_engine = EditorialEngine()
crisis_engine = CrisisEngine()
season_arc_engine = SeasonArcEngine()
payoff_engine = PayoffEngine()
hall_of_fame_engine = HallOfFameEngine()
legacy_engine = LegacyEngine()
achievements_engine = AchievementsEngine()
meta_achievements_engine = MetaAchievementsEngine()
career_dynamics_engine = CareerDynamicsEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.utcnow()
    print(f"[API] {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = (datetime.utcnow() - start).total_seconds()
    print(f"[API] {request.method} {request.url.path} -> {response.status_code} ({elapsed:.3f}s)")
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def read_state() -> Dict[str, Any]:
    # Leitura centralizada para manter tratamento de erro consistente em todos endpoints.
    if not STATE_PATH.exists():
        raise HTTPException(status_code=404, detail="state.json não encontrado")
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"state.json inválido: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"erro ao ler state.json: {exc}") from exc


def emit_system_event(
    event_type: str,
    payload: Dict[str, Any],
    save_uid: Optional[str],
    timestamp: Optional[datetime] = None,
    severity: int = 3,
) -> Dict[str, Any]:
    event_timestamp = timestamp or datetime.utcnow()
    event_id = insert_event_with_timestamp(
        event_type=event_type,
        payload=payload,
        timestamp=event_timestamp,
        save_uid=save_uid,
    )
    generated = narrative_engine.generate(event_type, payload, severity=severity)
    narrative_id = save_narrative(
        event_type=event_type,
        title=generated["title"],
        content=generated["content"],
        tone=generated["tone"],
        source=generated["source"],
        save_uid=save_uid,
    )
    bundle = narrative_engine.generate_bundle(event_type, payload, severity=severity)
    feed_item_ids: List[int] = []
    for item in bundle:
        feed_item_ids.append(
            save_feed_item(
                event_type=event_type,
                channel=item["channel"],
                title=item["title"],
                content=item["content"],
                tone=item["tone"],
                source=item["source"],
                save_uid=save_uid,
            )
        )
    return {"event_id": event_id, "narrative_id": narrative_id, "feed_item_ids": feed_item_ids}


def rebuild_legacy(save_uid: str) -> Dict[str, Any]:
    payoffs = get_recent_season_payoffs(limit=200, save_uid=save_uid)
    computed = legacy_engine.build_profile(payoffs)
    profile = upsert_legacy_profile(
        save_uid=save_uid,
        seasons_count=int(computed["seasons_count"]),
        average_score=float(computed["average_score"]),
        best_grade=str(computed["best_grade"]),
        legacy_rank=str(computed["legacy_rank"]),
        narrative_summary=str(computed["narrative_summary"]),
    )
    return profile


def rebuild_hall_of_fame(save_uid: str) -> Dict[str, Any]:
    entries = get_recent_hall_of_fame_entries(limit=500, save_uid=save_uid)
    legacy_profile = get_legacy_profile(save_uid)
    computed = hall_of_fame_engine.build_profile(entries, legacy_profile)
    profile = upsert_hall_of_fame_profile(
        save_uid=save_uid,
        total_entries=int(computed["total_entries"]),
        legacy_score=float(computed["legacy_score"]),
        tier=str(computed["tier"]),
        highlight_title=computed["highlight_title"],
    )
    return profile


def rebuild_achievements(save_uid: str) -> Dict[str, Any]:
    entries = get_recent_achievements(limit=500, save_uid=save_uid)
    computed = achievements_engine.build_profile(entries)
    profile = upsert_achievement_profile(
        save_uid=save_uid,
        total_achievements=int(computed["total_achievements"]),
        total_points=int(computed["total_points"]),
        career_level=str(computed["career_level"]),
        top_achievement=computed["top_achievement"],
    )
    return profile


def rebuild_meta_achievements(save_uid: str) -> Dict[str, Any]:
    entries = get_recent_meta_achievements(limit=500, save_uid=save_uid)
    computed = meta_achievements_engine.build_profile(entries)
    profile = upsert_meta_achievement_profile(
        save_uid=save_uid,
        total_meta=int(computed["total_meta"]),
        collection_progress=computed["collection_progress"],
        prestige_level=str(computed["prestige_level"]),
    )
    return profile


@app.get("/state")
def get_state() -> JSONResponse:
    return JSONResponse(content=read_state(), media_type="application/json")


@app.get("/state/schema")
def get_state_schema(save_uid: str = Query(...)) -> JSONResponse:
    payload = get_external_artifact(save_uid, "schema")
    if payload is None:
        raise HTTPException(status_code=404, detail="schema.json ainda não ingerido para este save_uid")
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/state/reference")
def get_state_reference(save_uid: str = Query(...)) -> JSONResponse:
    payload = get_external_artifact(save_uid, "reference_data")
    if payload is None:
        raise HTTPException(status_code=404, detail="reference_data.json ainda não ingerido para este save_uid")
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/stats/players")
def get_player_stats(save_uid: Optional[str] = Query(default=None)) -> JSONResponse:
    """Ranking completo de jogadores por gols, assistências e jogos na temporada."""
    state = {}
    try:
        state = read_state()
    except HTTPException:
        pass
    effective_save_uid = save_uid or str(((state.get("meta") or {}).get("save_uid")) or "") or None

    # Mapa playerid → nome (via squad do state ou save)
    name_map: Dict[int, str] = {}
    position_map: Dict[int, str] = {}
    overall_map: Dict[int, int] = {}

    for player in state.get("squad") or []:
        pid = int(player.get("playerid") or 0)
        if pid <= 0:
            continue
        # resolve nome
        for key in ("player_name", "commonname", "name"):
            v = str(player.get(key) or "").strip()
            if v and not v.isdigit():
                name_map[pid] = v
                break
        if pid not in name_map:
            first = str(player.get("firstname") or "").strip()
            last = str(player.get("lastname") or "").strip()
            full = f"{first} {last}".strip()
            name_map[pid] = full or f"#{pid}"
        position_map[pid] = str(player.get("position_label") or player.get("position") or "")
        overall_map[pid] = int(player.get("overallrating") or player.get("overall") or 0)

    # Carrega stats de cada jogador via save_parser (teamplayerlinks)
    scorers: List[Dict[str, Any]] = []
    assisters: List[Dict[str, Any]] = []
    all_players: Dict[int, Dict[str, Any]] = {}

    # Fonte 1: player_stats exportado pelo Lua (mais atualizado)
    lua_state_path = Path.home() / "Desktop" / "fc_companion" / "state_lua.json"
    if lua_state_path.exists():
        try:
            lua_data = json.loads(lua_state_path.read_bytes())
            lua_stats: List[Dict[str, Any]] = lua_data.get("player_stats") or []
            for row in lua_stats:
                pid = int(row.get("playerid") or 0)
                if pid <= 0:
                    continue
                all_players[pid] = {
                    "playerid": pid,
                    "name": name_map.get(pid, f"#{pid}"),
                    "position": position_map.get(pid, ""),
                    "overall": overall_map.get(pid, 0),
                    "goals": int(row.get("goals") or 0),
                    "assists": int(row.get("assists") or 0),
                    "appearances": int(row.get("appearances") or 0),
                    "clean_sheets": int(row.get("clean_sheets") or 0),
                    "yellow_cards": int(row.get("yellow_cards") or 0),
                    "red_cards": int(row.get("red_cards") or 0),
                }
        except Exception:
            pass

    # Fonte 2: save_probe/teamplayerlinks.json como fallback
    if not all_players:
        try:
            probe_root = Path.home() / "Desktop" / "fc_companion" / "save_probe"
            save_dirs = [d for d in probe_root.iterdir() if d.is_dir()] if probe_root.exists() else []
            if save_dirs:
                latest_dir = max(save_dirs, key=lambda d: d.stat().st_mtime)
                tpl_path = latest_dir / "db_1" / "teamplayerlinks.json"
                cu_path = latest_dir / "db_0" / "career_users.json"
                if tpl_path.exists() and cu_path.exists():
                    cu = json.loads(cu_path.read_bytes())
                    team_id = int((cu[0] if cu else {}).get("clubteamid") or -1)
                    tpl = json.loads(tpl_path.read_bytes())
                    for row in tpl:
                        if int(row.get("teamid") or -1) != team_id:
                            continue
                        pid = int(row.get("playerid") or 0)
                        if pid <= 0:
                            continue
                        all_players[pid] = {
                            "playerid": pid,
                            "name": name_map.get(pid, f"#{pid}"),
                            "position": position_map.get(pid, ""),
                            "overall": overall_map.get(pid, 0),
                            "goals": int(row.get("leaguegoals") or 0),
                            "assists": int(row.get("leagueassists") or row.get("assists") or 0),
                            "appearances": int(row.get("leagueappearances") or 0),
                            "clean_sheets": int(row.get("leaguecleansheets") or 0),
                            "yellow_cards": int(row.get("yellows") or 0),
                            "red_cards": int(row.get("reds") or 0),
                        }
        except Exception:
            pass

    # Garante que todos os jogadores do squad aparecem (mesmo com stats zeradas)
    for pid, pname in name_map.items():
        if pid not in all_players:
            all_players[pid] = {
                "playerid": pid,
                "name": pname,
                "position": position_map.get(pid, ""),
                "overall": overall_map.get(pid, 0),
                "goals": 0,
                "assists": 0,
                "appearances": 0,
                "clean_sheets": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            }

    # Fallback final: season_stats do state tem pelo menos top scorer/assist
    if not all_players:
        club = state.get("club") or {}
        ss = club.get("season_stats") or {}
        ts = ss.get("top_scorer") or {}
        ta = ss.get("top_assist") or {}
        if ts.get("playerid"):
            pid = int(ts["playerid"])
            all_players[pid] = {"playerid": pid, "name": name_map.get(pid, f"#{pid}"), "position": position_map.get(pid, ""), "overall": overall_map.get(pid, 0), "goals": int(ts.get("total_goals") or 0), "assists": 0, "appearances": 0, "clean_sheets": 0}
        if ta.get("playerid"):
            pid = int(ta["playerid"])
            existing = all_players.get(pid, {"playerid": pid, "name": name_map.get(pid, f"#{pid}"), "position": position_map.get(pid, ""), "overall": overall_map.get(pid, 0), "goals": 0, "appearances": 0, "clean_sheets": 0})
            existing["assists"] = int(ta.get("total_assists") or 0)
            all_players[pid] = existing

    players_list = list(all_players.values())
    scorers = sorted([p for p in players_list if p["goals"] > 0], key=lambda x: (-x["goals"], -x["assists"]))
    assisters = sorted([p for p in players_list if p["assists"] > 0], key=lambda x: (-x["assists"], -x["goals"]))
    most_played_filtered = [p for p in players_list if p["appearances"] > 0]
    most_played = sorted(most_played_filtered if most_played_filtered else players_list, key=lambda x: (-x["appearances"], -x["overall"]))

    return JSONResponse(content={
        "scorers": scorers,
        "assisters": assisters,
        "most_played": most_played,
        "all_players": players_list,
        "total_squad": len(players_list),
    })


@app.get("/stats/competitions")
def get_stats_competitions() -> JSONResponse:
    """Estatísticas por competição (Lua career_playerstats + progress; fallback save_probe)."""
    state: Dict[str, Any] = {}
    try:
        state = read_state()
    except HTTPException:
        pass
    squad = state.get("squad") if isinstance(state.get("squad"), list) else []
    lua_block = load_lua_competition_block()
    payload = build_competition_stats_response(squad, lua_block)
    club_comps = (payload.get("club") or {}).get("competitions") or []
    if not any(c.get("has_player_stats") for c in club_comps):
        alt = competition_stats_from_save_probe(squad)
        if alt:
            payload = alt
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/state/season-stats")
def get_state_season_stats(save_uid: str = Query(...)) -> JSONResponse:
    payload = get_external_artifact(save_uid, "season_stats")
    if payload is None:
        raise HTTPException(status_code=404, detail="season_stats.json ainda não ingerido para este save_uid")
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/state/transfer-history")
def get_state_transfer_history(save_uid: str = Query(...)) -> JSONResponse:
    payload = get_external_artifact(save_uid, "transfer_history")
    if payload is None:
        raise HTTPException(status_code=404, detail="transfer_history.json ainda não ingerido para este save_uid")
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/events/external/recent")
def external_events_recent(
    save_uid: str = Query(...),
    limit: int = Query(default=50, ge=1, le=300),
) -> JSONResponse:
    items = get_recent_external_event_logs(save_uid=save_uid, limit=limit)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/state/club")
def get_state_club() -> JSONResponse:
    state = read_state()
    payload = {
        "club": state.get("club"),
        "manager": state.get("manager"),
        "squad": state.get("squad"),
        "injuries": state.get("injuries"),
    }
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/state/fixtures")
def get_state_fixtures(completed: Optional[bool] = Query(default=None)) -> JSONResponse:
    state = read_state()
    fixtures = state.get("fixtures") or []
    if completed is not None:
        fixtures = [f for f in fixtures if bool(f.get("is_completed")) == completed]
    return JSONResponse(content=fixtures, media_type="application/json")


@app.get("/state/standings")
def get_state_standings() -> JSONResponse:
    state = read_state()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in state.get("standings") or []:
        comp = str(row.get("competition_id"))
        grouped.setdefault(comp, []).append(row)
        
    for comp_id, teams in grouped.items():
        teams.sort(key=lambda t: (
            -int((t.get("total", {}) or {}).get("points", 0) or 0),
            -int((t.get("total", {}) or {}).get("wins", 0) or 0),
            -(
                int((t.get("total", {}) or {}).get("goals_for", 0) or 0)
                - int((t.get("total", {}) or {}).get("goals_against", 0) or 0)
            ),
            -int((t.get("total", {}) or {}).get("goals_for", 0) or 0),
            str(t.get("team_name") or ""),
        ))
        
    return JSONResponse(content=grouped, media_type="application/json")


@app.get("/state/squad")
def get_state_squad() -> JSONResponse:
    state = read_state()
    save_uid = str(((state.get("meta") or {}).get("save_uid")) or "")
    squad = build_squad_overview(save_uid=save_uid or None, state=state)
    return JSONResponse(content=squad, media_type="application/json")


@app.get("/events/recent")
def events_recent(limit: int = Query(default=20, ge=1, le=500), save_uid: Optional[str] = Query(default=None)) -> JSONResponse:
    items = get_recent_events(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/events/type/{event_type}")
def events_by_type(event_type: str, save_uid: Optional[str] = Query(default=None)) -> JSONResponse:
    items = get_events_by_type(event_type=event_type, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/internal/event")
def internal_event(event: InternalEventIn) -> JSONResponse:
    primary = emit_system_event(event.event_type, event.payload, event.save_uid, timestamp=event.timestamp, severity=event.severity or 3)
    record_id = primary["event_id"]
    narrative_id = primary["narrative_id"]
    feed_item_ids = primary["feed_item_ids"]
    board_updates: List[Dict[str, Any]] = []
    career_management_state = None
    finance_ledger_entry_ids: List[int] = []
    player_relation_updates = 0

    if event.save_uid and event.event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
        payload_for_match = dict(event.payload or {})
        if not payload_for_match.get("club_name"):
            try:
                live_state = read_state()
            except HTTPException:
                live_state = {}
            fallback_club = str(((live_state.get("club") or {}).get("team_name")) or "")
            if fallback_club:
                payload_for_match["club_name"] = fallback_club
        upsert_match_result_from_match_event(
            save_uid=str(event.save_uid),
            payload=payload_for_match,
            occurred_at=event.timestamp or datetime.utcnow(),
        )

        def _managed_side(payload: Dict[str, Any]) -> str:
            if payload.get("is_home") is True:
                return "home"
            if payload.get("is_home") is False:
                return "away"
            try:
                user_team_id = int(payload.get("user_team_id") or 0)
                home_team_id = int(payload.get("home_team_id") or 0)
                away_team_id = int(payload.get("away_team_id") or 0)
            except (TypeError, ValueError):
                return "home"
            if user_team_id > 0 and user_team_id == away_team_id and user_team_id != home_team_id:
                return "away"
            return "home"

        # Adaptador para o novo payload do motor híbrido
        if event.event_type != "MATCH_COMPLETED":
            adapted_payload = {
                "home_score": event.payload.get("my_score"),
                "away_score": event.payload.get("opp_score"),
            }
            _outcome, points_earned = board_engine.extract_result(adapted_payload, managed_side="home")
        else:
            _outcome, points_earned = board_engine.extract_result(event.payload, managed_side=_managed_side(event.payload))
            
        active = get_active_board_challenge(event.save_uid, challenge_type="ULTIMATUM")
        if active:
            next_points = int(active["current_points"]) + int(points_earned)
            next_remaining = max(0, int(active["matches_remaining"]) - 1)
            next_status = board_engine.resolve_status(
                required_points=int(active["required_points"]),
                current_points=next_points,
                matches_remaining=next_remaining,
            )
            updated = update_board_challenge_progress(
                challenge_id=int(active["id"]),
                points_earned=points_earned,
                status=next_status,
            )
            message = board_engine.build_progress_message(
                status=updated["status"],
                current_points=int(updated["current_points"]),
                required_points=int(updated["required_points"]),
                matches_remaining=int(updated["matches_remaining"]),
            )
            sys_payload = {
                "challenge_id": updated["id"],
                "status": updated["status"],
                "current_points": updated["current_points"],
                "required_points": updated["required_points"],
                "matches_remaining": updated["matches_remaining"],
                "message": message,
            }
            board_updates.append({"type": "progress", "challenge": updated, "message": message})
            emitted = emit_system_event("BOARD_ULTIMATUM_UPDATED", sys_payload, event.save_uid)
            feed_item_ids.extend(emitted["feed_item_ids"])
        else:
            recent_payloads = get_recent_match_event_payloads(event.save_uid, limit=5)
            outcomes: List[str] = []
            for p in recent_payloads:
                result, _pts = board_engine.extract_result(p, managed_side=_managed_side(p))
                if result != "unknown":
                    outcomes.append(result)
            if board_engine.should_trigger_ultimatum(outcomes):
                challenge_data = board_engine.build_ultimatum()
                created = create_board_challenge(
                    save_uid=event.save_uid,
                    challenge_type="ULTIMATUM",
                    title=challenge_data["title"],
                    description=challenge_data["description"],
                    required_points=int(challenge_data["required_points"]),
                    matches_remaining=int(challenge_data["matches_remaining"]),
                )
                board_updates.append({"type": "created", "challenge": created})
                sys_payload = {
                    "challenge_id": created["id"],
                    "description": created["description"],
                    "required_points": created["required_points"],
                    "matches_remaining": created["matches_remaining"],
                }
                emitted = emit_system_event("BOARD_ULTIMATUM_CREATED", sys_payload, event.save_uid)
                feed_item_ids.extend(emitted["feed_item_ids"])

    profile_payload = None
    if event.save_uid:
        current_profile = get_or_create_coach_profile(event.save_uid)
        rep_delta, fan_delta, style_label = reputation_engine.event_impact(event.event_type, event.payload)
        reputation_score = reputation_engine.normalize_score(int(current_profile["reputation_score"]) + rep_delta)
        fan_sentiment_score = reputation_engine.normalize_score(int(current_profile["fan_sentiment_score"]) + fan_delta)
        profile_payload = update_coach_profile(
            save_uid=event.save_uid,
            reputation_score=reputation_score,
            reputation_label=reputation_engine.reputation_label(reputation_score),
            playstyle_label=style_label,
            fan_sentiment_score=fan_sentiment_score,
            fan_sentiment_label=reputation_engine.fan_label(fan_sentiment_score),
        )
        try:
            current_state = read_state()
        except HTTPException:
            current_state = {}
        existing_mgmt = get_or_create_career_management_state(event.save_uid)
        existing_relations = get_player_relations(event.save_uid, limit=500)
        next_mgmt, rel_updates, ledger_entries, emitted = career_dynamics_engine.on_event(
            event.event_type,
            event.payload,
            current_state,
            profile_payload,
            existing_mgmt,
            existing_relations,
        )
        career_management_state = upsert_career_management_state(
            save_uid=event.save_uid,
            locker_room=next_mgmt["locker_room"],
            finance=next_mgmt["finance"],
            tactical=next_mgmt["tactical"],
            academy=next_mgmt["academy"],
            medical=next_mgmt["medical"],
        )
        for rel in rel_updates:
            upsert_player_relation(
                save_uid=event.save_uid,
                playerid=int(rel["playerid"]),
                player_name=rel.get("player_name"),
                trust=int(rel.get("trust") or 50),
                role_label=str(rel.get("role_label") or "Rodízio"),
                status_label=str(rel.get("status_label") or "neutro"),
                frustration=int(rel.get("frustration") or 0),
                notes=dict(rel.get("notes") or {}),
            )
            player_relation_updates += 1
        for entry in ledger_entries:
            finance_ledger_entry_ids.append(
                save_finance_ledger_entry(
                    save_uid=event.save_uid,
                    period=str(entry.get("period") or "unknown"),
                    kind=str(entry.get("kind") or "unknown"),
                    amount=float(entry.get("amount") or 0.0),
                    description=str(entry.get("description") or ""),
                )
            )
        for ev in emitted:
            emitted_record = emit_system_event(ev.event_type, ev.payload, event.save_uid)
            feed_item_ids.extend(emitted_record["feed_item_ids"])
    rumor_id = None
    if event.save_uid and profile_payload and market_engine.should_generate(event.event_type):
        rumor = market_engine.build_rumor(event.event_type, event.payload, profile_payload)
        rumor_id = save_market_rumor(
            save_uid=event.save_uid,
            trigger_event=event.event_type,
            headline=rumor["headline"],
            content=rumor["content"],
            confidence_level=int(rumor["confidence_level"]),
            target_profile=rumor["target_profile"],
        )
    timeline_entry_ids: List[int] = []
    if event.save_uid and profile_payload and editorial_engine.should_generate(event.event_type):
        entries = editorial_engine.build_entries(event.event_type, event.payload, profile_payload)
        for entry in entries:
            timeline_entry_ids.append(
                save_timeline_entry(
                    save_uid=event.save_uid,
                    source_event=event.event_type,
                    phase=entry["phase"],
                    title=entry["title"],
                    content=entry["content"],
                    importance=int(entry["importance"]),
                )
            )
    crisis_updates: List[Dict[str, Any]] = []
    if event.save_uid and profile_payload:
        active_crisis = get_active_crisis_arc(event.save_uid)
        if active_crisis:
            progress = crisis_engine.progress(active_crisis, profile_payload, event.event_type)
            if int(progress["step_increment"]) > 0:
                updated = update_crisis_arc_progress(
                    crisis_id=int(active_crisis["id"]),
                    status=progress["status"],
                    step_increment=int(progress["step_increment"]),
                )
                crisis_updates.append({"type": "progress", "crisis": updated, "message": progress["message"]})
                emitted = emit_system_event(
                    "CRISIS_UPDATED",
                    {
                        "crisis_id": updated["id"],
                        "status": updated["status"],
                        "current_step": updated["current_step"],
                        "max_steps": updated["max_steps"],
                        "message": progress["message"],
                    },
                    event.save_uid,
                )
                feed_item_ids.extend(emitted["feed_item_ids"])
                timeline_entry_ids.append(
                    save_timeline_entry(
                        save_uid=event.save_uid,
                        source_event="CRISIS_UPDATED",
                        phase="crisis_step",
                        title="Crise: novo capítulo",
                        content=progress["message"],
                        importance=92,
                    )
                )
        else:
            if crisis_engine.should_start(profile_payload, event.event_type, len(board_updates)):
                trigger_type = "BOARD" if len(board_updates) > 0 else event.event_type
                start_data = crisis_engine.start_payload(profile_payload, trigger_type=trigger_type)
                created_crisis = create_crisis_arc(
                    save_uid=event.save_uid,
                    trigger_type=trigger_type,
                    severity=start_data["severity"],
                    summary=start_data["summary"],
                    max_steps=int(start_data["max_steps"]),
                )
                crisis_updates.append({"type": "created", "crisis": created_crisis})
                emitted = emit_system_event(
                    "CRISIS_STARTED",
                    {
                        "crisis_id": created_crisis["id"],
                        "severity": created_crisis["severity"],
                        "summary": created_crisis["summary"],
                        "max_steps": created_crisis["max_steps"],
                    },
                    event.save_uid,
                )
                feed_item_ids.extend(emitted["feed_item_ids"])
                timeline_entry_ids.append(
                    save_timeline_entry(
                        save_uid=event.save_uid,
                        source_event="CRISIS_STARTED",
                        phase="crisis_start",
                        title="Crise iniciada",
                        content=created_crisis["summary"],
                        importance=95,
                    )
                )
    season_arc_updates: List[Dict[str, Any]] = []
    season_payoff: Optional[Dict[str, Any]] = None
    hall_of_fame_profile: Optional[Dict[str, Any]] = None
    achievements_profile: Optional[Dict[str, Any]] = None
    meta_achievements_profile: Optional[Dict[str, Any]] = None
    if event.save_uid and profile_payload:
        active_season_arc = get_active_season_arc(event.save_uid)
        if active_season_arc:
            memory_text = season_arc_engine.memory_from_event(event.event_type, event.payload)
            updated_memory_arc = append_season_arc_memory(
                arc_id=int(active_season_arc["id"]),
                memory_text=memory_text,
                source_event=event.event_type,
            )
            progress = season_arc_engine.progress(updated_memory_arc, profile_payload, event.event_type)
            if int(progress["milestone_increment"]) > 0:
                updated_arc = update_season_arc_progress(
                    arc_id=int(updated_memory_arc["id"]),
                    status=progress["status"],
                    milestone_increment=int(progress["milestone_increment"]),
                )
                season_arc_updates.append({"type": "progress", "arc": updated_arc, "message": progress["message"]})
                emitted = emit_system_event(
                    "SEASON_ARC_UPDATED",
                    {
                        "arc_id": updated_arc["id"],
                        "status": updated_arc["status"],
                        "current_milestone": updated_arc["current_milestone"],
                        "max_milestones": updated_arc["max_milestones"],
                        "message": progress["message"],
                    },
                    event.save_uid,
                )
                feed_item_ids.extend(emitted["feed_item_ids"])
                timeline_entry_ids.append(
                    save_timeline_entry(
                        save_uid=event.save_uid,
                        source_event="SEASON_ARC_UPDATED",
                        phase="season_arc",
                        title="Arco sazonal avançou",
                        content=progress["message"],
                        importance=83,
                    )
                )
                if updated_arc["status"] in {"resolved", "failed"}:
                    already = get_recent_season_payoffs(limit=20, save_uid=event.save_uid)
                    has_payoff = any(int(x.get("season_arc_id", -1)) == int(updated_arc["id"]) for x in already)
                    if not has_payoff:
                        payoff = payoff_engine.build(updated_arc, profile_payload)
                        payoff_id = save_season_payoff(
                            save_uid=event.save_uid,
                            season_arc_id=int(updated_arc["id"]),
                            final_score=int(payoff["final_score"]),
                            grade=payoff["grade"],
                            title=payoff["title"],
                            epilogue=payoff["epilogue"],
                            factors=payoff["factors"],
                        )
                        season_payoff = {
                            "id": payoff_id,
                            "season_arc_id": int(updated_arc["id"]),
                            "final_score": int(payoff["final_score"]),
                            "grade": payoff["grade"],
                            "title": payoff["title"],
                        }
                        emitted_payoff = emit_system_event(
                            "SEASON_ARC_PAYOFF",
                            {
                                "season_arc_id": int(updated_arc["id"]),
                                "final_score": int(payoff["final_score"]),
                                "grade": payoff["grade"],
                                "title": payoff["title"],
                                "epilogue": payoff["epilogue"],
                            },
                            event.save_uid,
                        )
                        feed_item_ids.extend(emitted_payoff["feed_item_ids"])
                        timeline_entry_ids.append(
                            save_timeline_entry(
                                save_uid=event.save_uid,
                                source_event="SEASON_ARC_PAYOFF",
                                phase="season_arc_payoff",
                                title=payoff["title"],
                                content=payoff["epilogue"],
                                importance=98,
                            )
                        )
                        legacy_profile = rebuild_legacy(event.save_uid)
                        emitted_legacy = emit_system_event(
                            "LEGACY_UPDATED",
                            legacy_profile,
                            event.save_uid,
                        )
                        feed_item_ids.extend(emitted_legacy["feed_item_ids"])
                        hof_entry = hall_of_fame_engine.build_entry_from_payoff(
                            {
                                "final_score": int(payoff["final_score"]),
                                "grade": payoff["grade"],
                                "title": payoff["title"],
                            }
                        )
                        save_hall_of_fame_entry(
                            save_uid=event.save_uid,
                            category=hof_entry["category"],
                            title=hof_entry["title"],
                            description=hof_entry["description"],
                            score_impact=int(hof_entry["score_impact"]),
                            source=hof_entry["source"],
                        )
                        hall_of_fame_profile = rebuild_hall_of_fame(event.save_uid)
                        emitted_hof = emit_system_event("HOF_UPDATED", hall_of_fame_profile, event.save_uid)
                        feed_item_ids.extend(emitted_hof["feed_item_ids"])
                        unlocks = achievements_engine.unlocks_from_context(
                            payoff=payoff,
                            legacy_profile=legacy_profile,
                            hall_of_fame_profile=hall_of_fame_profile,
                        )
                        for unlock in unlocks:
                            if not has_achievement(event.save_uid, unlock["code"]):
                                save_achievement(
                                    save_uid=event.save_uid,
                                    code=unlock["code"],
                                    title=unlock["title"],
                                    description=unlock["description"],
                                    rarity=unlock["rarity"],
                                    points=int(unlock["points"]),
                                    source=unlock["source"],
                                )
                                emitted_achievement = emit_system_event("ACHIEVEMENT_UNLOCKED", unlock, event.save_uid)
                                feed_item_ids.extend(emitted_achievement["feed_item_ids"])
                                timeline_entry_ids.append(
                                    save_timeline_entry(
                                        save_uid=event.save_uid,
                                        source_event="ACHIEVEMENT_UNLOCKED",
                                        phase="achievement",
                                        title=unlock["title"],
                                        content=unlock["description"],
                                        importance=97,
                                    )
                                )
                        achievements_profile = rebuild_achievements(event.save_uid)
                        emitted_achievements = emit_system_event(
                            "ACHIEVEMENTS_UPDATED",
                            {
                                "summary": f"Conquistas: {achievements_profile['total_achievements']} totais, nível {achievements_profile['career_level']}.",
                                "career_level": achievements_profile["career_level"],
                            },
                            event.save_uid,
                        )
                        feed_item_ids.extend(emitted_achievements["feed_item_ids"])
                        current_achievements = get_recent_achievements(limit=500, save_uid=event.save_uid)
                        meta_unlocks = meta_achievements_engine.unlocks_from_achievements(current_achievements)
                        for meta_unlock in meta_unlocks:
                            if not has_meta_achievement(event.save_uid, meta_unlock["code"]):
                                save_meta_achievement(
                                    save_uid=event.save_uid,
                                    code=meta_unlock["code"],
                                    title=meta_unlock["title"],
                                    description=meta_unlock["description"],
                                    collection_tag=meta_unlock["collection_tag"],
                                    points=int(meta_unlock["points"]),
                                )
                                emitted_meta = emit_system_event("META_ACHIEVEMENT_UNLOCKED", meta_unlock, event.save_uid)
                                feed_item_ids.extend(emitted_meta["feed_item_ids"])
                        meta_achievements_profile = rebuild_meta_achievements(event.save_uid)
                        emitted_meta_profile = emit_system_event(
                            "META_ACHIEVEMENTS_UPDATED",
                            {
                                "summary": f"Meta-conquistas: {meta_achievements_profile['total_meta']} totais, prestígio {meta_achievements_profile['prestige_level']}.",
                            },
                            event.save_uid,
                        )
                        feed_item_ids.extend(emitted_meta_profile["feed_item_ids"])
                        timeline_entry_ids.append(
                            save_timeline_entry(
                                save_uid=event.save_uid,
                                source_event="LEGACY_UPDATED",
                                phase="legacy",
                                title="Legado recalculado",
                                content=legacy_profile["narrative_summary"],
                                importance=91,
                            )
                        )
        else:
            if season_arc_engine.should_start(event.event_type):
                season_label = str(((event.payload or {}).get("new_season")) or ((event.payload or {}).get("old_season")) or "atual")
                start_data = season_arc_engine.build_start(profile_payload, season_label=season_label)
                created_arc = create_season_arc(
                    save_uid=event.save_uid,
                    title=start_data["title"],
                    theme=start_data["theme"],
                    season_label=season_label,
                    max_milestones=int(start_data["max_milestones"]),
                )
                season_arc_updates.append({"type": "created", "arc": created_arc})
                append_season_arc_memory(
                    arc_id=int(created_arc["id"]),
                    memory_text=start_data["summary"],
                    source_event=event.event_type,
                )
                emitted = emit_system_event(
                    "SEASON_ARC_STARTED",
                    {
                        "arc_id": created_arc["id"],
                        "title": created_arc["title"],
                        "theme": created_arc["theme"],
                        "summary": start_data["summary"],
                        "max_milestones": created_arc["max_milestones"],
                    },
                    event.save_uid,
                )
                feed_item_ids.extend(emitted["feed_item_ids"])
                timeline_entry_ids.append(
                    save_timeline_entry(
                        save_uid=event.save_uid,
                        source_event="SEASON_ARC_STARTED",
                        phase="season_arc_start",
                        title=created_arc["title"],
                        content=start_data["summary"],
                        importance=88,
                    )
                )
    return JSONResponse(
        content={
            "status": "ok",
            "event_id": record_id,
            "narrative_id": narrative_id,
            "feed_item_ids": feed_item_ids,
            "coach_profile": profile_payload,
            "board_updates": board_updates,
            "career_management_state": career_management_state,
            "player_relation_updates": player_relation_updates,
            "finance_ledger_entry_ids": finance_ledger_entry_ids,
            "crisis_updates": crisis_updates,
            "season_arc_updates": season_arc_updates,
            "season_payoff": season_payoff,
            "hall_of_fame_profile": hall_of_fame_profile,
            "achievements_profile": achievements_profile,
            "meta_achievements_profile": meta_achievements_profile,
            "market_rumor_id": rumor_id,
            "timeline_entry_ids": timeline_entry_ids,
        },
        media_type="application/json",
    )


@app.get("/health")
def health() -> JSONResponse:
    if not STATE_PATH.exists():
        return JSONResponse(
            content={"status": "ok", "last_update": None},
            media_type="application/json",
        )
    stat = STATE_PATH.stat()
    return JSONResponse(
        content={"status": "ok", "last_update": datetime.fromtimestamp(stat.st_mtime).isoformat()},
        media_type="application/json",
    )


@app.get("/narratives/recent")
def narratives_recent(limit: int = Query(default=20, ge=1, le=200), save_uid: Optional[str] = Query(default=None)) -> JSONResponse:
    items = get_recent_narratives(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/narratives/event/{event_type}")
def narratives_by_event(event_type: str, save_uid: Optional[str] = Query(default=None)) -> JSONResponse:
    items = get_narratives_by_event_type(event_type=event_type, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/narratives/generate")
def narratives_generate(data: NarrativeIn) -> JSONResponse:
    generated = narrative_engine.generate(data.event_type, data.payload)
    narrative_id = save_narrative(
        event_type=data.event_type,
        title=generated["title"],
        content=generated["content"],
        tone=generated["tone"],
        source=generated["source"],
        save_uid=data.save_uid,
    )
    return JSONResponse(
        content={
            "status": "ok",
            "narrative_id": narrative_id,
            "event_type": data.event_type,
            "title": generated["title"],
            "content": generated["content"],
            "tone": generated["tone"],
            "source": generated["source"],
        },
        media_type="application/json",
    )


@app.get("/feed/recent")
def feed_recent(
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_feed(limit=limit, save_uid=save_uid, channel=channel)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/feed/channel/{channel}")
def feed_by_channel(
    channel: str,
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_feed(limit=limit, save_uid=save_uid, channel=channel)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/companion/overview")
def companion_overview(
    save_uid: Optional[str] = Query(default=None),
    events_limit: int = Query(default=10, ge=1, le=100),
    feed_limit: int = Query(default=15, ge=1, le=200),
) -> JSONResponse:
    state = {}
    try:
        state = read_state()
    except HTTPException:
        state = {}
    state = _hydrate_state_club_from_lua(state)
    effective_save_uid = save_uid or str(((state.get("meta") or {}).get("save_uid")) or "") or None
    # transfer_history.json fica em fc_companion/{save_uid}/ e o watcher só dispara com state_lua/save_data;
    # reingerir aqui garante dados frescos ao abrir o Mercado sem reiniciar o watcher.
    if effective_save_uid:
        ExternalIngestion().ingest_json_artifact(
            effective_save_uid, "transfer_history.json", "transfer_history"
        )
    th_artifact = get_external_artifact(effective_save_uid, "transfer_history") if effective_save_uid else None
    th_payload = (th_artifact or {}).get("payload") or {}
    club_rows, club_summary = _merge_market_live_club_history(th_payload, state)
    market_live = {
        "source": "live_editor",
        "updated_at": (th_artifact or {}).get("updated_at"),
        "history_club": club_rows,
        "history_world": th_payload.get("items_world") or [],
        "summary": club_summary,
        "meta_export": th_payload.get("meta") or {},
    }
    payload = {
        "state": {
            "meta": state.get("meta"),
            "manager": state.get("manager"),
            "club": state.get("club"),
            "transfer_offers": state.get("transfer_offers") or [],
            "transfer_history": state.get("transfer_history") or [],
            "market_live": market_live,
            "finance_live": state.get("finance_live") or {},
        },
        "season_context": build_season_context(effective_save_uid, state=state) if effective_save_uid else None,
        "events_recent": get_recent_events(limit=events_limit, save_uid=effective_save_uid),
        "feed_recent": get_recent_feed(limit=feed_limit, save_uid=effective_save_uid),
        "coach_profile": get_or_create_coach_profile(effective_save_uid) if effective_save_uid else None,
        "board_active_challenge": get_active_board_challenge(effective_save_uid, challenge_type="ULTIMATUM") if effective_save_uid else None,
        "crisis_active_arc": get_active_crisis_arc(effective_save_uid) if effective_save_uid else None,
        "season_arc_active": get_active_season_arc(effective_save_uid) if effective_save_uid else None,
        "season_payoffs_recent": get_recent_season_payoffs(limit=5, save_uid=effective_save_uid) if effective_save_uid else [],
        "legacy_hub": build_legacy_hub(effective_save_uid, state) if effective_save_uid else None,
        "legacy_profile": get_legacy_profile(effective_save_uid) if effective_save_uid else None,
        "hall_of_fame_profile": get_hall_of_fame_profile(effective_save_uid) if effective_save_uid else None,
        "hall_of_fame_entries": get_recent_hall_of_fame_entries(limit=5, save_uid=effective_save_uid) if effective_save_uid else [],
        "achievements_profile": get_achievement_profile(effective_save_uid) if effective_save_uid else None,
        "achievements_recent": get_recent_achievements(limit=8, save_uid=effective_save_uid) if effective_save_uid else [],
        "meta_achievements_profile": get_meta_achievement_profile(effective_save_uid) if effective_save_uid else None,
        "meta_achievements_recent": get_recent_meta_achievements(limit=8, save_uid=effective_save_uid) if effective_save_uid else [],
        "market_rumors_recent": get_recent_market_rumors(limit=8, save_uid=effective_save_uid) if effective_save_uid else [],
        "finance_ledger_recent": get_recent_finance_ledger(limit=12, save_uid=effective_save_uid) if effective_save_uid else [],
        "career_management_state": get_or_create_career_management_state(effective_save_uid) if effective_save_uid else None,
        "player_relations_recent": get_player_relations(effective_save_uid, limit=20) if effective_save_uid else [],
        "timeline_recent": get_recent_timeline_entries(limit=10, save_uid=effective_save_uid) if effective_save_uid else [],
        "schema_catalog": get_external_artifact(effective_save_uid, "schema") if effective_save_uid else None,
        "reference_data": get_external_artifact(effective_save_uid, "reference_data") if effective_save_uid else None,
        "season_stats": get_external_artifact(effective_save_uid, "season_stats") if effective_save_uid else None,
        "transfer_history_dataset": th_artifact if effective_save_uid else None,
        "external_events_recent": get_recent_external_event_logs(effective_save_uid, limit=30) if effective_save_uid else [],
    }
    enrich_companion_overview_payload(payload, state)
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/news/feed/daily")
def news_feed_daily(
    save_uid: str = Query(...),
    date: Optional[str] = Query(default=None),
    limit: int = Query(default=7, ge=1, le=10),
) -> JSONResponse:
    payload = build_news_feed_daily(save_uid=save_uid, date=date, limit=limit)
    return JSONResponse(content=payload, media_type="application/json")


@app.post("/news/feed/daily/rebuild")
def news_feed_daily_rebuild(
    save_uid: str = Query(...),
    date: Optional[str] = Query(default=None),
    limit: int = Query(default=7, ge=1, le=10),
) -> JSONResponse:
    payload = rebuild_news_feed_daily(save_uid=save_uid, date=date, limit=limit)
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/dashboard/home")
def dashboard_home(
    save_uid: str = Query(...),
    news_limit: int = Query(default=5, ge=1, le=5),
    timeline_limit: int = Query(default=6, ge=1, le=20),
    alerts_limit: int = Query(default=6, ge=1, le=20),
) -> JSONResponse:
    payload = build_dashboard_home(
        save_uid=save_uid,
        news_limit=news_limit,
        timeline_limit=timeline_limit,
        alerts_limit=alerts_limit,
    )
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/conference/context")
def conference_context(
    save_uid: str = Query(...),
    mode: Optional[str] = Query(default=None),
    questions_limit: int = Query(default=4, ge=3, le=6),
) -> JSONResponse:
    payload = build_conference_context(
        save_uid=save_uid,
        mode=mode,
        questions_limit=questions_limit,
    )
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/finance/hub")
def finance_hub(
    save_uid: Optional[str] = Query(default=None),
    ledger_limit: int = Query(default=80, ge=10, le=300),
    transactions_limit: int = Query(default=40, ge=5, le=100),
) -> JSONResponse:
    payload = build_finance_hub(
        save_uid=save_uid,
        ledger_limit=ledger_limit,
        transactions_limit=transactions_limit,
    )
    return JSONResponse(content=payload, media_type="application/json")


@app.get("/career/management/state")
def career_management_state(save_uid: str = Query(...)) -> JSONResponse:
    state = get_or_create_career_management_state(save_uid)
    return JSONResponse(content=state, media_type="application/json")


@app.post("/career/management/patch")
def career_management_patch(data: CareerManagementPatchIn) -> JSONResponse:
    current = get_or_create_career_management_state(data.save_uid)
    locker_room = dict(current.get("locker_room") or {})
    finance = dict(current.get("finance") or {})
    tactical = dict(current.get("tactical") or {})
    academy = dict(current.get("academy") or {})
    medical = dict(current.get("medical") or {})

    if data.locker_room:
        locker_room.update(data.locker_room)
    if data.finance:
        finance.update(data.finance)
    if data.tactical:
        tactical.update(data.tactical)
    if data.academy:
        academy.update(data.academy)
    if data.medical:
        medical.update(data.medical)

    saved = upsert_career_management_state(
        save_uid=data.save_uid,
        locker_room=locker_room,
        finance=finance,
        tactical=tactical,
        academy=academy,
        medical=medical,
    )
    return JSONResponse(content=saved, media_type="application/json")


@app.get("/career/players/relations")
def career_player_relations(
    save_uid: str = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
) -> JSONResponse:
    items = get_player_relations(save_uid, limit=limit)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/career/players/relations/patch")
def career_player_relation_patch(data: PlayerRelationPatchIn) -> JSONResponse:
    existing_list = get_player_relations(data.save_uid, limit=500)
    existing = next((x for x in existing_list if int(x.get("playerid") or -1) == int(data.playerid)), None) or {}
    saved = upsert_player_relation(
        save_uid=data.save_uid,
        playerid=int(data.playerid),
        player_name=data.player_name or existing.get("player_name"),
        trust=int(data.trust) if data.trust is not None else int(existing.get("trust") or 50),
        role_label=str(data.role_label or existing.get("role_label") or "Rodízio"),
        status_label=str(data.status_label or existing.get("status_label") or "neutro"),
        frustration=int(data.frustration) if data.frustration is not None else int(existing.get("frustration") or 0),
        notes=dict(data.notes) if data.notes is not None else dict(existing.get("notes") or {}),
    )
    emitted = emit_system_event(
        "PLAYER_RELATION_UPDATED",
        {
            "player_name": saved.get("player_name"),
            "role_label": saved.get("role_label"),
            "status_label": saved.get("status_label"),
            "trust": saved.get("trust"),
        },
        data.save_uid,
    )
    return JSONResponse(
        content={"status": "ok", "relation": saved, "event_id": emitted["event_id"], "feed_item_ids": emitted["feed_item_ids"]},
        media_type="application/json",
    )


@app.get("/career/finance/ledger/recent")
def finance_ledger_recent(
    save_uid: str = Query(...),
    limit: int = Query(default=30, ge=1, le=200),
) -> JSONResponse:
    items = get_recent_finance_ledger(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/profile/coach")
def coach_profile(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_or_create_coach_profile(save_uid)
    return JSONResponse(content=profile, media_type="application/json")


@app.get("/torcida/sentimento")
def fan_sentiment(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_or_create_coach_profile(save_uid)
    payload = {
        "save_uid": save_uid,
        "fan_sentiment_score": profile["fan_sentiment_score"],
        "fan_sentiment_label": profile["fan_sentiment_label"],
        "playstyle_label": profile["playstyle_label"],
        "updated_at": profile["updated_at"],
    }
    return JSONResponse(content=payload, media_type="application/json")


def _internal_comms_step_handler(data: InternalCommsStepIn) -> JSONResponse:
    from internal_comms_engine import run_internal_comms_step

    msgs = [{"role": m.role, "text": m.text} for m in data.messages]
    out = run_internal_comms_step(
        save_uid=data.save_uid or "",
        audience=(data.audience or "board").strip().lower(),
        interaction_mode=(data.interaction_mode or "group").strip().lower(),
        focus_player_id=data.focus_player_id,
        focus_player_name=data.focus_player_name,
        linked_headline=data.linked_headline,
        touchpoint_context=data.touchpoint_context,
        messages=msgs,
    )
    return JSONResponse(content=out, media_type="application/json")


@app.post("/internal-comms/step")
def internal_comms_step(data: InternalCommsStepIn) -> JSONResponse:
    return _internal_comms_step_handler(data)


@app.post("/companion/internal-comms/step")
def companion_internal_comms_step(data: InternalCommsStepIn) -> JSONResponse:
    """Alias estável (mesmo prefixo que /companion/overview) para proxy e SPA não confundirem com static."""
    return _internal_comms_step_handler(data)


@app.post("/press-conference/respond")
def press_conference_respond(data: PressConferenceIn) -> JSONResponse:
    from press_narrative import build_coach_press_answer, build_press_headline, build_press_reactions

    answer_text = (data.answer or "").strip()
    style = (data.response_style or "").strip().lower()
    audience = (data.audience or "").strip().lower() or None
    if style:
        answer_text = build_coach_press_answer(
            style,
            audience or "board",
            data.question,
            data.save_uid,
            topic_type=data.topic_type,
            focus_player_name=data.focus_player_name,
            interaction_mode=data.interaction_mode,
            linked_headline=data.linked_headline,
        )
    tone, reputation_delta, morale_delta = reputation_engine.analyze_press_answer(answer_text)
    board_active = get_active_board_challenge(data.save_uid, "ULTIMATUM") if data.save_uid else None
    crisis_active = get_active_crisis_arc(data.save_uid) if data.save_uid else None
    headline = build_press_headline(tone, audience, reputation_delta)
    reactions = build_press_reactions(tone, audience, reputation_delta, morale_delta, bool(board_active), bool(crisis_active))
    board_reaction = reactions["board"]
    locker_room_reaction = reactions["locker_room"]
    fan_reaction = reactions["fan"]
    current_game_date = _iso_game_date(_read_state())
    conference_id = save_press_conference(
        save_uid=data.save_uid,
        question=data.question,
        answer=answer_text,
        detected_tone=tone,
        reputation_delta=reputation_delta,
        morale_delta=morale_delta,
        headline=headline,
        board_reaction=board_reaction,
        locker_room_reaction=locker_room_reaction,
        fan_reaction=fan_reaction,
        game_date=current_game_date,
    )
    profile_payload = None
    if data.save_uid:
        current_profile = get_or_create_coach_profile(data.save_uid)
        reputation_score = reputation_engine.normalize_score(int(current_profile["reputation_score"]) + reputation_delta)
        fan_sentiment_score = reputation_engine.normalize_score(int(current_profile["fan_sentiment_score"]) + reputation_delta)
        profile_payload = update_coach_profile(
            save_uid=data.save_uid,
            reputation_score=reputation_score,
            reputation_label=reputation_engine.reputation_label(reputation_score),
            playstyle_label=current_profile["playstyle_label"],
            fan_sentiment_score=fan_sentiment_score,
            fan_sentiment_label=reputation_engine.fan_label(fan_sentiment_score),
        )
    press_fallout: Optional[Dict[str, Any]] = None
    if data.save_uid and current_game_date:
        fallout_facts = build_press_fallout_career_facts(
            save_uid=data.save_uid,
            game_date=current_game_date,
            conference_id=conference_id,
            headline=headline,
            board_reaction=board_reaction,
            locker_room_reaction=locker_room_reaction,
            fan_reaction=fan_reaction,
            audience=audience,
            focus_player_name=data.focus_player_name,
            linked_headline=data.linked_headline,
            detected_tone=tone,
            reputation_delta=reputation_delta,
            morale_delta=morale_delta,
        )
        merged_facts = merge_career_facts(data.save_uid, current_game_date, fallout_facts)
        fid = save_feed_item(
            event_type="PRESS_CONFERENCE_FALLOUT",
            channel="press",
            title=headline[:180],
            content=(answer_text[:500] + "\n\n—\n\n" + fan_reaction[:400]).strip(),
            tone=tone,
            source="press_conference",
            save_uid=data.save_uid,
        )
        press_fallout = {"career_facts_count": len(merged_facts), "feed_item_id": fid}
    payload_out: Dict[str, Any] = {
        "id": conference_id,
        "detected_tone": tone,
        "reputation_delta": reputation_delta,
        "morale_delta": morale_delta,
        "headline": headline,
        "board_reaction": board_reaction,
        "locker_room_reaction": locker_room_reaction,
        "fan_reaction": fan_reaction,
        "coach_profile": profile_payload,
        "answer_rendered": answer_text,
        "audience": audience,
        "response_style": style or None,
    }
    if press_fallout is not None:
        payload_out["press_fallout"] = press_fallout
    if (
        data.save_uid
        and data.focus_player_id
        and str(data.audience or "").strip().lower() == "players"
        and str(data.interaction_mode or "").strip().lower() == "one_on_one"
    ):
        pr_up = apply_one_on_one_interaction_to_relation(
            save_uid=data.save_uid,
            player_id=int(data.focus_player_id),
            player_name=data.focus_player_name,
            tone=tone,
            reputation_delta=reputation_delta,
            morale_delta=morale_delta,
        )
        if pr_up:
            payload_out["player_relation_update"] = pr_up
    if bool(getattr(data, "social_internal_comms", False)) and data.save_uid and current_game_date:
        record_internal_comms_completed(data.save_uid, current_game_date)
        payload_out["internal_comms_day_locked"] = True
        payload_out["locked_game_date"] = current_game_date
    return JSONResponse(content=payload_out, media_type="application/json")


@app.get("/press-conference/recent")
def press_conference_recent(
    limit: int = Query(default=20, ge=1, le=200),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_press_conferences(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/board/challenges/active")
def board_challenge_active(save_uid: str = Query(...)) -> JSONResponse:
    item = get_active_board_challenge(save_uid, challenge_type="ULTIMATUM")
    return JSONResponse(content=item, media_type="application/json")


@app.get("/board/challenges/recent")
def board_challenges_recent(
    limit: int = Query(default=20, ge=1, le=200),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_board_challenges(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/crisis/active")
def crisis_active(save_uid: str = Query(...)) -> JSONResponse:
    item = get_active_crisis_arc(save_uid)
    return JSONResponse(content=item, media_type="application/json")


@app.get("/crisis/recent")
def crisis_recent(
    limit: int = Query(default=20, ge=1, le=200),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_crisis_arcs(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/crisis/trigger")
def crisis_trigger(data: CrisisTriggerIn) -> JSONResponse:
    current = get_active_crisis_arc(data.save_uid)
    if current:
        return JSONResponse(content={"status": "active_exists", "crisis": current}, media_type="application/json")
    created = create_crisis_arc(
        save_uid=data.save_uid,
        trigger_type="MANUAL",
        severity=data.severity or "moderada",
        summary=data.reason,
        max_steps=4,
    )
    emitted = emit_system_event(
        "CRISIS_STARTED",
        {
            "crisis_id": created["id"],
            "severity": created["severity"],
            "summary": created["summary"],
            "max_steps": created["max_steps"],
        },
        data.save_uid,
    )
    timeline_id = save_timeline_entry(
        save_uid=data.save_uid,
        source_event="CRISIS_STARTED",
        phase="crisis_start",
        title="Crise iniciada manualmente",
        content=created["summary"],
        importance=95,
    )
    return JSONResponse(
        content={
            "status": "ok",
            "crisis": created,
            "event_id": emitted["event_id"],
            "timeline_entry_id": timeline_id,
        },
        media_type="application/json",
    )


@app.get("/season-arc/active")
def season_arc_active(save_uid: str = Query(...)) -> JSONResponse:
    item = get_active_season_arc(save_uid)
    return JSONResponse(content=item, media_type="application/json")


@app.get("/season-arc/recent")
def season_arc_recent(
    limit: int = Query(default=20, ge=1, le=200),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_season_arcs(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/season-arc/trigger")
def season_arc_trigger(data: SeasonArcTriggerIn) -> JSONResponse:
    current = get_active_season_arc(data.save_uid)
    if current:
        return JSONResponse(content={"status": "active_exists", "season_arc": current}, media_type="application/json")
    created = create_season_arc(
        save_uid=data.save_uid,
        title=data.title,
        theme=data.theme,
        season_label=data.season_label or "manual",
        max_milestones=5,
    )
    append_season_arc_memory(
        arc_id=int(created["id"]),
        memory_text=f"Início manual do arco: {data.title}",
        source_event="SEASON_ARC_TRIGGER",
    )
    emitted = emit_system_event(
        "SEASON_ARC_STARTED",
        {
            "arc_id": created["id"],
            "title": created["title"],
            "theme": created["theme"],
            "summary": f"O arco '{created['title']}' foi iniciado manualmente.",
            "max_milestones": created["max_milestones"],
        },
        data.save_uid,
    )
    return JSONResponse(
        content={"status": "ok", "season_arc": created, "event_id": emitted["event_id"]},
        media_type="application/json",
    )


@app.post("/season-arc/memory")
def season_arc_memory(data: SeasonArcMemoryIn) -> JSONResponse:
    active = get_active_season_arc(data.save_uid)
    if not active:
        raise HTTPException(status_code=404, detail="Nenhum arco sazonal ativo para este save")
    updated = append_season_arc_memory(
        arc_id=int(active["id"]),
        memory_text=data.memory_text,
        source_event=data.source_event,
    )
    return JSONResponse(content={"status": "ok", "season_arc": updated}, media_type="application/json")


@app.get("/season-arc/payoff/recent")
def season_arc_payoff_recent(
    limit: int = Query(default=10, ge=1, le=100),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_season_payoffs(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.get("/legacy/profile")
def legacy_profile(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_legacy_profile(save_uid)
    if profile is None:
        profile = rebuild_legacy(save_uid)
    return JSONResponse(content=profile, media_type="application/json")


@app.post("/legacy/rebuild")
def legacy_rebuild(save_uid: str = Query(...)) -> JSONResponse:
    profile = rebuild_legacy(save_uid)
    emitted = emit_system_event("LEGACY_UPDATED", profile, save_uid)
    hof_profile = rebuild_hall_of_fame(save_uid)
    emitted_hof = emit_system_event("HOF_UPDATED", hof_profile, save_uid)
    return JSONResponse(
        content={
            "status": "ok",
            "legacy_profile": profile,
            "event_id": emitted["event_id"],
            "hall_of_fame_profile": hof_profile,
            "hall_of_fame_event_id": emitted_hof["event_id"],
        },
        media_type="application/json",
    )


@app.get("/hall-of-fame/profile")
def hall_of_fame_profile(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_hall_of_fame_profile(save_uid)
    if profile is None:
        profile = rebuild_hall_of_fame(save_uid)
    return JSONResponse(content=profile, media_type="application/json")


@app.get("/hall-of-fame/entries")
def hall_of_fame_entries(
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_hall_of_fame_entries(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/hall-of-fame/rebuild")
def hall_of_fame_rebuild(save_uid: str = Query(...)) -> JSONResponse:
    profile = rebuild_hall_of_fame(save_uid)
    emitted = emit_system_event("HOF_UPDATED", profile, save_uid)
    return JSONResponse(
        content={"status": "ok", "hall_of_fame_profile": profile, "event_id": emitted["event_id"]},
        media_type="application/json",
    )


@app.get("/achievements/profile")
def achievements_profile(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_achievement_profile(save_uid)
    if profile is None:
        profile = rebuild_achievements(save_uid)
    return JSONResponse(content=profile, media_type="application/json")


@app.get("/achievements/recent")
def achievements_recent(
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_achievements(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/achievements/rebuild")
def achievements_rebuild(save_uid: str = Query(...)) -> JSONResponse:
    profile = rebuild_achievements(save_uid)
    emitted = emit_system_event(
        "ACHIEVEMENTS_UPDATED",
        {"summary": f"Conquistas recalculadas: nível {profile['career_level']}."},
        save_uid,
    )
    return JSONResponse(
        content={"status": "ok", "achievements_profile": profile, "event_id": emitted["event_id"]},
        media_type="application/json",
    )


@app.get("/meta-achievements/profile")
def meta_achievements_profile(save_uid: str = Query(...)) -> JSONResponse:
    profile = get_meta_achievement_profile(save_uid)
    if profile is None:
        profile = rebuild_meta_achievements(save_uid)
    return JSONResponse(content=profile, media_type="application/json")


@app.get("/meta-achievements/recent")
def meta_achievements_recent(
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_meta_achievements(limit=limit, save_uid=save_uid)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/meta-achievements/rebuild")
def meta_achievements_rebuild(save_uid: str = Query(...)) -> JSONResponse:
    profile = rebuild_meta_achievements(save_uid)
    emitted = emit_system_event(
        "META_ACHIEVEMENTS_UPDATED",
        {"summary": f"Meta-conquistas recalculadas: prestígio {profile['prestige_level']}."},
        save_uid,
    )
    return JSONResponse(
        content={"status": "ok", "meta_achievements_profile": profile, "event_id": emitted["event_id"]},
        media_type="application/json",
    )


@app.post("/season-arc/payoff/generate")
def season_arc_payoff_generate(data: SeasonPayoffIn) -> JSONResponse:
    active = get_active_season_arc(data.save_uid)
    if not active:
        raise HTTPException(status_code=404, detail="Nenhum arco sazonal ativo para este save")
    profile = get_or_create_coach_profile(data.save_uid)
    payoff = payoff_engine.build(active, profile)
    if data.summary_hint:
        payoff["epilogue"] = f"{payoff['epilogue']} {data.summary_hint}"
    payoff_id = save_season_payoff(
        save_uid=data.save_uid,
        season_arc_id=int(active["id"]),
        final_score=int(payoff["final_score"]),
        grade=payoff["grade"],
        title=payoff["title"],
        epilogue=payoff["epilogue"],
        factors=payoff["factors"],
    )
    emitted = emit_system_event(
        "SEASON_ARC_PAYOFF",
        {
            "season_arc_id": int(active["id"]),
            "final_score": int(payoff["final_score"]),
            "grade": payoff["grade"],
            "title": payoff["title"],
            "epilogue": payoff["epilogue"],
        },
        data.save_uid,
    )
    timeline_id = save_timeline_entry(
        save_uid=data.save_uid,
        source_event="SEASON_ARC_PAYOFF",
        phase="season_arc_payoff",
        title=payoff["title"],
        content=payoff["epilogue"],
        importance=98,
    )
    legacy_profile = rebuild_legacy(data.save_uid)
    emitted_legacy = emit_system_event("LEGACY_UPDATED", legacy_profile, data.save_uid)
    hof_entry = hall_of_fame_engine.build_entry_from_payoff(
        {
            "final_score": int(payoff["final_score"]),
            "grade": payoff["grade"],
            "title": payoff["title"],
        }
    )
    save_hall_of_fame_entry(
        save_uid=data.save_uid,
        category=hof_entry["category"],
        title=hof_entry["title"],
        description=hof_entry["description"],
        score_impact=int(hof_entry["score_impact"]),
        source=hof_entry["source"],
    )
    hall_of_fame_profile = rebuild_hall_of_fame(data.save_uid)
    emitted_hof = emit_system_event("HOF_UPDATED", hall_of_fame_profile, data.save_uid)
    unlocks = achievements_engine.unlocks_from_context(
        payoff=payoff,
        legacy_profile=legacy_profile,
        hall_of_fame_profile=hall_of_fame_profile,
    )
    unlocked_codes: List[str] = []
    for unlock in unlocks:
        if not has_achievement(data.save_uid, unlock["code"]):
            save_achievement(
                save_uid=data.save_uid,
                code=unlock["code"],
                title=unlock["title"],
                description=unlock["description"],
                rarity=unlock["rarity"],
                points=int(unlock["points"]),
                source=unlock["source"],
            )
            unlocked_codes.append(unlock["code"])
            emit_system_event("ACHIEVEMENT_UNLOCKED", unlock, data.save_uid)
    achievements_profile = rebuild_achievements(data.save_uid)
    emitted_achievements = emit_system_event(
        "ACHIEVEMENTS_UPDATED",
        {"summary": f"Conquistas: {achievements_profile['total_achievements']} totais, nível {achievements_profile['career_level']}."},
        data.save_uid,
    )
    current_achievements = get_recent_achievements(limit=500, save_uid=data.save_uid)
    meta_unlocks = meta_achievements_engine.unlocks_from_achievements(current_achievements)
    unlocked_meta_codes: List[str] = []
    for meta_unlock in meta_unlocks:
        if not has_meta_achievement(data.save_uid, meta_unlock["code"]):
            save_meta_achievement(
                save_uid=data.save_uid,
                code=meta_unlock["code"],
                title=meta_unlock["title"],
                description=meta_unlock["description"],
                collection_tag=meta_unlock["collection_tag"],
                points=int(meta_unlock["points"]),
            )
            unlocked_meta_codes.append(meta_unlock["code"])
            emit_system_event("META_ACHIEVEMENT_UNLOCKED", meta_unlock, data.save_uid)
    meta_achievements_profile = rebuild_meta_achievements(data.save_uid)
    emitted_meta_achievements = emit_system_event(
        "META_ACHIEVEMENTS_UPDATED",
        {"summary": f"Meta-conquistas: {meta_achievements_profile['total_meta']} totais, prestígio {meta_achievements_profile['prestige_level']}."},
        data.save_uid,
    )
    return JSONResponse(
        content={
            "status": "ok",
            "payoff_id": payoff_id,
            "event_id": emitted["event_id"],
            "legacy_event_id": emitted_legacy["event_id"],
            "legacy_profile": legacy_profile,
            "hall_of_fame_event_id": emitted_hof["event_id"],
            "hall_of_fame_profile": hall_of_fame_profile,
            "achievements_event_id": emitted_achievements["event_id"],
            "achievements_profile": achievements_profile,
            "unlocked_achievements": unlocked_codes,
            "meta_achievements_event_id": emitted_meta_achievements["event_id"],
            "meta_achievements_profile": meta_achievements_profile,
            "unlocked_meta_achievements": unlocked_meta_codes,
            "timeline_entry_id": timeline_id,
            "final_score": payoff["final_score"],
            "grade": payoff["grade"],
            "title": payoff["title"],
            "epilogue": payoff["epilogue"],
        },
        media_type="application/json",
    )


@app.get("/market/rumors/recent")
def market_rumors_recent(
    limit: int = Query(default=20, ge=1, le=200),
    save_uid: Optional[str] = Query(default=None),
    trigger_event: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_market_rumors(limit=limit, save_uid=save_uid, trigger_event=trigger_event)
    return JSONResponse(content=items, media_type="application/json")


@app.post("/market/rumors/generate")
def market_rumors_generate(data: MarketRumorIn) -> JSONResponse:
    profile = get_or_create_coach_profile(data.save_uid) if data.save_uid else {
        "reputation_score": 50,
        "playstyle_label": "equilibrado",
    }
    rumor = market_engine.build_rumor(data.trigger_event, data.payload, profile)
    rumor_id = save_market_rumor(
        save_uid=data.save_uid,
        trigger_event=data.trigger_event,
        headline=rumor["headline"],
        content=rumor["content"],
        confidence_level=int(rumor["confidence_level"]),
        target_profile=rumor["target_profile"],
    )
    return JSONResponse(
        content={
            "status": "ok",
            "rumor_id": rumor_id,
            "headline": rumor["headline"],
            "content": rumor["content"],
            "confidence_level": rumor["confidence_level"],
            "target_profile": rumor["target_profile"],
        },
        media_type="application/json",
    )


@app.get("/timeline/recent")
def timeline_recent(
    limit: int = Query(default=30, ge=1, le=300),
    save_uid: Optional[str] = Query(default=None),
    phase: Optional[str] = Query(default=None),
    source_event: Optional[str] = Query(default=None),
) -> JSONResponse:
    items = get_recent_timeline_entries(
        limit=limit,
        save_uid=save_uid,
        phase=phase,
        source_event=source_event,
    )
    return JSONResponse(content=items, media_type="application/json")


@app.post("/timeline/generate")
def timeline_generate(data: TimelineEntryIn) -> JSONResponse:
    profile = get_or_create_coach_profile(data.save_uid) if data.save_uid else {
        "reputation_score": 50,
        "playstyle_label": "equilibrado",
    }
    entries = editorial_engine.build_entries(data.source_event, data.payload, profile)
    ids: List[int] = []
    for entry in entries:
        ids.append(
            save_timeline_entry(
                save_uid=data.save_uid,
                source_event=data.source_event,
                phase=entry["phase"],
                title=entry["title"],
                content=entry["content"],
                importance=int(entry["importance"]),
            )
        )
    return JSONResponse(
        content={
            "status": "ok",
            "created": len(ids),
            "timeline_entry_ids": ids,
        },
        media_type="application/json",
    )

# ── Uploads de imagens (troféus e escudos de clube) ──────────────────────────
_UPLOADS_DIR = Path(__file__).parent / "uploads"
_UPLOADS_DIR.mkdir(exist_ok=True)
(_UPLOADS_DIR / "trophies").mkdir(exist_ok=True)
(_UPLOADS_DIR / "clubs").mkdir(exist_ok=True)

_ALLOWED_IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


def _safe_filename(name: str) -> str:
    import re
    name = re.sub(r"[^\w\-.]", "_", name.strip())
    return name[:120] if name else "image"


@app.post("/uploads/trophy")
async def upload_trophy_image(
    trophy_key: str = Query(..., description="Chave única do troféu, ex: domestic_cup_1"),
    file: UploadFile = File(...),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_IMG_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use JPG, PNG, WebP ou SVG.")
    dest = _UPLOADS_DIR / "trophies" / f"{_safe_filename(trophy_key)}{ext}"
    content = await file.read()
    dest.write_bytes(content)
    return {"url": f"/uploads/trophies/{dest.name}", "key": trophy_key}


@app.post("/uploads/club")
async def upload_club_image(
    club_name: str = Query(..., description="Nome do clube"),
    file: UploadFile = File(...),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_IMG_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use JPG, PNG, WebP ou SVG.")
    dest = _UPLOADS_DIR / "clubs" / f"{_safe_filename(club_name)}{ext}"
    content = await file.read()
    dest.write_bytes(content)
    return {"url": f"/uploads/clubs/{dest.name}", "club_name": club_name}


@app.get("/uploads/list")
def list_uploads():
    trophies = [f"/uploads/trophies/{f.name}" for f in (_UPLOADS_DIR / "trophies").iterdir() if f.is_file()]
    clubs = [f"/uploads/clubs/{f.name}" for f in (_UPLOADS_DIR / "clubs").iterdir() if f.is_file()]
    return {"trophies": trophies, "clubs": clubs}


app.mount("/uploads", StaticFiles(directory=str(_UPLOADS_DIR)), name="uploads")

# Mount Frontend PWA
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    # Fallback to index.html for SPA routing
    if request.method == "GET" and not request.url.path.startswith(("/api", "/state", "/events", "/feed", "/companion", "/career", "/profile", "/torcida", "/press-conference", "/board", "/crisis", "/season-arc", "/legacy", "/hall-of-fame", "/achievements", "/meta-achievements", "/market", "/timeline", "/dashboard", "/news", "/conference", "/finance", "/uploads", "/stats")):
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return JSONResponse({"detail": "Not Found"}, status_code=404)
