import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import requests

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

# Experimentation with metrics using st.metric, line chart using plotly express, histogram using plotly express, and percentage metrics using st.metric
col1, col2, col3, col4 = st.columns(4, gap='small')

with col1:
    st.metric(label="Total supermarkets", value="4392", delta="+2.1%")

with col2:
    st.metric(label="Average basket price", value="€25.50", delta="+3%")

with col3:
    st.metric(label="Market coverage", value="75%")

with col4:
    st.metric(label="Cybersecurity incidents", value="1", delta="-100%")

col1, col2 = st.columns(2, gap='small')
with col1:
    line_chart_data = pd.DataFrame(
        np.random.randn(20, 4),
        columns=["Albert Heijn", "Jumbo", "Lidl", "Plus"],
    )
    fig = px.line(line_chart_data, x=line_chart_data.index, y=["Albert Heijn", "Jumbo", "Lidl", "Plus"], title="Line Chart of Random Data")
    st.plotly_chart(fig)

with col2:
    #Experimentation with histogram using plotly express
    geojson_url = "https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/ogc/v1/collections/gemeentegebied/items?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FOGC%2F1.3%2FCRS84&f=json&limit=1000"
    response = requests.get(geojson_url)
    geojson_data = response.json()
    if geojson_data is None:
        st.error("Failed to fetch geojson data")
    else:
        geojson_data = response.json()

    df=pd.DataFrame({
        "Gemeente": ["Utrecht", "De Bilt", "Zeist", "Nijkerk", "Amersfoort", "Ede", "Barneveld", "Veenendaal", "Amsterdam", "Rotterdam", "Den Haag", "Groningen", "Maastricht", "Eindhoven", "Tilburg", "Utrechtse Heuvelrug", "Nieuwegein", "Houten", "Bunnik", "Renswoude"],
        "Waarde": [10, 100, 50, 80, 60, 90, 70, 40, 30, 20, 15, 25, 35, 45, 55, 65, 75, 85, 95, 5]
    })

    fig = px.choropleth_mapbox(
        df,
        geojson=geojson_data,
        locations="Gemeente",
        featureidkey="properties.naam",
        color="Waarde",
        color_continuous_scale="Plasma",
        mapbox_style="open-street-map",
        zoom=5,
        center={"lat": 52.1326, "lon": 5.2986},
        opacity=0.5,
        labels={"Value": "Score"},
    )
    st.plotly_chart(fig)

#Experimentation with percentage metrics using st.metric
coverage_percentage = 0.25
st.metric(label="Coverage percentage", value=f"{coverage_percentage*100}%")

