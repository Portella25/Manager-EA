from __future__ import annotations

from typing import Any, Dict, List


class AchievementsEngine:
    def unlocks_from_context(
        self,
        payoff: Dict[str, Any],
        legacy_profile: Dict[str, Any],
        hall_of_fame_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        unlocks: List[Dict[str, Any]] = []
        score = int(payoff.get("final_score") or 0)
        grade = str(payoff.get("grade") or "E")
        legacy_rank = str(legacy_profile.get("legacy_rank") or "em_formacao")
        hof_tier = str(hall_of_fame_profile.get("tier") or "aspirante")

        if grade in {"A+", "A"} or score >= 85:
            unlocks.append(
                {
                    "code": "SEASON_MASTER",
                    "title": "Mestre da Temporada",
                    "description": "Concluiu temporada com desempenho de elite.",
                    "rarity": "epic",
                    "points": 35,
                    "source": "season_payoff",
                }
            )
        if legacy_rank in {"dinastia", "consolidado"}:
            unlocks.append(
                {
                    "code": "LEGACY_ARCHITECT",
                    "title": "Arquiteto do Legado",
                    "description": "Construiu reputação histórica consistente em múltiplas temporadas.",
                    "rarity": "legendary",
                    "points": 50,
                    "source": "legacy_profile",
                }
            )
        if hof_tier in {"imortal", "lenda"}:
            unlocks.append(
                {
                    "code": "HALL_IMMORTAL",
                    "title": "Imortal do Hall",
                    "description": "Atingiu o topo do Hall da Fama com impacto histórico.",
                    "rarity": "legendary",
                    "points": 60,
                    "source": "hall_of_fame",
                }
            )
        return unlocks

    def build_profile(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(entries)
        total_points = sum(int(e.get("points", 0)) for e in entries)
        level = self._level(total_points)
        top = entries[0]["title"] if entries else None
        return {
            "total_achievements": total,
            "total_points": total_points,
            "career_level": level,
            "top_achievement": top,
        }

    def _level(self, total_points: int) -> str:
        if total_points >= 240:
            return "mitico"
        if total_points >= 160:
            return "lendario"
        if total_points >= 100:
            return "elite"
        if total_points >= 50:
            return "veterano"
        if total_points > 0:
            return "promissor"
        return "iniciante"
