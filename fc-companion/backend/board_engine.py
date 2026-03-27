from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class BoardEngine:
    def extract_result(self, payload: Dict[str, Any], managed_side: str = "home") -> Tuple[str, int]:
        my_score = payload.get("my_score")
        opp_score = payload.get("opp_score")
        if isinstance(my_score, (int, float)) and isinstance(opp_score, (int, float)):
            diff = int(my_score) - int(opp_score)
            if diff > 0:
                return "win", 3
            if diff == 0:
                return "draw", 1
            return "loss", 0
        home_score = payload.get("home_score")
        away_score = payload.get("away_score")
        if not isinstance(home_score, (int, float)) or not isinstance(away_score, (int, float)):
            return "unknown", 0
        diff = int(home_score) - int(away_score)
        if managed_side == "away":
            diff = -diff
        if diff > 0:
            return "win", 3
        if diff == 0:
            return "draw", 1
        return "loss", 0

    def should_trigger_ultimatum(self, recent_outcomes: List[str]) -> bool:
        if len(recent_outcomes) < 4:
            return False
        last_five = recent_outcomes[:5]
        losses = sum(1 for x in last_five if x == "loss")
        wins = sum(1 for x in last_five if x == "win")
        return losses >= 3 and wins == 0

    def build_ultimatum(self) -> Dict[str, Any]:
        return {
            "title": "Ultimato da Presidência",
            "description": "Conquiste ao menos 4 pontos nos próximos 2 jogos para manter estabilidade no cargo.",
            "required_points": 4,
            "matches_remaining": 2,
        }

    def resolve_status(self, required_points: int, current_points: int, matches_remaining: int) -> str:
        if current_points >= required_points:
            return "completed"
        if matches_remaining <= 0:
            return "failed"
        return "active"

    def build_progress_message(
        self,
        status: str,
        current_points: int,
        required_points: int,
        matches_remaining: int,
    ) -> str:
        if status == "completed":
            return "Objetivo cumprido e confiança da diretoria restaurada."
        if status == "failed":
            return "Objetivo não cumprido. A pressão por mudanças aumenta internamente."
        return (
            f"Objetivo em andamento: {current_points}/{required_points} pontos. "
            f"Restam {matches_remaining} jogo(s)."
        )
