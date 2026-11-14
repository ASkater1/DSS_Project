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

st.set_page_config(layout="wide")


#Function to render a date range filter for each of the dashboard pages
#It shows a two-way slider (start date on the left, end date on the right) and, below it,
#a start and an end date field that always show the selected dates and can also be typed in.
#The slider and the date fields are kept in sync. By default the whole period of the data is
#selected. It returns the selected start and end dates as timestamps, or None if there is no
#date available in the selection.
def render_date_filter(dataframes, key):
    """Render a date range slider with start and end date fields and return the selected pandas timestamps."""
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

    # Typing a date moves the slider (only when the start is on or before the end)
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


#Function to draw a price index chart: one line per supermarket and a grey comparison line
#(such as the CPI or cao wages), all rescaled to 100 in the base month by chain_price_index()
#in data_access.py.
def draw_price_index_chart(price_index, comparison_index, selected_supermarkets, category,
                           comparison_name, comparison_short, comparison_caption):
    if price_index.empty:
        st.info("No price data is available for this selection.")
        return

    # The base month is the first month shown for this category
    base_month = price_index["Date"].min()

    missing = sorted(set(selected_supermarkets) - set(price_index["SupermarketName"]))
    if missing:
        st.caption(f"No data for this category: {', '.join(missing)}.")

    late_starters = price_index.groupby("SupermarketName")["Date"].min()
    late_starters = late_starters[late_starters > base_month]
    if not late_starters.empty:
        st.caption(
            f"Starts later, at the {comparison_short} level of its first month: "
            + ", ".join(f"{name} ({month:%B %Y})" for name, month in late_starters.items())
            + "."
        )

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

    fig.update_layout(
        title=f"Price index: {category.lower()} compared with {comparison_short} ({base_month:%B %Y} = 100)",
        xaxis_title="Month",
        yaxis_title=f"Index ({base_month:%b %Y} = 100)",
        legend_title=f"Supermarket / {comparison_short}",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "The index shows how much the prices of the same products changed since the "
        "base month: 110 means 10% more expensive. Each month only products that also "
        "had a price the month before are compared, so newly added products do not "
        "cause jumps. A month without price changes keeps the level of the month "
        "before. Lighter dots are based on fewer than "
        f"{db.MIN_COMPARABLE_PRODUCTS} comparable products. {comparison_caption} "
        "The base month is the first month shown; a supermarket whose data starts later "
        f"starts at the {comparison_short} level of its first month."
    )


# SIDEBAR
# The dashboard has four pages, chosen with four tiles in the sidebar. Below the tiles
# the sidebar shows the filters of the selected page (added by each page further down).
# Each page focuses on a different part of supermarket affordability or accessibility.
PAGES = {
    "Overview": ":material/dashboard:",
    "Prices": ":material/sell:",
    "Economy": ":material/trending_up:",
    "Municipalities": ":material/map:",
}

# Hide the arrow that collapses the sidebar, so the sidebar always stays open,
# and make the page buttons in the sidebar look like tiles
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

# The selected page is remembered between reruns; the dashboard opens on Overview
if "page" not in st.session_state:
    st.session_state.page = "Overview"


# Function that runs when a tile is clicked: it selects that page before the rerun,
# so the right tile is highlighted straight away
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

# Functions to fetch the data from the database. Only the data the selected page needs
# is loaded, so pages without the slow price index open immediately.
try:
    if page in ("Overview", "Prices"):
        supermarkets = db.load_supermarkets()
        basket_prices_monthly = db.load_monthly_basket_prices()
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
# Shows general supermarket information, market shares and essential basket prices

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

    if filtered_overview_basket.empty or filtered_overview_economy.empty:
        st.info("Not enough basket price and income data is available for this comparison.")
    else:
        basket_comparison = filtered_overview_basket.copy()
        income_comparison = filtered_overview_economy.copy()
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

# PRICES PAGE
# Allows users to compare supermarket prices and monitor price development over time

elif page == "Prices":
    st.header("Supermarket Prices")
    st.write("Compare supermarket prices and monitor changes over time.")

# Filters (in the sidebar)
    with st.sidebar:
        prices_start, prices_end = render_date_filter(
            [basket_prices_monthly, price_index_links], "prices"
        )
        selected_supermarkets = st.multiselect(
            "Select supermarkets",
            supermarkets["Name"].tolist(),
            default=supermarkets["Name"].tolist()
        )

# Products are grouped into shared categories (see code/importer/categories), so the
# same category can be compared between supermarkets. The list only contains the
# categories of the selected supermarkets; "All food" combines all food categories.
    filtered_index_links = price_index_links[
        price_index_links["SupermarketName"].isin(selected_supermarkets)
    ]
    filtered_index_links = filter_by_date(
        filtered_index_links, prices_start, prices_end
    )

    with st.sidebar:
        selected_category = st.selectbox(
            "Select category",
            [db.ALL_FOOD] + sorted(filtered_index_links["Category"].unique().tolist())
        )

# Essential basket prices of the selected supermarkets
    filtered_basket = basket_prices_monthly[
        basket_prices_monthly["SupermarketName"].isin(selected_supermarkets)
    ]
    filtered_basket = filter_by_date(filtered_basket, prices_start, prices_end)
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

    st.subheader("Price index compared with CPI")

# Price index of the same products per supermarket, compared with the CPI, calculated in
# data_access.py. Unlike an average price, it does not jump when products are added.
# The first month shown is the base month (100); a supermarket whose data starts later
# starts at the CPI level of its first month.
    price_index, cpi_index = db.chain_price_index(
        filtered_index_links, selected_category, selected_supermarkets,
        economyStatistics[["Date", "CPI"]].rename(columns={"CPI": "Value"})
    )
    draw_price_index_chart(
        price_index, cpi_index, selected_supermarkets, selected_category,
        comparison_name="CPI (all items)",
        comparison_short="CPI",
        comparison_caption=(
            "The grey line is the consumer price index (CPI, all goods and services, CBS), "
            "rescaled to 100 in the same base month."
        )
    )

    st.subheader("Price index compared with cao wages")

# The same price index, compared with collective (cao) wages. The wage line is built from
# the stored yearly cao wage increase (YearlyWageIncrease), see data_access.py.
    price_index, wage_index = db.chain_price_index(
        filtered_index_links, selected_category, selected_supermarkets,
        db.wage_level_from_yearly_increase(economyStatistics)
    )
    draw_price_index_chart(
        price_index, wage_index, selected_supermarkets, selected_category,
        comparison_name="Cao wages (estimate)",
        comparison_short="cao wages",
        comparison_caption=(
            "The grey line shows collective (cao) wages per month, including special "
            "payments, for all sectors, rescaled to 100 in the same base month. It is an "
            "estimate built from the yearly cao wage increase of each month: CBS raises cao "
            "wages mostly in January and July, so the real wage level rises in steps, while "
            "this line spreads each increase evenly over the year."
        )
    )

    st.subheader("Price change per category")

# Percentage price change of the same products per food category and supermarket over
# one common period (KPI: % price change per category of products), calculated in
# data_access.py. This chart shows all food categories, so the category filter does
# not apply to it; the date range and supermarket filters do.
    category_changes, change_start, change_end = db.category_price_changes(
        filtered_index_links, selected_supermarkets
    )

    if category_changes.empty:
        st.info("Not enough price data is available for this selection.")
    else:
        # Categories from the largest to the smallest average change, with All food on top
        order = (
            category_changes[category_changes["Category"] != db.ALL_FOOD]
            .groupby("Category")["Change"].mean()
            .sort_values(ascending=False)
            .index.tolist()
        )
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

        # Supermarkets whose data starts after the start of the date range
        late_starters = (
            category_changes.groupby("SupermarketName")["StartMonth"].first()
        )
        late_starters = late_starters[late_starters > change_start]
        if not late_starters.empty:
            st.caption(
                "Shorter period, because the data starts later: "
                + ", ".join(f"{name} (from {month:%B %Y})" for name, month in late_starters.items())
                + ". Its bars cannot be compared one-to-one with the other supermarkets."
            )

        st.plotly_chart(change_fig, use_container_width=True)

        st.caption(
            "Each bar shows how much the prices of the same products in a food category "
            "changed over the period, at each supermarket: +5% means 5% more expensive. "
            "The period follows the date range in the sidebar. A supermarket whose data "
            "starts later covers a shorter period, from its first month with data. Lighter "
            f"bars are based on fewer than {db.MIN_COMPARABLE_PRODUCTS} comparable products "
            "per month."
        )

# ECONOMY PAGE
# Shows the monthly CPI, inflation and household income from the economy statistics

elif page == "Economy":
    st.header("Citizen Economy")
    with st.sidebar:
        economy_start, economy_end = render_date_filter(
            [economyStatistics], "economy"
        )
    filtered_economy = filter_by_date(
        economyStatistics, economy_start, economy_end
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

    income_cpi_increase_compare = make_subplots(specs=[[{"secondary_y": True}]])
    income_cpi_increase_compare.add_trace(
        go.Scatter(
            x=filtered_economy["Date"],
            y=filtered_economy["CPIYearlyRateOfChange"],
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
            x=filtered_economy["Date"],
            y=filtered_economy["AverageDisposableIncome"],
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

# MUNICIPALITIES PAGE
# Shows supermarket accessibility in different Dutch municipalities

elif page == "Municipalities":

    st.header("Supermarket Accessibility")
    with st.sidebar:
        st.caption("This page has no filters.")

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
