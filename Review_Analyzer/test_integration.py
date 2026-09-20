import os
import shutil
import subprocess
import sys
import pandas as pd
import json

def test_pipeline():
    print("Testing pipeline from empty out/ folder...")
    if os.path.exists("out"):
        shutil.rmtree("out")
    os.makedirs("out", exist_ok=True)
    
    # Run the pipeline
    result = subprocess.run([sys.executable, "run.py"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Pipeline failed!")
        print(result.stdout)
        print(result.stderr)
        return False
        
    print("Pipeline finished successfully. Checking files...")
    
    # 1. Check Section 1 values
    try:
        df_redacted = pd.read_csv("out/reviews_redacted.csv")
        df_redacted['date'] = pd.to_datetime(df_redacted['date'])
        latest_date = df_redacted['date'].max()
        current_week_start = latest_date - pd.Timedelta(days=7)
        df_current = df_redacted[(df_redacted['date'] > current_week_start) & (df_redacted['date'] <= latest_date)]
        review_count = len(df_current)
        avg_rating = df_current["rating"].mean() if review_count > 0 else 0
        end_date = latest_date.strftime("%Y-%m-%d")
        date_range = f"{current_week_start.strftime('%b %d')} - {latest_date.strftime('%b %d, %Y')}"
        print(f"Section 1: Loaded Review Count={review_count}, Avg Rating={avg_rating:.2f}, Range={date_range}")
    except Exception as e:
        print(f"Section 1 Failed: {e}")
        return False

    # 2. Check Section 2 values
    try:
        tags = ["[URL]", "[EMAIL]", "[ID]", "[PHONE]", "[NAME]"]
        def has_tag(text):
            if pd.isna(text): return False
            return any(tag in str(text) for tag in tags)
        redacted_count = df_redacted["review"].apply(has_tag).sum()
        print(f"Section 2: Loaded Redacted Count={redacted_count}")
    except Exception as e:
        print(f"Section 2 Failed: {e}")
        return False
        
    # 3. Check Section 3 values
    try:
        with open("out/evidence.json", "r", encoding="utf-8") as f:
            evidence = json.load(f)
        theme_mentions = evidence.get("theme_mentions", {})
        themes_data = []
        unthemed_count = 0
        for theme, data in theme_mentions.items():
            mentions = data.get("current", 0)
            change = data.get("change_pct", "N/A")
            if change != "N/A" and change is not None:
                change = f"{change:+.1f}%"
            else:
                prior = data.get("prior", 0)
                change = f"{mentions} vs {prior}"
            if theme.lower() == "unthemed":
                unthemed_count = mentions
            themes_data.append({"Theme": theme.capitalize(), "Mentions this week": mentions, "Change vs last week": change})
        print(f"Section 3: Loaded {len(themes_data)} themes, unthemed={unthemed_count}")
    except Exception as e:
        print(f"Section 3 Failed: {e}")
        return False
        
    # 4. Check Section 4 values
    try:
        pulse_file = f"out/pulse_{end_date}.md"
        if not os.path.exists(pulse_file):
            pulse_file = "out/pulse_latest.md"
        with open(pulse_file, "r", encoding="utf-8") as f:
            note_text = f.read()
        word_count = len(note_text.split())
        print(f"Section 4: Loaded Note from {pulse_file}, words={word_count}")
    except Exception as e:
        print(f"Section 4 Failed: {e}")
        return False
        
    # 5. Check Section 5 values
    try:
        with open("out/email_draft.txt", "r", encoding="utf-8") as f:
            email_txt = f.read()
        with open("out/email_draft.eml", "r", encoding="utf-8") as f:
            eml_content = f.read()
        with open("out/email_gmail_link.txt", "r", encoding="utf-8") as f:
            gmail_link = f.read()
        print(f"Section 5: Loaded email draft ({len(email_txt)} chars), eml ({len(eml_content)} chars), link ({len(gmail_link)} chars)")
    except Exception as e:
        print(f"Section 5 Failed: {e}")
        return False
        
    print("ALL TESTS PASSED! Every value the app displays can be loaded from the generated files.")
    return True

if __name__ == "__main__":
    if test_pipeline():
        sys.exit(0)
    else:
        sys.exit(1)
