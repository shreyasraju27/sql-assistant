import os
import re
import tempfile
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

st.set_page_config(page_title="SQL Assistant", page_icon="🌿", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --paper:   #f6f3ed;
    --card:    #ffffff;
    --ink:     #2f2b26;
    --forest:  #3f5b47;
    --rose:    #c98a7d;
    --muted:   #8a8377;
    --border:  #e3ddd0;
}

html, body, [class*="css"] { font-family: 'Work Sans', sans-serif !important; }
.stApp { background: var(--paper); color: var(--ink); }
#MainMenu, footer, header {visibility: hidden;}
section[data-testid="stSidebar"] {display: none;}
.block-container { padding-top: 2.2rem; max-width: 1100px; }

h1 { color: var(--ink) !important; font-weight: 700 !important; }

.gauge {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 10px rgba(63,91,71,0.06);
}
.gauge-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10.5px;
    letter-spacing: 0.14em;
    color: var(--forest);
    text-transform: uppercase;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}

.stButton > button {
    background: var(--forest) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    padding: 0.55rem 1rem !important;
    box-shadow: 0 2px 8px rgba(63,91,71,0.25);
}
.stButton > button:hover { opacity: 0.88; }

[data-testid="stFileUploaderDropzone"] {
    background: var(--paper) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stChatMessage"] {
    background: var(--card) !important;
    border: 1px solid var(--border);
    border-radius: 12px !important;
}
[data-testid="stChatInput"] textarea {
    background: var(--card) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
.stAlert { border-radius: 10px !important; background: var(--card) !important; border: 1px solid var(--border) !important; }
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    background: var(--card) !important;
}
code { color: var(--forest) !important; }
</style>
""", unsafe_allow_html=True)

st.title("🌿 SQL Assistant")
st.caption("Upload a CSV, then ask questions in plain English.")

api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", "")

if not api_key:
    st.error("No API key found. Add GOOGLE_API_KEY to your .env (local) or Secrets (deployed).")
    st.stop()

os.environ["GOOGLE_API_KEY"] = api_key

if "db_path" not in st.session_state:
    st.session_state.db_path = None
if "table_name" not in st.session_state:
    st.session_state.table_name = None
if "schema" not in st.session_state:
    st.session_state.schema = None
if "messages" not in st.session_state:
    st.session_state.messages = []


def get_schema_description(db_path, table_name):
    """Return a text description of columns, types, AND sample real values,
    so the model doesn't have to guess how text values are actually formatted."""
    conn = sqlite3.connect(db_path)

    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    cols = cursor.fetchall()

    lines = [f"Table `{table_name}` has columns:"]
    for col in cols:
        col_name, col_type = col[1], col[2]
        line = f"- {col_name} ({col_type})"

        if col_type.upper() in ("TEXT", "VARCHAR", ""):
            try:
                sample_cursor = conn.execute(
                    f'SELECT DISTINCT "{col_name}" FROM {table_name} '
                    f'WHERE "{col_name}" IS NOT NULL LIMIT 8'
                )
                samples = [str(row[0]) for row in sample_cursor.fetchall()]
                if samples:
                    line += f"  -- example values: {samples}"
            except Exception:
                pass

        lines.append(line)

    conn.close()
    return "\n".join(lines)


def get_text(content):
    """Normalize LLM response content to a plain string, whether it's a
    string or a list of content parts (newer Gemini client behavior)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
        return "".join(parts)
    return str(content)


def extract_sql(text):
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def answer_question(question, db_path, table_name, schema):
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)

    sql_prompt = f"""You are a SQLite expert. Given this table schema and example values:

{schema}

Write a single valid SQLite query that answers this question:
"{question}"

Important: text values must match the real formatting shown in the example values above (e.g. use LIKE with wildcards if the exact wording is uncertain, rather than assuming a clean exact match).

Only output the SQL query itself, wrapped in a ```sql code block. No explanation."""

    sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
    sql_query = extract_sql(get_text(sql_response.content))

    try:
        conn = sqlite3.connect(db_path)
        result_df = pd.read_sql_query(sql_query, conn)
        conn.close()
    except Exception as e:
        return f"The query failed to run: {e}", sql_query, None

    result_preview = result_df.head(20).to_string(index=False)
    explain_prompt = f"""The user asked: "{question}"

This SQL query was run:
{sql_query}

It returned this result:
{result_preview}

Answer the user's question in one or two clear sentences based on this result."""

    explain_response = llm.invoke([HumanMessage(content=explain_prompt)])
    return get_text(explain_response.content), sql_query, result_df


left, right = st.columns([1, 1.6], gap="large")

with left:
    st.markdown('<div class="gauge">', unsafe_allow_html=True)
    st.markdown('<p class="gauge-label">data source</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload CSV", type="csv", label_visibility="collapsed")

    if st.button("Load into database", use_container_width=True) and uploaded_file:
        with st.spinner("Indexing table..."):
            df = pd.read_csv(uploaded_file)
            df.columns = [
                c.strip().lower().replace(" ", "_").replace("-", "_")
                for c in df.columns
            ]

            tmp_dir = tempfile.mkdtemp()
            db_path = os.path.join(tmp_dir, "data.db")
            table_name = "data"

            conn = sqlite3.connect(db_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            conn.close()

            st.session_state.db_path = db_path
            st.session_state.table_name = table_name
            st.session_state.schema = get_schema_description(db_path, table_name)
            st.session_state.messages = []

        st.success(f"{len(df)} rows loaded")
        with st.expander("Columns"):
            st.write(list(df.columns))

    if st.session_state.db_path is not None:
        if st.button("Clear session", use_container_width=True):
            st.session_state.db_path = None
            st.session_state.table_name = None
            st.session_state.schema = None
            st.session_state.messages = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="gauge">', unsafe_allow_html=True)
    st.markdown('<p class="gauge-label">query console</p>', unsafe_allow_html=True)

    if st.session_state.db_path is None:
        st.info("Load a CSV on the left to get started.")
    else:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg.get("sql"):
                    with st.expander("SQL used"):
                        st.code(msg["sql"], language="sql")

        query = st.chat_input("Ask a question about your data...")

        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.write(query)

            with st.chat_message("assistant"):
                with st.spinner("Compiling query..."):
                    answer, sql_query, result_df = answer_question(
                        query,
                        st.session_state.db_path,
                        st.session_state.table_name,
                        st.session_state.schema,
                    )
                    st.write(answer)
                    with st.expander("SQL used"):
                        st.code(sql_query, language="sql")
                    if result_df is not None and len(result_df) > 0:
                        st.dataframe(result_df, use_container_width=True)

            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sql": sql_query}
            )
    st.markdown('</div>', unsafe_allow_html=True)