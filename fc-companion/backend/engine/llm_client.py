import os
import json
import time
from typing import Dict, Any

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
