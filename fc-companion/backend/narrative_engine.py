from __future__ import annotations

"""Motor de narrativa da Fase 2 com fallback local e suporte opcional a IA externa."""

import os
from typing import Any, Dict, List, Optional

import requests


from engine.content_generator import HybridContentGenerator
from models import GameEvent
from datetime import datetime

class NarrativeEngine:
    def __init__(self) -> None:
        self.provider = os.getenv("FC_COMPANION_AI_PROVIDER", "template").strip().lower()
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.hybrid_generator = HybridContentGenerator()

    def generate(self, event_type: str, payload: Dict[str, Any], severity: int = 3) -> Dict[str, str]:
        # Se for um evento do novo motor híbrido, delega para ele
        hybrid_events = ["match_won", "match_lost", "match_drawn", "player_injured", "board_budget_cut"]
        if event_type in hybrid_events:
            event = GameEvent(
                event_type=event_type,
                payload=payload,
                severity=severity,
                timestamp=datetime.now()
            )
            content = self.hybrid_generator.generate_content(event)
            tone = "dramático" if severity >= 8 else "jornalístico"
            source = "gemini_2.0_flash" if severity >= 8 else "template_hibrido"
            
            # Gerando um título baseado no tipo
            title_map = {
                "match_won": "Vitória Confirmada",
                "match_lost": "Revés em Campo",
                "match_drawn": "Empate no Placar",
                "player_injured": "Baixa no Elenco",
                "board_budget_cut": "Ajuste Financeiro"
            }
            title = title_map.get(event_type, f"Novo evento: {event_type}")
            
            return {"title": title, "content": content, "tone": tone, "source": source}

        # Lógica antiga para manter compatibilidade
        if self.provider == "openai" and self.openai_api_key:
            try:
                return self._generate_openai(event_type, payload)
            except Exception:
                return self._generate_template(event_type, payload, source="template_fallback")
        return self._generate_template(event_type, payload, source="template")

    def generate_bundle(self, event_type: str, payload: Dict[str, Any], severity: int = 3) -> List[Dict[str, str]]:
        base = self.generate(event_type, payload, severity=severity)
        source = base.get("source", "template")
        
        hybrid_events = ["match_won", "match_lost", "match_drawn", "player_injured", "board_budget_cut"]
        if event_type in hybrid_events:
            return [
                {
                    "channel": "imprensa",
                    "title": base["title"],
                    "content": base["content"],
                    "tone": base["tone"],
                    "source": source,
                }
            ]

        return [
            self._generate_channel_template(event_type, payload, "imprensa", source),
            self._generate_channel_template(event_type, payload, "presidente", source),
            self._generate_channel_template(event_type, payload, "torcida", source),
        ]

    def _build_prompt(self, event_type: str, payload: Dict[str, Any]) -> str:
        return (
            "Você é editor de um companion app de carreira no EA FC 26.\n"
            "Gere resposta em PT-BR no formato JSON com campos: title, content, tone.\n"
            f"Tipo do evento: {event_type}\n"
            f"Payload: {payload}\n"
            "Regras: título curto, texto 2-4 frases, sem emojis, tom jornalístico."
        )

    def _generate_openai(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, str]:
        url = f"{self.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.openai_model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": "Você escreve notícias e mensagens de vestiário."},
                {"role": "user", "content": self._build_prompt(event_type, payload)},
            ],
            "response_format": {"type": "json_object"},
        }
        response = requests.post(url, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        parsed = requests.models.complexjson.loads(content)
        title = str(parsed.get("title") or "Atualização de Carreira")
        text = str(parsed.get("content") or "Novo evento detectado na carreira.")
        tone = str(parsed.get("tone") or "jornalístico")
        return {"title": title, "content": text, "tone": tone, "source": "openai"}

    def _generate_template(self, event_type: str, payload: Dict[str, Any], source: str) -> Dict[str, str]:
        if event_type == "MATCH_COMPLETED":
            title = f"Pós-jogo: {payload.get('home_team')} {payload.get('home_score')} x {payload.get('away_score')} {payload.get('away_team')}"
            content = (
                f"Fim de partida na {payload.get('competition')}. "
                f"O confronto terminou em {payload.get('home_score')} a {payload.get('away_score')}. "
                "A comissão técnica já iniciou a análise de desempenho para o próximo compromisso."
            )
            tone = "jornalístico"
        elif event_type == "PLAYER_INJURED":
            title = f"Departamento médico: {payload.get('player_name')}"
            content = (
                f"{payload.get('player_name')} sofreu uma {payload.get('injury_type')}. "
                f"A projeção inicial é de {payload.get('games_remaining')} jogos fora. "
                "O staff avalia alternativas no elenco para manter o nível competitivo."
            )
            tone = "preocupado"
        elif event_type == "PLAYER_RECOVERED":
            title = f"Retorno ao elenco: {payload.get('player_name')}"
            content = (
                f"{payload.get('player_name')} está novamente disponível para o treinador. "
                "A expectativa interna é de reforçar rotação e intensidade nos próximos jogos."
            )
            tone = "otimista"
        elif event_type == "TRANSFER_OFFER_RECEIVED":
            title = f"Mercado agitado por {payload.get('player_name')}"
            content = (
                f"O clube recebeu proposta de {payload.get('from_team')} por {payload.get('player_name')}. "
                f"Valor ofertado: {payload.get('offer_amount')}. "
                "A diretoria analisa impacto esportivo e financeiro antes da decisão."
            )
            tone = "mercado"
        elif event_type == "BUDGET_CHANGED":
            title = "Mudança no orçamento de transferências"
            content = (
                f"O orçamento foi de {payload.get('old_budget')} para {payload.get('new_budget')}. "
                f"Variação registrada: {payload.get('difference')}. "
                "A janela pode ganhar novas prioridades estratégicas."
            )
            tone = "financeiro"
        elif event_type == "SEASON_CHANGED":
            title = "Nova temporada iniciada"
            content = (
                f"A carreira avançou da temporada {payload.get('old_season')} para {payload.get('new_season')}. "
                "Metas esportivas e planejamento de elenco foram atualizados."
            )
            tone = "institucional"
        elif event_type == "MORALE_DROP":
            title = f"Alerta de vestiário: queda de moral em {payload.get('player_name')}"
            content = (
                f"A moral de {payload.get('player_name')} caiu de {payload.get('old_morale')} para {payload.get('new_morale')}. "
                "A comissão técnica prepara ações para recuperar confiança e desempenho."
            )
            tone = "alerta"
        elif event_type == "DATE_ADVANCED":
            title = "Calendário avançou"
            content = (
                f"A data da carreira avançou de {payload.get('old_date')} para {payload.get('new_date')}. "
                "O app sincronizou os próximos marcos de treino, jogos e decisões de gestão."
            )
            tone = "informativo"
        elif event_type == "BOARD_ULTIMATUM_CREATED":
            title = "Diretoria impõe ultimato"
            content = (
                f"{payload.get('description')} "
                f"Meta: {payload.get('required_points')} pontos em {payload.get('matches_remaining')} jogos."
            )
            tone = "pressão"
        elif event_type == "BOARD_ULTIMATUM_UPDATED":
            title = "Atualização do objetivo da diretoria"
            content = payload.get("message") or "A diretoria atualizou o status do objetivo vigente."
            tone = "institucional"
        elif event_type == "CRISIS_STARTED":
            title = "Início de arco de crise"
            content = payload.get("summary") or "Um arco de crise foi iniciado e exige resposta imediata."
            tone = "pressão"
        elif event_type == "CRISIS_UPDATED":
            title = "Atualização do arco de crise"
            content = payload.get("message") or "A crise segue em evolução conforme os últimos acontecimentos."
            tone = "alerta"
        elif event_type == "SEASON_ARC_STARTED":
            title = "Novo arco de temporada iniciado"
            content = payload.get("summary") or "Um novo arco sazonal começou com metas narrativas de longo prazo."
            tone = "institucional"
        elif event_type == "SEASON_ARC_UPDATED":
            title = "Arco sazonal atualizado"
            content = payload.get("message") or "O arco da temporada avançou para um novo marco."
            tone = "informativo"
        elif event_type == "SEASON_ARC_PAYOFF":
            title = payload.get("title") or "Epilogo de temporada"
            content = payload.get("epilogue") or "O desfecho da temporada foi consolidado com base no histórico da gestão."
            tone = "epilogo"
        elif event_type == "LEGACY_UPDATED":
            title = "Atualização de legado do treinador"
            content = payload.get("narrative_summary") or "O legado histórico foi recalculado com os últimos resultados sazonais."
            tone = "historico"
        elif event_type == "HOF_UPDATED":
            title = "Hall da Fama atualizado"
            content = payload.get("narrative_summary") or "O Hall da Fama recebeu nova atualização de carreira."
            tone = "historico"
        elif event_type == "ACHIEVEMENT_UNLOCKED":
            title = payload.get("title") or "Conquista desbloqueada"
            content = payload.get("description") or "Um novo marco permanente foi desbloqueado na carreira."
            tone = "celebracao"
        elif event_type == "ACHIEVEMENTS_UPDATED":
            title = "Perfil de conquistas atualizado"
            content = payload.get("summary") or "O progresso de conquistas da carreira foi recalculado."
            tone = "historico"
        elif event_type == "META_ACHIEVEMENT_UNLOCKED":
            title = payload.get("title") or "Meta-conquista desbloqueada"
            content = payload.get("description") or "Uma meta-conquista especial foi adicionada ao histórico."
            tone = "celebracao"
        elif event_type == "META_ACHIEVEMENTS_UPDATED":
            title = "Coleção de meta-conquistas atualizada"
            content = payload.get("summary") or "O progresso de meta-conquistas foi recalculado."
            tone = "historico"
        elif event_type == "LOCKER_ROOM_TENSION":
            title = "Vestiário: sinais de tensão"
            content = (
                f"Cohesão do grupo em {payload.get('cohesion')}. "
                f"Jogadores em baixa de moral: {payload.get('low_morale_count')}. "
                "O comando técnico estuda medidas para evitar efeito cascata no desempenho."
            )
            tone = "alerta"
        elif event_type == "LOCKER_ROOM_CALMED":
            title = "Vestiário: ambiente estabilizado"
            content = (
                f"A coesão do grupo subiu para {payload.get('cohesion')}. "
                "O clima interno dá sinais de recuperação após ajustes de gestão e rotação."
            )
            tone = "otimista"
        elif event_type == "MEDICAL_LOAD_WARNING":
            title = "DM alerta para carga acumulada"
            content = (
                f"Índice de risco de lesão em {payload.get('injury_risk_index')}. "
                "A comissão recomenda controle de carga, retorno gradual e rotação para reduzir riscos."
            )
            tone = "preocupado"
        elif event_type == "MEDICAL_LOAD_STABLE":
            title = "DM reporta estabilidade de carga"
            content = (
                f"Índice de risco de lesão em {payload.get('injury_risk_index')}. "
                "O elenco mostra sinais de recuperação física e melhor gestão de fadiga."
            )
            tone = "informativo"
        elif event_type == "FINANCE_MONTHLY_REPORT":
            title = f"Fechamento mensal: {payload.get('period')}"
            content = (
                f"Folha mensal estimada: {payload.get('wage_bill_monthly')}. "
                f"Amortização: {payload.get('amortization_monthly')}. "
                f"Pressão de caixa: {payload.get('cash_pressure_index')}. "
                "O clube revisa prioridades antes de novos compromissos financeiros."
            )
            tone = "financeiro"
        elif event_type == "FINANCE_CASH_PRESSURE":
            title = "Alerta financeiro: pressão de caixa"
            content = (
                f"Pressão de caixa em {payload.get('cash_pressure_index')}. "
                "A diretoria cobra disciplina na folha, bônus e negociações de mercado."
            )
            tone = "pressão"
        elif event_type == "TACTICAL_IDENTITY_SHIFT":
            title = "Identidade tática em transição"
            content = (
                f"O estilo passou de {payload.get('old_identity')} para {payload.get('new_identity')}. "
                f"Estabilidade atual: {payload.get('stability')}. "
                "A mudança deve influenciar elenco, torcida e leitura do mercado."
            )
            tone = "tatico"
        elif event_type == "ACADEMY_BREAKTHROUGH":
            title = "Base em evidência"
            content = (
                f"{payload.get('prospect_name')} evoluiu e chegou a overall {payload.get('overall')}. "
                "O departamento de formação debate acelerar mentoria e integração progressiva."
            )
            tone = "promissor"
        elif event_type == "MARKET_AGENT_NARRATIVE":
            title = "Bastidores do mercado: jogo de agentes"
            content = (
                f"Após oferta por {payload.get('player_name')}, intermediários falam em {payload.get('angle')}. "
                "Vazamentos e blefes devem aumentar conforme a janela avança."
            )
            tone = "mercado"
        elif event_type == "PLAYER_RELATION_UPDATED":
            title = f"Gestão de elenco: ajuste com {payload.get('player_name')}"
            content = (
                f"Status definido: {payload.get('status_label')}, papel: {payload.get('role_label')}. "
                f"Nível de confiança: {payload.get('trust')}. "
                "A decisão deve influenciar moral e dinâmica de vestiário nas próximas semanas."
            )
            tone = "gestao"
        else:
            title = f"Novo evento: {event_type}"
            content = "Um novo evento foi identificado na carreira e registrado para acompanhamento."
            tone = "neutro"
        return {"title": title, "content": content, "tone": tone, "source": source}

    def _generate_channel_template(self, event_type: str, payload: Dict[str, Any], channel: str, source: str) -> Dict[str, str]:
        if channel == "imprensa":
            if event_type == "MATCH_COMPLETED":
                return {
                    "channel": channel,
                    "title": f"Manchete: {payload.get('home_team')} {payload.get('home_score')} x {payload.get('away_score')} {payload.get('away_team')}",
                    "content": f"A imprensa repercute o resultado pela {payload.get('competition')}. O desempenho coletivo entrou no radar dos analistas para medir consistência na temporada.",
                    "tone": "jornalístico",
                    "source": source,
                }
            return {
                "channel": channel,
                "title": f"Boletim da Imprensa: {event_type}",
                "content": "Os jornais locais destacam os impactos esportivos e estratégicos do novo acontecimento no clube.",
                "tone": "jornalístico",
                "source": source,
            }
        if channel == "presidente":
            if event_type == "BUDGET_CHANGED":
                return {
                    "channel": channel,
                    "title": "Mensagem da Presidência sobre orçamento",
                    "content": f"A direção confirma ajuste financeiro de {payload.get('difference')} no caixa de transferências e pede decisões alinhadas ao plano de médio prazo.",
                    "tone": "institucional",
                    "source": source,
                }
            if event_type == "MATCH_COMPLETED":
                return {
                    "channel": channel,
                    "title": "Recado do Presidente pós-jogo",
                    "content": "A diretoria reconhece o impacto do último resultado e cobra manutenção do foco competitivo nos próximos compromissos.",
                    "tone": "diretoria",
                    "source": source,
                }
            return {
                "channel": channel,
                "title": "Comunicado da Presidência",
                "content": "A direção acompanha o evento e reforça metas esportivas e disciplina de gestão.",
                "tone": "institucional",
                "source": source,
            }
        if event_type == "MATCH_COMPLETED":
            return {
                "channel": channel,
                "title": "Torcida reage ao resultado",
                "content": f"As redes da torcida discutem o {payload.get('home_score')} x {payload.get('away_score')}, com debates sobre escalação, postura e momento do time.",
                "tone": "social",
                "source": source,
            }
        if event_type == "PLAYER_INJURED":
            return {
                "channel": channel,
                "title": f"Torcida preocupada com {payload.get('player_name')}",
                "content": "A comunidade reage com apreensão e pede soluções rápidas para manter o nível da equipe.",
                "tone": "social",
                "source": source,
            }
        return {
            "channel": channel,
            "title": f"Reação da Torcida: {event_type}",
            "content": "Perfis e fóruns de torcedores já discutem como esse evento pode influenciar a sequência da temporada.",
            "tone": "social",
            "source": source,
        }
