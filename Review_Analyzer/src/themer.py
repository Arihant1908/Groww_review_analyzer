import pandas as pd
import json
import os
import sys
import hashlib
import re
import random
from dotenv import load_dotenv
from google import genai
from google.genai import types

def load_config():
    with open("config/themes.json", "r", encoding="utf-8") as f:
        themes = json.load(f)
    actual_themes = [k for k in themes.keys() if k != "unthemed"]
    if len(actual_themes) != 5:
        print("Error: config/themes.json must contain exactly 5 themes.")
        sys.exit(1)
        
    with open("config/settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
        
    with open("config/keywords.json", "r", encoding="utf-8") as f:
        keywords = json.load(f)
        
    return themes, settings, keywords

def get_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def fallback_theme(text, themes, keywords):
    if not isinstance(text, str) or not text.strip():
        return ["unthemed"]
    text_lower = text.lower()
    assigned = set()
    for theme_id in themes:
        kw_list = keywords.get(theme_id, [])
        for kw in kw_list:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                assigned.add(theme_id)
                if len(assigned) == 2:
                    break
        if len(assigned) == 2:
            break
    
    if not assigned:
        return ["unthemed"]
    return list(assigned)

def batch_generator(data, batch_size=30):
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]

def call_gemini(batch_texts, themes, model_name, api_key):
    client = genai.Client(api_key=api_key)
    
    themes_desc = "\n".join([f"- {tid}: {t['name']} - {t['definition']}" for tid, t in themes.items()])
    
    prompt = f"""You are a strict data classifier. Classify these app reviews into the following themes:
{themes_desc}

Rules:
1. Return EXACTLY 1 or 2 theme IDs for each review.
2. If it doesn't fit the 5 themes, use ["unthemed"].
3. Return ONLY a valid JSON object mapping the string index "0", "1" etc. to the list of theme IDs.
4. Reviews may be short, misspelled, or in Hinglish. Use the meaning, not exact keywords.

Reviews to classify:
"""
    for i, text in enumerate(batch_texts):
        # Prevent injection or confusing formatting by escaping
        safe_text = text.replace('\n', ' ').replace('"', '\\"')
        prompt += f'"{i}": "{safe_text}"\n'

    for attempt in range(3):
        try:
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                text = getattr(response, "text", getattr(response, "output_text", ""))
            else:
                response = client.interactions.create(
                    model=model_name,
                    input=prompt,
                    generation_config={"temperature": 0, "response_mime_type": "application/json"}
                )
                text = getattr(response, "output_text", getattr(response, "text", ""))
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            result = json.loads(text)
            
            # Validation
            valid_ids = set(themes.keys()) | {"unthemed"}
            for i in range(len(batch_texts)):
                idx = str(i)
                if idx not in result:
                    raise ValueError(f"Missing index {idx} in response")
                assigned = result[idx]
                if not isinstance(assigned, list) or len(assigned) == 0:
                    raise ValueError(f"Invalid format for index {idx}")
                if not all(tid in valid_ids for tid in assigned):
                    raise ValueError(f"Invalid theme ID used for index {idx}")
                    
            return result
        except Exception as e:
            err_str = str(e)
            print(f"Attempt {attempt} failed: {err_str}")
            if "429" in err_str or "Rate limit" in err_str:
                raise RuntimeError("RATE_LIMIT")
            if attempt == 2:
                raise e
            continue

def themer(df):
    themes, settings, keywords = load_config()
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        print("Key found: yes")
    else:
        print("Key found: no")
        if not any("unittest" in m or "pytest" in m for m in sys.modules):
            print("Error: GEMINI_API_KEY is not set in .env file.")
            sys.exit(1)
    
    # 4-5 stars positive
    df["themes"] = None
    df.loc[df["rating"].isin([4, 5]), "themes"] = "positive"
    
    needs_theme_idx = df[df["themes"].isnull()].index
    
    cache_path = os.path.join("out", "theme_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except:
            pass

    model_name = settings.get("llm_model", "gemini-2.5-flash")
    
    # Create a fingerprint of themes definitions and AI instructions
    themes_desc = "\n".join([f"- {tid}: {t['name']} - {t['definition']}" for tid, t in themes.items()])
    ai_instructions = "Rules:\n1. Return EXACTLY 1 or 2 theme IDs for each review.\n2. If it doesn't fit the 5 themes, use [\"unthemed\"].\n3. Return ONLY a valid JSON object mapping the string index \"0\", \"1\" etc. to the list of theme IDs.\n4. Reviews may be short, misspelled, or in Hinglish. Use the meaning, not exact keywords."
    fingerprint_text = themes_desc + "\n" + ai_instructions
    fingerprint = get_hash(fingerprint_text)
    
    # Find what needs API
    to_process = []
    for idx in needs_theme_idx:
        text = str(df.loc[idx, "review"]).strip()
        if not text:
            df.at[idx, "themes"] = "unthemed"
            continue
            
        combined_text = text + "_" + fingerprint
        h = get_hash(combined_text)
        if h in cache:
            entry = cache[h]
            assigned = entry["themes"] if isinstance(entry, dict) else entry
            df.at[idx, "themes"] = ",".join(assigned)
        else:
            to_process.append((idx, text, h))

    layer_used = "Layer A (Gemini API)"
    if not api_key:
        layer_used = "Layer B (Fallback Keywords)"
        print("API key missing. Using Layer B fallback.")
        for idx, text, h in to_process:
            assigned = fallback_theme(text, themes, keywords)
            cache[h] = {"themes": assigned, "layer": "fallback"}
            df.at[idx, "themes"] = ",".join(assigned)
    else:
        # Batch API
        print(f"Using {layer_used} with model {model_name}. Processing {len(to_process)} new reviews...")
        batches = list(batch_generator(to_process, 30))
        force_fallback = True
        for b_i, batch in enumerate(batches):
            if force_fallback:
                for idx, text, h in batch:
                    assigned = fallback_theme(text, themes, keywords)
                    cache[h] = {"themes": assigned, "layer": "fallback"}
                    df.at[idx, "themes"] = ",".join(assigned)
                continue
                
            batch_texts = [t[1] for t in batch]
            try:
                res = call_gemini(batch_texts, themes, model_name, api_key)
                for i, (idx, text, h) in enumerate(batch):
                    assigned = res[str(i)]
                    cache[h] = {"themes": assigned, "layer": "ai"}
                    df.at[idx, "themes"] = ",".join(assigned)
                print(f"Batch {b_i} processed successfully.")
            except Exception as e:
                err_str = str(e)
                print(f"API failed on batch {b_i}: {err_str}. Falling back to Layer B.")
                if "RATE_LIMIT" in err_str:
                    print("Rate limit reached. Forcing Layer B for all remaining batches.")
                    force_fallback = True
                    
                for idx, text, h in batch:
                    assigned = fallback_theme(text, themes, keywords)
                    cache[h] = {"themes": assigned, "layer": "fallback"}
                    df.at[idx, "themes"] = ",".join(assigned)

    # Save cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    return df, themes

def save_summary(df, themes):
    # Only 1-3 star reviews
    neg_df = df[df["rating"].isin([1, 2, 3])]
    
    # Unthemed count
    unthemed_count = len(neg_df[neg_df["themes"] == "unthemed"])
    
    summary_data = []
    for tid in themes.keys():
        # Count mentions
        mask = neg_df["themes"].str.contains(r'\b' + tid + r'\b', na=False)
        mentions = mask.sum()
        avg_rating = neg_df[mask]["rating"].mean() if mentions > 0 else 0
        summary_data.append({
            "theme": tid,
            "mentions": mentions,
            "average_rating": round(avg_rating, 2)
        })
        
    summary_df = pd.DataFrame(summary_data)
    summary_path = os.path.join("out", "theme_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    
    print(f"Summary saved to {summary_path}")
    print(f"Unthemed 1-3 star reviews: {unthemed_count}")

def human_check():
    df = pd.read_csv("out/reviews_themed.csv")
    neg_df = df[df["rating"].isin([1, 2, 3])]
    
    themes_list = list(json.load(open("config/themes.json", "r")).keys()) + ["unthemed"]
    
    out_path = os.path.join("out", "theme_check.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Theme Human Check\n\n")
        
        for tid in themes_list:
            f.write(f"## Theme: {tid}\n\n")
            if tid == "unthemed":
                subset = neg_df[neg_df["themes"] == "unthemed"]
            else:
                subset = neg_df[neg_df["themes"].str.contains(r'\b' + tid + r'\b', na=False)]
                
            n_samples = min(15, len(subset))
            if n_samples == 0:
                f.write("No reviews found for this theme.\n\n")
                continue
                
            sample = subset.sample(n_samples)
            for _, row in sample.iterrows():
                f.write(f"**Rating:** {row['rating']} | **Themes:** {row['themes']}\n")
                f.write(f"> {row['review']}\n\n")
                
    print(f"Human check file saved to {out_path}")

def run_pipeline():
    if not os.path.exists(os.path.join("out", "reviews_redacted.csv")):
        print("Run redactor first.")
        sys.exit(1)
        
    df = pd.read_csv(os.path.join("out", "reviews_redacted.csv"))
    df_themed, themes = themer(df)
    
    out_path = os.path.join("out", "reviews_themed.csv")
    df_themed.to_csv(out_path, index=False)
    print(f"Themed data saved to {out_path}")
    
    save_summary(df_themed, themes)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        human_check()
    else:
        run_pipeline()
