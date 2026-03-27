from typing import Dict, Any, List, Optional
from datetime import datetime
from models import GameState, GameEvent
from engine.analyzer import FootballAnalyzer

class EventDispatcher:
    """
    Avalia as mudanças e gera GameEvents com Severidade de 1 a 10.
    """
    def __init__(self, old_state: Optional[GameState], new_state: GameState):
        self.old_state = old_state
        self.new_state = new_state
        self.analyzer = FootballAnalyzer(old_state, new_state)
        self.team_id = new_state.manager.team_id if new_state.manager else None

    def dispatch(self) -> List[GameEvent]:
        events = []
        if not self.old_state:
            return events
            
        analysis = self.analyzer.get_full_analysis()
        
        # 1. Checar Novas Lesões
        old_injuries = {i.playerid: i for i in self.old_state.injuries}
        for inj in self.new_state.injuries:
            if inj.playerid not in old_injuries:
                # Nova lesão
                player = next((p for p in self.new_state.squad if p.playerid == inj.playerid), None)
                if player:
                    severity = 2 # Padrão
                    overall = player.overall or 50
                    
                    if overall >= 85:
                        severity = 8 # Lesão do craque
                    elif overall >= 75:
                        severity = 5
                        
                    events.append(GameEvent(
                        event_type="player_injured",
                        severity=severity,
                        payload={
                            "player_name": inj.player_name or player.commonname or "Jogador",
                            "injury_type": inj.injury_type,
                            "overall": overall,
                            "pressure": analysis["pressure"]
                        },
                        timestamp=datetime.now(),
                        save_uid=self.new_state.meta.save_uid
                    ))
                    
        # 2. Checar Novos Jogos (Resultados)
        old_fixtures = {f.id: f for f in self.old_state.fixtures if f.is_completed}
        for f in self.new_state.fixtures:
            if f.is_completed and f.id not in old_fixtures:
                # Jogo acabou de terminar
                if f.home_team_id == self.team_id or f.away_team_id == self.team_id:
                    is_home = (f.home_team_id == self.team_id)
                    my_score = f.home_score if is_home else f.away_score
                    opp_score = f.away_score if is_home else f.home_score
                    opp_name = f.away_team_name if is_home else f.home_team_name
                    
                    if my_score is not None and opp_score is not None:
                        severity = 3 # Padrão normal
                        event_type = "match_result"
                        
                        if my_score > opp_score:
                            event_type = "match_won"
                            if my_score - opp_score >= 3:
                                severity = 6 # Goleada a favor
                            elif analysis["momentum"] == "Crise":
                                severity = 7 # Vitória aliviando a crise
                        elif my_score == opp_score:
                            event_type = "match_drawn"
                            if not is_home:
                                severity = 2 # Empate fora é de boa
                        else:
                            event_type = "match_lost"
                            if opp_score - my_score >= 3:
                                severity = 9 # Goleada sofrida
                            elif analysis["pressure"] > 80:
                                severity = 10 # Risco de demissão
                            else:
                                severity = 5
                                
                        events.append(GameEvent(
                            event_type=event_type,
                            severity=severity,
                            payload={
                                "opponent": opp_name,
                                "my_score": my_score,
                                "opp_score": opp_score,
                                "is_home": is_home,
                                "pressure": analysis["pressure"],
                                "momentum": analysis["momentum"]
                            },
                            timestamp=datetime.now(),
                            save_uid=self.new_state.meta.save_uid
                        ))
                        
        # 3. Checar Mudanças Drásticas de Orçamento (Diretoria Mão de Vaca)
        old_budget = self.old_state.club.transfer_budget if self.old_state.club else 0
        new_budget = self.new_state.club.transfer_budget if self.new_state.club else 0
        
        if old_budget and new_budget:
            # Se o orçamento caiu muito (ex: > 30%) e não houve contratação
            if new_budget < old_budget * 0.7:
                events.append(GameEvent(
                    event_type="board_budget_cut",
                    severity=7,
                    payload={
                        "old_budget": old_budget,
                        "new_budget": new_budget,
                        "pressure": analysis["pressure"]
                    },
                    timestamp=datetime.now(),
                    save_uid=self.new_state.meta.save_uid
                ))

        return events
