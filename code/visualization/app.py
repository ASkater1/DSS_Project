import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import psycopg2

# Create dummy data based on the ER diagram
# This will later be replaced with data from our database

# Supermarket names and their market shares

supermarkets = pd.DataFrame({
    "SupermarketID": [1, 2, 3, 4],
    "Name": ["Albert Heijn", "Jumbo", "Lidl", "Plus"],
    "Year": [2024, 2024, 2024, 2024],
    "MarketShare": [37, 22, 11, 6]
})

# Product information including whether a product belongs to the essential basket

products = pd.DataFrame({
    "ProductID": [1, 2, 3, 4],
    "Name": [
        "Halfvolle melk 1L",
        "Volkoren brood",
        "Bananen 1kg",
        "Verse franse friet 700g"
    ],
    "IsBasketProduct": [True, True, True, False],
    "Brand": ["Huismerk", "Huismerk", "Huismerk", "AH"],
    "Category": [
        "Zuivel",
        "Brood",
        "Groente en fruit",
        "Aardappelen"
    ],
    "Description": [
        "Halfvolle melk",
        "Volkoren brood",
        "Verse bananen",
        "Verse franse friet"
    ]
})

# Create dummy prices for each supermarket and product
# Prices increase slightly each month to simulate price changes over time
price_rows = []

for month in range(1, 7):
    for supermarket_id in supermarkets["SupermarketID"]:
        for product_id in products["ProductID"]:

            price = 0.80 + product_id * 0.45
            price += supermarket_id * 0.08
            price += month * 0.03

            price_rows.append({
                "SupermarketID": supermarket_id,
                "ProductID": product_id,
                "Price": round(price, 2),
                "Date": pd.Timestamp(2025, month, 1)
            })

supermarket_product = pd.DataFrame(price_rows)

# Combine the supermarket and product data using their IDs
# This makes it possible to compare product prices between supermarkets
prices = supermarket_product.merge(
    supermarkets[["SupermarketID", "Name"]],
    on="SupermarketID"
    )

prices = prices.rename(columns={"Name": "SupermarketName"})
prices = prices.merge(
    products,
    on="ProductID"
)

avgIncome2025 = 3875*12
economyStatistics = pd.DataFrame({
    "Date": ["2025_jan", "2025_feb", "2025_mar", "2025_apr", "2025_may", "2025_jun", "2025_jul", "2025_aug", "2025_sep", "2025_oct", "2025_nov", "2025_dec"], 
        "CPI" : [141.83, 143.49, 143.50, 143.81, 144.96, 145.67, 146.72, 146.16, 145.62, 145.28, 145.11, 145.60], 
        "CPIYearlyRateOfChange": [0.6, 1.2, 0.0, 0.2, 0.8, 0.5, 0.7, -0.4, -0.4, -0.2, -0.1, 0.3],
        "IncomePartHousehold": [0.3, 0.29, 0.28, 0.27, 0.26, 0.25, 0.24, 0.23, 0.22, 0.21, 0.2, 0.19],
        "AverageDisposableIncome": [avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025, avgIncome2025],
        "AverageStandardizedIncome": [55600, 55600, 55600, 55600, 55600, 55600, 55600, 55600, 55600, 55600, 55600, 55600],
        "YearlyWageIncrease": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    })


# Load municipality data inserted into PostgreSQL by the static municipality importer
@st.cache_data(ttl=3600)
def load_municipalities_from_database() -> pd.DataFrame:
    required_variables = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing_variables = [
        variable for variable in required_variables
        if not os.environ.get(variable)
    ]

    if missing_variables:
        raise RuntimeError(
            "Missing database environment variables: "
            + ", ".join(missing_variables)
        )

    query = """
        SELECT
            municipalityid AS "MunicipalityID",
            name AS "Name",
            population AS "Population",
            year AS "Year",
            distanceclosestsupermarket AS "DistanceClosestSupermarket",
            supermarketswithin1km AS "SupermarketsWithin1KM",
            supermarketswithin3km AS "SupermarketsWithin3KM",
            supermarketswithin5km AS "SupermarketsWithin5KM"
        FROM municipalities
        ORDER BY name
    """

    with psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=5432,
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]

    municipalities = pd.DataFrame(rows, columns=columns)

    if municipalities.empty:
        raise RuntimeError(
            "No municipality data was found in the database. "
            "Run staticdata_loading_database_municipalities.py first."
        )

    numeric_columns = [
        "Population",
        "DistanceClosestSupermarket",
        "SupermarketsWithin1KM",
        "SupermarketsWithin3KM",
        "SupermarketsWithin5KM"
    ]
    for column in numeric_columns:
        municipalities[column] = pd.to_numeric(
            municipalities[column], errors="coerce"
        )

    # The importer stores an annual value as 1 January in the database DATE column
    municipalities["Year"] = pd.to_datetime(
        municipalities["Year"], errors="coerce"
    ).dt.year.astype("Int64")

    return municipalities


try:
    municipalities = load_municipalities_from_database()

except Exception as e:
    st.error(f"Could not load municipality data from the database: {e}")
    st.stop()

# Create the dashboard with four tabs
# Each tab focuses on a different part of supermarket affordability or accessibility

st.title("Food Security Dashboard")
st.write("Monitoring supermarket affordability and accessibility in the Netherlands")

tab1, tab2, tab3, tab4= st.tabs([
    "Overview",
    "Prices",
    "Economy",
    "Municipalities"
])

# OVERVIEW TAB
# Shows general supermarket information, market shares and essential basket prices

with tab1:

    st.header("Supermarket Overview")

# Use the most recent prices
    latest_date = prices["Date"].max()
    latest_prices = prices[prices["Date"] == latest_date]

# Only essential basket products
    basket = latest_prices[
        latest_prices["IsBasketProduct"] == True
    ]

# Calculate basket price per supermarket
    basket_prices = basket.groupby(
        "SupermarketName"
    )["Price"].sum().reset_index()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Supermarket chains",
            value=len(supermarkets)
        )

    with col2:
        st.metric(
            label="Combined market share",
            value=f"{supermarkets['MarketShare'].sum()}%"
        )

    with col3:
        st.metric(
            label="Average basket price",
            value=f"€{basket_prices['Price'].mean():.2f}"
        )

    st.subheader("Basket prices per supermarket")


# Combine the supermarket data with basket prices
    comparison = basket_prices.merge(
        supermarkets,
        left_on="SupermarketName",
        right_on="Name"
    )

    fig = px.bar(
        comparison,
        x="SupermarketName",
        y="Price",
        color="SupermarketName",
        hover_name="SupermarketName",
        labels={
            "Price": "Basket price (€)"
        },
        title="Basket price per supermarket"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.write(
        "This chart shows the average price of the essential basket in each supermarket."
    )

# PRICES TAB
# Allows users to compare supermarket prices and monitor price development over time

with tab2:

    st.header("Supermarket Prices")

    st.write("Compare supermarket prices and monitor changes over time.")

# Filters
    col1, col2 = st.columns(2)

    with col1:
        selected_supermarkets = st.multiselect(
            "Select supermarkets",
            supermarkets["Name"].tolist(),
            default=supermarkets["Name"].tolist()
        )

    with col2:
        selected_category = st.selectbox(
            "Select category",
            ["All categories"] + products["Category"].unique().tolist()
        )

# Filter data
    filtered_prices = prices[
        prices["SupermarketName"].isin(selected_supermarkets)
    ]

    if selected_category != "All categories":
        filtered_prices = filtered_prices[
            filtered_prices["Category"] == selected_category
        ]

    latest_prices = filtered_prices[
        filtered_prices["Date"] == filtered_prices["Date"].max()
    ]

    basket_prices = latest_prices[
        latest_prices["IsBasketProduct"] == True
    ]

# Calculate the total price of essential basket products for each supermarket

    basket_totals = basket_prices.groupby(
        "SupermarketName"
    )["Price"].sum()

# Only show the price metrics when data is available

    if not basket_totals.empty:

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Average basket price",
                value=f"€{basket_totals.mean():.2f}"
            )

        with col2:
            st.metric(
                label="Lowest basket price",
                value=f"€{basket_totals.min():.2f}"
            )

        with col3:
            st.metric(
                label="Highest basket price",
                value=f"€{basket_totals.max():.2f}"
            )

    st.subheader("Price development over time")

# Calculate basket prices for each supermarket over time
# This helps identify whether essential food products are becoming more expensive
    trend = filtered_prices[
        filtered_prices["IsBasketProduct"] == True
    ]

    trend = trend.groupby(
        ["Date", "SupermarketName"]
    )["Price"].sum().reset_index()

    fig = px.line(
        trend,
        x="Date",
        y="Price",
        color="SupermarketName",
        markers=True,
        title="Essential basket price over time",
        labels={
            "Date": "Date",
            "Price": "Basket price (€)",
            "SupermarketName": "Supermarket"
        }
    )

    st.plotly_chart(fig, use_container_width=True)


    st.subheader("Price comparison")

# Add a search bar so users can find individual products more easily
    search_product = st.text_input(
        "Search for a product",
        placeholder="Search for milk, bread, bananas..."
    )

# Filter products by name without considering capital letters
# Partial product names can also be used
    search_results = latest_prices[
        latest_prices["Name"].str.contains(
            search_product,
            case=False,
            na=False,
            regex=False
        )
    ]

# Compare prices between supermarkets
    comparison = search_results.pivot_table(
        index="Name",
        columns="SupermarketName",
        values="Price"
    )

# Display results
    st.dataframe(
        comparison.round(2),
        use_container_width=True
    )

    st.subheader("Average product price by category")

# Calculate the average product price per category over time
# This helps identify categories where prices are increasing
    category_prices = filtered_prices.groupby(
        ["Date", "Category"]
    )["Price"].mean().reset_index()

    fig = px.line(
        category_prices,
        x="Date",
        y="Price",
        color="Category",
        markers=True,
        labels={
            "Price": "Average price (€)",
            "Date": "Date"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

# MUNICIPALITIES TAB
# Shows supermarket accessibility in different Dutch municipalities

with tab3:
    st.header("Citizen Economy")

    col1, col2 = st.columns(2)
    with col1:
        CPI_Line = px.line(
            economyStatistics,
            x="Date",
            y="CPI",
            markers=True,
            title="Consumer Price Index (CPI)",
            labels={
            "Date": "Year",
            "CPI": "Consumer Price Index (CPI)"
            },
            line_shape='spline'
        )
        CPI_Line.update_traces(line_smoothing=0.75)  # Adjust smoothing factor
        st.plotly_chart(CPI_Line, use_container_width=True)

    with col2:
        # Display the CPI Yearly Rate of Change with a smoothed line
        CPI_Yearly_Rate = px.line(
            economyStatistics,
            x="Date",
            y="CPIYearlyRateOfChange",
            markers=True,
            title="Monthly Rate of Change in CPI",
            labels={
                "Date": "Year",
                "CPIYearlyRateOfChange": "Monthly Rate of Change in CPI"
            },
            line_shape='spline'
        )
        CPI_Yearly_Rate.update_traces(line_smoothing=0.75)  # Adjust smoothing factor
        st.plotly_chart(CPI_Yearly_Rate, use_container_width=True)

    income_cpi_increase_compare = make_subplots(specs=[[{"secondary_y": True}]])
    income_cpi_increase_compare.add_trace(
        go.Scatter(
            x=economyStatistics["Date"],
            y=economyStatistics["CPIYearlyRateOfChange"],
            mode="lines+markers",
            name="CPI Yearly Rate of Change",
            line={
            'shape': 'spline',
            'smoothing': 0.75,  # Range is from 0 to 1.3
        }),
        secondary_y=False
        )
    
    income_cpi_increase_compare.add_trace(
        go.Scatter(
            x=economyStatistics["Date"],
            y=economyStatistics["AverageDisposableIncome"],
            mode="lines",
            name="Average Disposable Income"
        ),
        secondary_y=True
    )
    income_cpi_increase_compare.update_layout(
        title="CPI Monthly Rate of Change vs Average Disposable Income",
        xaxis_title="Date",
        yaxis_title="CPI Monthly Rate of Change (%)",
        yaxis2_title="Average Disposable Income (€)",
        legend=dict(x=0.01, y=1.5, bordercolor="Black", borderwidth=1)
    )
    st.plotly_chart(income_cpi_increase_compare, use_container_width=True)

with tab4:

    st.header("Supermarket Accessibility")

    st.write("Explore supermarket accessibility across Dutch municipalities.")

# Calculate accessibility score using 1km, 3km and 5km
    municipalities["AccessibilityScore"] = (
        municipalities["SupermarketsWithin1KM"] * 1.0
        + (municipalities["SupermarketsWithin3KM"]
           - municipalities["SupermarketsWithin1KM"]) * 0.75
        + (municipalities["SupermarketsWithin5KM"]
           - municipalities["SupermarketsWithin3KM"]) * 0.5
    )



# KPI metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Average accessibility score",
            value=f"{municipalities['AccessibilityScore'].mean():.1f}"
        )

    with col2:
        st.metric(
            label="Average distance to closest supermarket",
            value=f"{municipalities['DistanceClosestSupermarket'].mean():.2f} km"
        )

    with col3:
        st.metric(
            label="Lowest accessibility score",
            value=f"{municipalities['AccessibilityScore'].min():.1f}"
        )

# Retrieve municipality boundaries from PDOK
# The map uses our calculated accessibility score per 10,000 residents
# Green indicates higher scores and red indicates lower scores
    st.subheader("Supermarket Accessibility by Municipality")

    geojson_url = (
        "https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/"
        "ogc/v1/collections/gemeentegebied/items"
        "?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FOGC%2F1.3%2FCRS84"
        "&f=json&limit=1000"
    )

    try:
        response = requests.get(geojson_url, timeout=15)
        response.raise_for_status()
        geojson_data = response.json()

        fig = px.choropleth_mapbox(
            municipalities,
            geojson=geojson_data,
            locations="Name",
            featureidkey="properties.naam",
            color="AccessibilityScore",
            color_continuous_scale=[
                [0.0, "#d73027"],  # Red: poor accessibility
                [0.5, "#fee08b"],  # Yellow: moderate accessibility
                [1.0, "#1a9850"]   # Green: good accessibility
            ],
            range_color=(0, 5),
            mapbox_style="open-street-map",
            zoom=6,
            center={"lat": 52.1326, "lon": 5.2986},
            opacity=0.6,
            hover_data=[
                "Population",
                "SupermarketsWithin1KM",
                "SupermarketsWithin3KM",
                "SupermarketsWithin5KM",
                "DistanceClosestSupermarket"
            ],
            labels={
                "AccessibilityScore": "Accessibility Score"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Map could not be loaded: {e}")


# Compare municipality population with supermarket accessibility
# This helps identify municipalities with relatively low accessibility scores
    st.subheader("Municipality Comparison")

    fig = px.scatter(
        municipalities,
        x="Population",
        y="AccessibilityScore",
        hover_name="Name",
        title="Supermarket Accessibility Compared to Population",
        labels={
            "Population": "Municipality population",
            "AccessibilityScore": "Accessibility score"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

# Display the municipality data and calculated accessibility scores in a table
# Users can inspect the values behind the map and scatter plot
    st.subheader("Municipality Data")

    st.dataframe(
        municipalities[
            [
                "MunicipalityID",
                "Name",
                "Population",
                "Year",
                "DistanceClosestSupermarket",
                "SupermarketsWithin1KM",
                "SupermarketsWithin3KM",
                "SupermarketsWithin5KM",
                "AccessibilityScore"
            ]
        ],
        use_container_width=True
    )
