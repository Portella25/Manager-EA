from __future__ import annotations

from typing import Any, Dict, List


class MetaAchievementsEngine:
    def unlocks_from_achievements(self, achievements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        codes = {str(a.get("code")) for a in achievements}
        unlocks: List[Dict[str, Any]] = []
        if {"SEASON_MASTER", "LEGACY_ARCHITECT"}.issubset(codes):
            unlocks.append(
                {
                    "code": "META_DYNASTY_FORGE",
                    "title": "Forjador de Dinastias",
                    "description": "Combinou excelência sazonal e construção de legado.",
                    "collection_tag": "dynasty",
                    "points": 90,
                }
            )
        if {"SEASON_MASTER", "HALL_IMMORTAL"}.issubset(codes):
            unlocks.append(
                {
                    "code": "META_ICONIC_ERA",
                    "title": "Era Icônica",
                    "description": "Consolidou temporada épica com presença histórica no Hall.",
                    "collection_tag": "iconic",
                    "points": 110,
                }
            )
        if {"LEGACY_ARCHITECT", "HALL_IMMORTAL"}.issubset(codes):
            unlocks.append(
                {
                    "code": "META_HISTORICAL_TRINITY",
                    "title": "Trindade Histórica",
                    "description": "Alcançou um marco raro de domínio em legado e Hall da Fama.",
                    "collection_tag": "legend",
                    "points": 120,
                }
            )
        return unlocks

    def build_profile(self, meta_achievements: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_meta = len(meta_achievements)
        points = sum(int(x.get("points", 0)) for x in meta_achievements)
        progress: Dict[str, int] = {}
        for item in meta_achievements:
            tag = str(item.get("collection_tag") or "general")
            progress[tag] = progress.get(tag, 0) + 1
        prestige = self._prestige(points, total_meta)
        return {
            "total_meta": total_meta,
            "collection_progress": progress,
            "prestige_level": prestige,
        }

    def _prestige(self, points: int, total_meta: int) -> str:
        if points >= 250 or total_meta >= 3:
            return "platinum"
        if points >= 140:
            return "gold"
        if points >= 70:
            return "silver"
        return "bronze"
