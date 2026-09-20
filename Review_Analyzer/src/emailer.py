import os
import sys
import json
import re
import urllib.parse
from email.message import EmailMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.redactor import pii_gate

def get_config():
    with open("config/settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def clean_markdown(text):
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove heading tags
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    return text

def create_email_drafts(pulse_file, recipient_email, date_range):
    with open(pulse_file, "r", encoding="utf-8") as f:
        note_text = f.read()

    # Clean markdown
    body = clean_markdown(note_text)

    # PII Check
    pii_gate(body)

    subject = f"Groww Weekly Pulse: {date_range}"

    # 1. Plain text draft
    txt_content = f"To: {recipient_email}\nSubject: {subject}\n\n{body}"
    with open("out/email_draft.txt", "w", encoding="utf-8") as f:
        f.write(txt_content)

    # 2. .eml file
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['To'] = recipient_email
    msg.set_content(body)
    with open("out/email_draft.eml", "w", encoding="utf-8") as f:
        f.write(str(msg))

    # 3. Gmail link
    base_url = "https://mail.google.com/mail/?view=cm&fs=1"
    params = {
        "to": recipient_email,
        "su": subject,
        "body": body
    }
    gmail_link = base_url + "&" + urllib.parse.urlencode(params)
    with open("out/email_gmail_link.txt", "w", encoding="utf-8") as f:
        f.write(gmail_link)
        
    print("Email drafts generated successfully in out/ directory.")

def main():
    settings = get_config()
    recipient = settings.get("recipient_email", "[EMAIL]")
    
    # Try to find date range
    end_date = "latest"
    date_range = "Latest"
    if os.path.exists("out/reviews_redacted.csv"):
        import pandas as pd
        try:
            df = pd.read_csv("out/reviews_redacted.csv")
            df['date'] = pd.to_datetime(df['date'])
            latest_date = df['date'].max()
            current_week_start = latest_date - pd.Timedelta(days=7)
            end_date = latest_date.strftime("%Y-%m-%d")
            date_range = f"{current_week_start.strftime('%b %d')} - {latest_date.strftime('%b %d, %Y')}"
        except Exception:
            pass
            
    pulse_file = f"out/pulse_{end_date}.md"
    if not os.path.exists(pulse_file):
        pulse_file = "out/pulse_latest.md"
        
    if not os.path.exists(pulse_file):
        print(f"Error: Could not find {pulse_file}")
        sys.exit(1)
        
    create_email_drafts(pulse_file, recipient, date_range)

if __name__ == "__main__":
    main()
