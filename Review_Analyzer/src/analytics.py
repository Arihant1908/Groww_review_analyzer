import os
import json
import re
import math
import pandas as pd
import numpy as np
from datetime import timedelta

STOP_WORDS = set([
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours",
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by",
    "for", "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "don", "should", "now", "app", "groww", "very", "really", "so", "much",
    "many", "please", "plz", "is", "the", "in", "on", "of", "and", "to", "a"
])

PROFANITY = ["fuck", "shit", "bitch", "ass", "asshole", "cunt", "bastard", "dick", "pussy"]

def get_words(text):
    return re.findall(r'\b[a-z]{2,}\b', str(text).lower())

def z_score(p1, n1, p2, n2):
    if n1 == 0 or n2 == 0:
        return 0.0
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return 0.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    if se == 0:
        return 0.0
    return (p1 - p2) / se

def parse_version(v):
    if pd.isna(v) or not isinstance(v, str):
        return (0, 0, 0)
    parts = re.findall(r'\d+', v)
    return tuple(map(int, parts)) if parts else (0, 0, 0)

def extract_sentences(text):
    sentences = re.split(r'[.!?\n]+', str(text))
    return [s.strip() for s in sentences if s.strip()]

def get_top_driver(df_theme, theme_config):
    sub_issues = theme_config.get("sub_issues", {})
    if not sub_issues:
        return None
    counts = {}
    text_corpus = " ".join(df_theme["review"].astype(str).tolist()).lower()
    for label, keywords in sub_issues.items():
        count = 0
        for kw in keywords:
            pattern = r'\b' + re.escape(kw.lower()) + r'\b'
            count += len(re.findall(pattern, text_corpus))
        counts[label] = count
    
    if not counts:
        return None
    top_label = max(counts, key=counts.get)
    if counts[top_label] > 0:
        return top_label
    return None

def score_quote(sentence, rating, driver_label, theme_config, thumbs_up):
    words = get_words(sentence)
    if not (6 <= len(words) <= 25):
        return -1
    
    ascii_chars = sum(1 for c in sentence if ord(c) < 128)
    if ascii_chars / max(len(sentence), 1) < 0.8:
        return -1
    
    if re.search(r'\[(NAME|ID|EMAIL|PHONE|URL)\]', sentence):
        return -1
        
    if any(p in words for p in PROFANITY):
        return -1
        
    clean_sent = re.sub(r'[^a-z ]', '', sentence.lower()).strip()
    generic_openers = ["worst app", "bad app", "very bad app", "worst application", "wrost app", "pathetic app", "worst"]
    if clean_sent in generic_openers:
        return -1
        
    score = 0
    if rating <= 2:
        score += 2
        
    if driver_label and driver_label in theme_config.get("sub_issues", {}):
        kws = theme_config["sub_issues"][driver_label]
        if any(re.search(r'\b' + re.escape(kw) + r'\b', clean_sent) for kw in kws):
            score += 3
            
    if re.search(r'\d', sentence):
        score += 2
        
    if thumbs_up and thumbs_up > 0:
        score += 1
        
    if "fraud" in words or "scam" in words:
        score -= 5
        
    return score

def count_theme(d, th):
    return sum(d['themes'].fillna("").apply(lambda x: th in [t.strip() for t in str(x).split(",")]))

def generate_evidence(df, themes):
    latest_date = df['date'].max()
    current_week_start = latest_date - timedelta(days=7)
    prior_week_start = current_week_start - timedelta(days=7)
    
    df_current = df[(df['date'] > current_week_start) & (df['date'] <= latest_date)]
    df_prior = df[(df['date'] > prior_week_start) & (df['date'] <= current_week_start)]
    
    evidence = {
        "current_week": {
            "reviews": len(df_current),
            "average_rating": round(float(df_current['rating'].mean()), 2) if len(df_current) > 0 else 0,
            "low_rated": len(df_current[df_current['rating'] <= 3])
        },
        "prior_week": {
            "reviews": len(df_prior),
            "average_rating": round(float(df_prior['rating'].mean()), 2) if len(df_prior) > 0 else 0,
            "low_rated": len(df_prior[df_prior['rating'] <= 3])
        }
    }
    
    df_curr_low = df_current[df_current['rating'] <= 3]
    df_prior_low = df_prior[df_prior['rating'] <= 3]
        
    theme_mentions = {}
    for th in themes.keys():
        curr_count = count_theme(df_curr_low, th)
        prior_count = count_theme(df_prior_low, th)
        change = None
        if curr_count >= 10 and prior_count >= 10:
            change = round(((curr_count - prior_count) / prior_count) * 100, 1)
        
        theme_mentions[th] = {
            "current": int(curr_count),
            "prior": int(prior_count),
            "change_pct": change
        }
        
    evidence["theme_mentions"] = theme_mentions
    
    sorted_themes = sorted(theme_mentions.items(), key=lambda x: x[1]["current"], reverse=True)
    top_3 = [t[0] for t in sorted_themes[:3]]
    
    evidence["top_themes"] = {}
    for th in top_3:
        th_df = df_curr_low[df_curr_low['themes'].fillna("").apply(lambda x: th in [t.strip() for t in str(x).split(",")])]
        driver = get_top_driver(th_df, themes.get(th, {}))
        evidence["top_themes"][th] = {
            "driver": driver
        }
        
    start_28 = current_week_start - timedelta(days=28)
    df_28 = df[(df['date'] > start_28) & (df['date'] <= current_week_start)]
    
    df_curr_low_daily = df_curr_low.groupby(df_curr_low['date'].dt.date).size()
    df_28_low = df_28[df_28['rating'] <= 3]
    df_28_low_daily = df_28_low.groupby(df_28_low['date'].dt.date).size()
    
    all_28_days = [start_28.date() + timedelta(days=i) for i in range(1, 29)]
    counts_28 = [df_28_low_daily.get(d, 0) for d in all_28_days]
    median_28 = np.median(counts_28) if counts_28 else 0
    
    spikes = []
    all_curr_days = [current_week_start.date() + timedelta(days=i) for i in range(1, 8)]
    for d in all_curr_days:
        c = df_curr_low_daily.get(d, 0)
        if c >= 20 and c >= 2 * median_28:
            day_reviews = df_curr_low[df_curr_low['date'].dt.date == d]['review'].tolist()
            prev_reviews = df_28_low['review'].tolist()
            
            day_words = {}
            for r in day_reviews:
                for w in get_words(r):
                    if w not in STOP_WORDS:
                        day_words[w] = day_words.get(w, 0) + 1
                        
            prev_words = {}
            for r in prev_reviews:
                for w in get_words(r):
                    if w not in STOP_WORDS:
                        prev_words[w] = prev_words.get(w, 0) + 1
                        
            word_diffs = {}
            for w, cnt in day_words.items():
                expected = prev_words.get(w, 0) / 28.0
                word_diffs[w] = cnt - expected
                
            top_words = sorted(word_diffs.items(), key=lambda x: x[1], reverse=True)[:3]
            
            spikes.append({
                "date": str(d),
                "count": int(c),
                "typical_count": float(median_28),
                "top_words": [w[0] for w in top_words]
            })
            
    evidence["spikes"] = spikes
    
    start_v = latest_date - timedelta(days=28)
    df_v = df[df['date'] > start_v].copy()
    
    version_counts = df_v['app_version'].value_counts()
    valid_versions = version_counts[version_counts >= 100].index.tolist()
    
    version_check = None
    if valid_versions:
        newest_v = max(valid_versions, key=parse_version)
        
        df_newest = df_v[df_v['app_version'] == newest_v]
        df_others = df_v[df_v['app_version'].isin(valid_versions) & (df_v['app_version'] != newest_v)]
        
        if len(df_newest) > 0 and len(df_others) > 0:
            n1 = len(df_newest)
            low1 = len(df_newest[df_newest['rating'] <= 2])
            p1 = low1 / n1
            
            n2 = len(df_others)
            low2 = len(df_others[df_others['rating'] <= 2])
            p2 = low2 / n2
            
            z = z_score(p1, n1, p2, n2)
            if z >= 2.5:
                version_check = {
                    "newest_version": newest_v,
                    "newest_share_1_2_star": round(p1, 3),
                    "others_share_1_2_star": round(p2, 3),
                    "z_score": round(z, 2)
                }
    evidence["version_check"] = version_check
    
    quotes = {}
    for th in top_3:
        th_df = df_curr_low[df_curr_low['themes'].fillna("").apply(lambda x: th in [t.strip() for t in str(x).split(",")])]
        driver_label = evidence["top_themes"][th]["driver"]
        
        cands = []
        seen_reviews = set()
        
        for idx, row in th_df.iterrows():
            rev = str(row['review'])
            sents = extract_sentences(rev)
            best_sent = None
            best_score = -1
            
            for s in sents:
                score = score_quote(s, row['rating'], driver_label, themes.get(th, {}), row.get('thumbs_up', 0))
                if score >= 0 and score > best_score:
                    best_score = score
                    best_sent = s
                    
            if best_sent:
                cands.append({
                    "quote": best_sent,
                    "score": best_score,
                    "rating": row['rating'],
                    "date": str(row['date']),
                    "review_id": idx,
                    "source_review": rev
                })
                
        cands = sorted(cands, key=lambda x: x['score'], reverse=True)
        final_quotes = []
        for c in cands:
            if c['review_id'] not in seen_reviews:
                if c['quote'] in c['source_review']:
                    seen_reviews.add(c['review_id'])
                    final_quotes.append({
                        "quote": c['quote'],
                        "rating": int(c['rating']),
                        "date": c['date']
                    })
            if len(final_quotes) == 5:
                break
        quotes[th] = final_quotes
        
    evidence["quotes"] = quotes
    
    return evidence

def generate_weekly_trend(df, themes):
    latest_date = df['date'].max()
    min_date = df['date'].min()
    current_end = latest_date
    trend_rows = []
    
    while current_end > min_date:
        current_start = current_end - timedelta(days=7)
        block = df[(df['date'] > current_start) & (df['date'] <= current_end)]
        
        if len(block) > 0:
            row = {
                "period_end": str(current_end.date()),
                "reviews": len(block),
                "average_rating": round(float(block['rating'].mean()), 2),
                "share_1_2_star": round(len(block[block['rating'] <= 2]) / len(block), 3),
                "low_rated_count": len(block[block['rating'] <= 3])
            }
            
            block_low = block[block['rating'] <= 3]
            for th in themes.keys():
                row[f"{th}_mentions"] = count_theme(block_low, th)
                
            trend_rows.append(row)
            
        current_end = current_start
        
    return pd.DataFrame(trend_rows)

def main():
    if not os.path.exists("out/reviews_themed.csv"):
        print("Data file not found.")
        return

    df = pd.read_csv("out/reviews_themed.csv")
    df['date'] = pd.to_datetime(df['date'])
    
    with open("config/themes.json", "r") as f:
        themes = json.load(f)
        
    evidence = generate_evidence(df, themes)
    with open("out/evidence.json", "w") as f:
        json.dump(evidence, f, indent=2)
        
    trend_df = generate_weekly_trend(df, themes)
    trend_df.to_csv("out/weekly_trend.csv", index=False)
    print("Numbers stage complete.")

if __name__ == "__main__":
    main()
