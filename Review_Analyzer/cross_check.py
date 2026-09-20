import csv
import json
from datetime import datetime, timedelta

def check_metrics():
    # Read themed reviews to calculate metrics
    themed_rows = []
    with open("out/reviews_themed.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            themed_rows.append(row)
            
    # Find latest date
    latest_date_str = max([r["date"] for r in themed_rows])
    latest_date = datetime.strptime(latest_date_str[:10], "%Y-%m-%d")
    current_week_start = latest_date - timedelta(days=7)
    
    # Compute current week metrics
    current_week_reviews = []
    for r in themed_rows:
        r_date = datetime.strptime(r["date"][:10], "%Y-%m-%d")
        if current_week_start < r_date <= latest_date:
            current_week_reviews.append(r)
            
    review_count = len(current_week_reviews)
    low_rated_count = sum(1 for r in current_week_reviews if int(r["rating"]) <= 3)
    avg_rating = sum(int(r["rating"]) for r in current_week_reviews) / review_count if review_count > 0 else 0
    
    # Theme counts
    theme_counts = {}
    for r in current_week_reviews:
        if int(r["rating"]) <= 3:
            # Parse themes: split by comma, strip
            themes = [t.strip() for t in r.get("themes", "").split(",") if t.strip()]
            if not themes:
                themes = ["unthemed"]
            for th in themes:
                theme_counts[th] = theme_counts.get(th, 0) + 1
                
    # Find top theme
    top_theme = max(theme_counts.items(), key=lambda x: x[1]) if theme_counts else (None, 0)
    
    print(f"Computed - count: {review_count}, low: {low_rated_count}, avg: {avg_rating:.2f}")
    print(f"Top Theme computed: {top_theme[0]} ({top_theme[1]} mentions)")
    
    # Check evidence.json
    with open("out/evidence.json", "r", encoding="utf-8") as f:
        evidence = json.load(f)
        
    ev_current = evidence.get("current_week", {})
    ev_count = ev_current.get("reviews")
    ev_low = ev_current.get("low_rated")
    ev_avg = ev_current.get("average_rating")
    
    # top theme from evidence
    ev_theme_mentions = evidence.get("theme_mentions", {})
    ev_top_theme = None
    ev_top_val = -1
    for th, vals in ev_theme_mentions.items():
        if vals.get("current", 0) > ev_top_val:
            ev_top_val = vals.get("current", 0)
            ev_top_theme = th
            
    print(f"Evidence - count: {ev_count}, low: {ev_low}, avg: {ev_avg:.2f}")
    print(f"Top Theme evidence: {ev_top_theme} ({ev_top_val} mentions)")

if __name__ == "__main__":
    check_metrics()
