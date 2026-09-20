import unittest
from unittest.mock import patch
import os
import pandas as pd
import sys
import tempfile
import io

from src.importer import import_reviews, load_config

class TestImporter(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    @patch("src.importer.load_config")
    def test_date_parsing_day_first(self, mock_load_config):
        mock_load_config.return_value = {"weeks_to_import": 12}
        csv_path = os.path.join(self.temp_dir.name, "reviews1.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("date,rating,review\n")
            f.write("12-09-2026 10:00,5,Great app!\n")
            
        df = import_reviews(csv_path)
        
        # Should be 12 September 2026
        parsed_date = df["date"].iloc[0]
        self.assertEqual(parsed_date.day, 12)
        self.assertEqual(parsed_date.month, 9)
        self.assertEqual(parsed_date.year, 2026)
        
    @patch("src.importer.load_config")
    def test_date_parsing_year_first(self, mock_load_config):
        mock_load_config.return_value = {"weeks_to_import": 12}
        csv_path = os.path.join(self.temp_dir.name, "reviews2.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("date,rating,review\n")
            f.write("2026-09-12 10:00:00,5,Awesome!\n")
            
        df = import_reviews(csv_path)
        
        # Should also be 12 September 2026
        parsed_date = df["date"].iloc[0]
        self.assertEqual(parsed_date.day, 12)
        self.assertEqual(parsed_date.month, 9)
        self.assertEqual(parsed_date.year, 2026)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_missing_rating_column(self, mock_stdout):
        csv_path = os.path.join(self.temp_dir.name, "reviews3.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("date,review\n")
            f.write("12-09-2026 10:00,Great app!\n")
            
        with self.assertRaises(SystemExit) as cm:
            import_reviews(csv_path)
            
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("missing", mock_stdout.getvalue())
        self.assertIn("rating", mock_stdout.getvalue())

if __name__ == "__main__":
    unittest.main()
