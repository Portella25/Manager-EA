from __future__ import annotations

from typing import Any, Dict, List


class EditorialEngine:
    def should_generate(self, event_type: str) -> bool:
        return event_type in {
            "MATCH_COMPLETED",
            "match_won",
            "match_lost",
            "match_drawn",
            "DATE_ADVANCED",
            "BOARD_ULTIMATUM_CREATED",
            "BOARD_ULTIMATUM_UPDATED",
            "TRANSFER_OFFER_RECEIVED",
        }

    def build_entries(self, event_type: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        style = str(profile.get("playstyle_label") or "equilibrado")
        if event_type in ("MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"):
            if event_type == "MATCH_COMPLETED":
                score_str = f"{payload.get('home_score')} x {payload.get('away_score')}"
            else:
                is_home = payload.get("is_home", True)
                my_score = payload.get("my_score")
                opp_score = payload.get("opp_score")
                score_str = f"{my_score} x {opp_score}" if is_home else f"{opp_score} x {my_score}"
                
            return [
                {
                    "phase": "pre_match",
                    "title": "Pré-jogo: foco total na sequência",
                    "content": f"O staff de perfil {style} ajusta detalhes táticos para manter consistência na campanha.",
                    "importance": 70,
                },
                {
                    "phase": "post_match",
                    "title": "Pós-jogo: leitura da comissão técnica",
                    "content": f"Resultado registrado em {score_str}. O desempenho coletivo entra em revisão imediata.",
                    "importance": 88,
                },
                {
                    "phase": "fan_reaction",
                    "title": "Torcida: repercussão do jogo",
                    "content": "A comunidade reage ao resultado e pressiona por ajustes na próxima rodada.",
                    "importance": 75,
                },
            ]
        if event_type == "DATE_ADVANCED":
            return [
                {
                    "phase": "calendar",
                    "title": "Agenda atualizada",
                    "content": f"O calendário avançou de {payload.get('old_date')} para {payload.get('new_date')} e a pauta editorial foi reordenada.",
                    "importance": 55,
                }
            ]
        if event_type == "BOARD_ULTIMATUM_CREATED":
            return [
                {
                    "phase": "board_note",
                    "title": "Diretoria define meta imediata",
                    "content": "A presidência estabeleceu uma meta curta de recuperação e aumentou o nível de cobrança institucional.",
                    "importance": 95,
                }
            ]
        if event_type == "BOARD_ULTIMATUM_UPDATED":
            return [
                {
                    "phase": "board_note",
                    "title": "Atualização do objetivo da diretoria",
                    "content": payload.get("message") or "O objetivo teve seu progresso revisado após o último compromisso.",
                    "importance": 85,
                }
            ]
        if event_type == "TRANSFER_OFFER_RECEIVED":
            return [
                {
                    "phase": "market_watch",
                    "title": "Mercado: nova proposta em avaliação",
                    "content": f"A oferta por {payload.get('player_name')} movimenta bastidores e impacta o plano de elenco.",
                    "importance": 80,
                }
            ]
        return []
