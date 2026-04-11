from __future__ import annotations

from typing import Any, Dict, Tuple


class ReputationEngine:
    def event_impact(self, event_type: str, payload: Dict[str, Any]) -> Tuple[int, int, str]:
        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
            if event_type == "MATCH_COMPLETED":
                my_score = payload.get("my_score")
                opp_score = payload.get("opp_score")
                if not isinstance(my_score, (int, float)) or not isinstance(opp_score, (int, float)):
                    home_score = payload.get("home_score")
                    away_score = payload.get("away_score")
                    try:
                        user_team_id = int(payload.get("user_team_id") or 0)
                    except (TypeError, ValueError):
                        user_team_id = 0
                    try:
                        home_team_id = int(payload.get("home_team_id") or 0)
                    except (TypeError, ValueError):
                        home_team_id = 0
                    try:
                        away_team_id = int(payload.get("away_team_id") or 0)
                    except (TypeError, ValueError):
                        away_team_id = 0
                    if isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)) and user_team_id > 0:
                        if user_team_id == home_team_id:
                            my_score = home_score
                            opp_score = away_score
                        elif user_team_id == away_team_id:
                            my_score = away_score
                            opp_score = home_score
            else:
                my_score = payload.get("my_score")
                opp_score = payload.get("opp_score")
                
            if isinstance(my_score, (int, float)) and isinstance(opp_score, (int, float)):
                diff = int(my_score) - int(opp_score)
                if diff >= 2:
                    return 4, 5, "ofensivo"
                if diff == 1:
                    return 2, 3, "equilibrado"
                if diff == 0:
                    return -1, -2, "pragmático"
                if diff <= -2:
                    return -5, -6, "instável"
                return -3, -4, "pressionado"
            return 0, 0, "equilibrado"
        if event_type in ("PLAYER_INJURED", "player_injured"):
            severity = str(payload.get("severity") or "").lower()
            if severity == "grave" or severity == "8":
                return -3, -5, "pressionado"
            if severity == "moderada" or severity == "5":
                return -2, -3, "pragmático"
            return -1, -1, "pragmático"
        if event_type == "PLAYER_RECOVERED":
            return 2, 3, "resiliente"
        if event_type == "TRANSFER_OFFER_RECEIVED":
            amount = payload.get("offer_amount")
            if isinstance(amount, (int, float)) and amount >= 10000000:
                return 2, 2, "estrategista"
            return 1, 1, "estrategista"
        if event_type in ("BUDGET_CHANGED", "board_budget_cut"):
            if event_type == "BUDGET_CHANGED":
                diff = payload.get("difference")
            else:
                diff = payload.get("new_budget", 0) - payload.get("old_budget", 0)
                
            if isinstance(diff, (int, float)):
                if diff > 0:
                    return 2, 2, "ambicioso"
                if diff < 0:
                    return -2, -2, "contenção"
            return 0, 0, "equilibrado"
        if event_type == "SEASON_CHANGED":
            return 3, 2, "visionário"
        if event_type == "MORALE_DROP":
            return -3, -4, "pressionado"
        if event_type == "DATE_ADVANCED":
            return 0, 0, "equilibrado"
        return 0, 0, "equilibrado"

    def normalize_score(self, score: int) -> int:
        return max(0, min(100, int(score)))

    def reputation_label(self, score: int) -> str:
        if score >= 80:
            return "Elite"
        if score >= 65:
            return "Respeitado"
        if score >= 50:
            return "Estável"
        if score >= 35:
            return "Questionado"
        return "Em risco"

    def fan_label(self, score: int) -> str:
        if score >= 80:
            return "Euforia"
        if score >= 65:
            return "Apoio"
        if score >= 50:
            return "Neutro"
        if score >= 35:
            return "Desconfiança"
        return "Hostil"

    def analyze_press_answer(self, answer: str) -> Tuple[str, int, int]:
        text = (answer or "").strip().lower()
        positive = [
            "confiante",
            "confio",
            "acredito",
            "preparado",
            "preparados",
            "orgulho",
            "evolução",
            "trabalho",
            "foco",
            "responsabilidade",
            "torcida",
        ]
        negative = ["culpa", "desastre", "fracasso", "inaceitável", "crise", "ruim"]
        evasive = ["sem comentários", "prefiro não", "não vou falar", "assunto interno"]
        pos_score = sum(1 for token in positive if token in text)
        neg_score = sum(1 for token in negative if token in text)
        evasive_score = sum(1 for token in evasive if token in text)
        if evasive_score > 0:
            return "evasivo", -2, -1
        if neg_score > pos_score:
            return "agressivo", -3, -3
        if pos_score > 0:
            return "confiante", 3, 2
        return "neutro", 0, 0
