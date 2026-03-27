from typing import Dict, Any, List
from engine.event_dispatcher import GameEvent
from engine.llm_client import GeminiClient

class HybridContentGenerator:
    """
    Implementa a Matriz de Decisão: Template Offline vs LLM.
    """
    def __init__(self):
        self.llm_client = GeminiClient()
        
    def generate_content(self, event: GameEvent) -> str:
        """
        Gera conteúdo baseado na severidade do evento.
        """
        if event.severity >= 8:
            return self._generate_via_llm(event)
        else:
            return self._generate_via_template(event)
            
    def _generate_via_template(self, event: GameEvent) -> str:
        """
        Templates robustos offline (f-strings).
        """
        payload = event.payload
        event_type = event.event_type
        
        # 1. match_won
        if event_type == "match_won":
            is_home = payload.get("is_home", True)
            local = "em casa" if is_home else "fora de casa"
            return f"O time garantiu uma vitória importante contra o {payload.get('opponent')} por {payload.get('my_score')}x{payload.get('opp_score')} {local}. Um respiro de alívio no calendário."
            
        # 2. match_lost
        elif event_type == "match_lost":
            return f"Derrota dura. O time perdeu para o {payload.get('opponent')} por {payload.get('opp_score')}x{payload.get('my_score')}. A equipe precisa revisar sua postura para o próximo jogo."
            
        # 3. match_drawn
        elif event_type == "match_drawn":
            return f"Empate morno de {payload.get('my_score')}x{payload.get('opp_score')} contra o {payload.get('opponent')}. Pontos divididos, mas fica o gosto de que poderia ser melhor."
            
        # 4. player_injured
        elif event_type == "player_injured":
            return f"Alerta no departamento médico: {payload.get('player_name')} sofreu uma lesão ({payload.get('injury_type')}). O treinador terá que buscar alternativas no elenco."
            
        # 5. board_budget_cut
        elif event_type == "board_budget_cut":
            return f"A diretoria apertou os cintos. O orçamento caiu drasticamente de {payload.get('old_budget')} para {payload.get('new_budget')}. Tempos de austeridade à vista."
            
        # Fallback
        return f"Aconteceu um evento: {event_type} (Severidade: {event.severity})."

    def _generate_via_llm(self, event: GameEvent) -> str:
        """
        Prepara o Dossiê de Contexto e chama a LLM.
        """
        payload = event.payload
        
        # Monta o Dossiê
        cenario = ""
        if event.event_type == "match_lost":
            cenario = f"Derrota pesada ou Clássico contra {payload.get('opponent')} ({payload.get('opp_score')}x{payload.get('my_score')})"
        elif event.event_type == "match_won":
            cenario = f"Vitória épica ou Goleada contra {payload.get('opponent')} ({payload.get('my_score')}x{payload.get('opp_score')})"
        elif event.event_type == "player_injured":
            cenario = f"Lesão dramática do craque do time ({payload.get('player_name')})"
        else:
            cenario = f"Evento crítico de impacto: {event.event_type}"
            
        context_dossier = {
            "cenario": cenario,
            "pressao_atual": payload.get("pressure", 50),
            "fase_time": payload.get("momentum", "Instável"),
            "severidade_evento": event.severity,
            "diretriz_llm": "Crie um texto dramático sobre este cenário crítico para o futuro do treinador e do clube."
        }
        
        return self.llm_client.generate_epic_narrative(context_dossier, event.event_type)
