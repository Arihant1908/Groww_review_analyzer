# Review Analyzer

## What this tool does
This tool processes recent app-store reviews and automatically generates a concise, one-page weekly summary note containing top themes, real user quotes, and actionable product ideas. It also generates a draft email containing this note for easy distribution. All privacy-sensitive data like usernames are scrubbed from the final outputs.

## How to re-run for a new week
1. Download the latest reviews CSV from the app store console.
2. Place the file inside the `data/raw/` folder and name it exactly `reviews_raw.csv` (overwriting the old one).
3. Open a terminal in this folder and run `python run.py`, or open the web dashboard by running `python -m streamlit run app.py` and clicking the run button.
4. The newly generated weekly note, email draft, and redacted CSV will appear in the `out/` folder.

## Theme legend
| ID | Name | What it captures | Example phrases |
|---|---|---|---|
| `support` | Customer support & resolution | unanswered tickets, bot loops, unhelpful/slow support | "no response", "bot", "did not help" |
| `charges` | Brokerage, charges & fees | brokerage, DP, tax, high/hidden charges | "high charges", "hidden", "expensive" |
| `perf` | App performance & stability | slow app, hanging, crashing, screens not loading | "crashing", "lagging", "white screen" |
| `features` | Trading tools & charts | charts, indicators, stop-loss, F&O, orders | "stop loss", "candles", "options" |
| `money` | Payments, withdrawals & account | UPI/mandate issues, withdrawal delays, KYC/Aadhaar | "stuck", "kyc rejected", "not credited" |
| `unthemed` | Unthemed | Praise, generic abuse, or complaints unrelated to the app | (Generic or unrelated comments) |

## How it works
1. **Importing (Code):** Loads the raw CSV and filters reviews to the target time window.
2. **Redacting (Code):** Scrubs emails, long numbers, and real usernames using regex and a Trie.
3. **Grouping (AI/Code):** Uses AI to map each review to a theme, falling back to keyword matching if AI fails.
4. **Crunching numbers (Code):** Calculates counts, averages, and week-over-week trends for each theme.
5. **Writing the note (AI):** The AI drafts the final one-page note using the hard evidence (or falls back to a template).
6. **Generating drafts (Code):** Assembles the note into a plain text and `.eml` email file.

## Privacy
- **What is removed:** All real usernames, email addresses, phone numbers, PANs, and long ID numbers are scrubbed from the text and replaced with placeholders like `[NAME]` or `[EMAIL]`.
- **What is never saved:** The original `user` column and `developer_reply` column from the raw data are completely dropped and never copied forward into the `out/` folder or displayed in the app.

## Known limitations
- Theme classification accuracy is approximate and may miscategorize nuanced reviews.
- Name masking is best-effort and relies on exact matches from the raw data; creative misspellings might slip through.
- Weekly review counts can be small, meaning percentage swings week-over-week can be noisy and exaggerated.
- The tool currently processes one store's export only unless another export format is manually added.

## Settings
The `config/settings.json` file controls the tool's behavior:
- `weeks_to_import`: The maximum number of historical weeks to load from the raw data for calculating baseline trends.
- `current_window_days`: The number of days considered as the "current week" for the final summary (usually 7).
- `recipient_email`: The target email address for the generated `.eml` draft file.
- `max_note_words`: The strict word count limit enforced on the AI-generated weekly note.
- `llm_model`: The primary Google Gemini AI model used for theming and note generation.
- `llm_model_backup`: The fallback Gemini AI model used if the primary model fails or rate-limits.
