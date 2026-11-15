import json
import os
import time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests
import psycopg2

import data_access as db

st.set_page_config(layout="wide")


#Function to render a date range filter for each of the dashboard pages as 2 way slider
def render_date_filter(dataframes, key):
    date_values = [
        pd.to_datetime(dataframe["Date"], errors="coerce")
        for dataframe in dataframes
        if "Date" in dataframe.columns
    ]
    valid_dates = pd.concat(date_values).dropna() if date_values else pd.Series(dtype="datetime64[ns]")

    if valid_dates.empty:
        st.info("No dates are available for this filter.")
        return None, None

    minimum_date = valid_dates.min().date()
    maximum_date = valid_dates.max().date()

    slider_key = f"{key}_range"
    start_key = f"{key}_start"
    end_key = f"{key}_end"

    # Start with the whole period; also reset when the stored dates fall outside the data
    stored_range = st.session_state.get(slider_key)
    if (
        stored_range is None
        or stored_range[0] < minimum_date
        or stored_range[1] > maximum_date
    ):
        st.session_state[slider_key] = (minimum_date, maximum_date)
        st.session_state[start_key] = minimum_date
        st.session_state[end_key] = maximum_date

    # Moving the slider updates the date fields
    def slider_changed():
        start, end = st.session_state[slider_key]
        st.session_state[start_key] = start
        st.session_state[end_key] = end

    # Typing a date moves the slider, only when the start date is on or before the end date
    def date_fields_changed():
        start = st.session_state[start_key] or minimum_date
        end = st.session_state[end_key] or maximum_date
        if start <= end:
            st.session_state[slider_key] = (start, end)

    st.slider(
        "Date range",
        min_value=minimum_date,
        max_value=maximum_date,
        format="YYYY-MM-DD",
        key=slider_key,
        on_change=slider_changed,
    )

    start_col, end_col = st.columns(2)
    with start_col:
        st.date_input(
            "Start date",
            min_value=minimum_date,
            max_value=maximum_date,
            key=start_key,
            on_change=date_fields_changed,
        )
    with end_col:
        st.date_input(
            "End date",
            min_value=minimum_date,
            max_value=maximum_date,
            key=end_key,
            on_change=date_fields_changed,
        )

    start_date = st.session_state[start_key] or minimum_date
    end_date = st.session_state[end_key] or maximum_date

    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return None, None

    return pd.Timestamp(start_date), pd.Timestamp(end_date)

#Filter to select the rows of the database that fall within the selected date range.
def filter_by_date(dataframe, start_date, end_date):
    """Keep rows whose Date falls inside the selected inclusive date range."""
    if start_date is None or end_date is None or "Date" not in dataframe.columns:
        return dataframe.iloc[0:0]
    dates = pd.to_datetime(dataframe["Date"], errors="coerce")
    end_exclusive = end_date + pd.Timedelta(days=1)
    return dataframe.loc[
        dates.ge(start_date) & dates.lt(end_exclusive)
    ].copy()


#Price index chart. 
def draw_price_index_chart(price_index, comparison_index, selected_supermarkets, category,
                           comparison_name, comparison_short, comparison_caption,
                           projection=None, comparison_projection=None):
    if price_index.empty:
        st.info("No price data is available for this selection.")
        return

    # The base month is the first month shown for this category
    base_month = price_index["Date"].min()

    missing = sorted(set(selected_supermarkets) - set(price_index["SupermarketName"]))
    if missing:
        st.caption(f"No data for this category: {', '.join(missing)}.")

    # Fixed colour per supermarket, so a supermarket keeps its colour when filtering
    colours = dict(zip(supermarkets["Name"], px.colors.qualitative.Plotly))

    fig = go.Figure()

    # Comparison line rescaled to 100 in the same base month
    if comparison_index.empty:
        st.caption(f"{comparison_name} is not available for {base_month:%B %Y}, so it is not shown.")
    else:
        fig.add_trace(go.Scatter(
            x=comparison_index["Date"],
            y=comparison_index["Index"],
            mode="lines",
            name=comparison_name,
            line={"color": "#888780", "width": 4},
            opacity=0.6,
            hovertemplate=f"{comparison_name}: %{{y:.1f}}<extra></extra>"
        ))

    # Prediction of the comparison line after its last month: a dashed grey line
    if comparison_projection is not None and not comparison_projection.empty:
        fig.add_trace(go.Scatter(
            x=comparison_projection["Date"],
            y=comparison_projection["Index"],
            mode="lines",
            name=f"{comparison_name} (projection)",
            line={"color": "#888780", "width": 3, "dash": "dash"},
            opacity=0.6,
            hovertemplate=f"{comparison_name} (projection): %{{y:.1f}}<extra></extra>"
        ))

    for supermarket_name, data in price_index.groupby("SupermarketName"):
        notes = np.where(
            data["LowReliability"],
            f"<br>fewer than {db.MIN_COMPARABLE_PRODUCTS} comparable products",
            ""
        )
        notes = notes + np.where(
            (data["PriceChanges"] == 0) & (data["Products"] > 0),
            "<br>no price changes this month",
            ""
        )
        fig.add_trace(go.Scatter(
            x=data["Date"],
            y=data["Index"],
            mode="lines+markers",
            name=supermarket_name,
            line={"color": colours.get(supermarket_name), "width": 2},
            # Less reliable months get a lighter dot
            marker={
                "color": colours.get(supermarket_name),
                "size": 6,
                "opacity": np.where(data["LowReliability"], 0.3, 1).tolist()
            },
            customdata=list(zip(data["Products"].astype(int), notes)),
            hovertemplate=(
                f"{supermarket_name}: %{{y:.1f}}"
                "<br>based on %{customdata[0]:,.0f} comparable products"
                "%{customdata[1]}<extra></extra>"
            )
        ))

    # Projection after the last month with real price data
    projected = projection if projection is not None else pd.DataFrame()
    for supermarket_name, data in (projected.groupby("SupermarketName") if not projected.empty else []):
        fig.add_trace(go.Scatter(
            x=data["Date"],
            y=data["Index"],
            mode="lines",
            name=f"{supermarket_name} (projection)",
            line={"color": colours.get(supermarket_name), "width": 2, "dash": "dash"},
            hovertemplate=f"{supermarket_name} (projection): %{{y:.1f}}<extra></extra>"
        ))

    fig.update_layout(
        title=f"Price index: {category.lower()} compared with {comparison_short} ({base_month:%B %Y} = 100)",
        xaxis_title="Month",
        yaxis_title=f"Index ({base_month:%b %Y} = 100)",
        legend_title=f"Supermarket / {comparison_short}",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    has_projection = not projected.empty or (
        comparison_projection is not None and not comparison_projection.empty
    )
    last_sentence = (
        f"Lighter dots are based on fewer than {db.MIN_COMPARABLE_PRODUCTS} comparable products."
    )
    if has_projection:
        last_sentence = (
            f"Dashed lines are predictions (linear regression, at most "
            f"{db.MAX_PROJECTION_MONTHS} months), and lighter dots are based on fewer than "
            f"{db.MIN_COMPARABLE_PRODUCTS} comparable products."
        )

    st.caption(
        "The index shows how much the prices of the same products changed since the "
        f"first month shown: 110 means 10% more expensive. {comparison_caption} "
        + last_sentence
    )

# Load annual supermarket market shares from PostgreSQL
def load_market_shares():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT year, SUM(marketShare)
                FROM MarketShares
                GROUP BY year
                ORDER BY year
            """)
            rows = cursor.fetchall()
    finally:
        conn.close()

    return pd.DataFrame(rows, columns=["Year", "MarketShare"])


# SIDEBAR

PAGES = {
    "Overview": ":material/dashboard:",
    "Prices": ":material/sell:",
    "Economy": ":material/trending_up:",
    "Municipalities": ":material/map:",
}

# Hide the arrow that collapses the sidebar
st.markdown(
    """
    <style>
    [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] {
        display: none;
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button {
        min-height: 4.5rem;
        border-radius: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# The selected page is remembered between reruns, overview is default
if "page" not in st.session_state:
    st.session_state.page = "Overview"


# Function that runs when a tile is clicked
def select_page(name):
    st.session_state.page = name


with st.sidebar:
    st.title("Food Security Dashboard")
    st.caption("Monitoring supermarket affordability and accessibility in the Netherlands")

    # Four tiles in a 2 x 2 grid; the tile of the selected page is highlighted
    tile_columns = st.columns(2)
    for position, (name, icon) in enumerate(PAGES.items()):
        with tile_columns[position % 2]:
            # The icon is part of the label (Streamlit 1.37 has no icon parameter on buttons)
            st.button(
                f"{icon} {name}",
                key=f"tile_{name}",
                type="primary" if st.session_state.page == name else "secondary",
                use_container_width=True,
                on_click=select_page,
                args=(name,)
            )

    st.divider()
    st.subheader("Filters")

page = st.session_state.page

# Functions to fetch the data from the database.
try:
    if page in ("Overview", "Prices"):
        supermarkets = db.load_supermarkets()
        basket_prices_monthly = db.load_monthly_basket_prices()

    if page == "Overview":
        market_shares = load_market_shares()
    if page in ("Overview", "Prices", "Economy"):
        economyStatistics = db.load_economy_statistics()
    if page == "Prices":
        price_index_links = db.load_price_index_links()
    if page == "Municipalities":
        municipalities = db.load_municipalities()

#Exception handling for database connection issues, or data loading errors.
except Exception as e:
    st.error(f"Could not load data from the database: {e}")
    st.stop()

if page == "Municipalities" and municipalities.empty:
    st.error(
        "No municipality data was found in the database. "
        "Run staticdata_loading_database_municipalities.py first."
    )
    st.stop()

# OVERVIEW PAGE

if page == "Overview":

    st.header("Supermarket Overview")
    with st.sidebar:
        overview_start, overview_end = render_date_filter(
            [basket_prices_monthly, economyStatistics], "overview"
        )
    filtered_overview_basket = filter_by_date(
        basket_prices_monthly, overview_start, overview_end
    )
    filtered_overview_economy = filter_by_date(
        economyStatistics, overview_start, overview_end
    )

# Use the most recent month with basket prices
    if filtered_overview_basket.empty:
        basket_prices = filtered_overview_basket
    else:
        latest_date = filtered_overview_basket["Date"].max()
        basket_prices = filtered_overview_basket[
            filtered_overview_basket["Date"] == latest_date
        ]

# KPI cards at the top of the page
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Supermarket chains",
            value=len(supermarkets)
        )

# Show the market share for the latest available year in the selected date range
    with col2:
        if overview_start is not None and overview_end is not None:
            filtered_shares = market_shares[
                (market_shares["Year"] >= overview_start.year) &
                (market_shares["Year"] <= overview_end.year)
            ]
        else:
            filtered_shares = market_shares.iloc[0:0]

        if not filtered_shares.empty:
            latest_year = filtered_shares["Year"].max()

            share = filtered_shares.loc[
                filtered_shares["Year"] == latest_year,
                "MarketShare"
            ].iloc[0]

            st.metric(
                label=f"Combined market share ({latest_year})",
                value=f"{share:.1f}%"
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

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Market share per supermarket")

    # Market share of each supermarket per year
        shares_per_supermarket = db.load_market_shares_per_supermarket()
        if overview_start is not None and overview_end is not None:
            shares_per_supermarket = shares_per_supermarket[
                shares_per_supermarket["Year"].between(overview_start.year, overview_end.year)
            ]

        if shares_per_supermarket.empty:
            st.info(
                "No market share data is available for this period. "
                "Run the market shares importer to load it."
            )
        else:
            share_colours = dict(zip(supermarkets["Name"], px.colors.qualitative.Plotly))
            share_fig = go.Figure()
            for supermarket_name, data in shares_per_supermarket.groupby("SupermarketName"):
                share_fig.add_trace(go.Scatter(
                    x=data["Year"],
                    y=data["MarketShare"],
                    mode="lines+markers",
                    name=supermarket_name,
                    line={"color": share_colours.get(supermarket_name), "width": 2},
                    marker={"size": 8},
                    hovertemplate=f"{supermarket_name}: %{{y:.1f}}%<extra></extra>"
                ))

            # Other supermarkets: the rest of the market per year (100% minus the chains above)
            other_shares = (
                100 - shares_per_supermarket.groupby("Year")["MarketShare"].sum()
            ).round(1)
            share_fig.add_trace(go.Scatter(
                x=other_shares.index,
                y=other_shares.values,
                mode="lines+markers",
                name="Other supermarkets",
                line={"color": "#888780", "width": 2, "dash": "dash"},
                marker={"size": 8},
                hovertemplate="Other supermarkets: %{y:.1f}%<extra></extra>"
            ))
            share_fig.update_layout(
                xaxis={"title": "Year", "dtick": 1},
                yaxis={"title": "Market share (%)", "rangemode": "tozero"},
                # Legend above the chart, so the plot keeps the full column width
                legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0,
                        "entrywidth": 0.33, "entrywidthmode": "fraction"},
                margin={"t": 70},
                hovermode="x unified"
            )
            st.plotly_chart(share_fig, use_container_width=True)

            st.caption(
                "Share of each chain in Dutch supermarket sales per year, "
                f"{shares_per_supermarket['Year'].min()}–{shares_per_supermarket['Year'].max()}. "
                "The grey dashed line is all other supermarkets together."
            )

    with chart_col2:
        st.subheader("Food prices compared with household income")

    # Food CPI and average disposable household income on one axis, standardized to first value
        food_income = filtered_overview_economy.dropna(subset=["FoodCPI"]).sort_values("Date")
        if food_income.empty:
            st.info("The food CPI is not in the database yet: run the financial importer.")
        else:
            income_base_month = food_income["Date"].iloc[0]
            food_index = 100 * food_income["FoodCPI"] / food_income["FoodCPI"].iloc[0]

            yearly_income = (
                filtered_overview_economy.dropna(subset=["AverageDisposableIncome"])
                .groupby(filtered_overview_economy["Date"].dt.year)["AverageDisposableIncome"].first()
            )
            base_year = income_base_month.year
            income_points = []
            if base_year in yearly_income.index:
                base_income = yearly_income[base_year]
                income_points.append((income_base_month, 100.0))
                for year, income in yearly_income.items():
                    mid_year = pd.Timestamp(year=year, month=7, day=1)
                    if income_base_month < mid_year <= food_income["Date"].iloc[-1]:
                        income_points.append((mid_year, 100 * income / base_income))

            food_income_fig = go.Figure()
            food_income_fig.add_trace(go.Scatter(
                x=food_income["Date"],
                y=food_index,
                mode="lines",
                name="Food prices (CPI food & soft drinks)",
                line={"color": "#eb6834", "width": 2},
                hovertemplate="Food prices: %{y:.1f}<extra></extra>"
            ))
            if len(income_points) > 1:
                food_income_fig.add_trace(go.Scatter(
                    x=[point[0] for point in income_points],
                    y=[point[1] for point in income_points],
                    mode="lines+markers",
                    name="Disposable household income (yearly)",
                    line={"color": "#2a78d6", "width": 2, "dash": "dash"},
                    marker={"size": 8},
                    hovertemplate="Disposable household income: %{y:.1f}<extra></extra>"
                ))
            food_income_fig.update_layout(
                xaxis_title="Month",
                yaxis_title=f"Index ({income_base_month:%b %Y} = 100)",
                # Legend above the chart, so the plot keeps the full column width
                legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
                margin={"t": 50},
                hovermode="x unified"
            )
            st.plotly_chart(food_income_fig, use_container_width=True)

            st.caption(
                "Food prices (CBS) and average disposable household income, both set to 100 in "
                f"{income_base_month:%B %Y}. When the income line is above the food line, income "
                "grew faster than food prices. Income is published once a year, so the months in "
                "between are estimated."
            )
            if len(income_points) <= 1:
                st.caption("No household income is available for this period yet.")

    st.subheader("Basket price as a share of household income")

# Affordability of the essential basket, supermarket basket price / monthly income in %
    yearly_income = (
        economyStatistics.dropna(subset=["AverageDisposableIncome"])
        .groupby(economyStatistics["Date"].dt.year)["AverageDisposableIncome"].first()
    )
    if filtered_overview_basket.empty or yearly_income.empty:
        st.info("Not enough basket price and income data is available for this comparison.")
    else:
        affordability = filtered_overview_basket.copy()
        affordability["Date"] = pd.to_datetime(affordability["Date"])

        mid_year_income = pd.Series(
            (yearly_income / 12).values,
            index=[pd.Timestamp(year=int(year), month=7, day=1) for year in yearly_income.index]
        )
        all_months = mid_year_income.index.union(pd.DatetimeIndex(affordability["Date"].unique()))
        monthly_income = (
            mid_year_income.reindex(all_months).interpolate(method="time").ffill().bfill()
        )
        affordability["MonthlyIncome"] = affordability["Date"].map(monthly_income)
        affordability["IncomeShare"] = 100 * affordability["Price"] / affordability["MonthlyIncome"]

        affordability_fig = go.Figure()
        for supermarket_name, supermarket_data in affordability.sort_values("Date").groupby(
            "SupermarketName"
        ):
            affordability_fig.add_trace(go.Scatter(
                x=supermarket_data["Date"],
                y=supermarket_data["IncomeShare"],
                mode="lines+markers",
                name=supermarket_name,
                customdata=supermarket_data[["Price", "MonthlyIncome"]],
                hovertemplate=(
                    f"{supermarket_name}: %{{y:.2f}}% "
                    "(basket €%{customdata[0]:.2f} of €%{customdata[1]:,.0f} per month)<extra></extra>"
                )
            ))

        affordability_fig.update_layout(
            title="Basket price as a share of monthly disposable household income",
            xaxis_title="Month",
            yaxis={"title": "Share of monthly income (%)", "rangemode": "tozero"},
            # Legend above the chart, so the plot keeps the full width
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
            title_y=0.98,
            title_yanchor="top",
            title_yref="container",
            margin={"t": 100},
            hovermode="x unified"
        )

        st.plotly_chart(affordability_fig, use_container_width=True)
        st.caption(
            "The basket price of each supermarket as a percentage of the average monthly "
            "disposable household income. A higher line means groceries take a bigger part of "
            "the budget. Income is published once a year, so the months in between are estimated."
        )

# PRICES PAGE
# Allows users to compare supermarket prices and monitor price development over time

elif page == "Prices":
    st.header("Supermarket Prices")
    st.write("Compare supermarket prices and monitor changes over time.")

# Filters (in the sidebar)
    with st.sidebar:
        # The economy data is included so the date range reaches the last CPI month
        prices_start, prices_end = render_date_filter(
            [basket_prices_monthly, price_index_links, economyStatistics], "prices"
        )
        selected_supermarkets = st.multiselect(
            "Select supermarkets",
            supermarkets["Name"].tolist(),
            default=supermarkets["Name"].tolist()
        )

#Category filter
    available_index_links = price_index_links[
        price_index_links["SupermarketName"].isin(selected_supermarkets)
    ]
    available_index_links = filter_by_date(
        available_index_links, prices_start, prices_end
    )

    with st.sidebar:
        category_options = sorted(
            available_index_links["Category"].dropna().unique().tolist()
        )
        if available_index_links["IsFood"].fillna(False).any():
            category_options = [db.ALL_FOOD] + [
                category for category in category_options
                if category != db.ALL_FOOD
            ]
        selected_categories = st.multiselect(
            "Select categories",
            category_options,
            default=[],
            placeholder="All categories — type to filter",
            filter_mode="contains",
            key="price_categories"
        )
        selected_products = st.multiselect(
            "Select products",
            db.load_product_names(tuple(selected_categories)),
            default=[],
            placeholder="All products — type to filter",
            filter_mode="contains",
            key="price_products"
        )

# Recalculate only the CPI and wage index dataset from the active product and category filters.
    if selected_products:
        visual_index_links = db.load_price_index_links(tuple(selected_products))
    else:
        visual_index_links = price_index_links

    filtered_index_links = visual_index_links[
        visual_index_links["SupermarketName"].isin(selected_supermarkets)
    ]
    filtered_index_links = filter_by_date(
        filtered_index_links, prices_start, prices_end
    )
    filtered_index_links = db.filter_selected_categories(
        filtered_index_links, tuple(selected_categories)
    )

    category_label = (
        "All categories" if not selected_categories
        else selected_categories[0] if len(selected_categories) == 1
        else f"{len(selected_categories)} selected categories"
    )

# Essential basket metrics and price development are independent of the product
# and category filters.
    filtered_basket = basket_prices_monthly[
        basket_prices_monthly["SupermarketName"].isin(selected_supermarkets)
    ]
    filtered_basket = filter_by_date(filtered_basket, prices_start, prices_end)
    basket_totals = filtered_basket["Price"]

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

# An empty product selection means all linked product clusters in the active
# category and supermarket filters. Selecting products restricts the table to
# those cluster names.
    product_results = db.load_product_prices(
        tuple(selected_products), tuple(selected_supermarkets), tuple(selected_categories)
    )

    if product_results.empty:
        st.write("No products found for the selected filters.")
    else:
# Display one row per linked product cluster and its latest price per supermarket
        st.dataframe(
            product_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                supermarket: st.column_config.NumberColumn(format="€%.2f")
                for supermarket in ["Albert Heijn", "Jumbo", "Lidl", "Plus"]
            }
        )

    # Supermarkets whose real price data ends before the end of the date range are
    # predicted with a linear regression up to the end of the date range (at most 6 months)
    projection_end = prices_end

    st.subheader("Price index compared with CPI")

# Price index of the same products per supermarket compared with CPI
    cpi_data = economyStatistics[["Date", "CPI"]].rename(columns={"CPI": "Value"})
    price_index, cpi_index = db.chain_price_index(
        filtered_index_links, tuple(selected_categories), selected_supermarkets,
        cpi_data, end_month=prices_end
    )

    # The CPI is only predicted after its last published month, not when the date range
    # ends earlier
    cpi_projection = None
    if not cpi_index.empty and cpi_index["Date"].max() == cpi_data.dropna()["Date"].max():
        cpi_projection = db.project_comparison(cpi_index)

    draw_price_index_chart(
        price_index, cpi_index, selected_supermarkets, category_label,
        projection=db.project_price_index(price_index, projection_end),
        comparison_projection=cpi_projection,
        comparison_name="CPI (all items)",
        comparison_short="CPI",
        comparison_caption=(
            "The grey line is the CPI (all goods and services), also set to 100 in that month."
        )
    )

    st.subheader("Price index compared with cao wages")

# The same price index, compared with collective (cao) wages.
    price_index, wage_index = db.chain_price_index(
        filtered_index_links, tuple(selected_categories), selected_supermarkets,
        db.wage_level_from_yearly_increase(economyStatistics), end_month=prices_end
    )
    draw_price_index_chart(
        price_index, wage_index, selected_supermarkets, category_label,
        projection=db.project_price_index(price_index, projection_end),
        comparison_name="Cao wages (estimate)",
        comparison_short="cao wages",
        comparison_caption=(
            "The grey line is the cao wage level, estimated from the yearly cao wage "
            "increase and also set to 100 in that month."
        )
    )

    st.subheader("Price change per category")

# Percentage price change of the same products per food category and supermarket over
# one common period (KPI: % price change per category of products)
    category_changes, change_start, change_end = db.category_price_changes(
        filtered_index_links,
        selected_supermarkets,
        include_all_food=db.ALL_FOOD in selected_categories
    )

    if category_changes.empty:
        st.info("Not enough price data is available for this selection.")
    else:
        # Categories from the largest to the smallest average change
        order = (
            category_changes[category_changes["Category"] != db.ALL_FOOD]
            .groupby("Category")["Change"].mean()
            .sort_values(ascending=False)
            .index.tolist()
        )
        if db.ALL_FOOD in set(category_changes["Category"]):
            order = [db.ALL_FOOD] + order

        colours = dict(zip(supermarkets["Name"], px.colors.qualitative.Plotly))
        change_fig = go.Figure()
        for supermarket_name in selected_supermarkets:
            data = category_changes[category_changes["SupermarketName"] == supermarket_name]
            if data.empty:
                continue
            data = data.set_index("Category").reindex(order).dropna(subset=["Change"]).reset_index()
            notes = np.where(
                data["LowReliability"],
                f"<br>fewer than {db.MIN_COMPARABLE_PRODUCTS} comparable products",
                ""
            )
            # A supermarket whose data starts later covers a shorter period
            supermarket_start = data["StartMonth"].iloc[0]
            if supermarket_start > change_start:
                notes = notes + f"<br>from {supermarket_start:%B %Y} (data starts later)"
            change_fig.add_trace(go.Bar(
                x=data["Change"],
                y=data["Category"],
                orientation="h",
                name=supermarket_name,
                # Less reliable bars are lighter
                marker={
                    "color": colours.get(supermarket_name),
                    "opacity": np.where(data["LowReliability"], 0.35, 1).tolist()
                },
                customdata=list(zip(data["Products"].round(0).astype(int), notes)),
                hovertemplate=(
                    f"{supermarket_name}: %{{x:+.1f}}%"
                    "<br>on average %{customdata[0]:,.0f} comparable products per month"
                    "%{customdata[1]}<extra></extra>"
                )
            ))

        change_fig.update_layout(
            title=(
                f"Price change per food category, {change_start:%B %Y} to {change_end:%B %Y}"
            ),
            barmode="group",
            xaxis_title="Price change of the same products (%)",
            yaxis={"categoryorder": "array", "categoryarray": order[::-1], "title": None},
            legend_title="Supermarket",
            height=max(450, 45 * len(order)),
            bargap=0.25
        )
        change_fig.add_vline(x=0, line_width=1, line_color="#888780")

        st.plotly_chart(change_fig, use_container_width=True)

        st.caption(
            "Each bar shows how much the prices of the same products in a food category "
            "changed over the selected period: +5% means 5% more expensive. Lighter bars "
            f"are based on fewer than {db.MIN_COMPARABLE_PRODUCTS} comparable products per month."
        )

# ECONOMY PAGE

elif page == "Economy":
    st.header("Citizen Economy")
    with st.sidebar:
        economy_start, economy_end = render_date_filter(
            [economyStatistics], "economy"
        )
    filtered_economy = filter_by_date(
        economyStatistics, economy_start, economy_end
    )

# KPI cards: Change in food prices and change in CPI compared with a year earlier

    def yearly_change_metric(column, label, empty_note):
        months = filtered_economy.dropna(subset=[column]).sort_values("Date")
        if months.empty:
            st.metric(label=label, value="n/a", border=True)
            st.caption(empty_note)
            return
        latest = months.iloc[-1]
        delta = None
        if len(months) > 1:
            previous = months.iloc[-2]
            delta = f"{latest[column] - previous[column]:+.1f} pt vs {previous['Date']:%B}"
        st.metric(
            label=f"{label} ({latest['Date']:%B %Y})",
            value=f"{latest[column]:+.1f}%",
            delta=delta,
            delta_color="inverse",
            chart_data=months[column].tolist(),
            chart_type="line",
            border=True
        )

    kpi_col1, kpi_col2 = st.columns(2)
    with kpi_col1:
        yearly_change_metric(
            "FoodCPIYearlyRateOfChange",
            "Food prices vs a year earlier",
            "The food CPI is not in the database yet: run the financial importer."
        )
    with kpi_col2:
        yearly_change_metric(
            "CPIYearlyRateOfChange",
            "All prices (inflation) vs a year earlier",
            "No CPI data is available for this period."
        )

    col1, col2 = st.columns(2)
    with col1:
        CPI_Line = px.line(
            filtered_economy,
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
            filtered_economy,
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

# MUNICIPALITIES PAGE
elif page == "Municipalities":

    st.header("Supermarket Accessibility")
    with st.sidebar:
        st.caption("This page has no filters.")

    st.write("Explore supermarket accessibility across Dutch municipalities.")
    st.caption(
        "The accessibility score counts the supermarkets near where people live: one within "
        "1 km counts as 1, one within 1–3 km as 0.75 and one within 3–5 km as 0.5. A higher "
        "score means more supermarkets close by, a low score means people have to travel "
        "further for their groceries."
    )

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
