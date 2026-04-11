"""Diálogos de comunicação interna (diretoria, elenco, comissão, 1:1) — tom Brasil, variação por seed."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from database import get_active_board_challenge, get_active_crisis_arc, get_player_relation
from internal_comms_coach_banks import build_coach_replies
from internal_comms_lock import is_internal_comms_locked_for_date
from front_read_models import (
    _competition_name_index,
    _decorate_fixture,
    _game_date_value,
    _iso_game_date,
    _last_completed_fixture,
    _manager_name,
    _next_fixture,
    _player_name,
    _read_state,
    _select_primary_league_table,
    _to_int,
    _user_team_id,
)


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


@dataclass
class _Ctx:
    club: str
    manager: str
    mode: str  # pre_match | post_match | generic
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
    linked_line: str
    touch_ctx: str
    game_date: str
    player_trust: Optional[int]
    player_frustration: Optional[int]


def _captain_name(squad: List[Dict[str, Any]]) -> str:
    if not squad:
        return "o grupo"
    best = max(squad, key=lambda p: (_to_int(p.get("overall"), 0), _to_int(p.get("form"), 0)))
    return _player_name(dict(best))


def _load_ctx(
    save_uid: str,
    focus_player_name: Optional[str],
    linked_headline: Optional[str],
    touchpoint_context: Optional[str],
    focus_player_id: Optional[int] = None,
    interaction_mode: str = "group",
) -> _Ctx:
    state = _read_state()
    club = str((state.get("club") or {}).get("team_name") or "Clube")
    manager = _manager_name(dict(state.get("manager") or {}))
    uid = _user_team_id(state)
    comp = _competition_name_index(save_uid)
    raw = _game_date_value(state)
    fixtures = list(state.get("fixtures") or [])
    squad = list(state.get("squad") or [])
    nf = _decorate_fixture(_next_fixture(fixtures, uid, raw), uid, comp) if uid else None
    lf = _decorate_fixture(_last_completed_fixture(fixtures, uid), uid, comp) if uid else None
    tbl = _select_primary_league_table(state, uid, nf, comp) if uid else None
    next_h = str((nf or {}).get("home_team_name") or "")
    next_a = str((nf or {}).get("away_team_name") or "")
    next_comp = str((nf or {}).get("competition_name") or "")
    hs = lf.get("home_score") if lf else None
    aws = lf.get("away_score") if lf else None
    last_score = f"{hs}×{aws}" if hs is not None and aws is not None else ""
    last_l = ""
    if lf and uid:
        hid = _to_int(lf.get("home_team_id"), 0)
        u = _to_int(lf.get("home_score"), 0)
        v = _to_int(lf.get("away_score"), 0)
        if hid == uid:
            last_l = "W" if u > v else ("D" if u == v else "L")
        else:
            last_l = "W" if v > u else ("D" if u == v else "L")
    mode = "generic"
    if nf:
        mode = "pre_match"
    elif lf:
        mode = "post_match"

    board = get_active_board_challenge(save_uid, "ULTIMATUM") if save_uid else None
    crisis = bool(get_active_crisis_arc(save_uid)) if save_uid else False
    p_trust: Optional[int] = None
    p_fr: Optional[int] = None
    if save_uid and focus_player_id and str(interaction_mode).lower() == "one_on_one":
        rel = get_player_relation(save_uid, int(focus_player_id))
        if rel:
            p_trust = _to_int(rel.get("trust"), 50)
            p_fr = _to_int(rel.get("frustration"), 0)
    rk = tbl.get("rank") if tbl else None
    pts = tbl.get("points") if tbl else None
    tcomp = str((tbl or {}).get("competition_name") or "")
    return _Ctx(
        club=club,
        manager=manager,
        mode=mode,
        next_h=next_h,
        next_a=next_a,
        next_comp=next_comp,
        last_score=last_score,
        last_letter=last_l,
        rank=rk if isinstance(rk, int) else (int(rk) if rk is not None else None),
        pts=pts if isinstance(pts, int) else (int(pts) if pts is not None else None),
        table_comp=tcomp,
        board_pressure=bool(board),
        crisis=crisis,
        captain=_captain_name(squad),
        focus_player=(focus_player_name or "").strip() or "atleta",
        linked_line=(linked_headline or "").strip(),
        touch_ctx=(touchpoint_context or "").strip(),
        game_date=_iso_game_date(state),
        player_trust=p_trust,
        player_frustration=p_fr,
    )


def _npc_open_board(ctx: _Ctx, seed: str) -> str:
    opp = f"{ctx.next_h} x {ctx.next_a}" if ctx.next_h and ctx.next_a else "o próximo compromisso"
    stake = (
        "O pessoal da presidência tá sendo cobrado na associação e nas redes — a gente precisa de narrativa de resultado e de projeto."
        if ctx.board_pressure
        else "A gente quer te ouvir com clareza, sem ruído com assessoria nem entrevista armada."
    )
    v_pre = [
        (
            f"Mister, te peguei antes da bola rolar. Sobre {opp}, como é que o {ctx.club} equilibra o que a diretoria quer "
            f"com o que dá pra mostrar em campo sem prometer o que o caixa não aguenta? {stake}"
        ),
        (
            f"Bom te achar agora. Em cima de {opp}, qual é o recorte que a gente leva pra reunião da diretoria: título, G4 ou pé no chão financeiro? "
            f"Preciso de número na mão, não de discurso bonito."
        ),
        (
            f"Mister, vamos direto: à véspera de {opp}, onde você coloca o teto de risco se o resultado não vier? "
            f"O {ctx.club} não pode se meter em duas briga ao mesmo tempo."
        ),
    ]
    v_post = [
        (
            f"Mister, depois do {ctx.last_score}, a leitura lá de cima é de {ctx.last_letter or '—'}. "
            f"O que muda no teu discurso pras próximas 48h — confiança renovada ou plano B na mesa?"
        ),
        (
            f"Com o placar na mesa, como você traduz isso pra gestão? Preciso saber o que passar pro conselho sem parecer que tô inventando moda."
        ),
        (
            f"Pós-jogo: o {ctx.club} precisa mostrar controle de crise ou segurar a narrativa? Me diz numa frase o que fecha a conta com a diretoria."
        ),
    ]
    v_gen = [
        (
            f"Mister, no ritmo maluco do calendário brasileiro, onde você acha que o {ctx.club} mais precisa alinhar o que rola por dentro com o que a torcida cobra lá fora?"
        ),
        (
            f"A gente tá de olho no CT e na imagem do clube. Qual é a prioridade número um pra você neste mês — resultado, elenco ou grana?"
        ),
    ]
    if ctx.mode == "pre_match" and ctx.next_h:
        return _pick_variant(v_pre, seed + ":board:pre")
    if ctx.mode == "post_match" and ctx.last_score:
        return _pick_variant(v_post, seed + ":board:post")
    return _pick_variant(v_gen, seed + ":board:gen")


def _npc_open_staff(ctx: _Ctx, seed: str) -> str:
    comp = ctx.next_comp or "competição"
    opp = f"{ctx.next_h} x {ctx.next_a}" if ctx.next_h and ctx.next_a else "o adversário"
    v_pre = [
        (
            f"Mister, fechando o microciclo pra {opp}: onde você quer ajuste fino no vídeo — transição ou bola parada? "
            f"O DM já me passou o que pode e o que não pode no treino de hoje."
        ),
        (
            f"Professor, time técnico na mesa: pra {comp}, qual é o sacrifício que você topa entre minutos de titular e carga no joelho do grupo?"
        ),
        (
            f"Antes de {opp}, preciso alinhar contigo: a ideia é intensidade no rachão ou poupar perna pro apito? A comissão tá dividida."
        ),
    ]
    v_post = [
        (
            f"Pós-{ctx.last_score}: o que a gente tira de dado objetivo pro relatório interno? Pressão alta, xG, duelo — o que manda na próxima semana?"
        ),
        (
            f"Mister, em cima do resultado, onde você viu o plano de jogo fugir da execução? Fala a língua da comissão, não de entrevista coletiva."
        ),
    ]
    v_gen = [
        (
            f"No dia a dia do CT no Brasil, o gargalo costuma ser viagem, calor e calendário apertado. Onde você quer que a gente proteja o grupo sem perder competitividade?"
        ),
    ]
    if ctx.mode == "pre_match" and ctx.next_h:
        return _pick_variant(v_pre, seed + ":staff:pre")
    if ctx.mode == "post_match":
        return _pick_variant(v_post + v_gen, seed + ":staff:post")
    return _pick_variant(v_gen + v_pre, seed + ":staff:gen")


def _npc_open_squad_group(ctx: _Ctx, seed: str) -> str:
    cap = ctx.captain
    opp = f"{ctx.next_h} x {ctx.next_a}" if ctx.next_h and ctx.next_a else "o próximo jogo"
    v_pre = [
        (
            f"Mister, aqui é o {cap} falando pelo grupo. Antes de {opp}, o vestiário tá te ouvindo, "
            f"mas a gente precisa saber: cobrança é no olho ou no gesto? O time sente quando é treinador ou quando é patrão."
        ),
        (
            f"Professor, o bando tá fechado, mas rola aquele burburinho de minuto e titular. "
            f"Pra {opp}, você fecha a escala cedo ou deixa a disputa aberta até o último treino?"
        ),
        (
            f"Capitão aqui. O elenco quer resultado, mas também respeito. O que você não abre mão nessa reta — caneta ou conversa?"
        ),
    ]
    v_post = [
        (
            f"Mister, depois do {ctx.last_score}, a rapaziada precisa de norte. Você manda a letra firme ou dá um respiro pro grupo antes do próximo jogo?"
        ),
        (
            f"Aqui é o {cap}. O vestiário sentiu o jogo no corpo. Você puxa o bonde na disciplina ou na confiança pros que tão menos em evidência?"
        ),
    ]
    if ctx.mode == "pre_match" and ctx.next_h:
        return _pick_variant(v_pre, seed + ":squad:pre")
    if ctx.mode == "post_match" and ctx.last_score:
        return _pick_variant(v_post, seed + ":squad:post")
    return _pick_variant(v_pre + v_post, seed + ":squad:any")


def _npc_open_player_1on1(ctx: _Ctx, seed: str) -> str:
    fn = ctx.focus_player
    t = ctx.player_trust
    f = ctx.player_frustration
    tense = t is not None and f is not None and (f >= 52 or t <= 42)
    warm = t is not None and f is not None and t >= 68 and f <= 36
    if tense:
        opener = _pick_variant(
            [
                f"Professor… preciso falar com o senhor. Tô incomodado com algumas coisas e não quero deixar isso virar panela no vestiário.",
                f"Mister, sem enrolação: minha cabeça não tá legal com o papel que eu tô tendo aqui. Dá pra gente ser direto?",
                f"Professor, respeito o senhor, mas preciso de clareza. Tô sentindo cobrança em cima de mim e quero saber onde eu tô errando de verdade.",
            ],
            seed + ":p11:tense",
        )
    elif warm:
        opener = _pick_variant(
            [
                f"Opa, professor! Tinha um tempinho? Queria alinhar umas ideias com o senhor — tô confiante no trabalho, mas quero ouvir seu recado.",
                f"Mister, bom te pegar a sós. Tô bem com o grupo e com o senhor; só queria alinhar expectativa pro próximo jogo.",
                f"Professor, valeu por abrir espaço. Eu confio no projeto — queria só alinhar detalhe de minutos e função sem drama.",
            ],
            seed + ":p11:warm",
        )
    else:
        opener = _pick_variant(
            [
                f"Opa, professor… o senhor me chamou? Eu tava precisando desenrolar uma parada com o senhor.",
                f"Professor, bom te pegar a sós. Pode falar — tô te ouvindo.",
                f"E aí, mister? Queria entender melhor o recado do treino hoje e o que o senhor espera de mim de verdade.",
            ],
            seed + ":p11:hi",
        )
    extra: List[str] = []
    if ctx.linked_line:
        extra.append(
            _pick_variant(
                [
                    f"Sobre essa manchete que tá na rua — «{_truncate(ctx.linked_line, 80)}» — isso pegou no vestiário. O senhor acha que eu devo me posicionar ou ficar quieto?",
                    f"Rodou notícia ligada a mim («{_truncate(ctx.linked_line, 60)}»). Quero saber se o clube tá me protegendo ou se eu tenho que me virar com a imprensa.",
                ],
                seed + ":p11:news",
            )
        )
    elif ctx.touch_ctx:
        extra.append(
            f"Sobre isso aqui: {_truncate(ctx.touch_ctx, 160)} — como é que a gente resolve em campo, mister? Tô querendo entender teu recado."
        )
    else:
        extra.append(
            _pick_variant(
                [
                    f"Minha cabeça tá no próximo jogo, mas também no meu papel aqui dentro. O senhor me vê como peça de confiança ou ainda tô provando?",
                    f"Tô sentindo o ritmo do calendário pesado — viagem, calor, pressão da torcida. O senhor reduz minha carga ou prefere que eu segure o tranco?",
                ],
                seed + ":p11:gen",
            )
        )
    return opener + "\n\n" + extra[0]


def _four_coach_replies(
    ctx: _Ctx,
    audience: str,
    interaction_mode: str,
    npc_text: str,
    seed: str,
) -> List[Dict[str, Any]]:
    """Quatro respostas com tons distintos — variantes amplas + eco do que o NPC disse (ver internal_comms_coach_banks)."""
    return build_coach_replies(ctx, audience, interaction_mode, npc_text, seed)


def _npc_followup(
    ctx: _Ctx,
    audience: str,
    interaction_mode: str,
    coach_last: str,
    turn_index: int,
    seed: str,
) -> str:
    stub = _truncate(coach_last, 100)
    stub_h = _h((coach_last or "")[:180])
    fn = ctx.focus_player
    opp = f"{ctx.next_h} x {ctx.next_a}" if ctx.next_h and ctx.next_a else "o próximo jogo"
    if audience == "players" and interaction_mode == "one_on_one":
        pools = [
            f"Entendi, mister. Sobre o que você falou («{stub}») — isso muda meu papel já no próximo jogo ou é mais pro médio prazo?",
            f"Beleza, tô ligado. E se o resultado não vier, como é que fica em cima de mim — titularidade ou rodízio?",
            f"Fechado. Só pra alinhar: você prefere que eu fale menos com a imprensa e mais com o grupo, ou o contrário?",
            f"Professor, anotando o «{stub}»: isso vale igual pra {opp} ou você ajusta se o adversário vier fechadinho?",
            f"Entendi teu recado. O vestiário interpreta isso como cobrança alta ou como apoio — qual dos dois você quer que eu reforce pro grupo?",
            f"Ok. E sobre minuto: isso que você falou fecha com o que a gente treinou essa semana ou ainda tem ajuste?",
            f"Mister, sincero: com essa linha («{stub}»), eu saio mais leve ou mais pressionado? Preciso saber pra não desandar.",
            f"Beleza. E se eu não render o que você pediu em {opp}, qual é o próximo passo — conversa, banco, ou trabalho específico?",
            f"Pelo que você trouxe («{stub}»), você quer que eu seja mais líder de grupo ou mais focado no meu quadrado em campo?",
            f"Professor, só cruzando: isso conversa com o que você falou na última reunião ou é um recado novo pro {fn}?",
        ]
        return _pick_variant(pools, seed + f":fu:p11:{turn_index}:{stub_h}")

    label = "a diretoria" if audience == "board" else ("a comissão" if audience == "staff" else "o vestiário")
    pools = [
        f"Mister, anotado. Quando você diz «{stub}», {label} entende mais como resultado ou como processo — qual dos dois você quer carregar agora?",
        f"Entendi a linha. Isso vale do mesmo jeito pra {opp} ou você muda o discurso se o jogo apertar?",
        f"Ok. Pressão de fora — torcida e mídia — você quer que a gente proteja o elenco ou que a cobrança entre no CT mais crua?",
        f"Pelo «{stub}», a leitura aqui é de time fechado ou de time com ressalvas — qual das duas você quer que eu leve?",
        f"Professor, cruzando com {opp}: isso que você falou vira regra de treino já amanhã ou é mais pra cabeça pro jogo?",
        f"Beleza. E se o placar não ajudar, esse discurso («{stub}») continua igual ou a gente muda o tom internamente?",
        f"Anotado. {label.capitalize()} precisa levar isso pra assembleia / reunião — você quer ênfase em resultado ou em processo?",
        f"Mister, sincero: com esse recado, a gente acelera mudança de modelo ou segura o que tá funcionando?",
        f"Entendi. Você quer mais transparência com torcida ou mais silêncio operacional até {opp}?",
        f"Pelo que você colocou («{stub}»), prioridade é fechar o grupo por dentro ou mandar mensagem forte pra fora também?",
    ]
    return _pick_variant(pools, seed + f":fu:grp:{turn_index}:{stub_h}")


def _npc_closing(ctx: _Ctx, audience: str, interaction_mode: str, seed: str) -> str:
    c = ctx.club
    if audience == "players" and interaction_mode == "one_on_one":
        return _pick_variant(
            [
                f"Fechou, mister. Valeu pelo papo — vou jogar isso pra treino e postura. Qualquer coisa eu te procuro depois do rachão.",
                f"Beleza, professor. Por hoje é isso; foco no que você pediu. Tamo junto.",
                f"Combinado. Vou segurar o recado no vestiário e correr atrás do que combinamos — até o próximo jogo.",
                f"Fechamos aqui. Obrigado pela clareza; agora é botar em campo sem enrolação.",
                f"Valeu, mister. Vou alinhar com quem preciso e manter a cabeça no lugar pra ajudar o {c}.",
                f"Por hoje é isso. Qualquer coisa eu bato de novo — mas foco total no trabalho.",
            ],
            seed + ":close:p11",
        )
    return _pick_variant(
        [
            f"Combinado, mister. Por hoje encerra aqui — a gente leva esse alinhamento pro dia a dia do {c}.",
            f"Fechamos por ora. Valeu pela franqueza; agora é mostrar em campo e no CT.",
            f"Beleza, professor. Tamo alinhados — próximo passo é execução, não discurso.",
            f"Fechou. Obrigado pelo papo reto; a gente segue firme com o {c}.",
            f"Por hoje é isso. Se pintar novidade, a gente retoma — mas o combinado fica claro.",
            f"Valeu. Vou levar isso pro grupo do jeito que combinamos — sem meia palavra.",
        ],
        seed + ":close:grp",
    )


def run_internal_comms_step(
    save_uid: str,
    audience: str,
    interaction_mode: str = "group",
    focus_player_id: Optional[int] = None,
    focus_player_name: Optional[str] = None,
    linked_headline: Optional[str] = None,
    touchpoint_context: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    messages: lista alternando npc/coach; última mensagem pode ser coach recém-escolhida.
    Devolve npc_blocks (texto do outro lado), coach_options (4 frases), conversation_done.
    """
    msgs = list(messages or [])
    coach_turns = sum(1 for m in msgs if m.get("role") == "coach")

    ctx = _load_ctx(
        save_uid,
        focus_player_name,
        linked_headline,
        touchpoint_context,
        focus_player_id=focus_player_id,
        interaction_mode=interaction_mode,
    )
    seed = f"{save_uid}|{ctx.game_date}|{audience}|{interaction_mode}|{focus_player_id or 0}|{_truncate(linked_headline or '', 40)}"

    if not msgs and save_uid and is_internal_comms_locked_for_date(save_uid, ctx.game_date):
        return {
            "npc_blocks": [
                "Olha, hoje já teve conversa interna por aqui — diretoria, comissão ou vestiário. "
                "Pra não virar desgaste nem bagunçar o dia a dia, isso fica pra quando o calendário avançar de novo. "
                "Amanhã a gente retoma."
            ],
            "coach_options": [],
            "conversation_done": False,
            "interaction_locked": True,
            "locked_game_date": ctx.game_date,
            "user_turns_used": 0,
            "max_user_turns": 3,
        }

    # Terceira resposta do treinador já enviada → só encerramento
    if coach_turns >= 3:
        return {
            "npc_blocks": [_npc_closing(ctx, audience, interaction_mode, seed + ":end")],
            "coach_options": [],
            "conversation_done": True,
            "user_turns_used": 3,
            "max_user_turns": 3,
        }

    # Primeira rodada: só NPC + opções
    if not msgs:
        if audience == "board":
            block = _npc_open_board(ctx, seed)
        elif audience == "staff":
            block = _npc_open_staff(ctx, seed)
        elif audience == "players" and interaction_mode == "one_on_one":
            block = _npc_open_player_1on1(ctx, seed)
        else:
            block = _npc_open_squad_group(ctx, seed)
        opts = _four_coach_replies(ctx, audience, interaction_mode, block, seed + ":t0")
        return {
            "npc_blocks": [block],
            "coach_options": opts,
            "conversation_done": False,
            "user_turns_used": 0,
            "max_user_turns": 3,
        }

    # Mensagens existem: última deve ser coach — geramos follow-up NPC + novas opções (se ainda < 3 coach)
    last = msgs[-1]
    if last.get("role") != "coach":
        return {
            "npc_blocks": ["(Erro de sequência na conversa.)"],
            "coach_options": [],
            "conversation_done": True,
            "user_turns_used": coach_turns,
            "max_user_turns": 3,
        }

    coach_last = str(last.get("text") or "")
    turn_idx = coach_turns

    fu = _npc_followup(ctx, audience, interaction_mode, coach_last, turn_idx, seed)
    next_opts = _four_coach_replies(ctx, audience, interaction_mode, fu, seed + f":t{coach_turns}")

    return {
        "npc_blocks": [fu],
        "coach_options": next_opts,
        "conversation_done": False,
        "user_turns_used": coach_turns,
        "max_user_turns": 3,
        "closing_hint": coach_turns >= 2,
    }
