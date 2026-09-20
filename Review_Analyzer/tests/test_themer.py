import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import json
import os
import sys

# Add src to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from themer import call_gemini, load_config, fallback_theme

class TestThemer(unittest.TestCase):

    def setUp(self):
        # We need a clean config for testing some functions
        self.themes = {
            "support": {"name": "Support", "definition": "support"},
            "charges": {"name": "Charges", "definition": "charges"},
            "perf": {"name": "Perf", "definition": "perf"},
            "features": {"name": "Features", "definition": "features"},
            "money": {"name": "Money", "definition": "money"}
        }

    @patch("themer.genai.Client")
    def test_invalid_theme_id_rejected(self, mock_client):
        # Setup mock to return invalid JSON
        mock_model = MagicMock()
        mock_response = MagicMock()
        # "invalid_theme" is not one of our keys
        mock_response.text = '{"0": ["invalid_theme"]}'
        mock_model.generate_content.return_value = mock_response
        
        mock_client.return_value.models = mock_model
        
        with self.assertRaises(ValueError):
            call_gemini(["test review"], self.themes, "gemini-2.5-flash", "test_key")

    def test_fallback_works_no_api_key(self):
        # Test fallback_theme directly
        keywords = {
            "perf": ["slow", "crash"],
            "support": ["ticket"]
        }
        
        res = fallback_theme("This app is so slow and crashes", self.themes, keywords)
        self.assertIn("perf", res)
        
        res2 = fallback_theme("Gibberish", self.themes, keywords)
        self.assertEqual(res2, ["unthemed"])

    @patch("themer.json.load")
    def test_sixth_theme_fails(self, mock_json_load):
        # If themes.json has 6 themes, load_config should sys.exit(1)
        mock_json_load.return_value = {
            "t1": {}, "t2": {}, "t3": {}, "t4": {}, "t5": {}, "t6": {}
        }
        
        with self.assertRaises(SystemExit) as cm:
            load_config()
            
        self.assertEqual(cm.exception.code, 1)

    @patch("themer.load_config")
    @patch("themer.os.environ.get")
    def test_cache_invalidation_on_definition_change(self, mock_env_get, mock_load_config):
        mock_env_get.return_value = None
        df = pd.DataFrame([{"review": "test review", "rating": 1}])
        
        mock_load_config.return_value = (self.themes, {}, {})
        if os.path.exists("out/theme_cache.json"):
            os.remove("out/theme_cache.json")
            
        from themer import themer
        with patch("themer.fallback_theme") as mock_fallback:
            mock_fallback.return_value = ["perf"]
            themer(df.copy())
            self.assertEqual(mock_fallback.call_count, 1)
            
        with patch("themer.fallback_theme") as mock_fallback:
            themer(df.copy())
            self.assertEqual(mock_fallback.call_count, 0)
            
        changed_themes = self.themes.copy()
        changed_themes["support"] = {"name": "Support", "definition": "different"}
        mock_load_config.return_value = (changed_themes, {}, {})
        with patch("themer.fallback_theme") as mock_fallback:
            mock_fallback.return_value = ["perf"]
            themer(df.copy())
            self.assertEqual(mock_fallback.call_count, 1)

if __name__ == "__main__":
    unittest.main()
