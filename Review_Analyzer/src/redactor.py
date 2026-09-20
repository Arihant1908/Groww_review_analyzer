import pandas as pd
import re
import sys
import os

def pii_gate(text):
    """
    Scans text for emails, phone numbers, PAN, and long ID numbers.
    Stops the program with an error if it finds one.
    """
    if pd.isna(text) or not isinstance(text, str):
        return

    # Email
    if re.search(r"[\w\.-]+@[\w\.-]+", text):
        print(f"PII GATE ERROR: Email found in '{text}'")
        sys.exit(1)
    # Phone (Indian 10-digit, optional +91)
    if re.search(r"(?:\+?91[\-\s]?)?\b[6-9]\d{9}\b", text):
        print(f"PII GATE ERROR: Phone number found in '{text}'")
        sys.exit(1)
    # PAN (5 letters, 4 digits, 1 letter)
    if re.search(r"(?i)\b[A-Z]{5}\d{4}[A-Z]\b", text):
        print(f"PII GATE ERROR: PAN found in '{text}'")
        sys.exit(1)
    # Number with 9 or more digits
    if re.search(r"\b\d{9,}\b", text):
        print(f"PII GATE ERROR: Long number/ID found in '{text}'")
        sys.exit(1)

def build_user_trie(users):
    trie = {}
    for u in users:
        words = tuple(u.lower().split())
        if not words: continue
        node = trie
        for w in words:
            if w not in node:
                node[w] = {}
            node = node[w]
        node['__MATCH__'] = True
    return trie

def redact_with_trie(text, trie):
    if not isinstance(text, str): return text
    parts = re.split(r'(\b\w+\b)', text)
    i = 0
    while i < len(parts):
        part = parts[i].lower()
        if part in trie:
            node = trie[part]
            j = i
            last_match = -1
            if '__MATCH__' in node:
                last_match = j
            
            j += 2
            while j < len(parts):
                p = parts[j].lower()
                if p in node:
                    node = node[p]
                    if '__MATCH__' in node:
                        last_match = j
                    j += 2
                else:
                    break
            
            if last_match != -1:
                parts[i] = '[NAME]'
                for k in range(i+1, last_match+1):
                    parts[k] = ''
                i = last_match
        i += 1
    return "".join(parts)


def redact_text(text, user_name, all_lower_words):
    if pd.isna(text) or not isinstance(text, str):
        return ""

    # Web links
    text = re.sub(r"(?i)https?://\S+|www\.\S+", "[URL]", text)
    # Emails
    text = re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL]", text)
    # PAN
    text = re.sub(r"(?i)\b[A-Z]{5}\d{4}[A-Z]\b", "[ID]", text)
    # Indian Phone
    text = re.sub(r"(?:\+?91[\-\s]?)?\b[6-9]\d{9}\b", "[PHONE]", text)
    # 9 or more digits
    text = re.sub(r"\b\d{9,}\b", "[ID]", text)
    # Numbers right after keywords
    # ticket, order, txn, transaction, reference, OTP, pin, code, id
    kw_pattern = r"(?i)(\b(?:ticket|order|txn|transaction|reference|otp|pin|code|id)[\s#:-]+)(\d+)\b"
    text = re.sub(kw_pattern, r"\1[ID]", text)
    
    # Names: User's own display name
    if isinstance(user_name, str) and len(user_name.strip()) > 2:
        uname = user_name.strip()
        # Case insensitive exact match of the display name
        text = re.sub(r"(?i)\b" + re.escape(uname) + r"\b", "[NAME]", text)

    # Names: Runs of two or more consecutive capitalized words
    # This is a best-effort rule; we replace only if the lowercase words never appear in lower case in the whole file.
    def replace_capitalized(match):
        phrase = match.group()
        words = phrase.split()
        # If any word in the phrase appears entirely lowercase elsewhere, we don't redact
        if any(w.lower() in all_lower_words for w in words):
            return phrase
        return "[NAME]"

    cap_pattern = r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
    text = re.sub(cap_pattern, replace_capitalized, text)

    # Collapse extra spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

def run_redactor(df):
    if df.empty:
        return df

    # Collect all words that appear in lower case anywhere in the whole file
    all_text = " ".join(df["review"].dropna().astype(str))
    # Finds words that are strictly lowercase
    all_lower_words = set(re.findall(r"\b[a-z]+\b", all_text))

    # Build the user trie for redacting any exact user name found in the corpus
    all_users_list = df["user"].dropna().astype(str).str.strip().unique().tolist()
    user_trie = build_user_trie(all_users_list)

    # Process developer reply
    if "developer_reply" in df.columns:
        df["developer_replied"] = df["developer_reply"].notna() & (df["developer_reply"] != "")
    else:
        df["developer_replied"] = False

    if "reply_date" in df.columns and "date" in df.columns:
        # date is already datetime from importer, but let's be safe
        dates = pd.to_datetime(df["date"])
        reply_dates = pd.to_datetime(df["reply_date"], errors="coerce", dayfirst=True)
        # hours taken
        hours = (reply_dates - dates).dt.total_seconds() / 3600
        df["reply_hours"] = hours.round(2)

    # Redact reviews
    redacted_reviews = []
    for idx, row in df.iterrows():
        user = row["user"] if "user" in df.columns else ""
        review = row["review"]
        
        redacted = redact_text(review, user, all_lower_words)
        redacted = redact_with_trie(redacted, user_trie)
        pii_gate(redacted)
        redacted_reviews.append(redacted)

    df["review"] = redacted_reviews

    # Drop columns
    cols_to_drop = [c for c in ["user", "developer_reply", "reply_date"] if c in df.columns]
    df = df.drop(columns=cols_to_drop)

    return df

def main():
    # To run standalone (usually called after importer)
    from src.importer import import_reviews
    raw_path = os.path.join("data", "raw", "reviews_raw.csv")
    df = import_reviews(raw_path)
    df_redacted = run_redactor(df)
    
    out_dir = "out"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    out_path = os.path.join(out_dir, "reviews_redacted.csv")
    df_redacted.to_csv(out_path, index=False)
    print(f"Redacted data saved to {out_path}")

    # Print 10 random redacted reviews
    print("--- 10 Random Redacted Reviews ---")
    sample = df_redacted.sample(min(10, len(df_redacted)))
    for _, row in sample.iterrows():
        try:
            print(f"- {row['review']}")
        except UnicodeEncodeError:
            print(f"- {row['review'].encode('ascii', 'ignore').decode('ascii')}")
            print(f"- {row['review'].encode('ascii', 'ignore').decode('ascii')}")

if __name__ == "__main__":
    main()
