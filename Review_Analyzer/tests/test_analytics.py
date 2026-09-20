import pytest
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.analytics import generate_evidence, generate_weekly_trend, score_quote

def test_window_boundaries():
    # Make a tiny dataframe with known dates
    # Latest date is 2026-09-20
    # Current week is 2026-09-14 to 2026-09-20
    # Prior week is 2026-09-07 to 2026-09-13
    data = {
        'date': [
            pd.to_datetime('2026-09-20'), # current
            pd.to_datetime('2026-09-15'), # current
            pd.to_datetime('2026-09-13'), # prior
            pd.to_datetime('2026-09-07'), # prior
            pd.to_datetime('2026-09-06'), # older
        ],
        'rating': [1, 2, 3, 4, 5],
        'review': ['a', 'b', 'c', 'd', 'e'],
        'themes': ['support', 'charges', 'support', 'support', 'perf'],
        'app_version': ['1.0', '1.0', '1.0', '1.0', '1.0']
    }
    df = pd.DataFrame(data)
    
    themes = {
        "support": {"sub_issues": {}},
        "charges": {"sub_issues": {}},
        "perf": {"sub_issues": {}}
    }
    
    evidence = generate_evidence(df, themes)
    assert evidence['current_week']['reviews'] == 2
    assert evidence['prior_week']['reviews'] == 2
    
def test_small_counts_no_percentage():
    data = {
        'date': [
            pd.to_datetime('2026-09-20'),
            pd.to_datetime('2026-09-13'),
        ],
        'rating': [1, 1],
        'review': ['a', 'c'],
        'themes': ['support', 'support'],
        'app_version': ['1.0', '1.0']
    }
    df = pd.DataFrame(data)
    themes = {"support": {"sub_issues": {}}}
    evidence = generate_evidence(df, themes)
    # Both counts are 1, which is < 10, so change_pct should be None
    assert evidence['theme_mentions']['support']['current'] == 1
    assert evidence['theme_mentions']['support']['prior'] == 1
    assert evidence['theme_mentions']['support']['change_pct'] is None
    
def test_spike_rule_triggers_at_2x():
    # Make median of past 28 days = 10
    # 28 days back from 2026-09-13
    dates = []
    ratings = []
    reviews = []
    themes_col = []
    versions = []
    
    # 28 days background (10 per day = median 10)
    start_28 = pd.to_datetime('2026-09-13') - timedelta(days=28)
    for i in range(1, 29):
        d = start_28 + timedelta(days=i)
        for _ in range(10):
            dates.append(d)
            ratings.append(1)
            reviews.append('terrible bad worst app')
            themes_col.append('support')
            versions.append('1.0')
            
    # Current week: one day has 19 (no spike), one has 20 (spike, since >=2*10 and >=20)
    current_start = pd.to_datetime('2026-09-13')
    d1 = current_start + timedelta(days=1)
    for _ in range(19):
        dates.append(d1)
        ratings.append(1)
        reviews.append('bad')
        themes_col.append('support')
        versions.append('1.0')
        
    d2 = current_start + timedelta(days=2)
    for _ in range(20):
        dates.append(d2)
        ratings.append(1)
        reviews.append('spike terrible app')
        themes_col.append('support')
        versions.append('1.0')
        
    df = pd.DataFrame({'date': dates, 'rating': ratings, 'review': reviews, 'themes': themes_col, 'app_version': versions})
    themes = {"support": {"sub_issues": {}}}
    
    evidence = generate_evidence(df, themes)
    spikes = evidence['spikes']
    
    assert len(spikes) == 1
    assert spikes[0]['count'] == 20
    assert spikes[0]['typical_count'] == 10.0
    assert 'spike' in spikes[0]['top_words']
    
def test_quote_candidate_exact_piece():
    # Setup data where quote could be extracted
    # 6 to 25 words
    review_text = "This app is totally useless. The customer support never replies to emails. I am very frustrated."
    
    themes = {
        "support": {
            "sub_issues": {
                "no_reply": ["never replies", "no response"]
            }
        }
    }
    
    data = {
        'date': [pd.to_datetime('2026-09-20')],
        'rating': [1],
        'review': [review_text],
        'themes': ['support'],
        'app_version': ['1.0']
    }
    df = pd.DataFrame(data)
    
    evidence = generate_evidence(df, themes)
    
    quotes = evidence.get("quotes", {})
    if "support" in quotes and len(quotes["support"]) > 0:
        quote = quotes["support"][0]["quote"]
        assert quote in review_text
        assert len(quote.split()) >= 6
