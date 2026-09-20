import streamlit as st
import pandas as pd
import json
import os
import subprocess
import urllib.parse
import sys
from fpdf import FPDF

# Configure Streamlit page
st.set_page_config(
    page_title="Review Analyzer",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- UTILS ---
def load_config():
    config_path = "config/settings.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    os.makedirs("config", exist_ok=True)
    with open("config/settings.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def run_pipeline(file_bytes=None):
    with st.spinner("Running pipeline... this may take a minute."):
        # Pass the file bytes via stdin so we never write to disk
        kwargs = {"capture_output": True, "text": True}
        if file_bytes:
            kwargs["input"] = file_bytes.decode("utf-8", errors="replace")
            
        # 2. Make the app read the API key from secrets if .env is missing
        env = os.environ.copy()
        if "GEMINI_API_KEY" not in env:
            try:
                env["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
            except Exception:
                pass
                
        result = subprocess.run([sys.executable, "run.py"], env=env, **kwargs)
        if result.returncode != 0:
            st.error(f"Pipeline failed!\n\n{result.stderr.strip() or result.stdout.strip()}")
            return False
        return True

def get_redacted_count():
    try:
        df = pd.read_csv("out/reviews_redacted.csv")
        tags = ["[URL]", "[EMAIL]", "[ID]", "[PHONE]", "[NAME]"]
        
        def has_tag(text):
            if pd.isna(text): return False
            return any(tag in str(text) for tag in tags)
            
        count = df["review"].apply(has_tag).sum()
        return count
    except Exception:
        return 0

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Convert utf-8 text to latin-1 to avoid fpdf errors, replacing unknown chars
    text = text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())

# --- APP LAYOUT ---
st.title("Weekly Pulse Generator")
st.write("Upload your own public review export. Nothing is stored.")
st.write("---")

# SECTION 1: Upload
st.header("1. Data & Configuration")
uploaded_file = st.file_uploader("Upload Reviews CSV", type=["csv"])

config = load_config()
col1, col2 = st.columns(2)
with col1:
    weeks_history = st.number_input("Weeks of history", min_value=8, max_value=12, value=config.get("weeks_to_import", 12))
with col2:
    recipient_email = st.text_input("Recipient Email", value=config.get("recipient_email", ""))

if st.button("Run Pipeline"):
    if uploaded_file is None:
        st.error("Please upload a CSV file first.")
    else:
        # Save config
        config["weeks_to_import"] = weeks_history
        if recipient_email:
            config["recipient_email"] = recipient_email
        save_config(config)
        
        # Run
        if run_pipeline(uploaded_file.getvalue()):
            st.session_state["run_success"] = True

if st.session_state.get("run_success"):
    try:
        df_redacted = pd.read_csv("out/reviews_redacted.csv")
        df_redacted['date'] = pd.to_datetime(df_redacted['date'])
        
        latest_date = df_redacted['date'].max()
        current_week_start = latest_date - pd.Timedelta(days=7)
        
        df_current = df_redacted[(df_redacted['date'] > current_week_start) & (df_redacted['date'] <= latest_date)]
        
        review_count = len(df_current)
        avg_rating = df_current["rating"].mean() if review_count > 0 else 0
        
        end_date = latest_date.strftime("%Y-%m-%d")
        date_range = f"{current_week_start.strftime('%b %d')} - {latest_date.strftime('%b %d, %Y')}"
            
        st.write(f"**Review Count:** {review_count}  |  **Date Range:** {date_range}  |  **Average Rating:** {avg_rating:.2f}")
    except Exception as e:
        st.warning(f"Could not load basic metrics: {e}")

    st.write("---")

    # SECTION 2: Privacy check
    st.header("2. Privacy Check")
    redacted_count = get_redacted_count()
    st.write(f"Reviews with redacted personal data: {redacted_count}")
    if redacted_count == 0:
        st.success("No personal data found in outputs.")
    else:
        st.warning("Personal data was found and redacted.")

    st.write("---")

    # SECTION 3: Themes
    st.header("3. Themes")
    try:
        with open("out/evidence.json", "r", encoding="utf-8") as f:
            evidence = json.load(f)
            
        theme_mentions = evidence.get("theme_mentions", {})
        themes_data = []
        unthemed_count = 0
        for theme, data in theme_mentions.items():
            mentions = data.get("current", 0)
            change = data.get("change_pct", "N/A")
            if change != "N/A" and change is not None:
                change = f"{change:+.1f}%"
            else:
                prior = data.get("prior", 0)
                change = f"{mentions} vs {prior}"
            if theme.lower() == "unthemed":
                unthemed_count = mentions
            themes_data.append({"Theme": theme.capitalize(), "Mentions this week": mentions, "Change vs last week": change})
            
        df_themes = pd.DataFrame(themes_data)
        
        st.dataframe(df_themes, use_container_width=True)
        
        top_5 = df_themes.sort_values(by="Mentions this week", ascending=False).head(5).set_index("Theme")["Mentions this week"]
        st.bar_chart(top_5)
        
        st.write(f"Low-rated reviews that were 'unthemed': {unthemed_count}")
    except Exception as e:
        st.warning(f"Could not load themes: {e}")

    st.write("---")

    # SECTION 4: Weekly Note
    st.header("4. Weekly Note")
    try:
        pulse_file = f"out/pulse_{end_date}.md"
        if not os.path.exists(pulse_file):
            pulse_file = "out/pulse_latest.md"
            
        with open(pulse_file, "r", encoding="utf-8") as f:
            note_text = f.read()
            
        word_count = len(note_text.split())
        st.text_area("Note", note_text, height=300, disabled=True)
        
        source_label = "written by AI" if "Note written by model" in note_text else "template"
        st.caption(f"{word_count} / 250 words • {source_label}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download note (.md)", data=note_text, file_name=pulse_file.split("/")[-1])
        with col2:
            pdf_bytes = create_pdf(note_text)
            st.download_button("Download note (.pdf)", data=pdf_bytes, file_name=pulse_file.split("/")[-1].replace(".md", ".pdf"), mime="application/pdf")
            
    except Exception as e:
        st.warning(f"Could not load note: {e}")

    st.write("---")

    # SECTION 5: Email Draft
    st.header("5. Email Draft")
    try:
        with open("out/email_draft.txt", "r", encoding="utf-8") as f:
            email_txt = f.read()
            
        st.text_area("Draft Content", email_txt, height=300, disabled=True)
        
        with open("out/email_draft.eml", "r", encoding="utf-8") as f:
            eml_content = f.read()
            
        with open("out/email_gmail_link.txt", "r", encoding="utf-8") as f:
            gmail_link = f.read()
            
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<a href="{gmail_link}" target="_blank"><button style="padding: 0.5rem 1rem; border-radius: 0.5rem; border: 1px solid #ccc; background-color: white; cursor: pointer;">Open in Gmail</button></a>', unsafe_allow_html=True)
        with col2:
            st.code(email_txt, language="text") # Hack to allow copying easily
        with col3:
            st.download_button("Download .eml", data=eml_content, file_name="email_draft.eml")
            
        st.caption("Nothing is sent automatically.")
    except Exception as e:
        st.warning(f"Could not load email draft: {e}")
