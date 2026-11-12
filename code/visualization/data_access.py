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

import pandas as pd
import psycopg2
import streamlit as st

# How long query results are cached, in seconds. The importers add data at most daily.
CACHE_TTL = 60 * 60

# The monthly category aggregate scans every price row (about 20 seconds),
# so it is kept longer
LONG_CACHE_TTL = 6 * 60 * 60

# Maximum number of products returned by the product search
SEARCH_LIMIT = 200

# SQL expression that turns the raw category path into a top-level category.
# Every supermarket stores its category path in a different format:
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



# MONTHLY AVERAGE PRICE PER SUPERMARKET AND TOP-LEVEL CATEGORY
# Each product is first averaged per month, so products that were scraped on more
# days do not weigh more; those product averages are then averaged per category.
@st.cache_data(ttl=LONG_CACHE_TTL, show_spinner="Calculating monthly category prices from all price records (the first load takes about 20 seconds)...")
def load_monthly_category_prices() -> pd.DataFrame:
    prices = run_query(f"""
        WITH product_month AS (
            SELECT
                supermarketid,
                productid,
                date_trunc('month', date)::date AS month,
                avg(price) AS price
            FROM supermarketsproducts
            WHERE price IS NOT NULL
            GROUP BY supermarketid, productid, date_trunc('month', date)
        )
        SELECT
            pm.month AS "Date",
            s.name AS "SupermarketName",
            {TOP_CATEGORY_SQL} AS "Category",
            avg(pm.price) AS "Price",
            count(*) AS "Products"
        FROM product_month pm
        JOIN products p ON p.productid = pm.productid
        JOIN supermarkets s ON s.supermarketid = pm.supermarketid
        GROUP BY pm.month, s.name, 3
        ORDER BY pm.month, s.name, 3
    """, work_mem="512MB")
    prices["Date"] = pd.to_datetime(prices["Date"])
    return to_numeric(prices, ["Price", "Products"])



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

    results = run_query(f"""
        SELECT
            s.name AS "SupermarketName",
            p.name AS "Name",
            {quantity_sql} AS "Quantity",
            {TOP_CATEGORY_SQL} AS "Category",
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
        ORDER BY p.name, s.name
    """, {
        "pattern": f"%{search_text.strip()}%",
        "limit": SEARCH_LIMIT,
        "supermarkets": list(supermarket_names)
    })
    results["Date"] = pd.to_datetime(results["Date"])
    return to_numeric(results, ["Price"])
