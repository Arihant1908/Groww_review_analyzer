import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.emailer import create_email_drafts

def test_subject_contains_date_range(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("out")
    
    pulse_file = "out/pulse_test.md"
    with open(pulse_file, "w") as f:
        f.write("Groww Weekly Pulse")
        
    create_email_drafts(pulse_file, "test@example.com", "Sep 12 - Sep 18, 2026")
    
    with open("out/email_draft.txt", "r") as f:
        content = f.read()
    assert "Sep 12 - Sep 18, 2026" in content

def test_body_has_quotes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("out")
    
    quotes = [
        "- \"Quote one\" (1 star)",
        "- \"Quote two\" (2 star)",
        "- \"Quote three\" (3 star)"
    ]
    
    pulse_file = "out/pulse_test.md"
    with open(pulse_file, "w") as f:
        f.write("Groww Weekly Pulse\n")
        for q in quotes:
            f.write(f"{q}\n")
            
    create_email_drafts(pulse_file, "test@example.com", "Date")
    
    with open("out/email_draft.txt", "r") as f:
        content = f.read()
        
    for q in quotes:
        assert q in content

def test_pii_gate_blocks_phone_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("out")
    
    pulse_file = "out/pulse_test.md"
    with open(pulse_file, "w") as f:
        f.write("Groww Weekly Pulse with phone number +91-9876543210")
        
    with pytest.raises(SystemExit):
        create_email_drafts(pulse_file, "test@example.com", "Date")
