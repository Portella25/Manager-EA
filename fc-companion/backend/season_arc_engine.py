from __future__ import annotations

from typing import Any, Dict


class SeasonArcEngine:
    def should_start(self, event_type: str) -> bool:
        return event_type in {"SEASON_CHANGED", "MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"}

    def build_start(self, profile: Dict[str, Any], season_label: str) -> Dict[str, Any]:
        style = str(profile.get("playstyle_label") or "equilibrado")
        rep = int(profile.get("reputation_score") or 50)
        if style in {"ofensivo", "ambicioso"}:
            theme = "ascensão ofensiva"
        elif style in {"pragmático", "contenção"}:
            theme = "resiliência tática"
        else:
            theme = "equilíbrio competitivo"
        title = f"Arco da temporada {season_label}"
        summary = f"O clube inicia um arco de {theme}, com decisões acumuladas moldando o desfecho da época."
        max_milestones = 5 if rep >= 40 else 4
        return {"title": title, "theme": theme, "summary": summary, "max_milestones": max_milestones}

    def memory_from_event(self, event_type: str, payload: Dict[str, Any]) -> str:
        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
            if event_type == "MATCH_COMPLETED":
                score_str = f"{payload.get('home_score')} x {payload.get('away_score')}"
            else:
                is_home = payload.get("is_home", True)
                my_score = payload.get("my_score")
                opp_score = payload.get("opp_score")
                score_str = f"{my_score} x {opp_score}" if is_home else f"{opp_score} x {my_score}"
            return f"Resultado registrado: {score_str}."
        if event_type == "TRANSFER_OFFER_RECEIVED":
            return f"Mercado acionado por proposta envolvendo {payload.get('player_name')}."
        if event_type == "BOARD_ULTIMATUM_CREATED":
            return "Diretoria aumentou pressão com ultimato de curto prazo."
        if event_type == "CRISIS_STARTED":
            return "Arco atravessou momento de crise institucional."
        return f"Evento relevante: {event_type}."

    def progress(self, arc: Dict[str, Any], profile: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        if event_type not in {"MATCH_COMPLETED", "match_won", "match_lost", "match_drawn", "DATE_ADVANCED", "BOARD_ULTIMATUM_UPDATED", "CRISIS_UPDATED"}:
            return {"status": arc.get("status", "active"), "milestone_increment": 0, "message": "Arco sem avanço neste evento."}
        current = int(arc.get("current_milestone") or 1)
        max_steps = int(arc.get("max_milestones") or 5)
        next_step = current + 1
        rep = int(profile.get("reputation_score") or 50)
        fan = int(profile.get("fan_sentiment_score") or 50)
        if next_step >= max_steps:
            if rep >= 50 and fan >= 50:
                return {"status": "resolved", "milestone_increment": 1, "message": "Arco sazonal concluído com desfecho positivo."}
            return {"status": "failed", "milestone_increment": 1, "message": "Arco sazonal encerra com desfecho adverso."}
        return {"status": "active", "milestone_increment": 1, "message": f"Arco sazonal avançou para etapa {next_step}/{max_steps}."}
