from __future__ import annotations

from typing import Any, Dict


class MarketEngine:
    def should_generate(self, event_type: str) -> bool:
        return event_type in {
            "MATCH_COMPLETED",
            "match_won",
            "match_lost",
            "match_drawn",
            "BUDGET_CHANGED",
            "board_budget_cut",
            "TRANSFER_OFFER_RECEIVED",
            "BOARD_ULTIMATUM_CREATED",
            "BOARD_ULTIMATUM_UPDATED",
        }

    def build_rumor(
        self,
        event_type: str,
        payload: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        style = str(profile.get("playstyle_label") or "equilibrado")
        rep = int(profile.get("reputation_score") or 50)
        confidence = self._confidence(event_type, rep)
        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
            headline = "Bastidores: clube monitora mercado após resultado recente"
            content = (
                f"Fontes locais indicam que a comissão de perfil {style} avalia reforços imediatos. "
                "A diretoria quer nomes capazes de responder ao momento competitivo da temporada."
            )
            target = self._target_by_style(style)
        elif event_type in ("BUDGET_CHANGED", "board_budget_cut"):
            headline = "Ajuste financeiro reacende conversas na janela"
            content = (
                f"Com mudanças no caixa, o staff alinhado ao perfil {style} volta a mapear oportunidades. "
                "Há expectativa de movimentação em posições de construção e intensidade."
            )
            target = "meia criativo"
        elif event_type == "TRANSFER_OFFER_RECEIVED":
            player_name = payload.get("player_name") or "jogador do elenco"
            headline = f"Rumor: saída de {player_name} pode abrir espaço no planejamento"
            content = (
                f"A proposta por {player_name} fez o clube acelerar planos de reposição. "
                "Intermediários relatam consultas por alternativas de impacto imediato."
            )
            target = "substituto direto"
        elif event_type == "BOARD_ULTIMATUM_CREATED":
            headline = "Pressão da presidência altera prioridades de mercado"
            content = (
                "Após o ultimato, dirigentes admitem que reforços de pronta resposta ganharam prioridade. "
                "A janela passa a ser tratada como peça-chave para reação esportiva."
            )
            target = "jogador experiente"
        else:
            headline = "Movimentações discretas no mercado"
            content = (
                "Observadores apontam contatos preliminares do clube com agentes e departamentos de scout. "
                "A tendência é ajustar o elenco ao contexto competitivo atual."
            )
            target = self._target_by_style(style)
        return {
            "headline": headline,
            "content": content,
            "confidence_level": confidence,
            "target_profile": target,
        }

    def _confidence(self, event_type: str, reputation_score: int) -> int:
        base = {
            "MATCH_COMPLETED": 62,
            "match_won": 65,
            "match_lost": 75,
            "match_drawn": 60,
            "BUDGET_CHANGED": 78,
            "board_budget_cut": 82,
            "TRANSFER_OFFER_RECEIVED": 84,
            "BOARD_ULTIMATUM_CREATED": 86,
            "BOARD_ULTIMATUM_UPDATED": 74,
        }.get(event_type, 60)
        adj = 6 if reputation_score >= 65 else (-6 if reputation_score <= 35 else 0)
        return max(30, min(95, base + adj))

    def _target_by_style(self, style: str) -> str:
        if style in {"ofensivo", "ambicioso"}:
            return "meia criativo"
        if style in {"pragmático", "contenção"}:
            return "volante marcador"
        if style in {"instável", "pressionado"}:
            return "zagueiro líder"
        return "peça versátil"
