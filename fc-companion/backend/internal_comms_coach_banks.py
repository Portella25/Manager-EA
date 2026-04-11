"""
Opções de resposta do treinador para comunicação interna — muitas variantes por tom/audiência,
com âncora no texto do NPC e no contexto (tabela, jogo, clube) para reduzir repetição.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Protocol, Sequence


def _h(seed: str) -> int:
    return int(hashlib.md5(seed.encode("utf-8")).hexdigest()[:8], 16)


def _pick_idx(options: Sequence[str], seed: str) -> int:
    if not options:
        return 0
    return _h(seed) % len(options)


def _pick_variant(options: Sequence[str], seed: str) -> str:
    if not options:
        return ""
    return options[_pick_idx(options, seed)]


def _truncate(s: str, n: int = 120) -> str:
    t = (s or "").strip().replace("\n", " ")
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


class CoachCtx(Protocol):
    club: str
    next_h: str
    next_a: str
    next_comp: str
    last_score: str
    last_letter: str
    rank: Optional[int]
    pts: Optional[int]
    table_comp: str
    board_pressure: bool
    crisis: bool
    captain: str
    focus_player: str
    mode: str
    player_trust: Optional[int]
    player_frustration: Optional[int]


def _opp(ctx: CoachCtx) -> str:
    if ctx.next_h and ctx.next_a:
        return f"{ctx.next_h} x {ctx.next_a}"
    return "o próximo jogo"


def _tbl(ctx: CoachCtx) -> str:
    if ctx.rank is not None and ctx.pts is not None and ctx.table_comp:
        return f"Na {ctx.table_comp}, estamos na {ctx.rank}ª colocação com {ctx.pts} pontos — "
    return ""


def _npc_anchor(npc_text: str, max_words: int = 14) -> str:
    t = _truncate(npc_text, 140)
    w = t.split()
    if len(w) <= max_words:
        return t
    return " ".join(w[:max_words]) + "…"


def _dynamic_echo(ctx: CoachCtx, npc_text: str, tone: str) -> List[str]:
    """Frases que ecoam o que o interlocutor acabou de dizer (curtas)."""
    stub = _npc_anchor(npc_text, 12)
    if len(stub) < 18:
        return []
    opp = _opp(ctx)
    c = ctx.club
    if tone == "aggressive":
        return [
            f"Pelo que você trouxe agora («{stub}»), meu recado é um só: em {opp} a cobrança do {c} não pode oscilar.",
            f"Em cima do que você falou («{stub}»), não tem meio-termo: ou fecha o combinado ou a gente recalibra forte.",
        ]
    if tone == "calm":
        return [
            f"Ouvindo você («{stub}»), eu respondo com calma: vamos separar o que é urgente do que é barulho antes de {opp}.",
            f"Sobre o que você colocou («{stub}»), minha prioridade é alinhar expectativa sem estourar o grupo.",
        ]
    if tone == "motivational":
        return [
            f"Do jeito que você falou («{stub}»), dá pra transformar isso em energia pra {opp} — com o {c} fechado.",
            f"Pelo tom da conversa («{stub}»), quero botar todo mundo na mesma página pra ir pra {opp} com confiança.",
        ]
    return [
        f"Traduzindo o que você trouxe («{stub}») em plano: vídeo, carga e adversário de {opp} entram na mesma conta.",
        f"Pelo que você abriu («{stub}»), o que fecha pra mim é dado de treino + leitura clara pra {opp}.",
    ]


def _dedupe_pick(pools: List[str], seed: str, used: set) -> str:
    for salt in range(0, 40):
        cand = _pick_variant(pools, f"{seed}|{salt}")
        if cand not in used:
            used.add(cand)
            return cand
    cand = _pick_variant(pools, seed)
    used.add(cand)
    return cand


def build_coach_replies(
    ctx: CoachCtx,
    audience: str,
    interaction_mode: str,
    npc_text: str,
    seed: str,
) -> List[Dict[str, Any]]:
    """Quatro opções com tons fixos; textos variados e, quando possível, sem repetir frase na mesma rodada."""
    opp = _opp(ctx)
    tbl = _tbl(ctx)
    c = ctx.club
    cap = ctx.captain
    fn = (ctx.focus_player or "atleta").strip() or "atleta"
    comp = ctx.next_comp or "competição"
    npc_h = _h((npc_text or "")[:240])

    pools: Dict[str, List[str]] = {
        "aggressive": [],
        "calm": [],
        "motivational": [],
        "analytical": [],
    }

    # --- BOARD ---
    if audience == "board":
        pools["aggressive"].extend(
            [
                f"{tbl}Diretoria quer ver número e postura: ou o {c} fecha conta em {opp} e no campeonato, ou a gente senta e redesenha meta sem discurso que não bate com planilha.",
                f"{tbl}Cobrança máxima: o que eu vendo pra mesa é trabalho e critério; o que eu cobro de volta é suporte real e orçamento que não vira ficção.",
                f"Sem enrolação com conselho e torcida organizada: ou a gente alinha prioridade agora ou cada um puxa o {c} pra um lado e o clube perde tempo.",
                f"{tbl}Pra presidência, o recado é claro: resultado com gestão. Promessa bonita sem caixa vira problema meu, seu e do sócio.",
                f"O {c} não pode brigar em duas frentes ao mesmo tempo — ou fecha narrativa de título ou estabiliza o barco; me diz onde tá o teto de risco.",
                f"{tbl}Se a diretoria quer G4, título ou sobrevivência financeira, isso tem que estar escrito — senão virou palestra.",
                f"Transparência total: calendário apertado, cobrança alta. Eu entrego plano esportivo; preciso de resposta na mesma moeda.",
                f"{tbl}Não vou empurrar promessa de palco: o combinado tem que aparecer em dado, em elenco e em caixa.",
                f"Ultimato ou não, o {c} precisa de decisão — não dá pra ficar no 'vamos ver' com torcida e patrocinador em cima.",
                f"{tbl}Quem manda na associação quer ver título ou sobrevivência — escolhe o discurso e eu executo o esportivo em cima disso.",
            ]
        )
        pools["calm"].extend(
            [
                f"{tbl}Vamos com calma, mas com trilho: resultado com governança. Eu trago marcos claros; a diretoria cobra, mas também libera o que dá no Brasil de hoje.",
                f"Ouço a pressão de cima — minha resposta é processo, comunicação interna e decisão técnica com critério. Bastidor barulhento derruba elenco.",
                f"Prefiro alinhamento de médio prazo: evolução em campo + sustentabilidade, sem vender ilusão que estoura no fim do ano.",
                f"{tbl}A gente constrói ponte: eu mostro plano esportivo com risco mapeado; vocês mostram onde o {c} pode investir de verdade.",
                f"Ruído institucional atrapalha vestiário — minha linha é fechar prioridade em reunião e executar no CT sem ficar mudando a história toda semana.",
                f"{tbl}Posso ouvir todo mundo, mas decisão técnica é uma: critério, transparência com o grupo e calendário realista.",
                f"O que eu não faço é prometer título com elenco curto e caixa curto — a gente combina meta possível e trabalha pesado em cima disso.",
                f"{tbl}Se a diretoria quer marca forte, isso passa por organização no dia a dia — não só por slogan.",
                f"Vamos separar o que é urgente do que é importante: às vezes segurar o resultado já é vitória no brasileiro.",
                f"{tbl}Meu compromisso é técnico e mensurável; o retorno eu espero em suporte e clareza de orçamento.",
            ]
        )
        pools["motivational"].extend(
            [
                f"{tbl}O {c} tem torcida e história pra brigar — minha missão é dar ambiente profissional e ambição todo dia. Isso atrai parceiro e fortalece marca.",
                f"Quero ver o clube com espírito de time grande: CT organizado, calendário encarado de frente, respeito à camisa.",
                f"Confiança se traduz em trabalho e resultado — é isso que eu levo pra mesa, sem atalho.",
                f"{tbl}Dá pra sonhar alto com os pés no chão: vamos levantar o nível sem perder a identidade do {c}.",
                f"A torcida cobra, a diretoria cobra — e o elenco precisa sentir que tem projeto vivo, não só cobrança solta.",
                f"{tbl}Quero energia de quem acredita no processo: vitória vira combustível, derrota vira ajuste — sem desmontar o grupo na primeira crise.",
                f"O {c} precisa de narrativa de orgulho — dentro e fora de campo — e isso se constrói com entrega diária.",
                f"{tbl}Minha mensagem pra cima é ambiciosa, mas realista: competir de igual pra cima com quem tiver na frente.",
                f"Vamos botar o clube de volta no mapa com trabalho sério — resultado vem como consequência.",
                f"{tbl}Time que se organiza, aguenta pressão; é isso que eu quero vender pra dentro e pra fora.",
            ]
        )
        pools["analytical"].extend(
            [
                f"{tbl}Minha leitura é de gestão: risco de elenco, janela, desempenho esperado, projeção de pontos — decisão técnica com dado, não com impulso.",
                f"Separo discurso de performance: o que dá pra medir no treino e no jogo é o que entra na conversa com o conselho.",
                f"Financeiro e esportivo andam juntos — sem sustentabilidade não tem projeto de título no futebol brasileiro.",
                f"{tbl}Pra {opp}, o plano tem etapas: transição, bola parada, perfil do adversário — tudo documentado pra não virar achismo.",
                f"O que eu levo pra diretoria é cenário: melhor caso, pior caso, e gatilho de decisão se o resultado não vier.",
                f"{tbl}Indicador que não fecha, a gente recalibra — sem narrativa fácil nem culpar o vento.",
                f"Gestão de elenco é gestão de risco: minutos, lesão, idade, valor — isso conversa com orçamento.",
                f"{tbl}Leitura fria: onde o {c} ganha xG, onde perde duelo, onde toma gol — isso guia o que peço de reforço.",
                f"Projeção de pontos não é promessa — é intervalo de confiança com base no que o grupo mostrou.",
                f"{tbl}Decisão embasada em dado reduz ruído com torcida e com patrocinador — é o que eu defendo.",
            ]
        )
        if ctx.board_pressure:
            for k in pools:
                pools[k].append(
                    f"Com a pressão que tá em cima da presidência, eu fecho o discurso em entrega e transparência — o {c} não pode parecer perdido."
                )
        if ctx.crisis:
            for k in pools:
                pools[k].append(
                    f"Em momento de crise, prioridade é um eixo só: o {c} não pode ter três narrativas diferentes ao mesmo tempo."
                )

    # --- STAFF ---
    elif audience == "staff":
        pools["aggressive"].extend(
            [
                f"Quero microciclo fechado pra {opp}: sem treino genérico, sem planilha bonita que não bate com o que o DM liberou.",
                f"Sem meia medida em vídeo e campo — ou o grupo entrega o combinado ou a gente corrige na hora, sem conversa mole.",
                f"Cobrança total da comissão: prazo, alinhamento e uma voz só. Divergência técnica vocês resolvem entre vocês e trazem posição única pra mim.",
                f"Pra {comp}, eu quero leitura de adversário com nome e sobrenome — não resumo genérico.",
                f"O treino de hoje tem que conversar com o jogo de amanhã; não quero treino 'pra gastar tempo'.",
                f"Se o DM barrou carga, o campo respeita — e o vídeo tem que refletir isso, sem fantasia.",
                f"Cobrança em cima de cada setor: preparação, análise, recuperação — tudo integrado.",
                f"Quero relatório que eu consiga defender na preleção — não texto que parece TCC.",
                f"Pra {opp}, prioridade é clareza: o que é inegociável no modelo de jogo e o que é ajuste fino.",
                f"Sem desculpa de 'faltou tempo': calendário apertado é regra no Brasil — a comissão precisa rodar afinada.",
            ]
        )
        pools["calm"].extend(
            [
                f"Vamos alinhar com método: prioridades de bloco, indicadores e o que pode esperar de cada sessão — preciso de segurança no relatório pra decidir com o elenco.",
                f"Ouço técnico e DM; a decisão final é minha, mas quero consenso sobre risco e carga — transparência evita lesão e ruído.",
                f"O CT tem que respirar profissionalismo: conversa franca, teste claro, vídeo objetivo — é assim que aguenta calendário brasileiro.",
                f"Pra {opp}, vamos separar o que é ajuste fino do que é mudança estrutural — sem misturar as duas coisas.",
                f"Quero plano B documentado: se o titular cair, quem entra e com qual função — sem improviso na véspera.",
                f"Descanso e intensidade têm que conversar — não adianta estourar no rachão e chegar morto no apito.",
                f"Comissão alinhada reduz atrito com jogador — todo mundo falando a mesma língua no vestiário.",
                f"Prioridade é saúde do grupo: DM manda, a gente adapta treino sem drama.",
                f"Quero vídeo curto e cirúrgico — jogador absorve melhor do que sessão interminável.",
                f"Pra essa semana, foquemos no que o adversário mais castigou nos últimos jogos — dado na mesa.",
            ]
        )
        pools["motivational"].extend(
            [
                f"Quero energia técnica: comissão afiada, jogador entendendo o plano e execução repetível — é assim que aguenta pressão e calendário.",
                f"Time que ganha é time que treina com intenção — vamos subir o nível do dia a dia sem perder o pé no chão.",
                f"Confiança no processo: cada um no seu papel, vídeo alinhado, campo com intensidade certa.",
                f"Pra {opp}, quero ver staff com fome de detalhe — é no detalhe que o brasileiro costuma punir.",
                f"Vamos levantar o padrão do trabalho diário: treino com competição interna saudável.",
                f"Comissão unida passa segurança pro elenco — isso vira resultado.",
                f"Quero ver o CT vibrando profissionalismo, não só correndo por correr.",
                f"Energia certa no rachão, foco no vídeo — sem desperdício de sessão.",
                f"Pra {comp}, temos tudo pra fazer um jogo inteligente — mão na massa.",
                f"Trabalho sério atrai resultado; é isso que eu espero de cada setor.",
            ]
        )
        pools["analytical"].extend(
            [
                f"Critério: carga, vídeo do adversário e sinal fisiológico — titularidade sai disso, não de feeling.",
                f"Vamos medir o que importa: transição, bola parada, duelo aéreo — e ajustar treino conforme o padrão do adversário.",
                f"Processo manda: microciclo coerente com DM e com o que o elenco aguenta no Brasil.",
                f"Pra {opp}, quero mapa de pressão e saída — onde a gente ganha e onde pode tomar.",
                f"Separar ruído de dado: o que se repete no treino é o que entra na preleção.",
                f"Indicador que não fecha, a gente recalibra — sem achismo e sem culpar o relvado.",
                f"Leitura de adversário com amostra grande o suficiente — não quero análise com dois jogos só.",
                f"Pra {comp}, ajuste fino de marcação e distância entre linhas — com números na mão.",
                f"Recuperação e treino têm que bater — senão vira lesão e desgaste emocional.",
                f"Quero relatório que una vídeo + dados + sensação do DM — decisão em cima disso.",
            ]
        )

    # --- PLAYERS GROUP ---
    elif audience == "players" and interaction_mode == "group":
        pools["aggressive"].extend(
            [
                f"{tbl}Ou a gente fecha o discurso em {opp} com competição de verdade, ou o vestiário vira grupo de WhatsApp. Quem não aguenta bronca, não fica à vontade.",
                f"{cap} representa a rapaziada: cobrança é no treino e no jogo. Quem tá incomodado com minuto, resolve com trabalho — não com indireta.",
                f"No futebol brasileiro, grupo que fecha junto aguenta torcida e diretoria — é isso que eu quero do {c}, sem estrelinha solta.",
                f"{tbl}Padrão alto: ou entrega ou não entra. Em {opp} não dá pra ter meia-intensidade.",
                f"Quero vestiário com hierarquia clara: quem manda em campo manda no exemplo, não no grito vazio.",
                f"{cap} sabe: time que se divide vira alvo fácil — ou fecha comigo ou a conversa é outra.",
                f"Cobrança é no olho também: início ruim, ajuste na hora — sem esperar virar novela.",
                f"O {c} não pode ter jogador passeando em campo — respeito com o grupo é lei.",
                f"{tbl}Pra {opp}, quero sangue no olho coletivo — não heroísmo individual.",
                f"Quem não comprar o processo, vai sentir — não tenho paciência pra sabotagem leve.",
            ]
        )
        pools["calm"].extend(
            [
                f"{tbl}A gente te ouve. O elenco precisa de clareza: critério de titular e respeito com quem entra e com quem fica de fora — sem humilhar ninguém.",
                f"O {c} é vestiário misturado: veterano e moleque. Vamos conversar com calma, mas com regra clara — hierarquia existe, tem que ser justa.",
                f"Prefiro alinhamento do que gritaria: problema puxa na sala antes de estourar em campo.",
                f"{tbl}Pra {opp}, quero mensagem única: todo mundo sabe o papel e o que o adversário mais explora.",
                f"Respeito mútuo é o mínimo — cobrança forte pode existir sem destruir o cara ao lado.",
                f"Quem tá fora hoje pode decidir amanhã — grupo precisa sentir isso.",
                f"{tbl}Vamos desacelerar o drama: foco no treino, foco no plano, foco no próximo passo.",
                f"Ambiente profissional não é ambiente frio — é ambiente com limite claro.",
                f"Ouço crítica quando vem com proposta — opinião vazia a gente deixa pra torcida nas redes.",
                f"Pra {opp}, quero vestiário fechado com a ideia de jogo — sem vazamento de desconfiança.",
            ]
        )
        pools["motivational"].extend(
            [
                f"{tbl}O bando quer sangue no olho pra {opp} — levanta poeira, mexe com quem precisa e bota o {c} pra cima de camisa.",
                f"Quero o grupo abraçando o momento: derrota vira lição, vitória vira combustível — é assim que aguenta o calendário.",
                f"Confiança se paga com entrega: quem corre por companheiro hoje ganha respeito amanhã.",
                f"{tbl}Pra {opp}, quero ver orgulho de vestir essa camisa — do primeiro ao último do banco.",
                f"Time que acredita no trabalho diário aguenta pressão — vamos provar isso em campo.",
                f"{cap} lidera com exemplo: energia contagia — quero ver isso no aquecimento até o apito final.",
                f"Vamos fazer o {c} incomodar — com intensidade e com união.",
                f"Vitória bonita é vitória coletiva — celebra junto, sofre junto, ajusta junto.",
                f"{tbl}Nada de cabeça baixa: próximo jogo já é chance de virar a chave.",
                f"Quero ver o vestiário com fogo, mas com controle — paixão com método.",
            ]
        )
        pools["analytical"].extend(
            [
                f"{tbl}Minha leitura é de grupo: encaixe tático, minutos e adversário — escalação conversa com plano de jogo, não com favoritismo.",
                f"Separando emoção de função: quem fecha o sistema, quem abre campo, quem fecha jogo — treinar até ficar automático.",
                f"Critério: treino repetível, vídeo alinhado, mensagem única pro vestiário — é o que segura resultado no Brasil.",
                f"Pra {opp}, o modelo tem que estar claro pros 11 e pros que entram depois — sem improviso de posição.",
                f"{tbl}Dado do adversário + dado nosso: é isso que define prioridade de pressão e saída.",
                f"Minutos não são prêmio — são função. Quem encaixa no plano joga.",
                f"Quero ver leitura compartilhada: lateral sabe o que o meia precisa, volante sabe linha de passe.",
                f"Pra {comp}, ajuste fino de transição — onde a gente perde bola e onde recupera.",
                f"Treino com repetição do cenário do jogo — não adianta simular o impossível.",
                f"{tbl}O que não tá funcionando, a gente muda com critério — sem mudar só por mudar.",
            ]
        )

    # --- PLAYERS 1:1 ---
    elif audience == "players" and interaction_mode == "one_on_one":
        pools["aggressive"].extend(
            [
                f"{fn}, sem rodeio: aqui é performance e postura. Cobrança é entrega e respeito ao grupo — bola não entra, atitude tem que estar em dia.",
                f"{fn}, ou você encaixa no que o {c} precisa em {opp}, ou a gente muda o tom da conversa sobre minuto — não tenho paciência pra meia-boca.",
                f"Cobrança individual: quero exemplo no treino todo dia — o vestiário te observa.",
                f"{fn}, o {c} não pode carregar quem não corresponde — em {opp} eu quero resposta em campo.",
                f"Sem drama: ou você fecha com o processo ou a gente redefine teu papel — simples assim.",
                f"{fn}, pressão eu sei que existe — mas desculpa fraca não entra no meu time.",
                f"Quero ver postura de quem quer carregar a camisa, não de quem quer só holofote.",
                f"{fn}, entrega abaixo do combinado vira conversa dura — e eu não vou maquiar isso.",
                f"Pra {opp}, ou você mostra porque tá em campo ou a disputa abre — futebol é isso.",
                f"{fn}, cobrança minha é clara: treino, comportamento, jogo — linha reta.",
            ]
        )
        pools["calm"].extend(
            [
                f"{fn}, quero te ouvir com calma. O que tá travando — confiança, minuto, barulho de fora — a gente desenha um caminho realista sem te jogar na fogueira.",
                f"{fn}, conversa de gente grande: me diz o que você precisa de mim e do clube pra render — sem vergonha.",
                f"Ambiente profissional: se tem algo incomodando, puxa comigo; solução passa por treino, gesto e alinhamento com o grupo.",
                f"{fn}, tô aberto a ouvir — mas preciso que você também escute o recado técnico.",
                f"Vamos separar o emocional do técnico: os dois existem, mas não podem se misturar demais.",
                f"{fn}, minuto é disputa — mas dignidade é regra. Ninguém aqui é peão.",
                f"Se a cabeça não tá legal, a gente aciona suporte — lesão mental também conta.",
                f"{fn}, quero que você se sinta parte do plano — me diz onde tá o incômodo.",
                f"Papo reto: o que você espera de mim nas próximas semanas?",
                f"{fn}, confiança se constrói nos detalhes — vamos alinhar isso com calma.",
            ]
        )
        pools["motivational"].extend(
            [
                f"{fn}, te coloco nesse papel porque acredito no teu potencial — vamos lapidar o que for preciso e mostrar em {opp} por que você veste essa camisa.",
                f"Quero ver você com fome e orgulho — o {c} precisa de jogador que abraça o momento.",
                f"{fn}, confiança se paga no detalhe: marcação, saída, último passe — é assim que vira referência.",
                f"Levanta a cabeça e bota foco: próximo jogo é tua chance de virar a página.",
                f"{fn}, o grupo precisa de você inteiro — vamos buscar isso junto.",
                f"Quero ver brilho no olho no treino — isso contagia o resto.",
                f"{fn}, teu talento precisa vir com consistência — aí ninguém tira você de campo.",
                f"Pra {opp}, quero ver você decisivo no teu quadrado — sem medo de errar tentando acertar.",
                f"{fn}, tamo no mesmo barco — derrota a gente divide, vitória também.",
                f"Vamos construir teu melhor momento com trabalho — sem atalho de mídia.",
            ]
        )
        pools["analytical"].extend(
            [
                f"{fn}, olhando frio: teu papel no modelo tá no vídeo; o adversário costuma atacar o espaço nas costas — ajustamos carga e leitura pra você render sem se queimar.",
                f"{fn}, separa ruído de performance: o dado que importa é o que repete no treino e aparece no vídeo — a partir daí fechamos minuto.",
                f"Critério tático e físico: onde você melhora o time e onde precisa de ajuda da comissão — é isso que vamos atacar.",
                f"{fn}, função em campo tem que estar clara — se precisar mudar, mudamos com plano.",
                f"Pra {opp}, leitura de duelo e apoio — quero ver teu mapa de calor alinhado com o que pedimos.",
                f"{fn}, ajuste de posicionamento pode destravar teu jogo — vamos trabalhar isso no campo reduzido.",
                f"Sem achismo: se o indicador não fecha, a gente muda estímulo no treino.",
                f"{fn}, adversário forte no teu lado? A gente dá suporte com cobertura — não é herói sozinho.",
                f"Pra {comp}, quero ver teu impacto mensurável — desarme, último passe, finalização, conforme teu papel.",
                f"{fn}, fadiga aparece no vídeo antes de aparecer no DM — vamos antecipar.",
            ]
        )
        # tom do relacionamento
        if ctx.player_trust is not None and ctx.player_frustration is not None:
            if ctx.player_frustration >= 52 or (ctx.player_trust is not None and ctx.player_trust <= 42):
                for k in pools:
                    pools[k].append(
                        f"{fn}, sei que o clima não tá fácil — mesmo assim precisamos de clareza e respeito mútuo pra não piorar o ambiente."
                    )
            elif ctx.player_trust is not None and ctx.player_trust >= 68 and ctx.player_frustration <= 36:
                for k in pools:
                    pools[k].append(
                        f"{fn}, a gente já tem uma boa sintonia — vamos usar isso pra afinar o que falta em {opp}."
                    )

    # --- fallback (não deveria acontecer) ---
    else:
        for tone_key in pools:
            pools[tone_key].extend(
                [
                    f"{tbl}Foco total em {opp}: padrão do {c} alto, comunicação clara e entrega em campo.",
                    f"Vamos com método e respeito — resultado vem de processo repetível.",
                    f"Confiança se paga com trabalho; cobrança vem com critério.",
                    f"Leitura técnica + grupo fechado — é o que sustenta no brasileiro.",
                ]
            )

    # Eco do NPC + enriquecimento por hash do texto
    for tone_key in ("aggressive", "calm", "motivational", "analytical"):
        pools[tone_key].extend(_dynamic_echo(ctx, npc_text, tone_key))

    order = [
        ("aggressive", "aggressive"),
        ("calm", "calm"),
        ("motivational", "motivational"),
        ("analytical", "analytical"),
    ]
    out: List[Dict[str, Any]] = []
    used: set = set()
    for ui, (tone_label, key) in enumerate(order):
        p = [x for x in pools[key] if x and len(x.strip()) > 10]
        if not p:
            p = [f"{tbl}Vamos com foco em {opp} e com o {c} alinhado."]
        sub = f"{seed}|{audience}|{interaction_mode}|{tone_label}|{ui}|npc:{npc_h}"
        text = _dedupe_pick(p, sub, used)
        out.append({"tone": tone_label, "text": text})
    return out
