from __future__ import annotations

from typing import Any, Dict


class CrisisEngine:
    def should_start(self, profile: Dict[str, Any], event_type: str, board_updates_count: int) -> bool:
        rep = int(profile.get("reputation_score") or 50)
        fan = int(profile.get("fan_sentiment_score") or 50)
        if board_updates_count > 0:
            return True
        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn") and (rep <= 35 or fan <= 35):
            return True
        if event_type == "MORALE_DROP" and (rep <= 45 or fan <= 45):
            return True
        return False

    def start_payload(self, profile: Dict[str, Any], trigger_type: str) -> Dict[str, Any]:
        rep = int(profile.get("reputation_score") or 50)
        fan = int(profile.get("fan_sentiment_score") or 50)
        severity = "moderada"
        if rep <= 30 or fan <= 30:
            severity = "grave"
        summary = "Crise em curso: resultados e ambiente interno exigem reação imediata."
        if trigger_type == "BOARD":
            summary = "Crise institucional: diretoria elevou o nível de pressão sobre o comando técnico."
        return {"severity": severity, "summary": summary, "max_steps": 4}

    def progress(self, arc: Dict[str, Any], profile: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        rep = int(profile.get("reputation_score") or 50)
        fan = int(profile.get("fan_sentiment_score") or 50)
        current = int(arc.get("current_step") or 1)
        max_steps = int(arc.get("max_steps") or 4)
        next_step = current + 1
        if rep >= 60 and fan >= 60:
            return {
                "status": "resolved",
                "message": "Sinais de recuperação consolidam a saída da crise.",
                "step_increment": 1,
            }
        if next_step >= max_steps and (rep < 45 or fan < 45):
            return {
                "status": "collapsed",
                "message": "A crise atingiu nível crítico e a pressão por ruptura aumentou.",
                "step_increment": 1,
            }
        if event_type in {"MATCH_COMPLETED", "match_won", "match_lost", "match_drawn", "DATE_ADVANCED", "BOARD_ULTIMATUM_UPDATED"}:
            return {
                "status": "active",
                "message": f"Crise em monitoramento: etapa {next_step}/{max_steps}.",
                "step_increment": 1,
            }
        return {
            "status": "active",
            "message": "Crise permanece ativa sem mudança estrutural.",
            "step_increment": 0,
        }
