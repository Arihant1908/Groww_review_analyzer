import os
import re
import pandas as pd
import json

def scan_privacy():
    print("--- Privacy Scan ---")
    files_to_scan = [
        "out/reviews_redacted.csv",
        "out/reviews_themed.csv",
        "out/evidence.json",
        "out/email_draft.txt",
        "out/email_draft.eml",
        "out/email_gmail_link.txt",
        "app.py"
    ]
    
    # regexes
    email_regex = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    phone_regex = r'\+?\d[\d -]{8,12}\d'
    pan_regex = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
    
    # 1. Check text files for regexes
    for file in files_to_scan:
        if not os.path.exists(file): continue
        with open(file, "r", encoding="utf-8") as f:
            text = f.read()
            # If it's email_draft, there's obviously the "recipient_email" which is config, not a privacy leak from the data.
            # But let's check for any PANs
            pans = set(re.findall(pan_regex, text))
            phones = set(re.findall(phone_regex, text))
            if pans:
                print(f"FAIL: {file} contains PAN: {pans}")
            if file not in ["out/email_draft.txt", "out/email_draft.eml", "out/email_gmail_link.txt", "app.py"]:
                emails = set(re.findall(email_regex, text))
                if emails:
                    print(f"FAIL: {file} contains Emails: {emails}")
                    
    # 2. Check for user column names in redacted reviews
    df_raw = pd.read_csv("data/raw/reviews_raw.csv")
    df_red = pd.read_csv("out/reviews_redacted.csv")
    
    # See if user column is present in out files
    if "user" in df_red.columns:
        print("FAIL: 'user' column is present in out/reviews_redacted.csv")
        
    df_themed = pd.read_csv("out/reviews_themed.csv")
    if "user" in df_themed.columns:
        print("FAIL: 'user' column is present in out/reviews_themed.csv")
        
    # See if any exact user names from raw data appear in redacted reviews text
    user_names = set(df_raw["user"].dropna().unique())
    user_names = {u for u in user_names if len(str(u).split()) > 1} # only check full names to avoid false positives with common words
    
    # For speed, check the corpus
    redacted_corpus = " ".join(df_red["review"].dropna().astype(str))
    leaks = 0
    for u in user_names:
        if str(u) in redacted_corpus:
            print(f"FAIL: Found user name '{u}' in out/reviews_redacted.csv text")
            leaks += 1
            
    if leaks == 0:
        print("PASS: No user names leaked into review text.")

if __name__ == "__main__":
    scan_privacy()
