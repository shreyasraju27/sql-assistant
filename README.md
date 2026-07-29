# 🌿 AI SQL Assistant

Upload a CSV and ask questions about it in plain English. The app writes the SQL query, runs it against your data, and explains the result — no SQL knowledge required.

**🔗 Live demo:** [sql-assistant-dvdshgeex7ag9klstfsmxe.streamlit.app](https://sql-assistant-dvdshgeex7ag9klstfsmxe.streamlit.app/)

## How it works

1. **Upload** — a CSV is uploaded and loaded into a temporary SQLite database, unique to your session.
2. **Understand the data** — the app reads the table's columns, types, and a sample of real values (not just column names), so the AI knows how the data is actually formatted.
3. **Write SQL** — Gemini is given the schema and sample values, and writes a SQL query to answer your question.
4. **Run it** — the query executes directly against the SQLite database.
5. **Explain it** — Gemini reads the raw result and turns it into a plain-English answer, while the actual SQL and result table stay visible for transparency.

## Why sample values matter

Early versions of this app only showed the AI column names and types, which caused it to guess at exact text values (e.g. assuming a value was `"Capital Goods Price Index"` when the real value was `"Capital Goods Price Index - CEP"`), producing silently wrong answers. Showing the AI real example values from each column, and instructing it to prefer `LIKE` matching over exact matching when uncertain, fixed this. Verified against a real 82,000-row government dataset.

## Tech stack

- **Google Gemini** (`gemini-flash-latest`) — SQL generation and result explanation
- **SQLite** — lightweight, file-based database, one per session
- **Pandas** — CSV parsing and result handling
- **Streamlit** — web interface

## Running locally

```bash
git clone https://github.com/shreyasraju27/sql-assistant.git
cd sql-assistant
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_gemini_api_key
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

Then run:

```bash
streamlit run app.py
```

## Notes

- Each session gets its own private SQLite database file (via a unique temp directory per upload), so multiple people can use the app at once without their data mixing.
- Uses Google Gemini's free tier — no billing required to run this project.
- The generated SQL and raw result table are always shown alongside the plain-English answer, so you can verify the AI's work rather than take it on faith.