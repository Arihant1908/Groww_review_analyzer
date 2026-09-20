import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.note_writer import validate_note, generate_fallback_note

evidence = {
    "current_week": {"reviews": 100, "average_rating": 4.0, "low_rated": 10},
    "prior_week": {"reviews": 110, "average_rating": 4.1, "low_rated": 11},
    "top_themes": {"perf": {"driver": "slow"}, "support": {"driver": "unreachable"}, "charges": {"driver": "fees"}},
    "theme_mentions": {"perf": {"current": 5, "change_pct": 0}, "support": {"current": 3, "change_pct": 0}, "charges": {"current": 2, "change_pct": 0}},
    "quotes": {
        "perf": [{"quote": "app is very slow", "rating": 1, "date": "2026-09-18"}],
        "support": [{"quote": "no reply", "rating": 2, "date": "2026-09-17"}],
        "charges": [{"quote": "too expensive", "rating": 3, "date": "2026-09-16"}]
    }
}

def test_validation_too_long():
    note = "word " * 260
    errors = validate_note(note, evidence)
    assert any("Word count" in e for e in errors)

def test_validation_edited_quote():
    note = """
Groww Weekly Pulse
    
Top themes:
1. perf
2. support
3. charges

User voice:
- "app is somewhat slow" (1 star, 2026-09-18)
- "no reply at all" (2 star, 2026-09-17)
- "too much expensive" (3 star, 2026-09-16)

Action ideas:
1. Action
2. Action
3. Action
    """
    errors = validate_note(note, evidence)
    assert any("not an exact match" in e for e in errors)

def test_validation_email_fails():
    note = """
Groww Weekly Pulse
    
Top themes:
1. perf
2. support
3. charges

User voice:
- "app is very slow" (1 star, 2026-09-18)
- "no reply" (2 star, 2026-09-17)
- "too expensive" (3 star, 2026-09-16)

Action ideas:
1. Action
2. Action
3. Action

Contact test@example.com
    """
    errors = validate_note(note, evidence)
    assert any("PII" in e for e in errors)
    
def test_fallback_passes():
    fallback = generate_fallback_note(evidence)
    errors = validate_note(fallback, evidence)
    assert not errors

from unittest.mock import patch, MagicMock
import json
from src.note_writer import run_ai

@patch("src.note_writer.time.sleep")
@patch("src.note_writer.genai.Client")
def test_429_stops_immediately_tries_backup(mock_client_cls, mock_sleep):
    mock_client = MagicMock()
    mock_model = MagicMock()
    # First model gets 429, second model gets 429
    mock_model.generate_content.side_effect = [
        Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for model A"),
        Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for model B")
    ]
    mock_client.models = mock_model
    mock_client_cls.return_value = mock_client
    
    note_text, ai_used, api_calls_made, quota_exhausted, used_model = run_ai(
        json.dumps(evidence), "Test prompt", "gemini-3.8-flash", "gemini-3.7-flash", "test_key"
    )
    
    assert ai_used is False
    assert quota_exhausted is True
    assert api_calls_made == 2 # 1 for primary, 1 for backup
    assert mock_model.generate_content.call_count == 2
    assert mock_sleep.call_count == 0 # No sleep on 429

@patch("src.note_writer.time.sleep")
@patch("src.note_writer.genai.Client")
def test_404_stops_immediately_no_backup(mock_client_cls, mock_sleep):
    mock_client = MagicMock()
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("404 NOT_FOUND")
    mock_client.models = mock_model
    mock_client_cls.return_value = mock_client
    
    note_text, ai_used, api_calls_made, quota_exhausted, used_model = run_ai(
        json.dumps(evidence), "Test prompt", "gemini-3.8-flash", "gemini-3.7-flash", "test_key"
    )
    
    assert ai_used is False
    assert quota_exhausted is False
    assert api_calls_made == 1 # 1 for primary only
    assert mock_model.generate_content.call_count == 1
    assert mock_sleep.call_count == 0

@patch("src.note_writer.time.sleep")
@patch("src.note_writer.genai.Client")
def test_503_retries_and_backup(mock_client_cls, mock_sleep):
    mock_client = MagicMock()
    mock_model = MagicMock()
    # 503 for primary (3 waits = 4 attempts total)
    # 503 for backup (3 waits = 4 attempts total)
    mock_model.generate_content.side_effect = [Exception("503 UNAVAILABLE")] * 8
    mock_client.models = mock_model
    mock_client_cls.return_value = mock_client
    
    note_text, ai_used, api_calls_made, quota_exhausted, used_model = run_ai(
        json.dumps(evidence), "Test prompt", "gemini-3.8-flash", "gemini-3.7-flash", "test_key"
    )
    
    assert ai_used is False
    assert api_calls_made == 8
    assert mock_sleep.call_count == 6 # 3 for primary, 3 for backup

@patch("src.note_writer.genai.Client")
def test_validation_retries(mock_client_cls):
    mock_client = MagicMock()
    mock_model = MagicMock()
    mock_resp_fail = MagicMock()
    mock_resp_fail.text = "This is a failing note because it is too short and has no numbered lines."
    
    mock_resp_success = MagicMock()
    mock_resp_success.text = generate_fallback_note(evidence) # use fallback which is perfectly valid
    
    # First attempt fails validation, second attempt succeeds
    mock_model.generate_content.side_effect = [mock_resp_fail, mock_resp_success]
    mock_client.models = mock_model
    mock_client_cls.return_value = mock_client
    
    note_text, ai_used, api_calls_made, quota_exhausted, used_model = run_ai(
        json.dumps(evidence), "Test prompt", "gemini-3.8-flash", "gemini-3.7-flash", "test_key"
    )
    
    assert ai_used is True
    assert api_calls_made == 2
    assert used_model == "gemini-3.8-flash"

def test_fallback_no_generic_phrases():
    fallback = generate_fallback_note(evidence)
    assert "Address top driver" not in fallback
    assert "Investigate spikes" not in fallback
    assert "Review top themes" not in fallback
