import os
import sys
import unittest
from streamlit.testing.v1 import AppTest

class TestStreamlitApp(unittest.TestCase):
    def test_app_loads_successfully(self):
        print("Starting headless Streamlit test...")
        
        # We need to simulate session state because run_success triggers the rest of the UI
        # We will directly run the app, then manipulate session state to emulate a successful pipeline run
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
        
        self.assertFalse(at.exception, "App crashed on initial load")
        
        # Initially, run_success is not in session state, so sections 2-5 are not rendered
        # Let's set it
        at.session_state["run_success"] = True
        at.run()
        
        self.assertFalse(at.exception, "App crashed after setting run_success=True")
        
        # Print all markdown, text, etc. just to debug what is rendered
        rendered_text = [elem.value for elem in at.markdown if hasattr(elem, 'value')]
        
        print("Rendered Markdown:")
        for t in rendered_text:
            print(f"- {t}")
            
        # Check that headers are present for all sections
        headers = [elem.value for elem in at.subheader] + [elem.value for elem in at.header]
        print("Headers:")
        for h in headers:
            print(f"- {h}")
            
        self.assertTrue(any("1. Data & Configuration" in h for h in headers))
        self.assertTrue(any("2. Privacy Check" in h for h in headers))
        self.assertTrue(any("3. Themes" in h for h in headers))
        self.assertTrue(any("4. Weekly Note" in h for h in headers))
        self.assertTrue(any("5. Email Draft" in h for h in headers))
        
        # Check that the email draft text area exists and has text
        text_areas = at.text_area
        self.assertGreaterEqual(len(text_areas), 2, "Should have at least 2 text areas (Note, Email Draft)")
        
        # Ensure Note text area is populated
        self.assertTrue(len(text_areas[0].value) > 10, "Weekly Note text area is empty")
        
        # Ensure Email text area is populated
        self.assertTrue(len(text_areas[1].value) > 10, "Email Draft text area is empty")
        
        print("All 5 sections rendered successfully!")
        
if __name__ == '__main__':
    unittest.main()
