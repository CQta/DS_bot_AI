import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ai_gm


class GeminiKeyTests(unittest.TestCase):
    def test_prefers_google_api_key_env_var(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "google-key", "GEMINI_API_KEY": "gemini-key"}, clear=True):
            self.assertEqual(ai_gm.get_gemini_api_key(), "google-key")

    def test_falls_back_to_gemini_api_key_env_var(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-key"}, clear=True):
            self.assertEqual(ai_gm.get_gemini_api_key(), "gemini-key")

    def test_returns_none_when_no_key_is_set(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(ai_gm.get_gemini_api_key())

    @patch("ai_gm.genai.list_models")
    def test_list_available_models_returns_names(self, mock_list_models):
        mock_list_models.return_value = [
            SimpleNamespace(name="models/gemini-2.0-flash"),
            SimpleNamespace(name="models/gemini-1.5-pro"),
        ]

        models = ai_gm.list_available_models()

        self.assertEqual(models, ["gemini-2.0-flash", "gemini-1.5-pro"])

    def test_extract_json_payload_handles_malformed_text(self):
        raw = '```json\n{"title": "Проблема", "description": "текст"}\nЭто лишний текст```'

        payload = ai_gm.extract_json_payload(raw)

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["title"], "Проблема")


if __name__ == "__main__":
    unittest.main()
