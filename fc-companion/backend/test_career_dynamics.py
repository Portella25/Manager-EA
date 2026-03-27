from __future__ import annotations

import unittest

from career_dynamics_engine import CareerDynamicsEngine


class CareerDynamicsEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CareerDynamicsEngine()

    def test_month_rollover_creates_monthly_report(self) -> None:
        state = {
            "meta": {"game_date": {"year": 2026, "month": 2, "day": 1}},
            "club": {"transfer_budget": 1_000_000, "wage_budget": 10_000_000},
            "squad": [
                {"playerid": 1, "firstname": "A", "lastname": "B", "wage": 50_000, "morale": 60, "overall": 80, "age": 28},
                {"playerid": 2, "firstname": "C", "lastname": "D", "wage": 30_000, "morale": 55, "overall": 78, "age": 25},
            ],
            "fixtures": [],
        }
        management_state = {"locker_room": {}, "finance": {}, "tactical": {}, "academy": {}, "medical": {}}
        payload = {"old_date": "2026-01-31", "new_date": "2026-02-01"}
        next_mgmt, _relations, ledger, emitted = self.engine.on_event(
            "DATE_ADVANCED", payload, state, {"playstyle_label": "equilibrado"}, management_state, []
        )
        self.assertTrue(any(e.event_type == "FINANCE_MONTHLY_REPORT" for e in emitted))
        self.assertTrue(any(x.get("kind") == "folha_salarial" for x in ledger))
        self.assertIn("cash_pressure_index", next_mgmt["finance"])

    def test_morale_drop_can_mark_frustrated(self) -> None:
        state = {
            "meta": {"game_date": {"year": 2026, "month": 3, "day": 10}},
            "squad": [{"playerid": 10, "firstname": "Joao", "lastname": "Silva", "morale": 30, "overall": 82, "age": 27}],
        }
        management_state = {"locker_room": {}, "finance": {}, "tactical": {}, "academy": {}, "medical": {}}
        existing_relations = [
            {
                "playerid": 10,
                "player_name": "Joao Silva",
                "trust": 40,
                "role_label": "rotacao",
                "status_label": "neutro",
                "frustration": 0,
                "notes": {},
            }
        ]
        payload = {"player_name": "Joao Silva", "old_morale": 55, "new_morale": 30}
        _next_mgmt, rel_updates, _ledger, _emitted = self.engine.on_event(
            "MORALE_DROP", payload, state, {"playstyle_label": "equilibrado"}, management_state, existing_relations
        )
        updated = next((r for r in rel_updates if int(r.get("playerid") or -1) == 10), None)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status_label"], "frustrado")

    def test_tactical_shift_emits_event_when_unstable(self) -> None:
        state = {"meta": {"game_date": {"year": 2026, "month": 4, "day": 2}}, "squad": []}
        management_state = {"locker_room": {}, "finance": {}, "tactical": {"stability": 40, "identity_label": "equilibrado"}, "academy": {}, "medical": {}}
        payload = {"home_score": 0, "away_score": 2}
        _next_mgmt, _rel_updates, _ledger, emitted = self.engine.on_event(
            "MATCH_COMPLETED", payload, state, {"playstyle_label": "ofensivo"}, management_state, []
        )
        self.assertTrue(any(e.event_type == "TACTICAL_IDENTITY_SHIFT" for e in emitted))

    def test_offer_emits_agent_narrative(self) -> None:
        state = {"meta": {"game_date": {"year": 2026, "month": 5, "day": 15}}, "squad": [], "club": {"transfer_budget": 500_000}}
        management_state = {"locker_room": {"cohesion": 60}, "finance": {}, "tactical": {}, "academy": {}, "medical": {}}
        payload = {"player_name": "Atacante X", "offer_amount": 12_000_000}
        _next_mgmt, _rel_updates, _ledger, emitted = self.engine.on_event(
            "TRANSFER_OFFER_RECEIVED", payload, state, {"playstyle_label": "equilibrado"}, management_state, []
        )
        self.assertTrue(any(e.event_type == "MARKET_AGENT_NARRATIVE" for e in emitted))


if __name__ == "__main__":
    unittest.main()

