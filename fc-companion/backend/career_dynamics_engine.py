from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import random
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _int_clamp(value: float, lo: int, hi: int) -> int:
    return int(_clamp(value, float(lo), float(hi)))


def _player_display_name(player: Dict[str, Any]) -> str:
    common = str(player.get("commonname") or "").strip()
    if common:
        return common
    first = str(player.get("firstname") or "").strip()
    last = str(player.get("lastname") or "").strip()
    merged = f"{first} {last}".strip()
    return merged if merged else f"#{player.get('playerid')}"


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_date_raw(value: Any) -> Optional[date]:
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    year = raw // 10000
    month = (raw // 100) % 100
    day = raw % 100
    if not (2000 <= year <= 2100):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _outcome_from_payload(payload: Dict[str, Any]) -> str:
    hs = payload.get("home_score")
    as_ = payload.get("away_score")
    try:
        hs_i = int(hs)
        as_i = int(as_)
    except (TypeError, ValueError):
        return "unknown"
    if hs_i > as_i:
        return "win"
    if hs_i < as_i:
        return "loss"
    return "draw"


@dataclass(frozen=True)
class EmittedEvent:
    event_type: str
    payload: Dict[str, Any]


class CareerDynamicsEngine:
    def on_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        state: Dict[str, Any],
        coach_profile: Optional[Dict[str, Any]],
        management_state: Dict[str, Any],
        existing_relations: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[EmittedEvent]]:
        locker = dict(management_state.get("locker_room") or {})
        finance = dict(management_state.get("finance") or {})
        tactical = dict(management_state.get("tactical") or {})
        academy = dict(management_state.get("academy") or {})
        medical = dict(management_state.get("medical") or {})

        game_date = self._best_game_date(state, payload, event_type)
        if game_date:
            locker.setdefault("last_game_date", game_date.isoformat())
            finance.setdefault("last_game_date", game_date.isoformat())
            tactical.setdefault("last_game_date", game_date.isoformat())
            academy.setdefault("last_game_date", game_date.isoformat())
            medical.setdefault("last_game_date", game_date.isoformat())

        squad = list(state.get("squad") or [])
        finance = self._bootstrap_finance(state, finance)
        tactical = self._bootstrap_tactical(coach_profile, tactical)

        relations_by_player = {int(r["playerid"]): r for r in existing_relations if r.get("playerid") is not None}
        relation_updates = self._ensure_relations(squad, relations_by_player)

        emitted: List[EmittedEvent] = []
        ledger_entries: List[Dict[str, Any]] = []

        if event_type == "MORALE_DROP":
            relation_updates.extend(self._apply_morale_drop(payload, squad, relations_by_player))

        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
            if event_type == "MATCH_COMPLETED":
                outcome = _outcome_from_payload(payload)
            else:
                if event_type == "match_won":
                    outcome = "win"
                elif event_type == "match_lost":
                    outcome = "loss"
                else:
                    outcome = "draw"
            relation_updates.extend(self._apply_match_outcome(outcome, squad, relations_by_player))
            tactical, tactical_emits = self._update_tactical_identity(outcome, coach_profile, tactical)
            emitted.extend(tactical_emits)
            finance, finance_emits, ledger = self._apply_match_finance(outcome, finance, game_date)
            emitted.extend(finance_emits)
            ledger_entries.extend(ledger)

        if event_type == "TRANSFER_OFFER_RECEIVED":
            emitted.extend(self._market_context_from_offer(payload, state, coach_profile, finance, locker))

        if event_type in ("BUDGET_CHANGED", "board_budget_cut"):
            finance = self._apply_budget_changed(payload, finance)

        if event_type == "DATE_ADVANCED":
            old_d = _parse_iso_date(str(payload.get("old_date") or ""))
            new_d = _parse_iso_date(str(payload.get("new_date") or ""))
            if old_d and new_d and new_d > old_d:
                locker, locker_emits = self._update_locker_room(state, locker)
                emitted.extend(locker_emits)
                medical, medical_emits = self._update_medical(state, medical, new_d)
                emitted.extend(medical_emits)
                academy, academy_emits = self._update_academy(state, academy, new_d)
                emitted.extend(academy_emits)
                finance, finance_emits, ledger = self._apply_finance_month_rollover(finance, old_d, new_d, state)
                emitted.extend(finance_emits)
                ledger_entries.extend(ledger)

        locker = self._finalize_locker_room(locker, relation_updates, state)

        next_state = {
            "locker_room": locker,
            "finance": finance,
            "tactical": tactical,
            "academy": academy,
            "medical": medical,
        }
        return next_state, relation_updates, ledger_entries, emitted

    def _bootstrap_finance(self, state: Dict[str, Any], finance: Dict[str, Any]) -> Dict[str, Any]:
        club = state.get("club") or {}
        transfer_budget = club.get("transfer_budget")
        wage_budget = club.get("wage_budget")
        if transfer_budget is not None:
            try:
                finance.setdefault("transfer_budget", float(transfer_budget))
            except (TypeError, ValueError):
                pass
        if wage_budget is not None:
            try:
                finance.setdefault("wage_budget", float(wage_budget))
            except (TypeError, ValueError):
                pass
        if "cash_balance" not in finance or finance.get("cash_balance") is None:
            base_cash = 0.0
            try:
                base_cash += float(finance.get("transfer_budget") or 0.0)
            except (TypeError, ValueError):
                pass
            finance["cash_balance"] = round(float(base_cash), 2)
        return finance

    def _apply_budget_changed(self, payload: Dict[str, Any], finance: Dict[str, Any]) -> Dict[str, Any]:
        new_budget = payload.get("new_budget")
        if new_budget is None:
            return finance
        try:
            finance["transfer_budget"] = float(new_budget)
        except (TypeError, ValueError):
            return finance
        if "cash_balance" not in finance or finance.get("cash_balance") is None:
            finance["cash_balance"] = round(float(finance.get("transfer_budget") or 0.0), 2)
        return finance

    def _bootstrap_tactical(self, coach_profile: Optional[Dict[str, Any]], tactical: Dict[str, Any]) -> Dict[str, Any]:
        coach_style = str((coach_profile or {}).get("playstyle_label") or "equilibrado")
        tactical.setdefault("coach_style", coach_style)
        tactical.setdefault("identity_label", str(tactical.get("identity_label") or coach_style))
        tactical.setdefault("stability", float(tactical.get("stability") or 55.0))
        return tactical

    def _best_game_date(self, state: Dict[str, Any], payload: Dict[str, Any], event_type: str) -> Optional[date]:
        from_state = ((state.get("meta") or {}).get("game_date")) or {}
        try:
            y = int(from_state.get("year"))
            m = int(from_state.get("month"))
            d = int(from_state.get("day"))
            return date(y, m, d)
        except (TypeError, ValueError):
            pass
        if event_type == "DATE_ADVANCED":
            return _parse_iso_date(str(payload.get("new_date") or ""))
        return None

    def _ensure_relations(self, squad: List[Dict[str, Any]], relations_by_player: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        updates: List[Dict[str, Any]] = []
        for p in squad:
            pid = p.get("playerid")
            if pid is None:
                continue
            pid_i = int(pid)
            existing = relations_by_player.get(pid_i)
            display_name = _player_display_name(p)
            morale = p.get("morale")
            trust_seed = 50
            if morale is not None:
                try:
                    trust_seed = _int_clamp(float(morale), 15, 85)
                except (TypeError, ValueError):
                    trust_seed = 50
            if existing is None:
                role_label = self._initial_role(p)
                updates.append(
                    {
                        "playerid": pid_i,
                        "player_name": display_name,
                        "trust": trust_seed,
                        "role_label": role_label,
                        "status_label": "neutro",
                        "frustration": 0,
                        "notes": {},
                    }
                )
                continue
            changed = False
            if (existing.get("player_name") or "") != display_name:
                existing["player_name"] = display_name
                changed = True
            if "role_label" not in existing or not existing.get("role_label"):
                existing["role_label"] = self._initial_role(p)
                changed = True
            if "status_label" not in existing or not existing.get("status_label"):
                existing["status_label"] = "neutro"
                changed = True
            if "trust" not in existing or existing.get("trust") is None:
                existing["trust"] = trust_seed
                changed = True
            if "frustration" not in existing or existing.get("frustration") is None:
                existing["frustration"] = 0
                changed = True
            if "notes" not in existing or existing.get("notes") is None:
                existing["notes"] = {}
                changed = True
            if changed:
                updates.append(existing)
        return updates

    def _initial_role(self, player: Dict[str, Any]) -> str:
        age = player.get("age")
        try:
            if age is not None and int(age) <= 21:
                return "promessa"
        except (TypeError, ValueError):
            pass
        ov = player.get("overall")
        try:
            if ov is not None and int(ov) >= 85:
                return "intocavel"
        except (TypeError, ValueError):
            pass
        return "rotacao"

    def _apply_morale_drop(
        self,
        payload: Dict[str, Any],
        squad: List[Dict[str, Any]],
        relations_by_player: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        target_name = str(payload.get("player_name") or "").strip()
        if not target_name:
            return []
        target_pid = None
        for p in squad:
            if _player_display_name(p) == target_name:
                target_pid = int(p.get("playerid"))
                break
        if target_pid is None:
            return []
        rel = relations_by_player.get(target_pid)
        if rel is None:
            return []
        trust = int(rel.get("trust") or 50)
        frustration = int(rel.get("frustration") or 0)
        trust = _int_clamp(trust - 6, 0, 100)
        frustration = _int_clamp(frustration + 8, 0, 100)
        rel["trust"] = trust
        rel["frustration"] = frustration
        if frustration >= 60 or trust <= 35:
            rel["status_label"] = "frustrado"
        return [rel]

    def _apply_match_outcome(
        self,
        outcome: str,
        squad: List[Dict[str, Any]],
        relations_by_player: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if outcome not in {"win", "draw", "loss"}:
            return []
        delta = 1 if outcome == "win" else (-1 if outcome == "loss" else 0)
        updates: List[Dict[str, Any]] = []
        for p in squad:
            pid = p.get("playerid")
            if pid is None:
                continue
            rel = relations_by_player.get(int(pid))
            if rel is None:
                continue
            trust = int(rel.get("trust") or 50)
            frustration = int(rel.get("frustration") or 0)
            if delta != 0:
                trust = _int_clamp(trust + delta, 0, 100)
                if delta > 0:
                    frustration = _int_clamp(frustration - 1, 0, 100)
                else:
                    frustration = _int_clamp(frustration + 1, 0, 100)
                rel["trust"] = trust
                rel["frustration"] = frustration
                if rel.get("status_label") == "frustrado" and frustration <= 45 and trust >= 45:
                    rel["status_label"] = "neutro"
                updates.append(rel)
        return updates

    def _update_locker_room(self, state: Dict[str, Any], locker: Dict[str, Any]) -> Tuple[Dict[str, Any], List[EmittedEvent]]:
        squad = list(state.get("squad") or [])
        morale_values: List[float] = []
        low_morale = 0
        for p in squad:
            m = p.get("morale")
            if m is None:
                continue
            try:
                m_f = float(m)
            except (TypeError, ValueError):
                continue
            morale_values.append(m_f)
            if m_f < 40:
                low_morale += 1
        morale_avg = sum(morale_values) / len(morale_values) if morale_values else 50.0
        cohesion = _int_clamp(morale_avg, 0, 100)
        prev = int(locker.get("cohesion") or 50)
        locker["cohesion"] = cohesion
        locker["morale_avg"] = round(morale_avg, 1)
        locker["low_morale_count"] = int(low_morale)
        locker["leaders"] = self._pick_leaders(squad)
        locker["factions"] = self._build_factions(squad)

        emitted: List[EmittedEvent] = []
        if cohesion <= 38 and prev > 45:
            emitted.append(
                EmittedEvent(
                    "LOCKER_ROOM_TENSION",
                    {
                        "cohesion": cohesion,
                        "low_morale_count": int(low_morale),
                        "leaders": locker["leaders"],
                        "summary": "O vestiário entrou em estado de tensão e exige gestão de grupo.",
                    },
                )
            )
        if cohesion >= 55 and prev < 45:
            emitted.append(
                EmittedEvent(
                    "LOCKER_ROOM_CALMED",
                    {
                        "cohesion": cohesion,
                        "leaders": locker["leaders"],
                        "summary": "O ambiente interno estabilizou e a confiança no grupo aumentou.",
                    },
                )
            )
        return locker, emitted

    def _finalize_locker_room(
        self,
        locker: Dict[str, Any],
        relation_updates: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if relation_updates:
            trust_values = [int(x.get("trust") or 50) for x in relation_updates if x.get("trust") is not None]
            if trust_values:
                locker["trust_avg"] = round(sum(trust_values) / len(trust_values), 1)
        squad = list(state.get("squad") or [])
        dissatisfied = 0
        for p in squad:
            m = p.get("morale")
            try:
                if m is not None and float(m) < 40:
                    dissatisfied += 1
            except (TypeError, ValueError):
                pass
        locker["dissatisfied_reserves_estimate"] = int(dissatisfied)
        return locker

    def _pick_leaders(self, squad: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for p in squad:
            ov = p.get("overall")
            age = p.get("age")
            if ov is None:
                continue
            try:
                score = float(ov)
            except (TypeError, ValueError):
                continue
            try:
                if age is not None:
                    score += 0.15 * float(age)
            except (TypeError, ValueError):
                pass
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        leaders: List[Dict[str, Any]] = []
        for _score, p in scored[:3]:
            leaders.append({"playerid": int(p.get("playerid")), "name": _player_display_name(p), "overall": p.get("overall")})
        return leaders

    def _build_factions(self, squad: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_nat: Dict[str, int] = {}
        for p in squad:
            nat = p.get("nationality")
            if nat is None:
                continue
            key = str(nat)
            by_nat[key] = by_nat.get(key, 0) + 1
        top = sorted(by_nat.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return [{"tag": f"nacao_{k}", "count": v} for k, v in top if v >= 3]

    def _update_medical(self, state: Dict[str, Any], medical: Dict[str, Any], today: date) -> Tuple[Dict[str, Any], List[EmittedEvent]]:
        prev_fatigue = float(medical.get("fatigue_index") or 35.0)
        squad = list(state.get("squad") or [])
        fitness_values: List[float] = []
        injured = 0
        for p in squad:
            if bool(p.get("is_injured")):
                injured += 1
            f = p.get("fitness")
            if f is None:
                continue
            try:
                fitness_values.append(float(f))
            except (TypeError, ValueError):
                continue
        fitness_avg = sum(fitness_values) / len(fitness_values) if fitness_values else 70.0
        congestion = self._fixture_congestion(state, today)
        fatigue = prev_fatigue + 3.5 * congestion - 0.08 * (fitness_avg - 60)
        fatigue = _clamp(fatigue, 0, 100)
        medical["fatigue_index"] = round(float(fatigue), 1)
        medical["injured_count"] = int(injured)
        medical["fitness_avg"] = round(float(fitness_avg), 1)
        medical["congestion_index"] = int(congestion)

        risk = _int_clamp(fatigue * 0.7 + injured * 2.5, 0, 100)
        prev_risk = int(medical.get("injury_risk_index") or 0)
        medical["injury_risk_index"] = int(risk)
        emitted: List[EmittedEvent] = []
        if risk >= 72 and prev_risk < 72:
            emitted.append(
                EmittedEvent(
                    "MEDICAL_LOAD_WARNING",
                    {
                        "injury_risk_index": int(risk),
                        "fatigue_index": medical["fatigue_index"],
                        "injured_count": int(injured),
                        "summary": "A carga acumulada elevou o risco de lesões. Rotação e gestão de minutos viram prioridade.",
                    },
                )
            )
        if risk <= 55 and prev_risk >= 72:
            emitted.append(
                EmittedEvent(
                    "MEDICAL_LOAD_STABLE",
                    {
                        "injury_risk_index": int(risk),
                        "fatigue_index": medical["fatigue_index"],
                        "summary": "O DM reporta estabilidade na carga e melhor controle de fadiga do elenco.",
                    },
                )
            )
        return medical, emitted

    def _fixture_congestion(self, state: Dict[str, Any], today: date) -> int:
        fixtures = list(state.get("fixtures") or [])
        upcoming = 0
        for fx in fixtures:
            if bool(fx.get("is_completed")):
                continue
            d = _parse_date_raw(fx.get("date_raw"))
            if d is None:
                continue
            if today <= d <= (today + timedelta(days=7)):
                upcoming += 1
        return int(_clamp(upcoming, 0, 5))

    def _update_academy(self, state: Dict[str, Any], academy: Dict[str, Any], today: date) -> Tuple[Dict[str, Any], List[EmittedEvent]]:
        base_seed = academy.get("seed")
        if base_seed is None:
            base_seed = int(hashlib.sha256(str(today).encode("utf-8")).hexdigest()[:8], 16)
            academy["seed"] = base_seed
        last = _parse_iso_date(str(academy.get("last_weekly_update") or ""))
        if last and (today - last).days < 7:
            return academy, []
        rng = random.Random(int(base_seed) ^ int(today.toordinal()))
        prospects = list(academy.get("prospects") or [])
        if not prospects:
            prospects = self._spawn_prospects(state, rng)
        mentors = self._mentor_factor(state)
        changed = False
        breakthrough = None
        for p in prospects:
            ov = int(p.get("overall") or 55)
            pot = int(p.get("potential") or (ov + 8))
            drift = rng.choice([-1, 0, 0, 1, 1, 2])
            drift = int(_clamp(drift + mentors, -1, 3))
            new_ov = _int_clamp(ov + drift, 40, pot)
            if new_ov != ov:
                p["overall"] = new_ov
                changed = True
                if drift >= 2 and (breakthrough is None or new_ov > int(breakthrough.get("overall") or 0)):
                    breakthrough = p
        academy["prospects"] = prospects
        academy["mentorship_factor"] = float(mentors)
        academy["last_weekly_update"] = today.isoformat()
        academy["top_prospect_overall"] = max((int(p.get("overall") or 0) for p in prospects), default=0)
        academy["stagnation_risk"] = _int_clamp(45 - mentors * 12 + rng.randint(-4, 6), 0, 100)
        emitted: List[EmittedEvent] = []
        if breakthrough and changed and int(breakthrough.get("overall") or 0) >= 66:
            emitted.append(
                EmittedEvent(
                    "ACADEMY_BREAKTHROUGH",
                    {
                        "prospect_name": breakthrough.get("name"),
                        "overall": breakthrough.get("overall"),
                        "summary": "A base teve evolução acima da curva e chamou atenção do staff.",
                    },
                )
            )
        return academy, emitted

    def _spawn_prospects(self, state: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
        club = state.get("club") or {}
        club_name = str(club.get("team_name") or "clube")
        count = rng.randint(4, 7)
        archetypes = ["zagueiro", "lateral", "volante", "meia", "ponta", "atacante", "goleiro"]
        prospects: List[Dict[str, Any]] = []
        for i in range(count):
            base = rng.randint(49, 62)
            potential = base + rng.randint(6, 16)
            prospects.append(
                {
                    "id": f"y{i+1}",
                    "name": f"Promessa {club_name} {i+1}",
                    "age": rng.randint(16, 19),
                    "overall": base,
                    "potential": potential,
                    "archetype": rng.choice(archetypes),
                }
            )
        return prospects

    def _mentor_factor(self, state: Dict[str, Any]) -> float:
        squad = list(state.get("squad") or [])
        veterans = 0
        for p in squad:
            try:
                age = int(p.get("age") or 0)
                ov = int(p.get("overall") or 0)
            except (TypeError, ValueError):
                continue
            if age >= 30 and ov >= 80:
                veterans += 1
        return float(_clamp(veterans * 0.15, 0, 0.6))

    def _update_tactical_identity(
        self, outcome: str, coach_profile: Optional[Dict[str, Any]], tactical: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[EmittedEvent]]:
        current = str(tactical.get("identity_label") or "")
        coach_style = str((coach_profile or {}).get("playstyle_label") or "equilibrado")
        if not current:
            current = coach_style
        stability = float(tactical.get("stability") or 55.0)
        drift = 0.0
        if outcome == "win":
            stability += 2.0
            drift -= 0.2
        elif outcome == "loss":
            stability -= 3.0
            drift += 0.6
        stability = _clamp(stability, 0, 100)
        tactical["stability"] = round(stability, 1)
        tactical["coach_style"] = coach_style

        emitted: List[EmittedEvent] = []
        if drift >= 0.5 and stability <= 48:
            next_label = self._shift_identity(current, coach_style)
            if next_label != current:
                tactical["identity_label"] = next_label
                emitted.append(
                    EmittedEvent(
                        "TACTICAL_IDENTITY_SHIFT",
                        {
                            "old_identity": current,
                            "new_identity": next_label,
                            "stability": tactical["stability"],
                            "summary": "A identidade tática sofreu ajuste após sequência de resultados.",
                        },
                    )
                )
        else:
            tactical["identity_label"] = current
        return tactical, emitted

    def _shift_identity(self, current: str, coach_style: str) -> str:
        if coach_style in {"ofensivo", "ambicioso"}:
            return "pressão alta" if current != "pressão alta" else "ofensivo"
        if coach_style in {"pragmático", "contenção"}:
            return "bloco baixo" if current != "bloco baixo" else "pragmático"
        return "equilibrado"

    def _apply_match_finance(
        self, outcome: str, finance: Dict[str, Any], game_date: Optional[date]
    ) -> Tuple[Dict[str, Any], List[EmittedEvent], List[Dict[str, Any]]]:
        cash = float(finance.get("cash_balance") or 0.0)
        win_bonus = float(finance.get("win_bonus") or 45000.0)
        draw_bonus = float(finance.get("draw_bonus") or 15000.0)
        loss_penalty = float(finance.get("loss_penalty") or 0.0)
        ledger: List[Dict[str, Any]] = []
        emitted: List[EmittedEvent] = []
        if game_date is None:
            return finance, emitted, ledger
        period = f"{game_date.year:04d}-{game_date.month:02d}"
        if outcome == "win" and win_bonus != 0:
            cash += win_bonus
            ledger.append({"period": period, "kind": "bonus_resultado", "amount": win_bonus, "description": "Bônus por vitória"})
        elif outcome == "draw" and draw_bonus != 0:
            cash += draw_bonus
            ledger.append({"period": period, "kind": "bonus_resultado", "amount": draw_bonus, "description": "Bônus por empate"})
        elif outcome == "loss" and loss_penalty != 0:
            cash -= abs(loss_penalty)
            ledger.append(
                {"period": period, "kind": "penalidade_resultado", "amount": -abs(loss_penalty), "description": "Penalidade por derrota"}
            )
        finance["cash_balance"] = round(float(cash), 2)
        return finance, emitted, ledger

    def _apply_finance_month_rollover(
        self, finance: Dict[str, Any], old_d: date, new_d: date, state: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[EmittedEvent], List[Dict[str, Any]]]:
        old_period = f"{old_d.year:04d}-{old_d.month:02d}"
        new_period = f"{new_d.year:04d}-{new_d.month:02d}"
        if new_period == old_period:
            return finance, [], []

        squad = list(state.get("squad") or [])
        wage_sum = 0.0
        for p in squad:
            w = p.get("wage")
            if w is None:
                continue
            try:
                wage_sum += float(w)
            except (TypeError, ValueError):
                continue
        wage_bill_monthly = float(finance.get("wage_bill_monthly") or 0.0)
        if wage_bill_monthly <= 0:
            wage_bill_monthly = wage_sum * 4.3
        amort = float(finance.get("amortization_monthly_override") or 0.0)
        bonus = float(finance.get("bonus_targets_monthly") or 0.0)

        cash = float(finance.get("cash_balance") or 0.0)
        cash -= wage_bill_monthly
        cash -= amort
        cash -= bonus
        finance["cash_balance"] = round(float(cash), 2)
        finance["wage_bill_monthly"] = round(float(wage_bill_monthly), 2)
        finance["amortization_monthly"] = round(float(amort), 2)
        finance["bonus_targets_monthly"] = round(float(bonus), 2)

        wage_budget = ((state.get("club") or {}).get("wage_budget"))
        try:
            wage_budget_f = float(wage_budget) if wage_budget is not None else 0.0
        except (TypeError, ValueError):
            wage_budget_f = 0.0
        utilization = (wage_bill_monthly * 12 / wage_budget_f) if wage_budget_f > 0 else 0.0
        finance["wage_utilization"] = round(float(utilization), 3)
        pressure = _int_clamp(utilization * 80 + (abs(cash) / 2_000_000.0) * 10, 0, 100)
        finance["cash_pressure_index"] = int(pressure)

        ledger: List[Dict[str, Any]] = [
            {"period": old_period, "kind": "folha_salarial", "amount": -wage_bill_monthly, "description": "Pagamento de folha"},
        ]
        if amort:
            ledger.append({"period": old_period, "kind": "amortizacao", "amount": -amort, "description": "Amortização de transferências"})
        if bonus:
            ledger.append({"period": old_period, "kind": "bonus_metas", "amount": -bonus, "description": "Bônus por metas"})

        emitted: List[EmittedEvent] = [
            EmittedEvent(
                "FINANCE_MONTHLY_REPORT",
                {
                    "period": old_period,
                    "cash_balance": finance["cash_balance"],
                    "wage_bill_monthly": finance["wage_bill_monthly"],
                    "amortization_monthly": finance["amortization_monthly"],
                    "cash_pressure_index": finance["cash_pressure_index"],
                    "summary": "Fechamento mensal consolidado com impacto de folha e compromissos do elenco.",
                },
            )
        ]
        if pressure >= 75:
            emitted.append(
                EmittedEvent(
                    "FINANCE_CASH_PRESSURE",
                    {
                        "period": old_period,
                        "cash_pressure_index": finance["cash_pressure_index"],
                        "summary": "A pressão de caixa subiu. A diretoria deve exigir disciplina em renovações e contratações.",
                    },
                )
            )
        finance["last_closed_period"] = old_period
        return finance, emitted, ledger

    def _market_context_from_offer(
        self,
        payload: Dict[str, Any],
        state: Dict[str, Any],
        coach_profile: Optional[Dict[str, Any]],
        finance: Dict[str, Any],
        locker: Dict[str, Any],
    ) -> List[EmittedEvent]:
        player_name = str(payload.get("player_name") or "jogador do elenco")
        offer_amount = payload.get("offer_amount")
        style = str((coach_profile or {}).get("playstyle_label") or "equilibrado")
        pressure = int(finance.get("cash_pressure_index") or 0)
        cohesion = int(locker.get("cohesion") or 50)
        angle = "planejamento" if pressure < 60 else "necessidade de caixa"
        if cohesion <= 40:
            angle = "troca de ambiente"
        return [
            EmittedEvent(
                "MARKET_AGENT_NARRATIVE",
                {
                    "player_name": player_name,
                    "offer_amount": offer_amount,
                    "style": style,
                    "angle": angle,
                    "summary": "Agentes alimentam narrativas para influenciar preço e timing da negociação.",
                },
            )
        ]
