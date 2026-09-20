import os
import json
import re
import sys
import io
import contextlib
import time
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.redactor import pii_gate

def validate_note(note_text, evidence):
    errors = []
    
    # 250 words or fewer
    words = re.findall(r'\b\w+\b', note_text)
    if len(words) > 250:
        errors.append(f"Word count is {len(words)}, strictly limit to 250 words maximum.")
        
    # Exactly 3 numbered theme lines + 3 numbered action lines = 6
    numbered_lines = re.findall(r"(?m)^\s*\d+\.\s", note_text)
    if len(numbered_lines) != 6:
        errors.append(f"Must have EXACTLY 3 numbered lines for 'Top themes' and 3 numbered lines for 'Action ideas'. Found {len(numbered_lines)} numbered lines.")
        
    # Exactly 3 quote bullets
    bullets = re.findall(r"(?m)^\s*[\-\*]\s", note_text)
    if len(bullets) != 3:
        errors.append(f"Must have EXACTLY 3 bullets for 'User voice'. Found {len(bullets)} bullets.")
        
    # Every quote is an exact piece of one of the quote candidates
    candidates = []
    if "quotes" in evidence:
        for th, q_list in evidence["quotes"].items():
            for q in q_list:
                candidates.append(q["quote"])
                
    bullet_lines = [line for line in note_text.split('\n') if re.match(r"^\s*[\-\*]\s", line)]
    for bl in bullet_lines:
        found = False
        for cand in candidates:
            if cand in bl:
                found = True
                break
        if not found:
            errors.append(f"The quote in this bullet is not an exact match from the evidence: '{bl.strip()}'. Never edit, merge, or translate the quotes.")
            
    # No PII pattern
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            pii_gate(note_text)
    except SystemExit:
        errors.append("PII (like email, PAN, phone number) was found in the text. Ensure privacy rules are followed.")
        
    return errors

def generate_fallback_note(evidence):
    current = evidence.get("current_week", {})
    prior = evidence.get("prior_week", {})
    
    lines = []
    lines.append("Groww Weekly Pulse · (Fallback Template)")
    lines.append(f"Reviews: {current.get('reviews')}, Average Rating: {current.get('average_rating')} vs {prior.get('average_rating')}, Low-Rated: {current.get('low_rated')} vs {prior.get('low_rated')}\n")
    
    lines.append("Top themes:")
    top_themes = evidence.get("top_themes", {})
    theme_mentions = evidence.get("theme_mentions", {})
    i = 1
    for th, th_data in top_themes.items():
        m = theme_mentions.get(th, {})
        driver_str = th_data.get('driver') if th_data.get('driver') else "general complaints"
        chg = f"{m.get('change_pct')}%" if m.get('change_pct') is not None else "no change data"
        lines.append(f"{i}. {th.capitalize()}: {m.get('current')} mentions (change {chg}). Driver: {driver_str}")
        i += 1
        
    lines.append("\nUser voice:")
    quotes = evidence.get("quotes", {})
    for th in top_themes.keys():
        if th in quotes and len(quotes[th]) > 0:
            q = quotes[th][0]
            lines.append(f"- \"{q['quote']}\" ({q['rating']} star, {q['date']})")
            
    try:
        with open("config/themes.json", "r", encoding="utf-8") as f:
            themes_config = json.load(f)
    except Exception:
        themes_config = {}

    lines.append("\nAction ideas:")
    i = 1
    for th in top_themes.keys():
        t_data = themes_config.get(th, {})
        owner = t_data.get("owner", "Team")
        action = t_data.get("action", "Review themes.")
        metric = t_data.get("metric", "metrics")
        lines.append(f"{i}. **{owner}**: {action} Track: {metric}")
        i += 1
    
    return "\n".join(lines)

def run_ai(evidence_text, prompt_text, model_name, backup_model_name, api_key):
    client = genai.Client(api_key=api_key)
    base_prompt = f"{prompt_text}\n\nEVIDENCE:\n{evidence_text}"
    
    api_calls_made = 0
    quota_exhausted = False
    
    models_to_try = [model_name]
    if backup_model_name:
        models_to_try.append(backup_model_name)
        
    for m_idx, current_model in enumerate(models_to_try):
        is_backup = (m_idx > 0)
        wait_times = [10, 30, 60]
        network_attempts = 0
        val_attempts = 0
        current_prompt = base_prompt
        
        while True:
            api_calls_made += 1
            attempt_number = network_attempts + val_attempts + 1
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=current_prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                note_text = response.text
                errors = validate_note(note_text, json.loads(evidence_text))
                if not errors:
                    print(f"Model: {current_model}, attempt {attempt_number}, result: success")
                    return note_text, True, api_calls_made, False, current_model
                else:
                    print(f"Model: {current_model}, attempt {attempt_number}, result: validation failure")
                    if val_attempts < 2:
                        val_attempts += 1
                        error_msg = "Your previous response failed validation with these errors:\n- " + "\n- ".join(errors) + "\nPlease fix them and try again."
                        current_prompt = f"{base_prompt}\n\n{error_msg}"
                        continue
                    else:
                        break # Give up on this model after 2 retries (3 total attempts)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    print(f"Model: {current_model}, attempt {attempt_number}, result: 429 quota error")
                    if not is_backup and backup_model_name:
                        break # Switch to backup model
                    else:
                        print("Daily quota is exhausted.")
                        return None, False, api_calls_made, True, current_model
                elif "404" in err_str or "not found" in err_str.lower():
                    print(f"Model: {current_model}, attempt {attempt_number}, result: 404 model not found")
                    print(f"Model ID {current_model} failed because it was not found.")
                    return None, False, api_calls_made, False, current_model
                elif "503" in err_str or "500" in err_str or "timeout" in err_str.lower():
                    print(f"Model: {current_model}, attempt {attempt_number}, result: 5xx/timeout error")
                    if network_attempts < len(wait_times):
                        time.sleep(wait_times[network_attempts])
                        network_attempts += 1
                        continue
                    else:
                        break # Switch to backup model after 3 network retries
                else:
                    print(f"Model: {current_model}, attempt {attempt_number}, result: unknown error")
                    break

    return None, False, api_calls_made, False, None

def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    with open("config/settings.json", "r") as f:
        settings = json.load(f)
    model_name = settings.get("llm_model", "gemini-3.8-flash")
    backup_model_name = settings.get("llm_model_backup")
    
    with open("out/evidence.json", "r") as f:
        evidence_text = f.read()
    evidence_json = json.loads(evidence_text)
    
    with open("prompts/note_prompt.md", "r") as f:
        prompt_text = f.read()
        
    note_text = None
    ai_used = False
    api_calls_made = 0
    quota_exhausted = False
    used_model = None
    
    if api_key:
        note_text, ai_used, api_calls_made, quota_exhausted, used_model = run_ai(
            evidence_text, prompt_text, model_name, backup_model_name, api_key
        )
        
    if not ai_used or not note_text:
        note_text = generate_fallback_note(evidence_json)
        ai_used = False

        
    end_date = "latest"
    if os.path.exists("out/reviews_redacted.csv"):
        try:
            df_red = pd.read_csv("out/reviews_redacted.csv")
            df_red['date'] = pd.to_datetime(df_red['date'])
            latest_date = df_red['date'].max()
            end_date = latest_date.strftime("%Y-%m-%d")
        except Exception:
            pass
            
    out_path = f"out/pulse_{end_date}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(note_text)
    with open("out/pulse_latest.md", "w", encoding="utf-8") as f:
        f.write(note_text)
        
    status = "AI used" if ai_used else "template used"
    if quota_exhausted:
        reason = "daily quota exhausted"
    else:
        reason = "model failed or not found"
        
    if ai_used:
        print(f"Note written by model: {used_model}")
    else:
        print(f"Written by: template used. Reason: {reason}")
        
    print(f"Total API calls: {api_calls_made}")
    print("\n--- NOTE PREVIEW ---\n")
    print(note_text)
    print("\n--------------------\n")

if __name__ == "__main__":
    main()
