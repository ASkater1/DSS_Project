"""INFOMDSS - Exercise 1 starter app.

Run it locally first, so you know what "working" looks like:
    pip install -r requirements.txt
    streamlit run app.py
Then open http://localhost:8501 in your browser.

You do NOT need to change this file for the exercise.
"""

import os
import streamlit as st

st.title("Prototype dashboard")
st.write("If this works, the real work can start")

# Part (b) only: this block reports whether a database is reachable.
# It is here so you can tell whether your docker-compose setup worked.
st.subheader("Database connection")
host = os.environ.get("DB_HOST", "not set")
st.write(f"DB_HOST is: {host}")

try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=5432,
        dbname=os.environ.get("DB_NAME", "dss"),
        user=os.environ.get("DB_USER", "dss"),
        password=os.environ.get("DB_PASSWORD", ""),
        connect_timeout=3,
    )
    cur = conn.cursor()
    cur.execute("SELECT version();")
    st.success(f"Connected. PostgreSQL says: {cur.fetchone()[0][:40]}...")
    conn.close()
except Exception as e:
    st.error(f"Not connected: {type(e).__name__}: {e}")
