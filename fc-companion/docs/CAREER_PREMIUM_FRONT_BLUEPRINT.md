# Blueprint do Hub de Carreira Premium

Este documento consolida a direção de produto, arquitetura de dados, reaproveitamento dos engines atuais e a estratégia de evolução do frontend sem quebrar a estrutura híbrida atual do backend.

## Objetivo

- O app deve parecer um hub de carreira premium, não um painel técnico.
- Ao abrir, o usuário final precisa sentir:
  - situação atual do clube
  - consequências do que aconteceu recentemente
  - próximas decisões que importam
- A experiência deve unir:
  - dashboard executivo
  - central esportiva
  - rede social e jornalismo esportivo
  - bastidores do vestiário
  - tomada de decisão com impacto narrativo

## Princípios de Produto

- Cada tela deve responder:
  - o que aconteceu
  - por que isso importa
  - o que eu faço agora
- O backend continua como fonte principal de verdade.
- O modelo híbrido permanece:
  - save primeiro
  - Live Editor como complemento quando o save não oferece o dado
- O frontend consome read models prontos e não monta inteligência pesada no cliente.
- A nova camada editorial deve ser plugada sobre o ecossistema atual, sem reescrever o motor sistêmico existente.

## Princípios Técnicos Obrigatórios

- Não quebrar a estrutura atual de `state.json`, `save_data.json`, `state_lua.json` e `/companion/overview`.
- Preservar o fluxo:
  - save -> parser Python
  - Live Editor/Lua -> `state_lua.json`
  - merger -> `state.json`
  - backend -> endpoints agregados e motores narrativos
- Toda evolução nova deve preferir:
  - novos endpoints
  - novos agregados
  - novos objetos editoriais
  - novas tabelas de leitura
- Evitar mover lógica pesada para Lua.
- O trabalho pesado continua no Python.

## Contrato Operacional do Sistema Híbrido

### Política de Fonte de Dados

- Regra oficial:
  - usar o save sempre que o dado existir de forma confiável
  - usar Live Editor apenas como fallback, enriquecimento ou dado de runtime
- Exemplos:
  - elenco, manager, contratos, atributos, season stats estruturais: priorizar save
  - data viva do jogo, fixtures, standings, eventos runtime, orçamento em memória, resolução complementar de nomes: usar Live Editor
  - nomes faltantes do plantel: resolver pelo runtime do Live Editor e consolidar no Python

### Fontes Atuais

- `save_data.json`
  - base estrutural persistente
  - elenco
  - manager
  - teams
  - injuries
  - transfer_offers
  - season_stats
- `state_lua.json`
  - estado volátil e sinais de runtime
  - club
  - fixtures
  - standings
  - events_raw
  - name_resolution
- `state.json`
  - read model híbrido principal consumido pelo app
- artefatos externos por `save_uid`
  - `schema.json`
  - `reference_data.json`
  - `season_stats.json`
  - `transfer_history.json`
  - `events.jsonl`

## O Que Já Existe e Deve Ser Reaproveitado

### Camada Base

- `merger.py`
  - consolida save + Lua em um snapshot final único
- `main.py`
  - já expõe `state`, `overview`, timeline, crises, arcos, mercado, relações, legado, hall da fama e conquistas
- `external_ingestion.py`
  - já ingere artefatos expandidos por `save_uid`

### Engines Sistêmicos Reaproveitáveis

- `career_dynamics_engine.py`
  - melhor fonte para:
    - vestiário
    - confiança
    - frustração
    - medical load
    - academy
    - identidade tática
    - ledger financeiro
  - deve alimentar telas de bastidores, alertas e radar de clima
- `reputation_engine.py`
  - base de:
    - reputação do treinador
    - sentimento da torcida
    - leitura pública do momento
  - deve alimentar hero principal, social e conferências
- `board_engine.py`
  - base da camada institucional
  - deve alimentar pressão, objetivos curtos e alertas críticos
- `crisis_engine.py`
  - base da narrativa de crise
  - deve alimentar home, bastidores, social e coletivas
- `season_arc_engine.py`
  - base do arco macro da temporada
  - deve alimentar timeline, home e tela de temporada
- `market_engine.py`
  - base de rumores e contexto de mercado
  - deve alimentar mercado, notícias e bastidores
- `editorial_engine.py`
  - hoje é simples, mas é o melhor ponto de partida para o pipeline editorial
- `legacy_engine.py`
  - base do legado multi-temporada
- `hall_of_fame_engine.py`
  - base de memória histórica prestigiosa
- `achievements_engine.py`
  - base de progressão e colecionismo
- `meta_achievements_engine.py`
  - base de prestígio de carreira
- `payoff_engine.py`
  - base de encerramento forte de ciclo sazonal

## O Que Reaproveitar, Ajustar ou Substituir

### Reaproveitar Quase Como Está

- `reputation_engine.py`
- `board_engine.py`
- `crisis_engine.py`
- `season_arc_engine.py`
- `legacy_engine.py`
- `hall_of_fame_engine.py`
- `achievements_engine.py`
- `meta_achievements_engine.py`
- `payoff_engine.py`

Motivo:

- já produzem objetos claros
- já têm utilidade direta de front
- já ajudam narrativa, progressão e contexto

### Ajustar e Expandir

- `career_dynamics_engine.py`
  - expandir sinais para alimentar melhor:
    - clima do elenco
    - risco de desgaste
    - promessas e insatisfação
    - preparação para maratona
  - manter o motor atual, adicionando mais read models derivados
- `market_engine.py`
  - enriquecer rumor com:
    - categoria
    - prioridade
    - fonte
    - confiabilidade textual
    - impacto esportivo
- `editorial_engine.py`
  - evoluir de entradas curtas para objetos editoriais completos
  - será o embrião do feed social premium
- fluxo de coletiva em `main.py`
  - hoje reage à resposta
  - precisa passar a gerar perguntas com base em contexto real da sessão

### Substituir Parcialmente por uma Camada Superior

- a geração editorial atual não deve ser removida, mas deve ser supersedida por uma camada nova:
  - `facts ledger`
  - `editorial planner`
  - `article renderer`
- em outras palavras:
  - não jogar fora o motor atual
  - subir um nível acima dele

## Arquitetura de Conteúdo Recomendada

### Nível 1: Dados Brutos

- `state`
- `save`
- `events_raw`
- `external_events_recent`
- `season_stats`
- `transfer_history`
- `player_relations`
- `career_management_state`
- `coach_profile`
- `board_challenges`
- `crisis`
- `season_arc`

### Nível 2: Fatos Canônicos

Objetivo:

- transformar dados dispersos em fatos consistentes e reutilizáveis

Exemplos:

- vitória importante
- derrota em confronto direto
- três vitórias seguidas
- quatro jogos sem vencer
- jogador em grande fase
- reserva frustrado
- titular desgastado
- proposta relevante recebida
- lesão crítica
- retorno importante
- pressão da diretoria
- piora do clima interno
- melhora do humor da torcida

### Nível 3: Sinais e Leitura Contextual

Objetivo:

- interpretar fatos para responder por que eles importam

Exemplos:

- momento de ascensão
- risco de crise
- ambiente instável
- janela estratégica
- jogo divisor de águas
- clássico de alta pressão
- oportunidade de consolidação

### Nível 4: Objetos Narrativos

- notícia
- análise
- rumor
- pauta de coletiva
- nota interna
- alerta executivo
- card de contexto
- marco de timeline

### Nível 5: Experiência de Front

- home
- feed social
- tela de notícia fullscreen
- tela de bastidores
- tela de coletivas
- radar do elenco
- radar da diretoria
- timeline

## Estrutura de UI Oficial

### 1. Home da Carreira

Objetivo:

- resumir o dia da carreira

Blocos:

- hero principal
  - clube
  - data atual
  - próximo jogo
  - forma recente
  - moral/clima do elenco
  - pressão da diretoria
- 4 cards principais
  - próximo jogo
  - elenco
  - notícias
  - alertas críticos
- módulo de 3 a 5 notícias do dia
- radar rápido
  - clima
  - mercado
  - confiança
  - risco

### 2. Central do Clube

Objetivo:

- fazer o usuário sentir que é o gestor

Blocos:

- desempenho esportivo
- orçamento e caixa
- objetivos da diretoria
- arco da temporada
- confiança institucional
- resumo de decisões recentes

### 3. Elenco

Objetivo:

- tomada de decisão sobre pessoas e plantel

Blocos:

- lista virtualizada
- filtros rápidos
- estados emocionais
- forma
- sharpness
- fitness
- papel no elenco
- vínculo contratual
- alertas de renovação
- atletas em alta ou em risco

### 4. Partidas e Competições

Objetivo:

- leitura de contexto esportivo

Blocos:

- próximos jogos
- retrospecto recente
- classificação por competição
- sequência do time
- jogos-chave
- análise de momento

### 5. Social / Notícias

Objetivo:

- transformar fatos e contexto em narrativa legível e imersiva

Blocos:

- feed vertical
- cards grandes
- máximo de 5 matérias por dia do jogo
- alternância entre:
  - manchete quente
  - bastidor
  - análise
  - mercado
  - ambiente

### 6. Bastidores

Objetivo:

- profundidade de manager career

Blocos:

- relações jogador ↔ técnico
- humor do elenco
- comissão técnica
- diretoria
- crises
- promessas
- insatisfações
- rumores internos

### 7. Conferências

Objetivo:

- transformar contexto em interação

Blocos:

- pré-jogo
- pós-jogo
- perguntas contextuais
- opções de resposta
- impactos simulados

### 8. Timeline

Objetivo:

- mostrar a história da carreira ao longo do tempo

Blocos:

- dia
- semana
- mês
- marcos esportivos
- marcos institucionais
- marcos narrativos

## Feed Social Premium

### Regras do Feed

- organizar por `game_date`
- gerar no máximo 5 matérias por dia
- se o dia estiver fraco, aceitar 2 ou 3 matérias
- preferir densidade e autenticidade em vez de volume

### Estrutura do Card

- imagem ou capa temática
- manchete
- subtítulo
- corpo resumido com 2 a 5 parágrafos curtos
- tags
  - Brasileirão
  - mercado
  - vestiário
  - diretoria
  - lesão
  - pressão
- impacto
  - baixo
  - médio
  - alto

### Tela Fullscreen da Matéria

- capa
- headline
- subheadline
- lead
- corpo curto
- bloco `por que isso importa`
- bloco `efeitos no clube`
- tags
- entidades envolvidas
- possíveis desdobramentos

## Modelo Editorial Recomendado

### Camada 1: Facts Ledger

Objetivo:

- consolidar fatos canônicos por sessão e por dia

Entradas:

- `events_raw`
- `external_events_recent`
- `fixtures`
- `standings`
- `transfer_offers`
- `season_stats`
- `player_relations`
- `career_management_state`
- `coach_profile`
- `board_active_challenge`
- `crisis_active_arc`
- `season_arc_active`

Saídas:

- fatos normalizados com:
  - tipo
  - data
  - importância
  - entidades
  - origem
  - confiança
  - consequências esperadas

### Camada 2: Editorial Planner

Objetivo:

- decidir o pacote editorial do dia

Regras:

- 1 matéria principal
- 1 bastidor
- 1 análise esportiva
- 1 mercado/plantel
- 1 institucional/ambiente
- descartar repetição
- priorizar variedade

### Camada 3: Article Renderer

Objetivo:

- converter pauta em objeto editorial completo

Saídas:

- headline
- subheadline
- lead
- corpo
- impacto
- contexto
- efeitos
- entidades
- CTA contextual

### Camada 4: IA Pontual

Usos permitidos:

- expandir uma matéria importante
- gerar uma coletiva especial
- escrever análise de clássico
- produzir falas mais humanas
- cruzar sinais raros

Usos não recomendados:

- inventar fatos
- substituir o motor sistêmico
- escrever tudo de forma livre sem lastro

## Conferências Pré e Pós-Jogo

### Geração de Perguntas

As perguntas devem nascer de:

- forma recente
- resultado anterior
- rivalidade
- pressão da tabela
- insatisfação de jogador
- rumor de mercado
- lesão importante
- pressão da diretoria
- clima da torcida

### Efeitos das Respostas

- moral do elenco
- relação com jogadores específicos
- confiança da diretoria
- tom da imprensa
- intensidade da crise
- reputação do treinador

### Diretriz Técnica

- manter a análise da resposta existente
- adicionar antes dela um gerador contextual de perguntas
- salvar:
  - pergunta
  - contexto gerador
  - tema
  - entidades
  - efeitos previstos

## Camada de Relações e Bastidores

### Relações Explícitas

- jogador ↔ técnico
- elenco ↔ técnico
- diretoria ↔ técnico
- torcida ↔ clube
- imprensa ↔ treinador

### Estados Possíveis

- confiança
- tensão
- apoio
- ceticismo
- desgaste

### Uso no App

- notícias
- alertas
- coletivas
- crises
- decisões
- cards de bastidor

## Radars de Controle

### Radar de Elenco

- quem está em alta
- quem está cansado
- quem está desmotivado
- quem pede renovação
- quem atrai interesse

### Radar da Diretoria

- objetivos
- risco atual
- confiança
- áreas críticas

### Radar da Temporada

- forma recente
- sequência
- fase ofensiva/defensiva
- jogos decisivos

### Radar de Clima

- humor do vestiário
- pressão da torcida
- tom da imprensa
- estabilidade institucional

## Navegação Recomendada

- Home
- Notícias
- Clube
- Elenco
- Partidas
- Mercado
- Bastidores
- Coletivas
- Timeline

## Estratégia de Backend Sem Quebrar a Base Atual

### O Que Não Mudar

- contrato base de `/state`
- contrato base de `/state/squad`
- contrato base de `/state/standings`
- estrutura de `/companion/overview`
- fluxo híbrido save + Lua

### O Que Adicionar

- novos endpoints agregados voltados a read model de front
- novas tabelas ou snapshots editoriais
- novos serviços internos que consomem a base atual

### Endpoints Novos Recomendados

- `GET /dashboard/home?save_uid=...`
  - payload pronto para a home premium
- `GET /news/feed/daily?save_uid=...&date=...`
  - pacote editorial do dia
- `GET /news/article/{id}`
  - matéria completa
- `GET /bastidores/overview?save_uid=...`
  - clima, relações, alertas, comissão, diretoria
- `GET /conference/context?save_uid=...`
  - perguntas e temas disponíveis para coletiva
- `GET /radars/overview?save_uid=...`
  - elenco, diretoria, clima e temporada

### Estratégia de Compatibilidade

- manter `/companion/overview` como agregador geral
- evoluir por novos agregados especializados
- evitar acoplamento do front diretamente em todas as tabelas internas

## Contratos dos Agregados de Front

### Regras Gerais

- todos os contratos novos são read models
- todos aceitam `save_uid`
- todos retornam objetos prontos para renderização
- o frontend não deve recalcular contexto pesado
- campos derivados devem ser produzidos no backend
- datas canônicas:
  - `game_date`: contexto do calendário do save
  - `generated_at`: timestamp ISO do agregado
  - `updated_at`: timestamp ISO de entidades persistidas
- estratégia de versionamento inicial:
  - incluir `contract_version`
  - começar em `1`

### 1. Contrato `GET /dashboard/home`

#### Objetivo

- entregar a home premium da carreira em um único payload
- responder imediatamente:
  - onde estou
  - o que acabou de acontecer
  - o que exige decisão agora

#### Query Params

- `save_uid` obrigatório
- `news_limit` opcional
  - default `5`
  - max `5`
- `timeline_limit` opcional
  - default `6`
- `alerts_limit` opcional
  - default `6`

#### Response Shape

```json
{
  "contract_version": 1,
  "save_uid": "string",
  "generated_at": "2026-03-25T20:10:00Z",
  "snapshot": {
    "game_date": {
      "day": 29,
      "month": 3,
      "year": 2026,
      "label": "29 Mar 2026"
    },
    "club": {
      "team_id": 517,
      "team_name": "Botafogo",
      "manager_name": "Martín Anselmi",
      "crest_url": null,
      "competition_focus": "Brasileirão"
    },
    "hero": {
      "headline": "Botafogo entra em semana decisiva",
      "subheadline": "Boa fase recente aumenta expectativa para o próximo confronto.",
      "state_label": "em_alta",
      "state_tone": "positive"
    }
  },
  "hero_panel": {
    "next_fixture": {
      "fixture_id": 1440,
      "competition_id": 1663,
      "competition_name": "Brasileirão",
      "home_team_id": 1053,
      "home_team_name": "Santos",
      "away_team_id": 517,
      "away_team_name": "Botafogo",
      "date_raw": 20261206,
      "time_raw": 1600,
      "is_user_team_fixture": true,
      "narrative_angle": "Jogo com peso direto na leitura pública da equipe."
    },
    "recent_form": {
      "last_5": ["W", "W", "D", "W", "L"],
      "points_last_5": 10,
      "trend_label": "positivo"
    },
    "club_health": {
      "locker_room_score": 72,
      "fan_sentiment_score": 68,
      "board_confidence_score": 61,
      "injury_risk_score": 34,
      "financial_pressure_score": 29
    },
    "strategic_focus": {
      "primary_decision": "gerir desgaste do elenco",
      "secondary_decision": "responder pressão da diretoria",
      "why_now": "Maratona de jogos e cobrança institucional aumentaram o risco de instabilidade."
    }
  },
  "cards": {
    "next_match": {
      "title": "Próximo jogo",
      "importance": 90,
      "summary": "Santos x Botafogo pelo Brasileirão.",
      "cta": "Ver análise da partida"
    },
    "squad": {
      "title": "Elenco",
      "highlights": {
        "in_form_count": 4,
        "fatigue_risk_count": 3,
        "unhappy_count": 2,
        "injured_count": 0
      },
      "cta": "Abrir gestão do elenco"
    },
    "news": {
      "title": "Notícias do dia",
      "stories_count": 5,
      "lead_story_title": "Botafogo mantém embalo e eleva expectativa da torcida",
      "cta": "Abrir feed completo"
    },
    "critical_alerts": {
      "title": "Alertas críticos",
      "count": 2,
      "top_alert": "Diretoria elevou o nível de cobrança",
      "cta": "Ver todos os alertas"
    }
  },
  "radars": {
    "squad": {
      "hot_players": [],
      "fatigue_watch": [],
      "contract_watch": [],
      "market_interest": []
    },
    "board": {
      "objective_label": "recuperação imediata",
      "status": "active",
      "risk_level": "medium",
      "message": "Objetivo em andamento: 1/4 pontos."
    },
    "season": {
      "arc_title": "Arco da temporada 2026",
      "arc_status": "active",
      "phase_label": "consolidação",
      "milestone_progress": "2/5"
    },
    "climate": {
      "locker_room_label": "estável",
      "fan_mood_label": "confiante",
      "press_tone_label": "atento",
      "institutional_pressure_label": "moderada"
    }
  },
  "alerts": [
    {
      "id": "string",
      "type": "board|medical|locker_room|market|match",
      "severity": "low|medium|high|critical",
      "title": "string",
      "message": "string",
      "cta_label": "string",
      "cta_target": "string",
      "source": "board_active_challenge"
    }
  ],
  "daily_news_preview": [
    {
      "article_id": "string",
      "slot": "lead|backstage|analysis|market|environment",
      "headline": "string",
      "subheadline": "string",
      "impact": "low|medium|high",
      "cover_image_url": null,
      "published_at": "2026-03-25T20:10:00Z"
    }
  ],
  "timeline_preview": [
    {
      "id": 1,
      "phase": "post_match",
      "title": "string",
      "content": "string",
      "importance": 88,
      "created_at": "2026-03-25T20:00:00Z"
    }
  ],
  "source_map": {
    "state": true,
    "coach_profile": true,
    "career_management_state": true,
    "board_active_challenge": true,
    "crisis_active_arc": true,
    "season_arc_active": true,
    "news_feed_daily": true
  }
}
```

#### Blocos Obrigatórios

- `snapshot`
  - identidade da carreira e contexto base da tela
- `hero_panel`
  - próximo jogo, forma, saúde do clube e foco estratégico
- `cards`
  - quatro áreas principais da home
- `radars`
  - leitura gerencial rápida
- `alerts`
  - itens acionáveis e não apenas informativos
- `daily_news_preview`
  - até 5 itens
- `timeline_preview`
  - últimos marcos mais importantes

#### Fontes de Dados Recomendadas

- `state.meta`, `state.club`, `state.manager`
- `coach_profile`
- `career_management_state`
- `board_active_challenge`
- `crisis_active_arc`
- `season_arc_active`
- `timeline_recent`
- `news/feed/daily`

### 2. Contrato `GET /news/feed/daily`

#### Objetivo

- entregar o pacote editorial diário do jogo
- servir tanto a home quanto a tela completa de notícias
- limitar o feed a no máximo 5 matérias fortes por `game_date`

#### Query Params

- `save_uid` obrigatório
- `date` opcional
  - formato `YYYY-MM-DD`
  - se ausente, usar a data atual do save
- `limit` opcional
  - default `5`
  - max `5`

#### Response Shape

```json
{
  "contract_version": 1,
  "save_uid": "string",
  "game_date": "2026-03-29",
  "generated_at": "2026-03-25T20:15:00Z",
  "editorial_package": {
    "package_id": "string",
    "edition_label": "Diário da Carreira",
    "lead_angle": "semana decisiva",
    "density_level": "full|medium|light",
    "stories_count": 5
  },
  "stories": [
    {
      "article_id": "string",
      "slot": "lead|backstage|analysis|market|environment",
      "kind": "news|analysis|rumor|internal_note|press_echo",
      "priority": 100,
      "impact": "low|medium|high",
      "headline": "string",
      "subheadline": "string",
      "lead": "string",
      "body": [
        "parágrafo 1",
        "parágrafo 2"
      ],
      "why_it_matters": "string",
      "club_effects": [
        "string"
      ],
      "tags": ["Brasileirão", "pressão"],
      "entities": {
        "club": ["Botafogo"],
        "players": ["string"],
        "staff": ["string"],
        "competitions": ["Brasileirão"]
      },
      "source_facts": [
        {
          "fact_type": "match_result|board_pressure|market_offer|locker_room_tension",
          "source": "events_recent|timeline_recent|market_rumors_recent|career_management_state",
          "confidence": 0.92
        }
      ],
      "cover_image_url": null,
      "theme": "dark_editorial",
      "published_at": "2026-03-25T20:15:00Z"
    }
  ],
  "secondary_modules": {
    "rumors": [
      {
        "id": 1,
        "headline": "string",
        "confidence_level": 84,
        "target_profile": "substituto direto",
        "created_at": "2026-03-25T19:00:00Z"
      }
    ],
    "timeline_hooks": [
      {
        "id": 10,
        "title": "string",
        "phase": "post_match",
        "importance": 88
      }
    ],
    "external_signals": [
      {
        "event_id_raw": "string",
        "category": "OTHER",
        "importance": "low",
        "summary": "string"
      }
    ]
  },
  "layout_hints": {
    "stack_order": ["lead", "backstage", "analysis", "market", "environment"],
    "fullscreen_default_article_id": "string",
    "show_more_available": false
  }
}
```

#### Regras Obrigatórias

- máximo de 5 matérias por dia
- pode retornar menos que 5
- sempre tentar diversidade por slot
- não repetir o mesmo fato principal em mais de uma matéria
- `stories[].body` deve vir pronto para renderização
- `why_it_matters` e `club_effects` são obrigatórios nas matérias principais

#### Fontes de Dados Recomendadas

- `feed_recent`
- `timeline_recent`
- `market_rumors_recent`
- `events_recent`
- `external_events_recent`
- `career_management_state`
- `coach_profile`
- `board_active_challenge`
- `crisis_active_arc`

### 3. Contrato `GET /conference/context`

#### Objetivo

- entregar o contexto completo da coletiva antes da resposta do usuário
- permitir geração coerente de perguntas pré ou pós-jogo
- deixar claro quais temas estão quentes e quais consequências são esperadas

#### Query Params

- `save_uid` obrigatório
- `mode` opcional
  - `pre_match`
  - `post_match`
  - `generic`
  - default: auto detectar
- `questions_limit` opcional
  - default `4`
  - min `3`
  - max `6`

#### Response Shape

```json
{
  "contract_version": 1,
  "save_uid": "string",
  "generated_at": "2026-03-25T20:20:00Z",
  "mode": "pre_match",
  "context_snapshot": {
    "game_date": "2026-03-29",
    "club_name": "Botafogo",
    "manager_name": "Martín Anselmi",
    "next_fixture": {
      "fixture_id": 1440,
      "competition_name": "Brasileirão",
      "home_team_name": "Santos",
      "away_team_name": "Botafogo",
      "is_rivalry": false,
      "stakes_label": "alta pressão"
    },
    "last_result": {
      "label": "vitória",
      "score": "2 x 1",
      "narrative": "Resultado reforçou expectativa de reação."
    }
  },
  "pressure_map": {
    "board": {
      "score": 61,
      "label": "moderada",
      "reason": "Diretoria acompanha sequência recente com cobrança ativa."
    },
    "fans": {
      "score": 68,
      "label": "confiantes",
      "reason": "Boa fase recente elevou expectativa."
    },
    "locker_room": {
      "score": 72,
      "label": "estável",
      "reason": "Cohesion positiva e baixa frustração média."
    },
    "media": {
      "score": 58,
      "label": "atenta",
      "reason": "O próximo jogo pode redefinir o tom da cobertura."
    }
  },
  "hot_topics": [
    {
      "topic_id": "string",
      "topic_type": "match|board|market|player|injury|locker_room|tactical",
      "title": "string",
      "summary": "string",
      "importance": 90,
      "entities": ["string"],
      "recommended_tone": "calmo|confiante|firme|defensivo"
    }
  ],
  "questions": [
    {
      "question_id": "string",
      "slot": 1,
      "topic_type": "match",
      "question": "string",
      "intent": "pressionar sobre resultado recente",
      "why_now": "string",
      "entities": ["string"],
      "predicted_effects": {
        "reputation_risk": "low|medium|high",
        "morale_risk": "low|medium|high",
        "board_sensitivity": "low|medium|high",
        "fan_sensitivity": "low|medium|high"
      }
    }
  ],
  "response_guidance": {
    "safe_tone": "equilibrado",
    "recommended_approach": "Reconhecer pressão sem demonstrar instabilidade.",
    "danger_zones": [
      "conflitar com diretoria",
      "expor jogador insatisfeito"
    ]
  },
  "expected_consequences": {
    "positive_path": [
      "Aumenta confiança pública no treinador"
    ],
    "negative_path": [
      "Eleva desconforto interno e piora tom da imprensa"
    ]
  },
  "source_map": {
    "coach_profile": true,
    "board_active_challenge": true,
    "crisis_active_arc": true,
    "player_relations_recent": true,
    "career_management_state": true,
    "events_recent": true,
    "news_feed_daily": true
  }
}
```

#### Regras Obrigatórias

- o contrato não responde a coletiva, apenas prepara o contexto
- as perguntas devem vir prontas para renderização
- `hot_topics` e `questions` devem refletir o mesmo contexto-base
- `response_guidance` deve ser curto, útil e acionável
- `expected_consequences` deve traduzir o que a resposta pode afetar no sistema

#### Fontes de Dados Recomendadas

- `coach_profile`
- `board_active_challenge`
- `crisis_active_arc`
- `player_relations_recent`
- `career_management_state`
- `events_recent`
- `timeline_recent`
- `news/feed/daily`

### Decisões de Contrato

- `dashboard/home` é o read model mais abrangente da home
- `news/feed/daily` é o read model editorial do dia
- `conference/context` é o read model de preparação de coletiva
- os três contratos devem compartilhar:
  - `contract_version`
  - `save_uid`
  - `generated_at`
- os três contratos devem expor dados derivados, não apenas brutos
- os três contratos devem continuar consumindo a base híbrida atual, sem exigir mudança estrutural no pipeline save + Lua

### Ordem Recomendada de Implementação

- primeiro `GET /news/feed/daily`
  - porque ele fecha a camada editorial
- depois `GET /dashboard/home`
  - porque passa a consumir o feed diário já pronto
- depois `GET /conference/context`
  - porque se beneficia de notícias, sinais e pressões já agregados

## Base Robusta Antes de Iniciar a Implementação

### Objetivo

- travar as peças mínimas para começar com segurança
- evitar retrabalho entre backend, feed, home e coletiva
- garantir coerência entre produto, dados e narrativa

### O Que Precisa Estar Fechado

- facts ledger
- builder editorial determinístico
- política de persistência editorial
- mapeamento campo -> fonte -> fallback
- recorte formal de MVP vs Fase 2

## Facts Ledger

### Objetivo

- transformar sinais dispersos em fatos canônicos reutilizáveis
- reduzir acoplamento direto do `news/feed/daily` com múltiplas fontes
- garantir que home, notícias e coletiva usem a mesma base semântica

### Conceito

- um fato é a menor unidade narrativa confiável do sistema
- ele precisa representar algo que aconteceu ou que está acontecendo
- um fato nunca deve depender do frontend para ser interpretado

### Contrato do Fato

```json
{
  "fact_id": "string",
  "save_uid": "string",
  "game_date": "2026-03-29",
  "fact_type": "important_win",
  "category": "match|form|locker_room|board|market|medical|player|season",
  "title": "Botafogo vence confronto direto",
  "summary": "Vitória fortalece a leitura pública de recuperação.",
  "importance": 90,
  "confidence": 0.95,
  "status": "active|resolved|historical",
  "entities": {
    "club_ids": [517],
    "player_ids": [244364],
    "staff_labels": ["manager"],
    "competition_ids": [1663]
  },
  "source_refs": [
    {
      "source": "events_recent",
      "ref_id": "123"
    }
  ],
  "signals": {
    "trend": "positive",
    "pressure_delta": -10,
    "morale_delta": 8,
    "media_heat": 72
  },
  "editorial_flags": {
    "eligible_for_news": true,
    "eligible_for_home": true,
    "eligible_for_conference": true,
    "dedupe_group": "match_2026-03-29_botafogo"
  },
  "created_at": "2026-03-25T20:30:00Z",
  "updated_at": "2026-03-25T20:30:00Z"
}
```

### Tipos de Fato do MVP

- `important_win`
- `important_loss`
- `positive_streak`
- `winless_streak`
- `board_pressure_active`
- `board_ultimatum_active`
- `key_player_in_form`
- `reserve_frustrated`
- `critical_injury`
- `return_from_injury`
- `market_offer_strong`
- `market_rumor_hot`
- `locker_room_tension`
- `tactical_identity_shift`
- `season_arc_milestone`

### Fontes de Origem do Facts Ledger

- `events_recent`
- `timeline_recent`
- `market_rumors_recent`
- `career_management_state`
- `player_relations_recent`
- `board_active_challenge`
- `crisis_active_arc`
- `season_arc_active`
- `state.fixtures`
- `state.standings`
- `state.squad`

### Regras Operacionais

- fatos são derivados no backend
- fatos iguais devem cair no mesmo `dedupe_group`
- fatos sem impacto prático não entram no ledger do MVP
- fatos devem ser marcados com elegibilidade por superfície:
  - notícia
  - home
  - coletiva
- um fato pode permanecer ativo por mais de um dia se ainda estiver relevante

### Persistência Recomendada

- criar uma tabela dedicada de fatos normalizados

```json
{
  "table": "career_facts",
  "keys": [
    "id",
    "save_uid",
    "game_date",
    "fact_type",
    "category",
    "importance",
    "confidence",
    "status",
    "title",
    "summary",
    "entities_json",
    "source_refs_json",
    "signals_json",
    "editorial_flags_json",
    "created_at",
    "updated_at"
  ]
}
```

## Builder Editorial Determinístico

### Objetivo

- decidir quais fatos viram matéria
- escolher slot editorial
- evitar repetição e ruído
- manter consistência entre chamadas

### Entradas

- `career_facts` do `save_uid` e `game_date`
- `coach_profile`
- `career_management_state`
- `board_active_challenge`
- `crisis_active_arc`
- `season_arc_active`

### Saída

- pacote editorial do dia consumido por `news/feed/daily`

### Pipeline

- coletar fatos elegíveis
- deduplicar por `dedupe_group`
- ranquear por prioridade editorial
- preencher slots
- renderizar matérias
- persistir pacote final

### Ranking Base

- primeiro por `importance`
- depois por `confidence`
- depois por aderência ao slot
- depois por recência

### Slots do MVP

- `lead`
- `backstage`
- `analysis`
- `market`
- `environment`

### Regras por Slot

- `lead`
  - exige fato de alto impacto
  - prioriza jogo, pressão, marco de temporada ou crise
- `backstage`
  - prioriza relações, vestiário, comissão e insatisfação
- `analysis`
  - prioriza forma, identidade tática, sequência e leitura esportiva
- `market`
  - prioriza oferta, rumor forte e necessidade de reposição
- `environment`
  - prioriza diretoria, torcida, imprensa e clima institucional

### Regras de Dedupe

- não repetir o mesmo `dedupe_group` em mais de uma matéria
- se um fato dominar o `lead`, os demais slots só podem usar fatos correlatos se o foco mudar
- matérias com impacto `low` não podem ocupar `lead`

### Regras de Qualidade

- o pacote diário deve ter no máximo 5 matérias
- pode ter menos de 5 se a densidade real do dia for baixa
- cada matéria deve responder:
  - o que aconteceu
  - por que isso importa
  - o que isso muda no clube
- matérias do mesmo dia devem preservar ordem estável entre requests

### Renderização das Matérias

- `headline`
- `subheadline`
- `lead`
- `body[]`
- `why_it_matters`
- `club_effects[]`
- `tags[]`
- `entities`

### Recomendação de Implementação

- criar um builder puro e determinístico
- evitar geração aleatória no MVP
- IA entra só como enriquecimento posterior, nunca como seletor principal

## Política de Persistência Editorial

### Decisão Fechada

- o feed diário deve ser gerado e persistido por `save_uid + game_date`

### Motivos

- consistência narrativa
- performance
- histórico confiável
- menor risco de divergência entre home e coletiva

### Estratégia Recomendada

- no primeiro request do dia:
  - gerar facts
  - gerar pacote editorial
  - persistir
- nos requests seguintes:
  - servir pacote persistido
- permitir rebuild controlado somente quando:
  - `game_date` mudar
  - rebuild manual for solicitado
  - regra interna detectar pacote incompleto ou inválido

### Tabelas Recomendadas

```json
{
  "table": "news_daily_packages",
  "keys": [
    "id",
    "save_uid",
    "game_date",
    "edition_label",
    "lead_angle",
    "density_level",
    "stories_count",
    "layout_hints_json",
    "created_at",
    "updated_at"
  ]
}
```

```json
{
  "table": "news_daily_articles",
  "keys": [
    "id",
    "package_id",
    "save_uid",
    "game_date",
    "slot",
    "kind",
    "priority",
    "impact",
    "headline",
    "subheadline",
    "lead",
    "body_json",
    "why_it_matters",
    "club_effects_json",
    "tags_json",
    "entities_json",
    "source_facts_json",
    "cover_image_url",
    "published_at",
    "created_at",
    "updated_at"
  ]
}
```

### Regras de Invalidação

- invalidar pacote quando `game_date` mudar
- invalidar pacote se a versão de contrato editorial mudar
- não invalidar automaticamente apenas por novos eventos menores no mesmo dia do save no MVP

## Mapeamento Campo -> Fonte -> Fallback

### Campos Críticos do MVP

| Campo | Fonte principal | Fallback | Transformação |
| --- | --- | --- | --- |
| `dashboard.home.hero_panel.next_fixture` | `state.fixtures` | `news/feed/daily.lead` para narrativa complementar | escolher próximo jogo do user team |
| `dashboard.home.hero_panel.recent_form` | `state.fixtures` | `career_facts` de sequência | converter resultados em `W/D/L` e pontos |
| `dashboard.home.club_health.locker_room_score` | `career_management_state.locker_room.cohesion` | `trust_avg` | normalizar para 0-100 |
| `dashboard.home.club_health.fan_sentiment_score` | `coach_profile.fan_sentiment_score` | `coach_profile.reputation_score` | nenhum |
| `dashboard.home.club_health.board_confidence_score` | derivado de `board_active_challenge` + `coach_profile.reputation_score` | `coach_profile.reputation_score` | calcular índice sintético |
| `dashboard.home.club_health.injury_risk_score` | `career_management_state.medical.injury_risk_index` | `injured_count` | normalizar para 0-100 |
| `dashboard.home.club_health.financial_pressure_score` | `career_management_state.finance.cash_pressure_index` | `wage_utilization` | normalizar para 0-100 |
| `dashboard.home.alerts` | `board_active_challenge`, `crisis_active_arc`, `career_management_state`, `market_rumors_recent` | `timeline_recent` | ordenar por severidade |
| `news.feed.daily.stories` | `career_facts` | `timeline_recent` apenas para preencher hooks | renderizar por slot |
| `conference.context.hot_topics` | `career_facts` | `board_active_challenge`, `market_rumors_recent`, `player_relations_recent` | ranquear por relevância |
| `conference.context.questions` | `hot_topics` | regras por modo (`pre_match`, `post_match`) | gerar texto fixo por tipo de tema |
| `conference.context.pressure_map.board` | `board_active_challenge` | `coach_profile.reputation_score` | label + score |
| `conference.context.pressure_map.locker_room` | `career_management_state.locker_room` | `player_relations_recent` | agregar confiança/frustração |

### Regra de Fonte

- usar dado já agregado antes de consultar camadas mais baixas
- o builder não deve abrir exceções por falta de um campo secundário
- toda falta deve cair em fallback conhecido e documentado

## Escopo Fechado do MVP

### MVP Obrigatório

- `build_news_feed_daily`
- rota `GET /news/feed/daily`
- persistência editorial diária
- `build_dashboard_home`
- rota `GET /dashboard/home`
- notícia fullscreen
- `build_conference_context`
- rota `GET /conference/context`
- facts ledger do MVP
- mapeamento documentado de campos críticos

### MVP Não Inclui

- jornalistas com personalidade
- estilos editoriais por veículo
- rumor com múltiplos graus de fonte
- especiais semanais
- especiais de clássico
- dossiê profundo de jogador
- IA premium de escrita longa

### Fase 2

- jornalistas/personas
- rumor com credibilidade avançada
- dossiês
- especiais
- resumos semanais
- memória editorial mais rica
- enriquecimento pontual por IA em matérias premium

## Checklist de Prontidão para Começar

### Obrigatório

- contrato de `news/feed/daily` fechado
- contrato de `dashboard/home` fechado
- contrato de `conference/context` fechado
- facts ledger do MVP fechado
- persistência editorial fechada
- mapeamento campo -> fonte -> fallback fechado
- escopo do MVP congelado

### Recomendável

- tabela de severidade comum para alertas
- helpers utilitários para:
  - próximo jogo
  - forma recente
  - labels de clima
  - prioridade editorial
- endpoint de rebuild manual do pacote diário

### Pode Esperar Fase 2

- IA rica de escrita
- múltiplos tons editoriais por jornal
- imagem temática sofisticada
- simulação de ecos sociais mais avançada

## Decisão Final para Início Seguro

- já é seguro iniciar a modernização do app
- o início seguro depende de implementar primeiro:
  - facts ledger do MVP
  - builder editorial determinístico
  - persistência do pacote diário
- depois disso:
  - `dashboard/home` fica simples
  - `conference/context` fica muito mais consistente

## Mapeamento de Aproveitamento por Tela

### Home

- `state.meta`
- `state.club`
- `coach_profile`
- `board_active_challenge`
- `crisis_active_arc`
- `season_arc_active`
- `timeline_recent`
- `events_recent`
- futuro `dashboard/home`

### Notícias

- `timeline_recent`
- `market_rumors_recent`
- `external_events_recent`
- `events_recent`
- `editorial_engine` expandido
- futuro `news/feed/daily`

### Clube

- `club`
- `manager`
- `career_management_state`
- `finance_ledger_recent`
- `season_arc_active`
- `coach_profile`

### Elenco

- `state.squad`
- `player_relations_recent`
- `injuries`
- `transfer_offers`
- sinais futuros do `career_dynamics_engine`

### Partidas

- `fixtures`
- `standings`
- `events_recent`
- `season_stats`

### Mercado

- `transfer_offers`
- `transfer_history_dataset`
- `market_rumors_recent`
- `finance_ledger_recent`

### Bastidores

- `career_management_state`
- `player_relations_recent`
- `crisis_active_arc`
- `board_active_challenge`
- `coach_profile`

### Coletivas

- `press-conference/recent`
- `coach_profile`
- `board_active_challenge`
- `crisis_active_arc`
- `events_recent`
- `news/feed/daily`

### Timeline

- `timeline_recent`
- `season_arc_active`
- `season_payoffs_recent`
- `legacy_profile`
- `hall_of_fame_entries`
- `achievements_recent`

## Fases Recomendadas de Implementação

### Fase 1: Fundação de Experiência

- home premium
- read model da home
- feed diário com até 5 matérias
- tela fullscreen de notícia
- pipeline editorial baseado em regras

Resultado esperado:

- primeira versão do app já parece produto premium

### Fase 2: Profundidade Sistêmica

- bastidores
- relações
- conferências contextuais
- radars de controle
- efeitos mais fortes de clima e pressão

Resultado esperado:

- o usuário sente que gere pessoas e ambiente, não só partidas

### Fase 3: Sofisticação e Memória

- jornalistas com personalidade
- rumores com credibilidade
- especiais semanais
- especiais de clássico
- dossiê de jogador
- IA pontual em matérias premium

Resultado esperado:

- carreira com identidade editorial própria e memória longa

## Riscos e Mitigações

### Risco 1: IA exagerada

Mitigação:

- fatos primeiro
- motor sistêmico depois
- IA apenas para acabamento

### Risco 2: excesso de notícia

Mitigação:

- máximo de 5 matérias por dia
- aceitar menos quando o dia estiver fraco
- forte descarte de repetição

### Risco 3: contradição narrativa

Mitigação:

- facts ledger como camada obrigatória
- objetos editoriais vinculados a fatos
- estado esportivo e bastidores compartilhando a mesma base

### Risco 4: quebrar backend atual

Mitigação:

- preservar contratos existentes
- adicionar camadas por agregação
- não reescrever o pipeline híbrido

## Decisões Fechadas

- o frontend seguirá o modelo premium descrito neste documento
- a arquitetura de dados continua híbrida
- save é fonte principal
- Live Editor é fallback e enriquecimento
- Python continua responsável pelo trabalho pesado
- a evolução nova deve respeitar e reutilizar o backend atual
- a camada editorial será construída sobre facts ledger + motor sistêmico + IA pontual

## Próximo Passo Técnico Recomendado

- criar o read model `dashboard/home`
- criar o read model `news/feed/daily`
- evoluir `editorial_engine.py` para gerar pautas e não apenas entradas curtas
- criar uma estrutura persistente para artigos editoriais diários por `save_uid` e `game_date`
- criar um agregador de contexto para conferências
- só depois plugar as telas do front sobre esses contratos estáveis
