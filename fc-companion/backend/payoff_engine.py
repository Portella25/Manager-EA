from __future__ import annotations

from typing import Any, Dict, List


class PayoffEngine:
    def build(self, arc: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        memories: List[Dict[str, Any]] = arc.get("memories", [])
        rep = int(profile.get("reputation_score") or 50)
        fan = int(profile.get("fan_sentiment_score") or 50)
        milestone_ratio = 0.0
        max_m = int(arc.get("max_milestones") or 1)
        cur_m = int(arc.get("current_milestone") or 1)
        if max_m > 0:
            milestone_ratio = min(1.0, max(0.0, cur_m / max_m))
        base = int((rep * 0.4) + (fan * 0.35) + (milestone_ratio * 100 * 0.2) + (min(len(memories), 20) * 0.25))
        status = str(arc.get("status") or "active")
        if status == "resolved":
            base += 8
        elif status == "failed":
            base -= 8
        final_score = max(0, min(100, base))
        grade = self._grade(final_score)
        title = self._title(grade, arc)
        epilogue = self._epilogue(grade, arc, rep, fan, len(memories))
        factors = {
            "reputation_score": rep,
            "fan_sentiment_score": fan,
            "milestones": {"current": cur_m, "max": max_m},
            "memories_count": len(memories),
            "arc_status": status,
        }
        return {
            "final_score": final_score,
            "grade": grade,
            "title": title,
            "epilogue": epilogue,
            "factors": factors,
        }

    def _grade(self, score: int) -> str:
        if score >= 85:
            return "A+"
        if score >= 75:
            return "A"
        if score >= 65:
            return "B"
        if score >= 55:
            return "C"
        if score >= 40:
            return "D"
        return "E"

    def _title(self, grade: str, arc: Dict[str, Any]) -> str:
        arc_title = arc.get("title") or "Arco de Temporada"
        return f"Epilogo {grade} — {arc_title}"

    def _epilogue(self, grade: str, arc: Dict[str, Any], rep: int, fan: int, memories_count: int) -> str:
        theme = arc.get("theme") or "equilíbrio competitivo"
        if grade in {"A+", "A"}:
            return (
                f"A temporada fechou com nota {grade}. O tema '{theme}' virou marca da gestão, "
                f"com reputação em {rep}, apoio da torcida em {fan} e {memories_count} decisões relevantes acumuladas."
            )
        if grade in {"B", "C"}:
            return (
                f"O ciclo terminou com nota {grade}. Houve avanços e oscilações no eixo '{theme}', "
                f"com sinais de estabilidade parcial para o próximo ano esportivo."
            )
        return (
            f"O arco encerra com nota {grade}, deixando lições duras no tema '{theme}'. "
            f"A próxima temporada exigirá reconstrução de confiança e respostas consistentes."
        )
