from __future__ import annotations

"""Detecção de eventos de gameplay a partir de diff entre estados sucessivos."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from models import GameEvent


class EventDetector:
    def detect(self, old_state: Optional[Dict[str, Any]], new_state: Dict[str, Any]) -> List[GameEvent]:
        # O primeiro estado serve como baseline e não gera eventos.
        if old_state is None:
            return []
        events: List[GameEvent] = []
        events.extend(self._detect_match_completed(old_state, new_state))
        events.extend(self._detect_player_injured(old_state, new_state))
        events.extend(self._detect_player_recovered(old_state, new_state))
        events.extend(self._detect_transfer_offer_received(old_state, new_state))
        events.extend(self._detect_budget_changed(old_state, new_state))
        events.extend(self._detect_season_changed(old_state, new_state))
        events.extend(self._detect_morale_drop(old_state, new_state))
        events.extend(self._detect_date_advanced(old_state, new_state))
        return events

    def _save_uid(self, state: Dict[str, Any]) -> Optional[str]:
        return ((state.get("meta") or {}).get("save_uid"))

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _fixture_key(self, fixture: Dict[str, Any]) -> Tuple[Any, Any, Any]:
        return fixture.get("id"), fixture.get("date_raw"), fixture.get("competition_id")

    def _user_team_id(self, state: Dict[str, Any]) -> int:
        club = dict(state.get("club") or {})
        manager = dict(state.get("manager") or {})
        for value in (club.get("team_id"), manager.get("team_id")):
            try:
                team_id = int(value)
            except (TypeError, ValueError):
                team_id = 0
            if team_id > 0:
                return team_id
        return 0

    def _detect_match_completed(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        user_team_id = self._user_team_id(new_state)
        if user_team_id <= 0:
            return []
        old_fixtures = {self._fixture_key(f): f for f in (old_state.get("fixtures") or [])}
        new_fixtures = {self._fixture_key(f): f for f in (new_state.get("fixtures") or [])}
        found: List[GameEvent] = []
        for key, new_fx in new_fixtures.items():
            old_fx = old_fixtures.get(key)
            if not old_fx:
                continue
            old_done = bool(old_fx.get("is_completed"))
            new_done = bool(new_fx.get("is_completed"))
            if (not old_done) and new_done:
                try:
                    home_team_id = int(new_fx.get("home_team_id") or 0)
                except (TypeError, ValueError):
                    home_team_id = 0
                try:
                    away_team_id = int(new_fx.get("away_team_id") or 0)
                except (TypeError, ValueError):
                    away_team_id = 0
                if user_team_id not in (home_team_id, away_team_id):
                    continue
                is_home = user_team_id == home_team_id
                home_score = new_fx.get("home_score")
                away_score = new_fx.get("away_score")
                payload = {
                    "user_team_id": user_team_id,
                    "fixture_id": new_fx.get("id"),
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "home_team": new_fx.get("home_team_name"),
                    "away_team": new_fx.get("away_team_name"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "is_home": is_home,
                    "my_score": home_score if is_home else away_score,
                    "opp_score": away_score if is_home else home_score,
                    "opponent_team_id": away_team_id if is_home else home_team_id,
                    "opponent_team_name": new_fx.get("away_team_name") if is_home else new_fx.get("home_team_name"),
                    "club_name": (new_state.get("club") or {}).get("team_name"),
                    "competition": new_fx.get("competition_name"),
                    "competition_id": new_fx.get("competition_id"),
                    "date": new_fx.get("date_raw"),
                }
                found.append(
                    GameEvent(
                        event_type="MATCH_COMPLETED",
                        payload=payload,
                        timestamp=self._now(),
                        save_uid=self._save_uid(new_state),
                    )
                )
        return found

    def _injury_set(self, state: Dict[str, Any]) -> Set[Any]:
        return {inj.get("playerid") for inj in (state.get("injuries") or []) if inj.get("playerid") is not None}

    def _injury_map(self, state: Dict[str, Any]) -> Dict[Any, Dict[str, Any]]:
        return {inj.get("playerid"): inj for inj in (state.get("injuries") or []) if inj.get("playerid") is not None}

    def _detect_player_injured(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_set = self._injury_set(old_state)
        new_map = self._injury_map(new_state)
        found: List[GameEvent] = []
        for player_id in new_map.keys() - old_set:
            inj = new_map[player_id]
            payload = {
                "player_name": inj.get("player_name"),
                "injury_type": inj.get("injury_type"),
                "severity": inj.get("severity"),
                "games_remaining": inj.get("games_remaining"),
            }
            found.append(
                GameEvent(
                    event_type="PLAYER_INJURED",
                    payload=payload,
                    timestamp=self._now(),
                    save_uid=self._save_uid(new_state),
                )
            )
        return found

    def _detect_player_recovered(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_map = self._injury_map(old_state)
        new_set = self._injury_set(new_state)
        found: List[GameEvent] = []
        for player_id in old_map.keys() - new_set:
            inj = old_map[player_id]
            payload = {"player_name": inj.get("player_name")}
            found.append(
                GameEvent(
                    event_type="PLAYER_RECOVERED",
                    payload=payload,
                    timestamp=self._now(),
                    save_uid=self._save_uid(new_state),
                )
            )
        return found

    def _offer_key(self, offer: Dict[str, Any]) -> Tuple[Any, Any, Any, Any]:
        return (
            offer.get("playerid"),
            offer.get("from_team_id"),
            offer.get("offer_amount"),
            offer.get("offer_type"),
        )

    def _detect_transfer_offer_received(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_keys = {self._offer_key(o) for o in (old_state.get("transfer_offers") or [])}
        found: List[GameEvent] = []
        for offer in (new_state.get("transfer_offers") or []):
            key = self._offer_key(offer)
            if key in old_keys:
                continue
            payload = {
                "player_name": offer.get("player_name"),
                "from_team": offer.get("from_team_name"),
                "offer_amount": offer.get("offer_amount"),
                "offer_type": offer.get("offer_type"),
            }
            found.append(
                GameEvent(
                    event_type="TRANSFER_OFFER_RECEIVED",
                    payload=payload,
                    timestamp=self._now(),
                    save_uid=self._save_uid(new_state),
                )
            )
        return found

    def _detect_budget_changed(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_budget = ((old_state.get("club") or {}).get("transfer_budget"))
        new_budget = ((new_state.get("club") or {}).get("transfer_budget"))
        if old_budget is None or new_budget is None:
            return []
        diff = float(new_budget) - float(old_budget)
        # Regra de negócio: ignora pequenas variações menores ou iguais a 100k.
        if abs(diff) <= 100000:
            return []
        payload = {
            "old_budget": old_budget,
            "new_budget": new_budget,
            "difference": diff,
        }
        return [
            GameEvent(
                event_type="BUDGET_CHANGED",
                payload=payload,
                timestamp=self._now(),
                save_uid=self._save_uid(new_state),
            )
        ]

    def _detect_season_changed(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_season = ((old_state.get("meta") or {}).get("season"))
        new_season = ((new_state.get("meta") or {}).get("season"))
        if old_season is None or new_season is None or old_season == new_season:
            return []
        payload = {"old_season": old_season, "new_season": new_season}
        return [
            GameEvent(
                event_type="SEASON_CHANGED",
                payload=payload,
                timestamp=self._now(),
                save_uid=self._save_uid(new_state),
            )
        ]

    def _squad_map(self, state: Dict[str, Any]) -> Dict[Any, Dict[str, Any]]:
        return {p.get("playerid"): p for p in (state.get("squad") or []) if p.get("playerid") is not None}

    def _detect_morale_drop(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_players = self._squad_map(old_state)
        new_players = self._squad_map(new_state)
        found: List[GameEvent] = []
        for pid, new_player in new_players.items():
            old_player = old_players.get(pid)
            if not old_player:
                continue
            old_morale = old_player.get("morale")
            new_morale = new_player.get("morale")
            if old_morale is None or new_morale is None:
                continue
            if (float(old_morale) - float(new_morale)) > 15:
                display_name = new_player.get("commonname") or f"{new_player.get('firstname', '')} {new_player.get('lastname', '')}".strip()
                payload = {
                    "player_name": display_name,
                    "old_morale": old_morale,
                    "new_morale": new_morale,
                }
                found.append(
                    GameEvent(
                        event_type="MORALE_DROP",
                        payload=payload,
                        timestamp=self._now(),
                        save_uid=self._save_uid(new_state),
                    )
                )
        return found

    def _extract_date(self, state: Dict[str, Any]) -> Optional[Tuple[int, int, int]]:
        date_obj = ((state.get("meta") or {}).get("game_date")) or {}
        day = date_obj.get("day")
        month = date_obj.get("month")
        year = date_obj.get("year")
        if day is None or month is None or year is None:
            return None
        return int(year), int(month), int(day)

    def _detect_date_advanced(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[GameEvent]:
        old_date = self._extract_date(old_state)
        new_date = self._extract_date(new_state)
        if old_date is None or new_date is None:
            return []
        if new_date <= old_date:
            return []
        payload = {
            "old_date": f"{old_date[0]:04d}-{old_date[1]:02d}-{old_date[2]:02d}",
            "new_date": f"{new_date[0]:04d}-{new_date[1]:02d}-{new_date[2]:02d}",
        }
        return [
            GameEvent(
                event_type="DATE_ADVANCED",
                payload=payload,
                timestamp=self._now(),
                save_uid=self._save_uid(new_state),
            )
        ]
