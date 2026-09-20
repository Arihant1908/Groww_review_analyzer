import unittest
import pandas as pd
import os
import sys

# Add src to path just in case, though we use standard imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from src.redactor import redact_text, run_redactor, pii_gate

class TestRedactor(unittest.TestCase):

    def test_pii_gate(self):
        # Should raise SystemExit on PII
        with self.assertRaises(SystemExit):
            pii_gate("Contact me at test@example.com")
        with self.assertRaises(SystemExit):
            pii_gate("Call 9876543210")
        with self.assertRaises(SystemExit):
            pii_gate("PAN ABCDE1234F")
        with self.assertRaises(SystemExit):
            pii_gate("ID 123456789012")
            
        # Should pass
        try:
            pii_gate("This is a clean [EMAIL] and [PHONE]")
        except SystemExit:
            self.fail("pii_gate raised SystemExit on clean text")

    def test_redact_text(self):
        # We simulate all_lower_words containing "good", "app", "stop", "loss"
        all_lower_words = {"good", "app", "stop", "loss"}
        
        # 1. Email and truncated email
        self.assertEqual(redact_text("Email test@example.com", "", all_lower_words), "Email [EMAIL]")
        self.assertEqual(redact_text("Email support@groww....", "", all_lower_words), "Email [EMAIL]")
        
        # 2. Phone number
        self.assertEqual(redact_text("Call 9876543210 please", "", all_lower_words), "Call [PHONE] please")
        self.assertEqual(redact_text("Call +91-9876543210", "", all_lower_words), "Call [PHONE]")
        
        # 3. PAN
        self.assertEqual(redact_text("My PAN is ABCDE1234F", "", all_lower_words), "My PAN is [ID]")
        
        # 4. 12-digit number
        self.assertEqual(redact_text("Code 123456789012", "", all_lower_words), "Code [ID]")
        
        # 5. Ticket number
        self.assertEqual(redact_text("ticket 123", "", all_lower_words), "ticket [ID]")
        self.assertEqual(redact_text("order: 456", "", all_lower_words), "order: [ID]")
        
        # 6. Reviewer's own name
        self.assertEqual(redact_text("Thanks from John Doe", "John Doe", all_lower_words), "Thanks from [NAME]")
        
        # 7. Two-word personal name (should be replaced because it's not in all_lower_words)
        self.assertEqual(redact_text("Spoke to Rahul Sharma", "", all_lower_words), "Spoke to [NAME]")
        
        # 8. "Good App" and "Stop Loss" survive
        # because "good", "app", "stop", "loss" are in all_lower_words
        self.assertEqual(redact_text("This is a Good App with Stop Loss", "", all_lower_words), "This is a Good App with Stop Loss")

    def test_run_redactor(self):
        # Create a sample DataFrame
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-18", "2026-09-19"]),
            "rating": [5, 4],
            "review": ["My name is John Doe and email is a@b.com", "good app stop loss"],
            "user": ["John Doe", "Alice"],
            "developer_reply": ["Thanks", ""],
            "reply_date": ["2026-09-18 12:00:00", ""]
        })
        
        redacted_df = run_redactor(df.copy())
        
        # Check columns
        self.assertNotIn("user", redacted_df.columns)
        self.assertNotIn("developer_reply", redacted_df.columns)
        self.assertNotIn("reply_date", redacted_df.columns)
        
        self.assertIn("developer_replied", redacted_df.columns)
        self.assertTrue(redacted_df.iloc[0]["developer_replied"])
        self.assertFalse(redacted_df.iloc[1]["developer_replied"])
        
        # Check that John Doe was redacted
        self.assertEqual(redacted_df.iloc[0]["review"], "My name is [NAME] and email is [EMAIL]")
        
        # Check that good app stop loss survived
        self.assertEqual(redacted_df.iloc[1]["review"], "good app stop loss")
        
    def test_run_redactor_trie(self):
        # Create a sample DataFrame to test the trie logic
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-18", "2026-09-19"]),
            "rating": [5, 4],
            "review": ["Rakesh fixed my issue.", "All In one app."],
            "user": ["Rakesh", "All In one"],
            "developer_reply": ["Thanks", ""],
            "reply_date": ["2026-09-18 12:00:00", ""]
        })
        
        redacted_df = run_redactor(df.copy())
        
        self.assertEqual(redacted_df.iloc[0]["review"], "[NAME] fixed my issue.")
        self.assertEqual(redacted_df.iloc[1]["review"], "[NAME] app.")

if __name__ == "__main__":
    unittest.main()
