import sys
import os
import unittest
from datetime import datetime

# Adiciona o diretório backend ao PYTHONPATH para imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from models import GameState, Meta, Manager, Club, Player, Fixture, Standing, PartialStats, TotalStats, Injury
from engine.analyzer import FootballAnalyzer
from engine.event_dispatcher import EventDispatcher
from engine.content_generator import HybridContentGenerator

def create_mock_state(
    team_id=1, 
    wins=0, 
    losses=0, 
    standings_position=1, 
    budget=10000000,
    has_injured_star=False
):
    # Mockando o meta
    meta = Meta(timestamp=123456789, is_in_career_mode=True)
    manager = Manager(team_id=team_id, reputation=80)
    club = Club(team_id=team_id, transfer_budget=budget)
    
    # Mockando o elenco
    squad = [
        Player(playerid=1, commonname="Craque", overall=88, morale=30), # Moral baixa -> Harmonia cai
        Player(playerid=2, commonname="Bagre", overall=60, morale=50)
    ]
    
    # Mockando os jogos (Fixtures)
    fixtures = []
    for i in range(wins):
        fixtures.append(Fixture(
            id=i, is_completed=True, home_team_id=team_id, away_team_id=99,
            home_score=2, away_score=0
        ))
    for i in range(losses):
        fixtures.append(Fixture(
            id=100+i, is_completed=True, home_team_id=team_id, away_team_id=99,
            home_score=0, away_score=3
        ))
        
    # Mockando a tabela (Standings)
    standings = []
    if standings_position == 1:
        standings.append(Standing(team_id=team_id, total=TotalStats(points=90, goals_for=50, goals_against=10)))
        standings.append(Standing(team_id=99, total=TotalStats(points=88, goals_for=40, goals_against=20)))
    else:
        # Cria 15 times na frente dele
        for i in range(2, 17):
            standings.append(Standing(team_id=100+i, total=TotalStats(points=90-i, goals_for=50, goals_against=10)))
        standings.append(Standing(team_id=team_id, total=TotalStats(points=40, goals_for=30, goals_against=40)))
        
    # Mockando lesões
    injuries = []
    if has_injured_star:
        injuries.append(Injury(playerid=1, injury_type="Joelho", severity="grave"))
        
    return GameState(
        meta=meta,
        manager=manager,
        club=club,
        squad=squad,
        fixtures=fixtures,
        standings=standings,
        injuries=injuries
    )

class TestFootballLogicEngine(unittest.TestCase):

    def test_analyzer_momentum_crise(self):
        old_state = create_mock_state(wins=0, losses=0)
        new_state = create_mock_state(wins=0, losses=3) # 3 derrotas = Crise
        
        analyzer = FootballAnalyzer(old_state, new_state)
        self.assertEqual(analyzer.calculate_team_momentum(), "Crise")
        
    def test_analyzer_pressure_high(self):
        # Time grande (rep 80) perdendo jogos e mal na tabela (position != 1)
        old_state = create_mock_state()
        new_state = create_mock_state(wins=0, losses=3, standings_position=15)
        
        analyzer = FootballAnalyzer(old_state, new_state)
        pressure = analyzer.calculate_manager_pressure()
        self.assertTrue(pressure > 80, f"Pressão esperada alta, mas foi {pressure}")

    def test_dispatcher_star_injury(self):
        old_state = create_mock_state(has_injured_star=False)
        new_state = create_mock_state(has_injured_star=True)
        
        dispatcher = EventDispatcher(old_state, new_state)
        events = dispatcher.dispatch()
        
        injury_events = [e for e in events if e.event_type == "player_injured"]
        self.assertEqual(len(injury_events), 1)
        self.assertEqual(injury_events[0].severity, 8) # Overall 88 = severity 8

    def test_dispatcher_match_lost_goleada(self):
        # Time perdeu por 3 a 0
        old_state = create_mock_state(wins=0, losses=0)
        new_state = create_mock_state(wins=0, losses=1)
        
        dispatcher = EventDispatcher(old_state, new_state)
        events = dispatcher.dispatch()
        
        match_events = [e for e in events if e.event_type == "match_lost"]
        self.assertTrue(len(match_events) > 0)
        self.assertEqual(match_events[0].severity, 9) # Goleada sofrida

    def test_content_generator_templates(self):
        old_state = create_mock_state(budget=10000)
        new_state = create_mock_state(budget=5000) # Caiu pela metade
        
        dispatcher = EventDispatcher(old_state, new_state)
        events = dispatcher.dispatch()
        
        budget_event = [e for e in events if e.event_type == "board_budget_cut"][0]
        self.assertEqual(budget_event.severity, 7)
        
        generator = HybridContentGenerator()
        content = generator.generate_content(budget_event)
        self.assertIn("caiu drasticamente", content) # Texto do template
        
    def test_analyzer_table_narratives(self):
        old_state = create_mock_state()
        new_state = create_mock_state(standings_position=1) # 1º com 90, 2º com 88
        
        analyzer = FootballAnalyzer(old_state, new_state)
        narratives = analyzer.analyze_table_narratives()
        
        # Ameaça fantasma deve estar presente (90 vs 88)
        threat = [n for n in narratives if n["type"] == "Ameaça Fantasma"]
        self.assertEqual(len(threat), 1)

if __name__ == '__main__':
    unittest.main()
