# QA Report

## Overview
A strict review of the system was performed based on `PROJECT_RULES.md`. Here are the results of the 9 requested checks.

### 1. Run all tests
**PASS**
- Evidence: Executed `pytest tests/`. 26 tests passed, 0 failed.

### 2. Cross-check
**PASS**
- Evidence: Using a standalone Python script without pandas, the computed current-week review count is 1044, average rating is 4.29, low-rated count is 186, and the top theme counts matched exactly with the data in `out/evidence.json`.

### 3. Dates
**PASS**
- Evidence: The earliest and latest review dates in `out/reviews_redacted.csv` match the original file (`2026-07-22` and `2026-09-18`). Renaming `out/reviews_redacted.csv` to act as raw input and re-running the pipeline results in an identical `pulse_latest.md` note.

### 4. Privacy
**FAIL**
- **Evidence 1**: The placeholder email `m*@example.com` appears in `out/email_draft.txt` and `out/email_draft.eml`.
- **Evidence 2**: A regex scan found some original usernames (like "Technical Support" and "All In one") appearing word-for-word in the text of `out/reviews_redacted.csv`. The current redaction logic does not reliably catch all user names if they are mentioned by others or themselves in different cases.
- **File**: `src/emailer.py` (for the email), `src/redactor.py` (for the name redaction).
- **Proposed Fix**: Remove the hardcoded `m*@example.com` default in `src/emailer.py`. Enhance `src/redactor.py` to compile a list of all usernames and strictly mask them out of the review text regardless of capitalization.

### 5. Note rules
**PASS**
- Evidence: The note (`out/pulse_latest.md`) is 156 words (well under the 250-word limit). It contains exactly 3 themes, 3 quotes, and 3 action ideas. A script verified that all 3 quotes exist word-for-word in `out/reviews_redacted.csv`.

### 6. Themes
**FAIL**
- **Evidence**: Rule 3 restricts themes to "at most 5". However, `config/themes.json` contains 6 themes (`support`, `charges`, `perf`, `features`, `money`, `unthemed`).
- **File**: `config/themes.json`
- **Proposed Fix**: Remove or consolidate one of the themes in `config/themes.json` so that the total number of themes does not exceed 5.

### 7. Email
**PASS**
- Evidence: `src/emailer.py` only generates draft files (`.eml`, `.txt`) and a Gmail compose link. There are no code paths using `smtplib` or external APIs to actually send mail.

### 8. Secrets
**PASS**
- Evidence: A global search confirmed the API key only exists in `.env`. The key is fetched securely via `os.environ.get()` and is never printed in any script. `.gitignore` successfully excludes `.env`, `data/raw/`, and `out/`.

### 9. Original file unchanged
**PASS**
- Evidence: The checksum of `data/raw/reviews_raw.csv` remains completely unchanged after full pipeline execution.
