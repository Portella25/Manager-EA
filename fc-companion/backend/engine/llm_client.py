import os
import json
import time
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    load_dotenv = None
    find_dotenv = None

class GeminiClient:
    """
    Cliente da LLM Gemini para gerar narrativas épicas baseadas no Dossiê de Contexto.
    """
    _last_call_ts = 0.0
    _cooldown_until_ts = 0.0
    _calls_in_process = 0
    _last_press_ts = 0.0

    def __init__(self):
        self.model = None
        self.client = None
        self.sdk_mode = None
        self.unavailable_reason = None
        self.last_response_origin = "init"
        self.last_error_type = None
        self.last_error_message = None
        self.min_interval_seconds = float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "20"))
        self.cooldown_seconds = float(os.getenv("GEMINI_COOLDOWN_SECONDS", "120"))
        self.max_calls_per_process = int(os.getenv("GEMINI_MAX_CALLS_PER_PROCESS", "5"))

        if load_dotenv and find_dotenv:
            load_dotenv(find_dotenv(), override=True)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            self.unavailable_reason = "GEMINI_API_KEY ausente"
            self.last_response_origin = "fallback_no_key"
            return

        try:
            from google import genai as genai_sdk
            self.client = genai_sdk.Client(api_key=api_key)
            self.sdk_mode = "google_genai"
            self.last_response_origin = "ready"
            return
        except Exception:
            pass

        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            self.model = legacy_genai.GenerativeModel("gemini-2.0-flash")
            self.sdk_mode = "google_generativeai"
            self.last_response_origin = "ready"
            return
        except Exception as e:
            self.unavailable_reason = f"SDK indisponível/incompatível: {e}"
            self.last_response_origin = "fallback_sdk_unavailable"

    def generate_epic_narrative(self, context_dossier: Dict[str, Any], event_type: str) -> str:
        """
        Recebe o dossiê e gera uma narrativa profunda, dramática e contextualizada.
        """
        if not self.model and not self.client:
            reason = self.unavailable_reason or "cliente indisponível"
            self.last_response_origin = "fallback_unavailable"
            return f"[Modo Fallback - {reason}] Evento {event_type} ocorreu. Pressão: {context_dossier.get('pressao_atual')}"

        now = time.time()
        if now < GeminiClient._cooldown_until_ts:
            wait_s = int(GeminiClient._cooldown_until_ts - now)
            self.last_response_origin = "fallback_cooldown"
            return f"[Modo Fallback - cooldown {wait_s}s] Evento {event_type} ocorreu. Pressão: {context_dossier.get('pressao_atual')}"

        if GeminiClient._calls_in_process >= self.max_calls_per_process:
            self.last_response_origin = "fallback_max_calls"
            return f"[Modo Fallback - limite de chamadas] Evento {event_type} ocorreu. Pressão: {context_dossier.get('pressao_atual')}"

        elapsed = now - GeminiClient._last_call_ts
        if elapsed < self.min_interval_seconds:
            wait_s = int(self.min_interval_seconds - elapsed) + 1
            self.last_response_origin = "fallback_rate_limited_local"
            return f"[Modo Fallback - aguarde {wait_s}s] Evento {event_type} ocorreu. Pressão: {context_dossier.get('pressao_atual')}"

        dossier_json = json.dumps(context_dossier, indent=2, ensure_ascii=False)
        
        prompt = f"""
Você é um repórter esportivo investigativo e dramático, especializado nos bastidores do futebol.
Você recebeu o seguinte 'Dossiê de Contexto' sobre o momento atual de um clube de futebol.
Baseado APENAS nestes dados (para não alucinar eventos que não aconteceram), crie uma narrativa épica, imersiva e realista.

TIPO DE EVENTO: {event_type}

DOSSIÊ DE CONTEXTO:
{dossier_json}

DIRETRIZES:
1. Escreva no formato de uma matéria esportiva ou relato de bastidor (2 a 3 parágrafos curtos).
2. Se a pressão estiver alta e for uma derrota, use um tom de crise iminente.
3. Se for uma goleada ou vitória épica, use um tom eufórico, exaltando a reviravolta.
4. Foque na narrativa humana: o treinador, os jogadores, a torcida.
5. Não use saudações, entregue apenas o texto da matéria.
"""

        try:
            GeminiClient._calls_in_process += 1
            GeminiClient._last_call_ts = time.time()
            if self.client and self.sdk_mode == "google_genai":
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                self.last_response_origin = "llm_success"
                return response.text.strip() if response.text else "Sem resposta do modelo."

            response = self.model.generate_content(prompt)
            self.last_response_origin = "llm_success"
            return response.text.strip() if response.text else "Sem resposta do modelo."
        except Exception as e:
            raw = str(e)
            lowered = raw.lower()
            self.last_error_message = raw
            if "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
                self.last_error_type = "quota"
                GeminiClient._cooldown_until_ts = time.time() + self.cooldown_seconds
            else:
                self.last_error_type = "other"
            self.last_response_origin = "fallback_error"
            return f"Os ânimos se exaltaram após o último evento ({event_type}), e a tensão paira no ar."

    def try_generate_press_coach_reply(self, bundle: Dict[str, Any]) -> Optional[str]:
        """
        Resposta curta de treinador em coletiva (PT-BR, 1ª pessoa). Não compete com o rate limit
        das narrativas épicas; usa intervalo próprio (GEMINI_PRESS_MIN_INTERVAL_SECONDS).
        """
        if not self.model and not self.client:
            return None
        now = time.time()
        if now < GeminiClient._cooldown_until_ts:
            return None
        min_gap = float(os.getenv("GEMINI_PRESS_MIN_INTERVAL_SECONDS", "1.25"))
        if now - GeminiClient._last_press_ts < min_gap:
            return None
        coach = str(bundle.get("coach_name") or "Treinador")
        club = str(bundle.get("club") or "Clube")
        style = str(bundle.get("style") or "analytical")
        audience = str(bundle.get("audience") or "staff")
        question = str(bundle.get("question") or "").strip()
        topic = str(bundle.get("topic_type") or "season").strip().lower()
        theme_label = str(bundle.get("topic_theme_label") or "CONTEXTO DA TEMPORADA")
        opp = str(bundle.get("next_opponent") or "o adversário")
        comp = str(bundle.get("next_competition") or "competição")
        last_sc = str(bundle.get("last_score") or "").strip()
        last_l = str(bundle.get("last_result_letter") or "").strip()
        rank = bundle.get("table_rank")
        pts = bundle.get("table_points")
        tcomp = str(bundle.get("table_competition") or "")
        inj = bundle.get("injured_count")
        cong = bundle.get("congestion_index")
        fatigue = bundle.get("fatigue_index")

        facts_lines = [f"Clube: {club}", f"Competição em foco: {comp}"]
        include_opp_score = topic in ("match", "form")
        if include_opp_score and opp:
            facts_lines.append(f"Próximo adversário: {opp}")
        if include_opp_score and last_sc:
            facts_lines.append(f"Último placar (seu time): {last_sc} (resultado: {last_l or '—'})")
        if topic in ("season", "market", "board") and rank is not None and pts is not None:
            facts_lines.append(f"Tabela ({tcomp or comp}): posição {rank}ª com {pts} pontos")
        if topic == "medical":
            if inj is not None:
                facts_lines.append(f"Desfalques reportados: {inj}")
            if cong is not None:
                facts_lines.append(f"Índice de congestão de calendário: {cong}")
            if fatigue is not None:
                facts_lines.append(f"Desgaste médio do elenco (referência): {fatigue}")
        elif topic == "market":
            facts_lines.append("Contexto: perguntas sobre mercado/janela/rumores — não invente negociações.")
        facts_block = "\n".join(facts_lines)

        tema_regras = (
            f"TEMA OBRIGATÓRIO DA RESPOSTA: {theme_label}.\n"
            "Responda diretamente a essa pauta. Não desvie para preparação detalhada do próximo adversário nem cite placar de jogo passado "
            "se o tema for MERCADO, DIRETORIA, VESTIÁRIO ou PARTE FÍSICA, salvo se a pergunta pedir explicitamente.\n"
            "Se o tema for MERCADO/JANELA, fale de rumor vs trabalho interno, foco no elenco atual e critério com a diretoria — não 'fechar plano tático contra X'.\n"
            "Seja específico ao que foi perguntado; evite repetir a mesma frase genérica de coletiva."
        )

        style_hints = {
            "aggressive": "firme, exigente, responsabilidade e resultado; sem insultos",
            "calm": "sereno, método, controle emocional",
            "motivational": "confiante, orgulho do grupo, trabalho e foco; cite torcida quando couber",
            "analytical": "processo, clareza, decisões objetivas, sem promessa vazia",
        }
        style_hint = style_hints.get(style.lower(), style_hints["analytical"])

        prompt = f"""Você é {coach}, treinador do {club}, em coletiva de imprensa no Brasil.
Responda em português do Brasil, na primeira pessoa (eu/nós), em 2 a 4 frases curtas e naturais.
Tom pedido: {style} — {style_hint}.
Audiência implícita da pergunta: {audience} (diretoria / elenco / comissão).

{tema_regras}

PERGUNTA DO JORNALISTA:
{question}

FATOS (use só o que for listado; não invente lesionados, placares ou negociações):
{facts_block}

Regras: sem meta-comentário de IA; sem aspas; não repita a pergunta inteira.
Inclua pelo menos uma destas palavras quando fizer sentido: trabalho, foco ou confiante (ajuda na análise automática do tom)."""

        try:
            GeminiClient._last_press_ts = time.time()
            if self.client and self.sdk_mode == "google_genai":
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                text = (response.text or "").strip() if response.text else ""
            else:
                response = self.model.generate_content(prompt)
                text = (response.text or "").strip() if response.text else ""
            self.last_response_origin = "press_llm_success"
            if len(text) < 28:
                return None
            return text[:1400]
        except Exception as e:
            raw = str(e)
            lowered = raw.lower()
            self.last_error_message = raw
            if "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
                self.last_error_type = "quota"
                GeminiClient._cooldown_until_ts = time.time() + self.cooldown_seconds
            else:
                self.last_error_type = "other"
            self.last_response_origin = "press_llm_error"
            return None
