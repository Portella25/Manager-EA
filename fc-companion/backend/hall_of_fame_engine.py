from __future__ import annotations

from typing import Any, Dict, List, Optional


class HallOfFameEngine:
    def build_entry_from_payoff(self, payoff: Dict[str, Any]) -> Dict[str, Any]:
        grade = str(payoff.get("grade") or "E")
        score = int(payoff.get("final_score") or 0)
        title = str(payoff.get("title") or "Epilogo de temporada")
        category = "season_epilogue"
        description = f"Temporada encerrada com nota {grade} e score {score}."
        impact = self._impact_from_grade(grade, score)
        return {
            "category": category,
            "title": title,
            "description": description,
            "score_impact": impact,
            "source": "season_payoff",
        }

    def build_profile(self, entries: List[Dict[str, Any]], legacy_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        total_entries = len(entries)
        impact_sum = sum(int(e.get("score_impact", 0)) for e in entries)
        legacy_avg = float((legacy_profile or {}).get("average_score", 0))
        legacy_rank = str((legacy_profile or {}).get("legacy_rank", "em_formacao"))
        legacy_bonus = {
            "dinastia": 20,
            "consolidado": 12,
            "promissor": 6,
            "instavel": 2,
            "em_risco": -4,
            "em_formacao": 0,
        }.get(legacy_rank, 0)
        legacy_score = max(0.0, min(100.0, (legacy_avg * 0.7) + (impact_sum * 0.6) + legacy_bonus))
        tier = self._tier(legacy_score)
        highlight = entries[0]["title"] if entries else None
        return {
            "total_entries": total_entries,
            "legacy_score": round(legacy_score, 2),
            "tier": tier,
            "highlight_title": highlight,
        }

    def _impact_from_grade(self, grade: str, score: int) -> int:
        base = {"A+": 12, "A": 10, "B": 7, "C": 4, "D": 1, "E": -3}.get(grade, 0)
        modifier = 2 if score >= 80 else (-2 if score <= 40 else 0)
        return base + modifier

    def _tier(self, legacy_score: float) -> str:
        if legacy_score >= 85:
            return "imortal"
        if legacy_score >= 72:
            return "lenda"
        if legacy_score >= 58:
            return "idolo"
        if legacy_score >= 45:
            return "relevante"
        return "aspirante"
