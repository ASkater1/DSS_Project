import json
import os
import time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

import data_access as db

# All data comes from the PostgreSQL database through the data access layer
# (data_access.py). Each loader is cached, so the database is only queried again
# when the cache expires.
try:
    supermarkets = db.load_supermarkets()
    economyStatistics = db.load_economy_statistics()
    municipalities = db.load_municipalities()
    basket_prices_monthly = db.load_monthly_basket_prices()
    category_prices_monthly = db.load_monthly_category_prices()

except Exception as e:
    st.error(f"Could not load data from the database: {e}")
    st.stop()

if municipalities.empty:
    st.error(
        "No municipality data was found in the database. "
        "Run staticdata_loading_database_municipalities.py first."
    )
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

# Use the most recent month with basket prices
    if basket_prices_monthly.empty:
        basket_prices = basket_prices_monthly
    else:
        latest_date = basket_prices_monthly["Date"].max()
        basket_prices = basket_prices_monthly[
            basket_prices_monthly["Date"] == latest_date
        ]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Supermarket chains",
            value=len(supermarkets)
        )

# Market shares are only shown once they have been filled in the database
    with col2:
        if supermarkets["MarketShare"].notna().any():
            st.metric(
                label="Combined market share",
                value=f"{supermarkets['MarketShare'].sum():.0f}%"
            )
        else:
            st.metric(label="Combined market share", value="n/a")

    with col3:
        if basket_prices.empty:
            st.metric(label="Average basket price", value="n/a")
        else:
            st.metric(
                label="Average basket price",
                value=f"€{basket_prices['Price'].mean():.2f}"
            )

    st.subheader("Basket prices per supermarket")

    if basket_prices.empty:
        st.info(
            "No essential basket has been defined yet: no product has "
            "isBasketProduct set in the database."
        )
    else:
        fig = px.bar(
            basket_prices,
            x="SupermarketName",
            y="Price",
            color="SupermarketName",
            hover_name="SupermarketName",
            hover_data=["Products"],
            labels={
                "Price": "Basket price (€)",
                "SupermarketName": "Supermarket",
                "Products": "Basket products"
            },
            title=f"Basket price per supermarket ({latest_date:%B %Y})"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.write(
            "This chart shows the price of the essential basket in each supermarket, "
            "based on the average price of each basket product in the latest month."
        )

    st.subheader("Average basket price per supermarket compared to increase of income")

    if basket_prices_monthly.empty or economyStatistics.empty:
        st.info("Not enough basket price and income data is available for this comparison.")
    else:
        basket_comparison = basket_prices_monthly.copy()
        income_comparison = economyStatistics.copy()
        basket_comparison["Date"] = pd.to_datetime(basket_comparison["Date"])
        income_comparison["Date"] = pd.to_datetime(income_comparison["Date"])

        # Income is stored as a monthly series; calculate its increase from
        # the previous month before combining it with the basket prices.
        income_comparison = income_comparison.sort_values("Date")
        income_comparison["IncomeIncreasePerMonth"] = (
            income_comparison["AverageDisposableIncome"].diff()
        )

        comparison_fig = make_subplots(specs=[[{"secondary_y": True}]])

        for supermarket_name, supermarket_data in basket_comparison.groupby(
            "SupermarketName"
        ):
            comparison_fig.add_trace(
                go.Scatter(
                    x=supermarket_data["Date"],
                    y=supermarket_data["Price"],
                    mode="lines+markers",
                    name=supermarket_name
                ),
                secondary_y=False
            )

        comparison_fig.add_trace(
            go.Scatter(
                x=income_comparison["Date"],
                y=income_comparison["IncomeIncreasePerMonth"],
                mode="lines+markers",
                name="Income increase per month",
                line={"dash": "dash", "color": "black"}
            ),
            secondary_y=True
        )

        comparison_fig.update_layout(
            title="Monthly basket price compared with income increase",
            xaxis_title="Month",
            hovermode="x unified"
        )
        comparison_fig.update_yaxes(
            title_text="Average basket price (€)", secondary_y=False
        )
        comparison_fig.update_yaxes(
            title_text="Income increase per month (€)", secondary_y=True
        )

        st.plotly_chart(comparison_fig, use_container_width=True)
        st.caption(
            "Income increase is calculated as the change in average disposable "
            "income compared with the previous month."
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

# Products are grouped into shared categories (see code/importer/categories), so the
# same category can be compared between supermarkets. The list only contains the
# categories of the selected supermarkets.
    filtered_categories = category_prices_monthly[
        category_prices_monthly["SupermarketName"].isin(selected_supermarkets)
    ]

    with col2:
        selected_category = st.selectbox(
            "Select category",
            ["All categories"] + sorted(filtered_categories["Category"].unique().tolist())
        )

# Essential basket prices of the selected supermarkets
    filtered_basket = basket_prices_monthly[
        basket_prices_monthly["SupermarketName"].isin(selected_supermarkets)
    ]
    basket_totals = filtered_basket[
        filtered_basket["Date"] == filtered_basket["Date"].max()
    ].set_index("SupermarketName")["Price"]

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

# Basket prices for each supermarket over time
# This helps identify whether essential food products are becoming more expensive
    if filtered_basket.empty:
        st.info(
            "The essential basket price will appear here once basket products "
            "are marked in the database (isBasketProduct)."
        )
    else:
        fig = px.line(
            filtered_basket,
            x="Date",
            y="Price",
            color="SupermarketName",
            markers=True,
            title="Essential basket price over time",
            labels={
                "Date": "Month",
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

# The search runs in the database: product names are matched without considering
# capital letters, and partial product names can also be used
    if search_product.strip():
        search_results = db.search_products(
            search_product, tuple(selected_supermarkets)
        )

        if search_results.empty:
            st.write("No products found.")
        else:
            if len(search_results) >= db.SEARCH_LIMIT:
                st.caption(
                    f"Showing the first {db.SEARCH_LIMIT} matching products. "
                    "Refine your search to see more specific results."
                )

# Hide the quantity column when the database has no product quantities
            if search_results["Quantity"].isna().all():
                search_results = search_results.drop(columns="Quantity")

# Display the latest known price of every matching product
            st.dataframe(
                search_results.rename(columns={
                    "SupermarketName": "Supermarket",
                    "Name": "Product",
                    "Price": "Latest price (€)",
                    "Date": "Price date"
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Latest price (€)": st.column_config.NumberColumn(format="€%.2f"),
                    "Price date": st.column_config.DateColumn(format="YYYY-MM-DD")
                }
            )

    st.subheader("Average product price by category")

# Calculate the average product price per supermarket over time
# This helps identify categories where prices are increasing
    if selected_category == "All categories":
        chart_data = filtered_categories.assign(
            Total=filtered_categories["Price"] * filtered_categories["Products"]
        ).groupby(["Date", "SupermarketName"], as_index=False)[["Total", "Products"]].sum()
        chart_data["Price"] = chart_data["Total"] / chart_data["Products"]
    else:
        chart_data = filtered_categories[
            filtered_categories["Category"] == selected_category
        ]

    fig = px.line(
        chart_data,
        x="Date",
        y="Price",
        color="SupermarketName",
        markers=True,
        title=f"Average product price: {selected_category.lower()}",
        hover_data=["Products"],
        labels={
            "Price": "Average price (€)",
            "Date": "Month",
            "SupermarketName": "Supermarket",
            "Products": "Products"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Each product is averaged per month first; the chart shows the average "
        "of those product prices."
    )

# ECONOMY TAB
# Shows the monthly CPI, inflation and household income from the economy statistics

with tab3:
    st.header("Citizen Economy")

    col1, col2 = st.columns(2)
    with col1:
        CPI_Line = px.line(
            economyStatistics,
            x="Date",
            y="CPI",
            markers=True,
            title="Consumer Price Index (CPI, 2015 = 100)",
            labels={
            "Date": "Month",
            "CPI": "Consumer Price Index (CPI)"
            },
            line_shape='spline'
        )
        CPI_Line.update_traces(line_smoothing=0.75)  # Adjust smoothing factor
        st.plotly_chart(CPI_Line, use_container_width=True)

    with col2:
        # Display the CPI change on the previous month with a smoothed line
        CPI_Monthly_Rate = px.line(
            economyStatistics,
            x="Date",
            y="CPIMonthlyRateOfChange",
            markers=True,
            title="Monthly Rate of Change in CPI",
            labels={
                "Date": "Month",
                "CPIMonthlyRateOfChange": "Change on the previous month (%)"
            },
            line_shape='spline'
        )
        CPI_Monthly_Rate.update_traces(line_smoothing=0.75)  # Adjust smoothing factor
        st.plotly_chart(CPI_Monthly_Rate, use_container_width=True)

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
        title="CPI Yearly Rate of Change (inflation) vs Average Disposable Income",
        xaxis_title="Month",
        yaxis_title="CPI change on a year earlier (%)",
        yaxis2_title="Average Disposable Income (€)",
        legend=dict(x=0.01, y=1.5, bordercolor="Black", borderwidth=1)
    )
    st.plotly_chart(income_cpi_increase_compare, use_container_width=True)

    st.caption(
        "Household income is published by CBS per year, so every month shows the "
        "income of its year. Months without published income are left empty."
    )

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
    cached_municipality_geojson = "municipalities.geojson"
    try:
        try:
            if (os.path.exists(cached_municipality_geojson) and
                os.path.getsize(cached_municipality_geojson) > 0 and
                time.time() - os.path.getmtime(cached_municipality_geojson) < 60 * 60 * 24 * 30):
                with open(cached_municipality_geojson, "r") as f:
                    geojson_data = json.loads(f.read())
            else: 
                response = requests.get(geojson_url, timeout=15)
                response.raise_for_status()
                geojson_data = response.json()
                # write the geojson data to a file
                with open(cached_municipality_geojson, "w") as f:
                    json.dump(geojson_data, f)
        except requests.RequestException as e:
            print("Warning: could not fetch live municipality geodata.")
            geojson_data  = ""
            # use static geojson data from the local file if the request fails
            with open(cached_municipality_geojson, "r") as f:
                geojson_data = json.loads(f.read())
            raise


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
