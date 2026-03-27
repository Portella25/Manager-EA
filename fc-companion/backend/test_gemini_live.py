import os
import unittest

from engine.llm_client import GeminiClient

try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    load_dotenv = None
    find_dotenv = None


class TestGeminiLive(unittest.TestCase):
    def test_generate_epic_narrative_live(self):
        if load_dotenv and find_dotenv:
            load_dotenv(find_dotenv(), override=True)
        if not os.getenv("GEMINI_API_KEY"):
            self.skipTest("GEMINI_API_KEY não configurada no ambiente")
        client = GeminiClient()
        if not client.model and not client.client:
            self.skipTest(f"SDK Gemini indisponível neste ambiente: {client.unavailable_reason}")
        text = client.generate_epic_narrative(
            context_dossier={
                "cenario": "Coletiva pós-derrota no clássico",
                "pressao_atual": 85,
                "fase_time": "3 jogos sem vencer",
                "posicao_tabela": "Caiu de 2º para 4º",
                "clima_vestiario": "Tenso (Capitão com moral baixa)",
                "diretriz_llm": "Aja como repórteres agressivos. Faça perguntas curtas e duras.",
            },
            event_type="press_conference",
        )
        self.assertIsInstance(text, str)
        self.assertTrue(len(text.strip()) > 40)
        strict = os.getenv("GEMINI_STRICT_LIVE_TEST", "0") == "1"
        if strict:
            self.assertEqual(client.last_response_origin, "llm_success")
            self.assertNotIn("[Modo Fallback", text)


if __name__ == "__main__":
    unittest.main()
