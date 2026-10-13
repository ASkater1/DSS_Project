import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

#Below is code for the assignment 0.2 prototype dashboard. The DB connection is only used to check whether the connection still works.
#This should be removed when working on the actual prototype dashboard. All code here is placeholder
st.title("Prototype dashboard")
st.write("If this works, the real work can start")

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

# Experimentation with map using streamlit, Geoplot should still be experimented, could potentially 
# use plotly express or other medium
map_data = pd.DataFrame(
    np.random.randn(1000, 2) / [50, 50] + [37.76, -122.4], columns=["lat", "lon"]
)
st.map(map_data)

#Experimentation with line chart using streamlit
line_data = pd.DataFrame(
    np.random.randn(20, 3), columns=["a", "b", "c"]
)
st.line_chart(line_data)

#Experimentation with bar chart using streamlit
bar_data = pd.DataFrame(
    np.random.randn(50, 3), columns=["a", "b", "c"]
)
st.bar_chart(bar_data)

#Experimentation with histogram using plotly express
histogram_data = pd.DataFrame(
    np.random.randn(1000), columns=["data"]
)
fig = px.histogram(histogram_data, x="data", nbins=30, title="Histogram of Random Data")
st.plotly_chart(fig)

#Experimentation with percentage metrics using st.metric
coverage_percentage = 0.25
st.metric(label="Coverage percentage", value=f"{coverage_percentage*100}%")