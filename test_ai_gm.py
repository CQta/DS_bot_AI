import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import ai_gm


class GeminiKeyTests(unittest.TestCase):
    @patch("ai_gm.client")
    @patch("ai_gm.extract_json_payload")
    def test_parse_actions_includes_units_in_description_text(self, mock_extract, mock_client):
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response
        mock_extract.return_value = [
            {"id": 1, "action_type": "GATHER", "target": "лес", "is_secret": False},
            {"id": 2, "action_type": "BUILD", "target": "лагерь", "is_secret": False},
        ]

        actions = __import__("asyncio").run(
            ai_gm.parse_actions("25 юнитов собирают еду; 5 юнитов строят лагерь", {"faction_name": "Тест", "race": "Люди", "path": "CULTIVATION", "alignment": "GOOD", "population": 50})
        )

        self.assertTrue(any("25 юнит" in a["description"] for a in actions))
        self.assertTrue(any("5 юнит" in a["description"] for a in actions))

    def test_prefers_google_api_key_env_var(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "google-key", "GEMINI_API_KEY": "gemini-key"}, clear=True):
            self.assertEqual(ai_gm.get_gemini_api_key(), "google-key")

    def test_falls_back_to_gemini_api_key_env_var(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-key"}, clear=True):
            self.assertEqual(ai_gm.get_gemini_api_key(), "gemini-key")

    def test_returns_none_when_no_key_is_set(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(ai_gm.get_gemini_api_key())

    @patch("ai_gm.client")
    def test_list_available_models_returns_names(self, mock_client):
        mock_client.models.list.return_value = [
            SimpleNamespace(name="models/gemini-2.5-flash"),
            SimpleNamespace(name="models/gemini-2.0-flash"),
        ]

        models = ai_gm.list_available_models()

        self.assertEqual(models, ["gemini-2.5-flash", "gemini-2.0-flash"])

    @patch("ai_gm.client")
    @patch("ai_gm.extract_json_payload")
    def test_parse_actions_splits_semicolon_segments(self, mock_extract, mock_client):
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response
        mock_extract.return_value = {
            "action_type": "GATHER",
            "target": "лес",
            "is_secret": False
        }

        actions = __import__("asyncio").run(
            ai_gm.parse_actions("10 юнитов собирают еду; 5 юнитов исследуют руну", {"faction_name": "Тест", "race": "Люди", "path": "CULTIVATION", "alignment": "GOOD", "population": 50})
        )

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["units"], 10)
        self.assertEqual(actions[1]["units"], 5)

    def test_extract_json_payload_handles_malformed_text(self):
        raw = '```json\n{"title": "Проблема", "description": "текст"}\nЭто лишний текст```'

        payload = ai_gm.extract_json_payload(raw)

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["title"], "Проблема")


if __name__ == "__main__":
    unittest.main()
