"""Narrativas dinâmicas para coletivas e interações (tom + audiência + momento do clube)."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from database import get_active_board_challenge, get_active_crisis_arc, get_or_create_career_management_state
from press_theme_templates import (
    THEME_LABEL_PT,
    normalize_topic,
    options_for_topic,
    question_hook,
)
from front_read_models import (
    _competition_name_index,
    _decorate_fixture,
    _game_date_value,
    _last_completed_fixture,
    _manager_name,
    _next_fixture,
    _read_state,
    _result_letter,
    _select_primary_league_table,
    _user_team_id,
)


def load_press_context(save_uid: str) -> Dict[str, Any]:
    state = _read_state()
    club = dict(state.get("club") or {})
    uid = _user_team_id(state)
    comp = _competition_name_index(save_uid)
    raw = _game_date_value(state)
    fixtures = list(state.get("fixtures") or [])
    next_f = _decorate_fixture(_next_fixture(fixtures, uid, raw), uid, comp) if uid else None
    last_f = _decorate_fixture(_last_completed_fixture(fixtures, uid), uid, comp) if uid else None
    board = get_active_board_challenge(save_uid, "ULTIMATUM") if save_uid else None
    crisis = get_active_crisis_arc(save_uid) if save_uid else None
    last_letter = _result_letter(last_f, uid) if last_f and uid else None
    opp_next = None
    if next_f and uid:
        hid = int(next_f.get("home_team_id") or 0)
        opp_next = str(next_f.get("away_team_name") if hid == uid else next_f.get("home_team_name") or "")
    last_score_txt = ""
    if last_f and uid is not None:
        hs = last_f.get("home_score")
        aws = last_f.get("away_score")
        if hs is not None and aws is not None:
            last_score_txt = f"{hs}×{aws}"
    mg = get_or_create_career_management_state(save_uid) if save_uid else {}
    medical = dict((mg or {}).get("medical") or {})
    primary_table = _select_primary_league_table(state, uid, next_f, comp) if uid else None
    return {
        "club_name": str(club.get("team_name") or "Clube"),
        "manager_name": _manager_name(dict(state.get("manager") or {})),
        "board_active": board,
        "crisis_active": crisis,
        "next_fixture": next_f,
        "last_fixture": last_f,
        "last_result_letter": last_letter,
        "next_opponent": opp_next,
        "last_score_text": last_score_txt,
        "user_team_id": uid,
        "medical": medical,
        "table": primary_table,
    }


def _stakes_fragment(ctx: Dict[str, Any]) -> str:
    if ctx.get("crisis_active"):
        return "em um momento de pressão institucional, "
    if ctx.get("board_active"):
        return "com a diretoria cobrando resultado, "
    return ""


def _pick_variant(seed_parts: List[str], options: List[str]) -> str:
    if not options:
        return ""
    h = hashlib.md5("|".join(seed_parts).encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(options)
    return options[idx]


def _press_bundle_for_llm(
    ctx: Dict[str, Any],
    style: str,
    audience: str,
    question: str,
    topic: str,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tbl = dict(ctx.get("table") or {})
    med = dict(ctx.get("medical") or {})
    ex = dict(extras or {})
    return {
        "coach_name": ctx.get("manager_name") or "Treinador",
        "club": ctx.get("club_name") or "Clube",
        "style": (style or "analytical").lower(),
        "audience": (audience or "staff").lower(),
        "question": question,
        "focus_player_name": str(ex.get("focus_player_name") or ""),
        "interaction_mode": str(ex.get("interaction_mode") or ""),
        "linked_headline": str(ex.get("linked_headline") or ""),
        "topic_type": topic,
        "topic_theme_label": THEME_LABEL_PT.get(topic, THEME_LABEL_PT["season"]),
        "next_opponent": ctx.get("next_opponent") or "",
        "next_competition": str((ctx.get("next_fixture") or {}).get("competition_name") or ""),
        "last_score": ctx.get("last_score_text") or "",
        "last_result_letter": ctx.get("last_result_letter") or "",
        "table_rank": tbl.get("rank"),
        "table_points": tbl.get("points"),
        "table_competition": tbl.get("competition_name") or "",
        "injured_count": med.get("injured_count"),
        "congestion_index": med.get("congestion_index"),
        "fatigue_index": med.get("fatigue_index"),
    }


def _try_gemini_press_reply(bundle: Dict[str, Any]) -> Optional[str]:
    import os

    if os.getenv("GEMINI_PRESS_ENABLE", "1").strip().lower() in ("0", "false", "no"):
        return None
    try:
        from engine.llm_client import GeminiClient

        client = GeminiClient()
        return client.try_generate_press_coach_reply(bundle)
    except Exception:
        return None


def _template_coach_press_answer(
    ctx: Dict[str, Any],
    style_l: str,
    aud: str,
    question: str,
    topic_type: Optional[str],
    save_uid: Optional[str],
) -> str:
    """Três variantes por tema × tom × audiência (press_theme_templates)."""
    topic = normalize_topic(topic_type)
    club = ctx["club_name"]
    stakes = _stakes_fragment(ctx)
    opp = str(ctx.get("next_opponent") or "")
    comp_next = str((ctx.get("next_fixture") or {}).get("competition_name") or "competição")
    last_l = ctx.get("last_result_letter")
    last_score = str(ctx.get("last_score_text") or "").strip()
    last_frag = (
        "depois da última vitória"
        if last_l == "W"
        else ("depois do último empate" if last_l == "D" else ("depois da última derrota" if last_l == "L" else "neste trecho da temporada"))
    )
    tbl = dict(ctx.get("table") or {})
    rank, pts = tbl.get("rank"), tbl.get("points")
    tcomp = str(tbl.get("competition_name") or "") or comp_next
    med = dict(ctx.get("medical") or {})
    inj = int(med.get("injured_count") or 0)
    fatigue = med.get("fatigue_index")
    open_ref = question_hook(question, club, opp, topic)
    options = options_for_topic(
        topic,
        style_l,
        aud,
        ctx,
        open_ref,
        club,
        stakes,
        comp_next,
        opp,
        last_frag,
        last_score,
        rank,
        pts,
        tcomp,
        inj,
        fatigue,
    )
    seed = [topic, style_l, aud, question[:140], club, save_uid or "", last_score, opp]
    return _pick_variant(seed, options)


def build_coach_press_answer(
    style: str,
    audience: str,
    question: str,
    save_uid: Optional[str],
    topic_type: Optional[str] = None,
    *,
    focus_player_name: Optional[str] = None,
    interaction_mode: Optional[str] = None,
    linked_headline: Optional[str] = None,
) -> str:
    """Resposta em PT-BR; tenta Gemini (se configurado) e cai para templates por tema."""
    ctx = load_press_context(save_uid or "")
    style_l = (style or "analytical").lower()
    if style_l == "agressive":
        style_l = "aggressive"
    aud = (audience or "board").lower()
    topic = normalize_topic(topic_type)
    q_eff = (question or "").strip()
    mode = (interaction_mode or "").strip().lower()
    if mode == "one_on_one" and (focus_player_name or "").strip():
        q_eff = f"[Conversa reservada com {focus_player_name.strip()}] {q_eff}"
    elif (linked_headline or "").strip():
        lh = linked_headline.strip()
        q_eff = f"[Eco da mídia: «{lh[:100]}»] {q_eff}"
    extras = {
        "focus_player_name": focus_player_name or "",
        "interaction_mode": mode,
        "linked_headline": linked_headline or "",
    }
    bundle = _press_bundle_for_llm(ctx, style_l, aud, q_eff, topic, extras)
    llm_text = _try_gemini_press_reply(bundle)
    if llm_text:
        return llm_text
    return _template_coach_press_answer(ctx, style_l, aud, q_eff, topic_type, save_uid)


def build_press_headline(
    tone: str,
    audience: Optional[str],
    reputation_delta: int,
) -> str:
    aud = (audience or "midia").lower()
    if reputation_delta >= 2:
        base = "Coletiva: mensagem firme ganha três frentes"
    elif reputation_delta <= -2:
        base = "Coletiva: resposta gera atrito na leitura pública"
    else:
        base = "Coletiva: tom equilibrado na comunicação do treinador"

    if aud == "board":
        return f"{base} — foco na diretoria"
    if aud == "players":
        return f"{base} — foco no elenco"
    if aud == "staff":
        return f"{base} — foco na comissão técnica"
    return base


def build_press_reactions(
    tone: str,
    audience: Optional[str],
    reputation_delta: int,
    morale_delta: int,
    board_active: bool,
    crisis_active: bool,
) -> Dict[str, str]:
    aud = (audience or "").lower()
    rep_ok = reputation_delta >= 0
    mor_ok = morale_delta >= 0

    if board_active:
        board = (
            "Com ultimato ativo, a diretoria lê a fala sob lente de resultado imediato e cobrança explícita."
            if rep_ok
            else "Com ultimato ativo, a diretoria vê o discurso como insuficiente para acalmar a pressão institucional."
        )
    else:
        board = _pick_variant(
            [str(aud), str(rep_ok), "board"],
            [
                "A diretoria interpreta a postura como alinhada ao plano e às metas de curto prazo.",
                "Na sala de diretoria, leem a fala como gesto de controle e priorização do que é mensurável no curto prazo.",
            ]
            if rep_ok
            else [
                "A diretoria espera mais estratégia e menos ruído na mensagem pública.",
                "O conselho ouve a entrevista e cobra plano mais explícito para a sequência de jogos.",
            ],
        )
    if aud == "board" and crisis_active:
        board = (
            "Com crise institucional em curso, a diretoria exige mensagem que proteja a imagem do clube e mostre controle."
            if rep_ok
            else "Com crise institucional em curso, a diretoria avalia a fala como arriscada para a estabilidade do cargo."
        )

    if crisis_active:
        locker = (
            "O vestiário sente o peso do momento: cada entrevista vira referência interna para confiança e hierarquia."
            if mor_ok
            else "O vestiário reage com tensão: o tom público aumenta a pressão sobre o grupo."
        )
    else:
        locker = _pick_variant(
            [str(aud), str(mor_ok), "lock"],
            [
                "O vestiário absorve a mensagem como reforço de confiança no comando.",
                "Internamente, o grupo traduz a entrevista como sinal de estabilidade no discurso do treinador.",
            ]
            if mor_ok
            else [
                "Há desconforto interno com o tom adotado na entrevista.",
                "Alguns jogadores comentam nos bastidores que a fala soou mais dura do que o tom do dia a dia no CT.",
            ],
        )
    if aud == "players" and mor_ok:
        locker = "O elenco entende a fala como cobrança direta, mas com respeito ao trabalho diário do grupo."
    if aud == "players" and not mor_ok:
        locker = "O elenco percebe o tom como duro e isso aumenta o desgaste no dia a dia."

    if aud == "staff":
        fan = (
            "A torcida associa a entrevista ao trabalho da comissão e cobra coerência tática no próximo jogo."
            if rep_ok
            else "A torcida critica o discurso e pede menos explicação e mais resultado em campo."
        )
    else:
        fan = _pick_variant(
            [str(aud), str(rep_ok), "fan"],
            [
                "Nas redes, a torcida reage de forma majoritariamente favorável ao discurso.",
                "Entre os apoiadores, ganha tração a ideia de que o técnico está no controle da narrativa.",
            ]
            if rep_ok
            else [
                "Nas redes, parte da torcida amplia críticas após a entrevista.",
                "Há hashtags e debates divididos: parte do público pede menos conversa e mais resultado em campo.",
            ],
        )

    if aud == "players" and (not mor_ok) and reputation_delta <= -1:
        fan = (
            fan
            + " Circulam rumores de que um jogador teria detalhado o clima do vestiário a colunistas."
        )

    return {"board": board, "locker_room": locker, "fan": fan}
