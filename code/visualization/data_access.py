#************************************************************************************
#----------------------------- DASHBOARD DATA ACCESS LAYER --------------------------*
#************************************************************************************
#
# Middle layer between the PostgreSQL database and the Streamlit dashboard (app.py).
# Every function runs one query, converts the result to a pandas DataFrame with the
# column names app.py uses, and is cached by Streamlit so the database is not queried
# again on every interaction.
#
# Heavy work (aggregating ~19 million price rows) is done inside PostgreSQL, so only
# small summary tables are sent to the dashboard.


# Importing necessary libraries
import os

import numpy as np
import pandas as pd
import psycopg2
import streamlit as st

# How long query results are cached, in seconds. The importers add data at most daily.
CACHE_TTL = 60 * 60

# The price index query scans every price row (up to a minute),
# so it is kept longer
LONG_CACHE_TTL = 6 * 60 * 60

# Maximum number of products returned by the product search
SEARCH_LIMIT = 200

# PRICE INDEX SETTINGS
# Price ratios (this month / previous month of the same product) outside these limits
# are ignored as probable data errors or pack-size changes
MIN_PRICE_RATIO = 0.5
MAX_PRICE_RATIO = 2.0

# Months based on fewer comparable products than this are shown as less reliable
MIN_COMPARABLE_PRODUCTS = 10

# Name of the index over all food categories together
ALL_FOOD = "All food"

# Fallback for databases without shared categories (Categories table and
# Products.categoryId, filled by code/importer/categories/category_importer.py):
# an SQL expression that turns the raw category path into a top-level category.
# These are not comparable between supermarkets. Every supermarket stores its
# category path in a different format:
#   AH     Home\Producten\Zuivel, eieren\Yoghurt en skyr\...  -> "Zuivel, eieren"
#   Plus   Zuivel eieren boter\Verse zuivel\Yoghurt           -> "Zuivel eieren boter"
#   Jumbo  Koek, snoep, chocolade en chips ; Chocolade ; ...  -> "Koek, snoep, chocolade en chips"
#   Lidl   Home/Eten & drinken/Kaas & Zuivel &&& ...           -> "Kaas & Zuivel"
# Paths that match none of these (mostly Lidl's Open Food Facts labels) become "Overig".
TOP_CATEGORY_SQL = r"""
    CASE
        WHEN p.category IS NULL OR p.category = '' THEN 'Overig'
        WHEN split_part(p.category, '\', 1) = 'Home' THEN split_part(p.category, '\', 3)
        WHEN position('\' IN p.category) > 0 THEN split_part(p.category, '\', 1)
        WHEN position(' ; ' IN p.category) > 0 THEN split_part(p.category, ' ; ', 1)
        WHEN left(p.category, 5) = 'Home/' THEN
            trim(split_part(split_part(p.category, '/', 3), '&&&', 1))
        ELSE 'Overig'
    END
"""

# Function to check the database settings and open a connection
def get_connection():
    required_variables = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing_variables = [
        variable for variable in required_variables
        if not os.environ.get(variable)
    ]
    if missing_variables:
        raise RuntimeError(
            "Missing database environment variables: " + ", ".join(missing_variables)
        )

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )



# Function to run a query and return the result as a DataFrame.
# work_mem gives PostgreSQL more memory for large aggregations (only for this query),
# so it can group in memory instead of on disk.
def run_query(query: str, params: dict | None = None,
              work_mem: str | None = None) -> pd.DataFrame:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if work_mem:
                cursor.execute("SELECT set_config('work_mem', %s, true)", (work_mem,))
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
    connection.close()
    return pd.DataFrame(rows, columns=columns)



# Function to convert DECIMAL columns (returned as Decimal objects) to numbers
def to_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df





# SUPERMARKETS
@st.cache_data(ttl=CACHE_TTL)
def load_supermarkets() -> pd.DataFrame:
    supermarkets = run_query("""
        SELECT
            supermarketid AS "SupermarketID",
            name AS "Name",
            marketshare AS "MarketShare"
        FROM supermarkets
        ORDER BY supermarketid
    """)
    return to_numeric(supermarkets, ["MarketShare"])



# ECONOMY STATISTICS (one row per month, filled by the financial importer)
@st.cache_data(ttl=CACHE_TTL)
def load_economy_statistics() -> pd.DataFrame:
    economy = run_query("""
        SELECT
            date AS "Date",
            cpi AS "CPI",
            cpiyearlyrateofchange AS "CPIYearlyRateOfChange",
            cpimonthlyrateofchange AS "CPIMonthlyRateOfChange",
            averagegrossincome AS "AverageGrossIncome",
            averagedisposableincome AS "AverageDisposableIncome",
            averagestandardizedincome AS "AverageStandardizedIncome",
            yearlywageincrease AS "YearlyWageIncrease"
        FROM economystatistics
        ORDER BY date
    """)
    economy["Date"] = pd.to_datetime(economy["Date"])
    return to_numeric(economy, [column for column in economy.columns if column != "Date"])



# MUNICIPALITIES (filled by the static municipality importer)
@st.cache_data(ttl=CACHE_TTL)
def load_municipalities() -> pd.DataFrame:
    municipalities = run_query("""
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
    """)

    municipalities = to_numeric(municipalities, [
        "Population",
        "DistanceClosestSupermarket",
        "SupermarketsWithin1KM",
        "SupermarketsWithin3KM",
        "SupermarketsWithin5KM"
    ])

    # The importer stores an annual value as 1 January in the database DATE column
    municipalities["Year"] = pd.to_datetime(
        municipalities["Year"], errors="coerce"
    ).dt.year.astype("Int64")
    return municipalities



# MONTHLY PRICE CHANGE OF THE SAME PRODUCTS, PER SUPERMARKET AND CATEGORY
# The basis of the price index (see chain_price_index below). For every product:
#   1. its average price per month,
#   2. the ratio between that price and its price in its previous month with a price
#      (this also bridges months without any data, such as Plus in March-April 2024).
# Per supermarket, category and month the query returns the average of the logarithms
# of those ratios (the logarithm of their geometric mean, the method CBS uses for the
# CPI), the number of comparable products and how many of them changed price.
# New products only count from their second month, so they do not cause jumps.
@st.cache_data(ttl=LONG_CACHE_TTL, show_spinner="Calculating the price index from all price records (the first load can take up to a minute)...")
def load_price_index_links() -> pd.DataFrame:
    category, category_join = category_sql()
    is_food = "COALESCE(c.isfood, false)" if category_join else "true"

    links = run_query(f"""
        WITH product_month AS (
            SELECT
                supermarketid,
                productid,
                date_trunc('month', date)::date AS month,
                avg(price) AS price
            FROM supermarketsproducts
            WHERE price > 0
            GROUP BY supermarketid, productid, date_trunc('month', date)
        ),
        product_link AS (
            SELECT
                supermarketid,
                productid,
                month,
                price / lag(price) OVER (
                    PARTITION BY supermarketid, productid ORDER BY month
                ) AS ratio
            FROM product_month
        )
        SELECT
            pl.month AS "Date",
            s.name AS "SupermarketName",
            {category} AS "Category",
            {is_food} AS "IsFood",
            avg(ln(pl.ratio)) FILTER (WHERE pl.ratio BETWEEN %(min_ratio)s AND %(max_ratio)s) AS "AvgLogRatio",
            count(*) FILTER (WHERE pl.ratio BETWEEN %(min_ratio)s AND %(max_ratio)s) AS "Products",
            count(*) FILTER (WHERE pl.ratio BETWEEN %(min_ratio)s AND %(max_ratio)s AND pl.ratio <> 1) AS "PriceChanges"
        FROM product_link pl
        JOIN products p ON p.productid = pl.productid
        JOIN supermarkets s ON s.supermarketid = pl.supermarketid
        {category_join}
        GROUP BY pl.month, s.name, 3, 4
        ORDER BY pl.month, s.name, 3
    """, {"min_ratio": MIN_PRICE_RATIO, "max_ratio": MAX_PRICE_RATIO}, work_mem="512MB")

    links["Date"] = pd.to_datetime(links["Date"])
    links["IsFood"] = links["IsFood"].astype(bool)
    return to_numeric(links, ["AvgLogRatio", "Products", "PriceChanges"])



# Function to turn the monthly links into a price index for one category (or ALL_FOOD)
# and the selected supermarkets, compared with another series such as the CPI or wages.
# The comparison series is a DataFrame with the columns Date and Value (any level, for
# example the CPI with 2015 = 100).
# The base month is the first month shown: the earliest month in the given links (so the
# date filter decides it). In the base month the comparison series and every supermarket
# with data are 100; from there the monthly changes are multiplied. A supermarket whose
# data starts later (such as Lidl) starts at the comparison level of its first month and
# follows its own price changes from there. A month without price changes keeps the index
# at the level of the month before. Months without any data for a supermarket stay empty
# (the chart connects the line).
# Returns the price index and the comparison series rescaled to 100 in the base month.
def chain_price_index(links: pd.DataFrame, category: str, supermarkets: list[str],
                      comparison: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = links[links["SupermarketName"].isin(supermarkets)]

    if category == ALL_FOOD:
        # The geometric mean over all food products: the category averages weighted
        # by their number of comparable products
        food = selected[selected["IsFood"]].copy()
        food["WeightedLog"] = food["AvgLogRatio"].fillna(0) * food["Products"]
        selected = food.groupby(["Date", "SupermarketName"], as_index=False)[
            ["WeightedLog", "Products", "PriceChanges"]
        ].sum()
        selected["AvgLogRatio"] = np.where(
            selected["Products"] > 0, selected["WeightedLog"] / selected["Products"].where(selected["Products"] > 0), np.nan
        )
    else:
        selected = selected[selected["Category"] == category]

    columns = ["Date", "SupermarketName", "Index", "Products", "PriceChanges", "LowReliability"]
    if selected.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=["Date", "Index"])

    # The base month: the first month shown
    base_month = selected["Date"].min()

    # Comparison series rescaled to 100 in the base month, for the months of the chart
    comparison = comparison.dropna(subset=["Value"])
    comparison = comparison[
        (comparison["Date"] >= base_month) & (comparison["Date"] <= selected["Date"].max())
    ]
    comparison_base = comparison.loc[comparison["Date"] == base_month, "Value"]
    if comparison_base.empty:
        comparison_index = pd.DataFrame(columns=["Date", "Index"])
    else:
        comparison_index = pd.DataFrame({
            "Date": comparison["Date"],
            "Index": 100 * comparison["Value"] / comparison_base.iloc[0]
        })
    comparison_level = comparison_index.set_index("Date")["Index"]

    chained = []
    for supermarket, data in selected.groupby("SupermarketName"):
        data = data.sort_values("Date").copy()
        # No comparable products (the first month, or a month with only new products):
        # the index stays at the level of the month before
        relative = np.exp(data["AvgLogRatio"].fillna(0).cumsum())
        start_month = data["Date"].iloc[0]

        # Starting level: 100 in the base month, or the comparison level of the first month
        # for a supermarket whose data starts later (left out when that level is unknown)
        if start_month == base_month:
            start_level = 100.0
        elif start_month in comparison_level.index:
            start_level = comparison_level[start_month]
        else:
            continue

        data["Index"] = start_level * relative / relative.iloc[0]
        data["SupermarketName"] = supermarket
        chained.append(data)

    if not chained:
        return pd.DataFrame(columns=columns), comparison_index
    index = pd.concat(chained, ignore_index=True)

    # A month is less reliable when it is based on few comparable products; the first
    # month of every supermarket is the starting point and has nothing to compare with
    first_month = index["Date"] == index.groupby("SupermarketName")["Date"].transform("min")
    index["LowReliability"] = (index["Products"] < MIN_COMPARABLE_PRODUCTS) & ~first_month
    return index[columns].sort_values(["SupermarketName", "Date"]).reset_index(drop=True), comparison_index



# Function to calculate the price change of the same products per food category and
# supermarket, for the "price change per category" bar chart.
# The period is set by the date filter: from the first month in the given links (the
# start of the date range) up to the last month. A supermarket whose data starts later
# (such as Lidl) covers its own, shorter period from its first month; its start month is
# returned in StartMonth, so the chart can say so. The change is the product of the
# monthly changes after the start month: (geometric mean ratio of month 1) x (month 2)
# x ... - 1. Also returns ALL_FOOD (all food categories together) and the average number
# of comparable products per month, to mark less reliable bars.
# Returns the changes and the start and end month of the period.
def category_price_changes(links: pd.DataFrame, supermarkets: list[str]
                           ) -> tuple[pd.DataFrame, pd.Timestamp | None, pd.Timestamp | None]:
    columns = ["Category", "SupermarketName", "Change", "Products", "LowReliability", "StartMonth"]
    food = links[links["SupermarketName"].isin(supermarkets) & links["IsFood"]].copy()
    if food.empty:
        return pd.DataFrame(columns=columns), None, None

    start_month = food["Date"].min()
    end_month = food["Date"].max()

    # Start month per supermarket: the start of the period, or its first month with data
    supermarket_start = food.groupby("SupermarketName")["Date"].min()
    food["StartMonth"] = food["SupermarketName"].map(supermarket_start)

    # Only the monthly changes after each supermarket's start month count
    period = food[food["Date"] > food["StartMonth"]].copy()
    if period.empty:
        return pd.DataFrame(columns=columns), start_month, end_month

    # All food: per month the category averages weighted by their comparable products
    period["WeightedLog"] = period["AvgLogRatio"].fillna(0) * period["Products"]
    all_food = period.groupby(["Date", "SupermarketName"], as_index=False)[
        ["WeightedLog", "Products"]
    ].sum()
    all_food["AvgLogRatio"] = all_food["WeightedLog"] / all_food["Products"].where(all_food["Products"] > 0)
    all_food["Category"] = ALL_FOOD
    combined = pd.concat([period, all_food], ignore_index=True)

    changes = combined.groupby(["Category", "SupermarketName"], as_index=False).agg(
        LogChange=("AvgLogRatio", lambda values: values.fillna(0).sum()),
        Products=("Products", "mean")
    )
    changes["StartMonth"] = changes["SupermarketName"].map(supermarket_start)
    # Rounded to one decimal; + 0.0 turns a rounded -0.0 into 0.0
    changes["Change"] = (100 * (np.exp(changes["LogChange"]) - 1)).round(1) + 0.0
    changes["LowReliability"] = changes["Products"] < MIN_COMPARABLE_PRODUCTS
    return changes[columns], start_month, end_month



# Function to build a monthly cao wage level from the stored yearly wage increases
# (YearlyWageIncrease: the change of cao wages compared with the same month a year
# earlier). Each month the level grows by the twelfth root of that month's yearly
# change, for example 4.7% per year becomes about 0.38% per month. CBS raises cao wages
# mostly in January and July, so this approximation is smoother than the real cao wage
# index. Returns a DataFrame with Date and Value (100 in the first month).
def wage_level_from_yearly_increase(economy: pd.DataFrame) -> pd.DataFrame:
    wages = economy[["Date", "YearlyWageIncrease"]].dropna().sort_values("Date")
    if wages.empty:
        return pd.DataFrame(columns=["Date", "Value"])
    monthly_factor = (1 + wages["YearlyWageIncrease"] / 100) ** (1 / 12)
    # The first month is the starting point (100); growth starts from the second month
    monthly_factor.iloc[0] = 1.0
    return pd.DataFrame({"Date": wages["Date"], "Value": 100 * monthly_factor.cumprod()})



# MONTHLY ESSENTIAL BASKET PRICE PER SUPERMARKET
# Sum of the monthly average prices of the products marked isBasketProduct.
# Returns an empty table while no products are marked as basket products.
@st.cache_data(ttl=CACHE_TTL, show_spinner="Calculating basket prices...")
def load_monthly_basket_prices() -> pd.DataFrame:
    basket = run_query("""
        WITH product_month AS (
            SELECT
                sp.supermarketid,
                sp.productid,
                date_trunc('month', sp.date)::date AS month,
                avg(sp.price) AS price
            FROM supermarketsproducts sp
            JOIN products p ON p.productid = sp.productid
            WHERE p.isbasketproduct AND sp.price IS NOT NULL
            GROUP BY sp.supermarketid, sp.productid, date_trunc('month', sp.date)
        )
        SELECT
            pm.month AS "Date",
            s.name AS "SupermarketName",
            sum(pm.price) AS "Price",
            count(*) AS "Products"
        FROM product_month pm
        JOIN supermarkets s ON s.supermarketid = pm.supermarketid
        GROUP BY pm.month, s.name
        ORDER BY pm.month, s.name
    """)
    basket["Date"] = pd.to_datetime(basket["Date"])
    return to_numeric(basket, ["Price", "Products"])



# Function to choose how products are grouped into categories: the shared
# categories when the database has them, otherwise each supermarket's own
# top-level category. Returns the SQL expression and the JOIN it needs.
@st.cache_data(ttl=CACHE_TTL)
def category_sql() -> tuple[str, str]:
    columns = run_query("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_name IN ('products', 'categories')
    """)
    has_shared_categories = (
        (columns["table_name"] == "categories").any()
        and "categoryid" in set(columns.loc[columns["table_name"] == "products", "column_name"])
    )
    if has_shared_categories:
        return "COALESCE(c.name, 'Onbekend')", "LEFT JOIN categories c ON c.categoryid = p.categoryid"
    return TOP_CATEGORY_SQL, ""



# Function to check whether the products table has the quantity columns
# (databases created from an older initdb.sql do not have them)
@st.cache_data(ttl=CACHE_TTL)
def products_have_quantity() -> bool:
    columns = run_query("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'products'
    """)
    return {"quantity_value", "quantity_units"} <= set(columns["column_name"])



# PRODUCT SEARCH: the latest known price of every product whose name matches
@st.cache_data(ttl=CACHE_TTL)
def search_products(search_text: str, supermarket_names: tuple[str, ...]) -> pd.DataFrame:
    if not search_text.strip() or not supermarket_names:
        return pd.DataFrame(
            columns=["SupermarketName", "Name", "Quantity", "Category", "Price", "Date"]
        )

    quantity_sql = (
        "trim(concat_ws(' ', p.quantity_value::float::text, p.quantity_units))"
        if products_have_quantity() else "NULL::text"
    )

    category, category_join = category_sql()
    results = run_query(f"""
        SELECT
            s.name AS "SupermarketName",
            p.name AS "Name",
            {quantity_sql} AS "Quantity",
            {category} AS "Category",
            latest.price AS "Price",
            latest.date AS "Date"
        FROM (
            SELECT * FROM products
            WHERE name ILIKE %(pattern)s
            ORDER BY name
            LIMIT %(limit)s
        ) p
        CROSS JOIN LATERAL (
            SELECT sp.supermarketid, sp.price, sp.date
            FROM supermarketsproducts sp
            JOIN supermarkets s2 ON s2.supermarketid = sp.supermarketid
            WHERE sp.productid = p.productid
              AND s2.name = ANY(%(supermarkets)s)
            ORDER BY sp.date DESC
            LIMIT 1
        ) latest
        JOIN supermarkets s ON s.supermarketid = latest.supermarketid
        {category_join}
        ORDER BY p.name, s.name
    """, {
        "pattern": f"%{search_text.strip()}%",
        "limit": SEARCH_LIMIT,
        "supermarkets": list(supermarket_names)
    })
    results["Date"] = pd.to_datetime(results["Date"])
    return to_numeric(results, ["Price"])
