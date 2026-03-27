from __future__ import annotations

from typing import Any, Dict, List


class LegacyEngine:
    def build_profile(self, payoffs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not payoffs:
            return {
                "seasons_count": 0,
                "average_score": 0.0,
                "best_grade": "-",
                "legacy_rank": "em_formacao",
                "narrative_summary": "Sem histórico suficiente para avaliar legado.",
            }
        seasons_count = len(payoffs)
        avg = sum(float(p.get("final_score", 0)) for p in payoffs) / seasons_count
        best_grade = min((str(p.get("grade", "E")) for p in payoffs), key=self._grade_order)
        legacy_rank = self._legacy_rank(avg, best_grade, seasons_count)
        narrative_summary = self._summary(avg, best_grade, seasons_count, legacy_rank)
        return {
            "seasons_count": seasons_count,
            "average_score": round(avg, 2),
            "best_grade": best_grade,
            "legacy_rank": legacy_rank,
            "narrative_summary": narrative_summary,
        }

    def _grade_order(self, grade: str) -> int:
        order = {"A+": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
        return order.get(grade, 99)

    def _legacy_rank(self, avg: float, best_grade: str, seasons_count: int) -> str:
        if seasons_count >= 3 and avg >= 80 and best_grade in {"A+", "A"}:
            return "dinastia"
        if seasons_count >= 2 and avg >= 70:
            return "consolidado"
        if avg >= 60:
            return "promissor"
        if avg >= 45:
            return "instavel"
        return "em_risco"

    def _summary(self, avg: float, best_grade: str, seasons_count: int, legacy_rank: str) -> str:
        return (
            f"Legado com {seasons_count} temporada(s), média {avg:.1f}, melhor nota {best_grade} "
            f"e classificação histórica '{legacy_rank}'."
        )
