import pandas as pd
import json
import sys
import re
from datetime import timedelta
import os

def load_config():
    config_path = os.path.join("config", "settings.json")
    if not os.path.exists(config_path):
        return {"weeks_to_import": 12}
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    weeks = config.get("weeks_to_import", 12)
    if not (8 <= weeks <= 12):
        weeks = 12
    return {"weeks_to_import": weeks}

def import_reviews(file_path):
    import io
    try:
        if not sys.stdin.isatty():
            df = pd.read_csv(io.StringIO(sys.stdin.read()))
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        sys.exit(1)

    # 1. Rename columns to lower case
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Handle 'text' vs 'review'
    if "text" in df.columns and "review" not in df.columns:
        df = df.rename(columns={"text": "review"})

    # 2. Check for missing required columns
    required_cols = {"date", "rating", "review"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        missing_str = ", ".join(missing_cols)
        print(f"Error: The following required columns are missing from the file: {missing_str}.")
        sys.exit(1)

    # 3. Date parsing
    if df.empty:
        print("Error: The file is empty.")
        sys.exit(1)
        
    first_date = str(df["date"].dropna().iloc[0]).strip()
    
    # Check formats
    if re.match(r"^\d{2}-\d{2}-\d{4}", first_date):
        # Format: DD-MM-YYYY HH:MM (e.g., 18-09-2026 23:56)
        try:
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y %H:%M")
        except ValueError:
            print("Error: Date format mismatch. Expected DD-MM-YYYY HH:MM.")
            sys.exit(1)
    elif re.match(r"^\d{4}-\d{2}-\d{2}", first_date):
        # Format: YYYY-MM-DD HH:MM:SS (e.g., 2026-09-18 23:56:00)
        try:
            df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M:%S")
        except ValueError:
            print("Error: Date format mismatch. Expected YYYY-MM-DD HH:MM:SS.")
            sys.exit(1)
    else:
        print("Error: Unrecognized date format in the file. Expected DD-MM-YYYY HH:MM or YYYY-MM-DD HH:MM:SS.")
        sys.exit(1)

    # 4. Filter last N weeks
    config = load_config()
    weeks = config["weeks_to_import"]
    
    max_date = df["date"].max()
    cutoff_date = max_date - timedelta(weeks=weeks)
    df = df[df["date"] >= cutoff_date]

    # 5. Clean table
    # Fill empty review text
    df["review"] = df["review"].fillna("").astype(str)
    
    # Optional columns
    allowed_optional = {"title", "thumbs_up", "app_version", "user", "developer_reply", "reply_date"}
    existing_optional = [c for c in df.columns if c in allowed_optional]
    
    final_cols = ["date", "rating", "review"] + existing_optional
    df = df[final_cols].copy()

    # Cast rating (assuming it might be string or float)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0).astype(int)

    return df

def run_import_and_summarize(file_path):
    df = import_reviews(file_path)
    
    # 6. Print summary
    num_reviews = len(df)
    if num_reviews == 0:
        print("No reviews found in the specified timeframe.")
        return df
        
    earliest_date = df["date"].min().strftime("%d %B %Y")
    latest_date = df["date"].max().strftime("%d %B %Y")
    avg_rating = df["rating"].mean()
    
    rating_counts = df["rating"].value_counts().sort_index(ascending=False).to_dict()
    
    print("--- Import Summary ---")
    print(f"Total reviews: {num_reviews}")
    print(f"Earliest date: {earliest_date}")
    print(f"Latest date: {latest_date}")
    print(f"Average rating: {avg_rating:.2f}")
    print("Reviews per rating:")
    for r in range(5, 0, -1):
        print(f"  {r} star: {rating_counts.get(r, 0)}")
        
    return df

if __name__ == "__main__":
    run_import_and_summarize(os.path.join("data", "raw", "reviews_raw.csv"))
