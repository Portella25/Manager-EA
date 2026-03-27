import math
from typing import Dict, Any, List, Optional
from models import GameState

class FootballAnalyzer:
    """
    Motor Híbrido: Analisador do Futebol
    Calcula métricas invisíveis baseadas nas mudanças de estado.
    """

    def __init__(self, old_state: Optional[GameState], new_state: GameState):
        self.old_state = old_state
        self.new_state = new_state
        
        # Pega o ID do time atual
        self.team_id = None
        if new_state.manager and new_state.manager.team_id:
            self.team_id = new_state.manager.team_id

    def calculate_team_momentum(self) -> str:
        """
        Calcula o momentum do time baseado nas últimas partidas (sequência de V/E/D).
        """
        if not self.team_id:
            return "Neutro"
            
        completed_fixtures = [f for f in self.new_state.fixtures if f.is_completed]
        # Ordena pelas datas (simplificado, pega os últimos 5 na lista se assumirmos ordem)
        # Vamos usar o fato de que estão no array
        recent_fixtures = completed_fixtures[-5:] if len(completed_fixtures) >= 5 else completed_fixtures
        
        if not recent_fixtures:
            return "Neutro"
            
        wins, draws, losses = 0, 0, 0
        for f in recent_fixtures:
            is_home = (f.home_team_id == self.team_id)
            is_away = (f.away_team_id == self.team_id)
            
            if not is_home and not is_away:
                continue
                
            my_score = f.home_score if is_home else f.away_score
            opp_score = f.away_score if is_home else f.home_score
            
            if my_score is not None and opp_score is not None:
                if my_score > opp_score:
                    wins += 1
                elif my_score == opp_score:
                    draws += 1
                else:
                    losses += 1
                    
        total = wins + draws + losses
        if total == 0:
            return "Neutro"
            
        if losses >= 3:
            return "Crise"
        elif wins >= 4 or (wins == 3 and draws == 0 and losses == 0):
            return "Oba-oba"
        elif wins > losses:
            return "Em Alta"
        elif losses > wins:
            return "Em Baixa"
        else:
            return "Instável"

    def calculate_locker_room_harmony(self) -> int:
        """
        Calcula a harmonia do vestiário (média de moral ponderada pelo overall).
        0 a 100.
        """
        squad = self.new_state.squad
        if not squad:
            return 50 # Neutro
            
        total_weight = 0
        weighted_morale_sum = 0
        
        for player in squad:
            morale = player.morale if player.morale is not None else 50
            overall = player.overall if player.overall is not None else 50
            
            # Peso é baseado no overall (jogadores melhores influenciam mais)
            weight = math.exp((overall - 50) / 10.0) 
            
            weighted_morale_sum += morale * weight
            total_weight += weight
            
        if total_weight == 0:
            return 50
            
        harmony = int(weighted_morale_sum / total_weight)
        return max(0, min(100, harmony))

    def get_team_standing(self) -> Optional[Any]:
        if not self.team_id:
            return None
        for s in self.new_state.standings:
            if s.team_id == self.team_id:
                return s
        return None

    def calculate_manager_pressure(self) -> int:
        """
        Calcula a pressão sobre o treinador (0-100).
        Baseado em momentum, harmonia, e posição na tabela vs reputação do clube.
        """
        pressure = 50 # Base
        
        # 1. Momentum Impact
        momentum = self.calculate_team_momentum()
        if momentum == "Crise":
            pressure += 25
        elif momentum == "Em Baixa":
            pressure += 10
        elif momentum == "Em Alta":
            pressure -= 10
        elif momentum == "Oba-oba":
            pressure -= 20
            
        # 2. Harmony Impact
        harmony = self.calculate_locker_room_harmony()
        if harmony < 30:
            pressure += 15
        elif harmony < 50:
            pressure += 5
        elif harmony > 70:
            pressure -= 10
            
        # 3. Table Position vs Expectation
        standing = self.get_team_standing()
        club_reputation = self.new_state.manager.reputation if self.new_state.manager and self.new_state.manager.reputation else 50
        
        if standing:
            # Simplificação da expectativa: Reputação alta -> Top 4. Reputação média -> Top 10.
            # Como não temos posição exata facilmente sem ordenar a tabela, vamos ordenar:
            sorted_standings = sorted(self.new_state.standings, key=lambda x: (x.total.points, x.total.goals_for - x.total.goals_against), reverse=True)
            try:
                position = next(i for i, s in enumerate(sorted_standings) if s.team_id == self.team_id) + 1
                
                if club_reputation > 80:
                    if position > 10:
                        pressure += 30 # Expectativa vs Realidade
                    elif position > 4:
                        pressure += 15
                elif club_reputation > 50:
                    if position > 15:
                        pressure += 15
                else:
                    # Time pequeno
                    if position <= 10:
                        pressure -= 15 # Boa campanha
                    
            except StopIteration:
                pass
                
        return max(0, min(100, pressure))

    def analyze_table_narratives(self) -> List[Dict[str, Any]]:
        """
        Encontra 'Ameaças' (times próximos) e 'Oportunidades' (tropeço do líder).
        """
        narratives = []
        if not self.team_id or not self.new_state.standings:
            return narratives
            
        sorted_standings = sorted(self.new_state.standings, key=lambda x: (x.total.points, x.total.goals_for - x.total.goals_against), reverse=True)
        
        try:
            my_idx = next(i for i, s in enumerate(sorted_standings) if s.team_id == self.team_id)
            my_team = sorted_standings[my_idx]
            
            # Ameaça Fantasma
            if my_idx < len(sorted_standings) - 1:
                team_behind = sorted_standings[my_idx + 1]
                if my_team.total.points - team_behind.total.points <= 3:
                    narratives.append({
                        "type": "Ameaça Fantasma",
                        "description": f"O {team_behind.team_name or 'rival'} está respirando no cangote, a apenas {my_team.total.points - team_behind.total.points} pontos de diferença."
                    })
                    
            # A Secada (Oportunidade)
            if my_idx == 1: # Somos o 2º colocado
                leader = sorted_standings[0]
                if leader.total.points - my_team.total.points <= 3:
                    narratives.append({
                        "type": "Oportunidade de Ouro",
                        "description": "O líder tropeçou ou está ao alcance. Uma vitória pode mudar tudo."
                    })
                    
            # Fim de Feira (Limbo)
            # Simplificação: rodadas passadas > 30 e posição no meio (ex: 8º a 14º)
            games_played = my_team.total.wins + my_team.total.draws + my_team.total.losses
            if games_played >= 30 and 8 <= my_idx + 1 <= 14:
                narratives.append({
                    "type": "Fim de feira",
                    "description": "Time no meio da tabela sem grandes pretensões. Foco já começa a ser a próxima temporada."
                })
                
        except StopIteration:
            pass
            
        return narratives

    def get_full_analysis(self) -> Dict[str, Any]:
        """Retorna o dossiê completo analisado."""
        return {
            "momentum": self.calculate_team_momentum(),
            "pressure": self.calculate_manager_pressure(),
            "harmony": self.calculate_locker_room_harmony(),
            "table_narratives": self.analyze_table_narratives()
        }
