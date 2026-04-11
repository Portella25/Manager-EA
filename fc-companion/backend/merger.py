from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class StateMerger:
    # Mesclador tolerante a falhas: sempre retorna estado válido mesmo com fonte ausente.
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / "Desktop" / "fc_companion")
        self.state_lua_path = self.base_dir / "state_lua.json"
        self.save_data_path = self.base_dir / "save_data.json"

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            if not path.exists():
                return {}
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return {}
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _safe_list(self, value: Any) -> List[Any]:
        return value if isinstance(value, list) else []

    def _safe_dict(self, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _extract_lua_name_map(self, lua: Dict[str, Any]) -> Dict[int, str]:
        name_resolution = self._safe_dict(lua.get("name_resolution"))
        resolved_raw = self._safe_dict(name_resolution.get("resolved"))
        out: Dict[int, str] = {}
        for key, value in resolved_raw.items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            name = str(value or "").strip()
            if pid > 0 and name:
                out[pid] = name
        return out

    def _apply_name_resolution(self, squad: List[Dict[str, Any]], name_map: Dict[int, str]) -> None:
        for player in squad:
            try:
                pid = int(player.get("playerid") or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid <= 0:
                continue
            resolved = str(name_map.get(pid) or "").strip()
            if resolved:
                player["player_name"] = resolved
                player["name_source"] = "lua_runtime"

    def _extract_lua_live_role_map(self, lua: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        raw_roles = self._safe_dict(lua.get("live_player_roles"))
        out: Dict[int, Dict[str, Any]] = {}
        for key, value in raw_roles.items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            if pid <= 0:
                continue
            if isinstance(value, dict):
                role = value.get("playerrole")
                source = value.get("source")
                contract_status = value.get("contract_status")
            else:
                role = value
                source = "lua_player_status_manager"
                contract_status = None
            try:
                role_i = int(role)
            except (TypeError, ValueError):
                role_i = -1
            if role_i >= 0:
                out[pid] = {
                    "playerrole": role_i,
                    "source": str(source or "lua_player_status_manager"),
                    "contract_status": contract_status,
                }
        return out

    def _apply_live_roles(self, squad: List[Dict[str, Any]], live_role_map: Dict[int, Dict[str, Any]]) -> None:
        if not live_role_map:
            return
        for player in squad:
            try:
                pid = int(player.get("playerid") or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid <= 0:
                continue
            payload = live_role_map.get(pid)
            if not payload:
                continue
            player["playerrole"] = payload.get("playerrole")
            player["playerrole_source"] = payload.get("source")
            if payload.get("contract_status") is not None and player.get("contract_status") is None:
                player["contract_status"] = payload.get("contract_status")

    def _extract_live_db_players(self, lua: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        raw = self._safe_dict(lua.get("live_db_players"))
        out: Dict[int, Dict[str, Any]] = {}
        for key, value in raw.items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or not isinstance(value, dict):
                continue
            out[pid] = value
        return out

    def _apply_live_db_players(self, squad: List[Dict[str, Any]], live_db: Dict[int, Dict[str, Any]]) -> None:
        if not live_db:
            return
        for player in squad:
            try:
                pid = int(player.get("playerid") or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid <= 0:
                continue
            snap = live_db.get(pid)
            if not snap:
                continue
            ovr = snap.get("overallrating")
            if ovr is not None:
                try:
                    player["overallrating"] = int(ovr)
                except (TypeError, ValueError):
                    player["overallrating"] = ovr
                player["overallrating_source"] = "lua_le_db"
            pos = snap.get("preferredposition1")
            if pos is not None:
                try:
                    player["preferredposition1"] = int(pos)
                except (TypeError, ValueError):
                    player["preferredposition1"] = pos
                player["preferredposition_source"] = "lua_le_db"
            pot = snap.get("potential")
            if pot is not None and player.get("potential") is None:
                try:
                    player["potential"] = int(pot)
                except (TypeError, ValueError):
                    player["potential"] = pot
            for fld in ("age", "form", "fitness", "sharpness"):
                v = snap.get(fld)
                if v is not None and player.get(fld) is None:
                    player[fld] = v

    def merge(self) -> Dict[str, Any]:
        try:
            lua = self._read_json(self.state_lua_path)
            save = self._read_json(self.save_data_path)

            lua_meta = self._safe_dict(lua.get("meta"))
            save_manager = self._safe_dict(save.get("manager"))
            lua_club = self._safe_dict(lua.get("club"))
            save_stats = self._safe_dict(save.get("season_stats"))
            squad = self._safe_list(save.get("squad"))
            lua_name_map = self._extract_lua_name_map(lua)
            lua_live_roles = self._extract_lua_live_role_map(lua)
            lua_live_db = self._extract_live_db_players(lua)
            self._apply_name_resolution(squad, lua_name_map)
            self._apply_live_db_players(squad, lua_live_db)
            self._apply_live_roles(squad, lua_live_roles)
            squad.sort(
                key=lambda p: p.get("overall_live") or p.get("overallrating") or 0,
                reverse=True,
            )

            merged_meta = dict(lua_meta)
            merged_meta["save_extracted_at"] = save.get("extracted_at")
            merged_meta["name_resolution_count"] = len(lua_name_map)
            merged_meta["live_roles_count"] = len(lua_live_roles)
            merged_meta["live_db_players_count"] = len(lua_live_db)
            sources = []
            if lua:
                sources.append("lua_memory")
            if save:
                sources.append("save_file")
            merged_meta["sources"] = sources or ["unknown"]
            if "timestamp" not in merged_meta:
                merged_meta["timestamp"] = int(datetime.now().timestamp())
            if "is_in_career_mode" not in merged_meta:
                merged_meta["is_in_career_mode"] = bool(lua)
            if "source" not in merged_meta:
                merged_meta["source"] = "merged"

            standings = self._safe_list(lua.get("standings"))
            for row in standings:
                if not row.get("team_name") and row.get("team_id"):
                    row["team_name"] = f"Team {row.get('team_id')}"

            fixtures = self._safe_list(lua.get("fixtures"))
            for fx in fixtures:
                if not fx.get("home_team_name") and fx.get("home_team_id"):
                    fx["home_team_name"] = f"Team {fx.get('home_team_id')}"
                if not fx.get("away_team_name") and fx.get("away_team_id"):
                    fx["away_team_name"] = f"Team {fx.get('away_team_id')}"

            merged = {
                "meta": merged_meta,
                "manager": save_manager,
                "club": {
                    **lua_club,
                    "season_stats": save_stats,
                },
                "squad": squad,
                "fixtures": fixtures,
                "standings": standings,
                "injuries": self._safe_list(save.get("injuries")),
                "transfer_offers": self._safe_list(save.get("transfer_offers")),
                "transfer_history": self._safe_list(save.get("transfer_history")),
                "all_teams": self._safe_list(save.get("teams")),
                "events_raw": self._safe_list(lua.get("events_raw")),
                "finance_live": self._safe_dict(lua.get("finance_live")),
            }
            return merged
        except Exception:
            return {
                "meta": {
                    "timestamp": int(datetime.now().timestamp()),
                    "is_in_career_mode": False,
                    "source": "merged",
                    "sources": ["unknown"],
                },
                "manager": {},
                "club": {},
                "squad": [],
                "fixtures": [],
                "standings": [],
                "injuries": [],
                "transfer_offers": [],
                "transfer_history": [],
                "all_teams": [],
                "events_raw": [],
                "finance_live": {},
            }

    def merge_and_save(self, output_path: Path) -> Dict[str, Any]:
        payload = self.merge()
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = output_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            if output_path.exists():
                output_path.unlink()
            tmp_path.replace(output_path)
        except Exception:
            return payload
        return payload
