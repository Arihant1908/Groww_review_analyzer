# RULES
1. Purpose: turn recent app-store reviews of Groww into a one-page weekly note (top 3 themes, 3 real user quotes, 3 action ideas, at most 250 words) and a draft email containing that note.
2. Data: use only public review exports that I upload (CSV) and, optionally, Apple's public reviews feed. No scraping behind logins.
3. Themes: at most 5. The list lives only in config/themes.json.
4. Privacy: no usernames, emails, phone numbers, IDs or personal names may appear in ANY file inside out/ or in the app screen. The original username column and developer-reply text must never be copied forward.
5. The AI never calculates numbers, dates or percentages. Code calculates them. The AI only reads text and writes the note from a fixed evidence file.
6. Quotes must be copied word for word from a redacted review. The code must verify this.
7. Never send an email. Only create a draft or a file.
8. Never write my API key into any file except .env. Never print it.
9. Never edit or overwrite anything in data/raw/. All outputs go to out/.
10. One small file per stage, plain-English comments, no clever tricks.
11. After each task, run the tests and tell me the result in plain English (what passed, what failed).
12. Do not add features, libraries or files I did not ask for. If you think something is missing, ask me first.
13. Never change a value in config/settings.json (such as the model name) without asking me first.
