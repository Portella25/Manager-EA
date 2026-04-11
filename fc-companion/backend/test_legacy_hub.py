import unittest

from legacy_hub import (
    _calc_aproveitamento,
    _calc_records,
    _calc_streaks,
    _merge_match_sources,
    _matches_from_state_fixtures,
)


class TestLegacyHub(unittest.TestCase):
    def test_aproveitamento_points_and_pct(self) -> None:
        matches = [
            {"outcome": "W", "points": 3, "occurred_at": "2026-01-01", "my_score": 2, "opp_score": 0, "goal_diff": 2},
            {"outcome": "D", "points": 1, "occurred_at": "2026-01-02", "my_score": 1, "opp_score": 1, "goal_diff": 0},
            {"outcome": "L", "points": 0, "occurred_at": "2026-01-03", "my_score": 0, "opp_score": 2, "goal_diff": -2},
        ]
        res = _calc_aproveitamento(matches)
        self.assertEqual(res["games"], 3)
        self.assertEqual(res["wins"], 1)
        self.assertEqual(res["draws"], 1)
        self.assertEqual(res["losses"], 1)
        self.assertEqual(res["points"], 4)
        self.assertEqual(res["points_possible"], 9)
        self.assertAlmostEqual(res["pct"], round((4 / 9) * 100, 2))

    def test_records_biggest_win_and_worst_loss(self) -> None:
        matches = [
            {
                "occurred_at": "2026-01-01",
                "my_score": 4,
                "opp_score": 0,
                "goal_diff": 4,
                "opponent_name": "Rival A",
                "competition_name": "Liga",
                "date_raw": "2026-01-01",
            },
            {
                "occurred_at": "2026-01-02",
                "my_score": 0,
                "opp_score": 3,
                "goal_diff": -3,
                "opponent_name": "Rival B",
                "competition_name": "Copa",
                "date_raw": "2026-01-02",
            },
        ]
        records = _calc_records(matches)
        self.assertEqual(records["biggest_win"]["scoreline"], "4 x 0")
        self.assertEqual(records["biggest_win"]["goal_diff"], 4)
        self.assertEqual(records["worst_loss"]["scoreline"], "0 x 3")
        self.assertEqual(records["worst_loss"]["goal_diff"], -3)

    def test_streaks(self) -> None:
        matches = [
            {"outcome": "W", "occurred_at": "2026-01-01"},
            {"outcome": "W", "occurred_at": "2026-01-02"},
            {"outcome": "D", "occurred_at": "2026-01-03"},
            {"outcome": "W", "occurred_at": "2026-01-04"},
        ]
        streaks = _calc_streaks(matches)
        self.assertEqual(streaks["longest_win_streak"]["count"], 2)
        self.assertEqual(streaks["current_win_streak"]["count"], 1)

    def test_merge_matches_state_and_db_without_duplicate(self) -> None:
        state = {
            "club": {"team_id": 10, "team_name": "Botafogo"},
            "fixtures": [
                {
                    "is_completed": True,
                    "home_team_id": 10,
                    "away_team_id": 20,
                    "home_team_name": "Botafogo",
                    "away_team_name": "Flamengo",
                    "home_score": 2,
                    "away_score": 1,
                    "date_raw": "20260315",
                    "competition_id": 1663,
                    "competition_name": "Brasileirão",
                }
            ],
        }
        rows_state = _matches_from_state_fixtures(state)
        self.assertEqual(len(rows_state), 1)
        self.assertEqual(rows_state[0]["outcome"], "W")
        db_dup = [
            {
                "occurred_at": "2026-03-15T12:00:00",
                "date_raw": "20260315",
                "competition_id": 1663,
                "home_team_id": 10,
                "away_team_id": 20,
                "my_score": 2,
                "opp_score": 1,
                "outcome": "W",
                "points": 3,
                "goal_diff": 1,
            }
        ]
        merged, src = _merge_match_sources(db_dup, rows_state)
        self.assertEqual(src, "merged")
        self.assertEqual(len(merged), 1)

    def test_merge_uses_state_when_db_empty(self) -> None:
        state = {
            "club": {"team_id": 1, "team_name": "A"},
            "fixtures": [
                {
                    "is_completed": True,
                    "home_team_id": 2,
                    "away_team_id": 1,
                    "home_score": 0,
                    "away_score": 0,
                    "date_raw": "20260101",
                    "competition_id": 1,
                    "home_team_name": "B",
                    "away_team_name": "A",
                }
            ],
        }
        rows = _matches_from_state_fixtures(state)
        merged, src = _merge_match_sources([], rows)
        self.assertEqual(src, "state")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["outcome"], "D")


if __name__ == "__main__":
    unittest.main()

