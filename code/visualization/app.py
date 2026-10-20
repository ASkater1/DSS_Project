import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

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

# Create dummy municipality data for supermarket accessibility
# Includes population, distance to closest supermarket and supermarkets within 1, 3 and 5 km
#municipalities = pd.DataFrame({
#    "MunicipalityID": list(range(1, 11)),
#    "Name": [
#        "Amsterdam", "Rotterdam", "Utrecht",
#        "Den Haag", "Eindhoven", "Groningen",
#        "Zeist", "Amersfoort", "Tilburg", "Maastricht"
#    ],
#    "Population": [
#        920000, 670000, 370000, 570000, 245000,
#        240000, 66000, 160000, 230000, 125000
#    ],
#    "Year": [2025] * 10,
#    "DistanceClosestSupermarket": [
#        0.3, 0.4, 0.2, 0.4, 0.5,
#        0.6, 0.8, 0.5, 0.6, 0.7
#    ],
#    "SupermarketsWithin1KM": [
#        20, 16, 12, 13, 8, 7, 3, 6, 7, 4
#    ],
#    "SupermarketsWithin3KM": [
#        60, 45, 35, 40, 24, 20, 9, 18, 21, 13
#    ],
#    "SupermarketsWithin5KM": [
#        100, 80, 60, 70, 43, 35, 16, 30, 36, 23
#    ]
#})


# Load real municipality data from CBS
# Sources:
# 80305ned - Supermarket accessibility
# 03759ned - Municipality population

CBS_BASE_URL = "https://opendata.cbs.nl/ODataApi/OData"
YEAR = 2025


@st.cache_data(ttl=86400)
def get_cbs_data(table, endpoint, params=None):
    """Download paginated data from the CBS OData API."""
    url = f"{CBS_BASE_URL}/{table}/{endpoint}"
    all_rows = []

    with requests.Session() as session:
        while url:
            response = session.get(
                url,
                params=params,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()

            all_rows.extend(result.get("value", []))

            url = (
                result.get("odata.nextLink")
                or result.get("@odata.nextLink")
            )
            params = None

    return pd.DataFrame(all_rows)


def get_category_key(df, title):
    """Find a CBS category key using its title."""
    matches = df[
        df["Title"].astype(str).str.strip().str.casefold()
        == title.casefold()
    ]

    if matches.empty:
        raise ValueError(f"CBS category not found: {title}")

    return matches.iloc[0]["Key"]


def get_period_key(table, year):
    periods = get_cbs_data(table, "Perioden")

    matches = periods[
        periods["Title"].astype(str).str.strip()
        .str.startswith(str(year))
    ]

    if matches.empty:
        raise ValueError(
            f"No data period for {year} in {table}"
        )

    return matches.iloc[0]["Key"]


@st.cache_data(ttl=86400)
def load_municipalities(year=2025):

    # -----------------------------
    # 1. Supermarket accessibility
    # -----------------------------

    table = "80305ned"

    properties = get_cbs_data(
        table, "DataProperties"
    ).reset_index(drop=True)

    titles = properties["Title"].fillna("").str.strip()

    distance_rows = properties[
        titles == "Afstand tot grote supermarkt"
    ]

    if distance_rows.empty:
        raise ValueError(
            "Supermarket distance field not found"
        )

    distance_key = distance_rows.iloc[0]["Key"]

    # Locate the three distance bands associated
    # with 'Aantal grote supermarkten'
    group_indexes = properties.index[
        titles == "Aantal grote supermarkten"
    ]

    if len(group_indexes) == 0:
        raise ValueError(
            "Supermarket count group not found"
        )

    group_index = group_indexes[0]

    bands = properties.iloc[
        group_index + 1:group_index + 4
    ]

    expected = {
        "Binnen 1 km": "SupermarketsWithin1KM",
        "Binnen 3 km": "SupermarketsWithin3KM",
        "Binnen 5 km": "SupermarketsWithin5KM"
    }

    band_columns = {}

    for _, row in bands.iterrows():
        title = row["Title"].strip()
        if title in expected:
            band_columns[row["Key"]] = expected[title]

    if len(band_columns) != 3:
        raise ValueError(
            "Could not identify the 1, 3 and 5 km "
            "supermarket fields in CBS metadata"
        )

    supermarket_columns = {
        distance_key: "DistanceClosestSupermarket",
        **band_columns
    }

    period = get_period_key(table, year)

    supermarket_data = get_cbs_data(
        table,
        "TypedDataSet",
        params={
            "$filter": f"Perioden eq '{period}'",
            "$select": ",".join([
                "RegioS",
                *supermarket_columns.keys()
            ]),
            "$top": 10000
        }
    )

    supermarket_data = supermarket_data[
        supermarket_data["RegioS"].str.startswith(
            "GM", na=False
        )
    ].copy()

    supermarket_data = supermarket_data.rename(
        columns=supermarket_columns
    )

    # -----------------------------
    # 2. Population
    # -----------------------------

    table = "03759ned"

    properties = get_cbs_data(
        table, "DataProperties"
    )

    population_key = get_category_key(
        properties,
        "Bevolking op 1 januari"
    )

    period = get_period_key(table, year)

    dimensions = {
        "Geslacht": "Totaal mannen en vrouwen",
        "Leeftijd": "Totaal",
        "BurgerlijkeStaat": "Totaal burgerlijke staat"
    }

    filters = [f"Perioden eq '{period}'"]

    for dimension, title in dimensions.items():

        categories = get_cbs_data(
            table, dimension
        )

        key = get_category_key(categories, title)

        filters.append(
            f"{dimension} eq '{key}'"
        )

    population_data = get_cbs_data(
        table,
        "TypedDataSet",
        params={
            "$filter": " and ".join(filters),
            "$select": f"RegioS,{population_key}",
            "$top": 10000
        }
    )

    population_data = population_data[
        population_data["RegioS"].str.startswith(
            "GM", na=False
        )
    ].copy()

    population_data = population_data.rename(
        columns={population_key: "Population"}
    )

    # -----------------------------
    # 3. Municipality names
    # -----------------------------

    regions = get_cbs_data(
        "80305ned", "RegioS"
    )

    regions = regions[
        regions["Key"].str.startswith("GM", na=False)
    ][["Key", "Title"]].copy()

    regions = regions.rename(
        columns={
            "Key": "RegioS",
            "Title": "Name"
        }
    )

    regions["Name"] = regions["Name"].str.strip()

    # -----------------------------
    # 4. Combine the data
    # -----------------------------

    municipalities = supermarket_data.merge(
        population_data[["RegioS", "Population"]],
        on="RegioS",
        how="left",
        validate="one_to_one"
    )

    municipalities = municipalities.merge(
        regions,
        on="RegioS",
        how="left",
        validate="many_to_one"
    )

    municipalities["MunicipalityID"] = (
        municipalities["RegioS"]
        .str.replace("GM", "", regex=False)
        .astype(int)
    )

    municipalities["Year"] = year

    columns = [
        "MunicipalityID",
        "Name",
        "Population",
        "Year",
        "DistanceClosestSupermarket",
        "SupermarketsWithin1KM",
        "SupermarketsWithin3KM",
        "SupermarketsWithin5KM"
    ]

    municipalities = municipalities[columns].copy()

    numeric_columns = [
        "Population",
        "DistanceClosestSupermarket",
        "SupermarketsWithin1KM",
        "SupermarketsWithin3KM",
        "SupermarketsWithin5KM"
    ]

    for column in numeric_columns:
        municipalities[column] = pd.to_numeric(
            municipalities[column],
            errors="coerce"
        )

    return (
        municipalities
        .sort_values("Name")
        .reset_index(drop=True)
    )


# Load municipality data into the dashboard
try:
    municipalities = load_municipalities(YEAR)

    # Clean municipality names for matching with PDOK
    municipalities["Name"] = (
        municipalities["Name"]
        .str.strip()
        .str.replace(r"\s*\(gemeente\)", "", regex=True, case=False)
        .str.replace(r"\(([^()]*)\.\)", r"(\1)", regex=True)
        .replace({
            "Middelburg (Z)": "Middelburg",
            "Laren (NH)": "Laren",
            "Rijswijk (ZH)": "Rijswijk",
            "Stein (L)": "Stein",
            "Beek (L)": "Beek",
        })
    )

    if municipalities.empty:
        st.error("CBS returned no municipality data.")
        st.stop()

    st.success(
        f"Loaded {len(municipalities)} municipalities "
        f"from CBS ({YEAR})"
    )

except Exception as e:
    st.error(f"Could not load CBS data: {e}")
    st.stop()


# Create the dashboard with three tabs
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

    st.subheader("Market share and basket prices")

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
            "MarketShare": "Market share (%)",
            "Price": "Basket price (€)"
        },
        title="Market share compared to essential basket price"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.write(
        "This chart shows whether supermarkets with a "
        "larger market share have higher or lower basket prices."
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
            economy,
            x="Date",
            y="CPI",
            markers=True,
            title="Consumer Price Index (CPI)",
            labels={
            "Date": "Year",
            "CPI": "Consumer Price Index (CPI)"
            }
        )
        st.plotly_chart(CPI_Line, use_container_width=True)

    with col2:
        CPI_Yearly_Rate = px.line(
            economy,
            x="Date",
            y="CPIYearlyRateOfChange",
            markers=True,
            title="Monthly Rate of Change in CPI",
            labels={
                "Date": "Year",
                "CPIYearlyRateOfChange": "Monthly Rate of Change in CPI"
            }
        )
        st.plotly_chart(CPI_Yearly_Rate, use_container_width=True)

    income_cpi_increase_compare = make_subplots(specs=[[{"secondary_y": True}]])
    income_cpi_increase_compare.add_trace(
        go.Scatter(
            x=economy["Date"],
            y=economy["CPIYearlyRateOfChange"],
            mode="lines+markers",
            name="CPI Yearly Rate of Change",
            line={
            'shape': 'spline',
            'smoothing': 1.0,  # Range is from 0 to 1.3
        }),
        secondary_y=False
        )
    
    income_cpi_increase_compare.add_trace(
        go.Scatter(
            x=economy["Date"],
            y=economy["AverageDisposableIncome"],
            mode="lines",
            name="Average Disposable Income"
        ),
        secondary_y=True
    )
    income_cpi_increase_compare.update_layout(
        title="CPI Yearly Rate of Change vs Average Disposable Income",
        xaxis_title="Date",
        yaxis_title="CPI Yearly Rate of Change (%)",
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