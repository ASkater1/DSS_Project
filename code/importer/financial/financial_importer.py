#************************************************************************************
#------------------------- ECONOMY STATISTICS DATA LOADER --------------------------*
#************************************************************************************
#
# Downloads monthly economic indicators for the Netherlands from the CBS Open Data API
# and loads them into the EconomyStatistics table (one row per month, dated the 1st),
# starting in START_MONTH.
#
#   83136NED  Consumentenprijzen; basisjaren vanaf 1969        -> CPI, CPIYearlyRateOfChange, CPIMonthlyRateOfChange (monthly)
#   83932NED  Inkomen van huishoudens; huishoudenskenmerken   -> average gross, disposable and
#                                                                standardized income (yearly, repeated
#                                                                on every month of that year)
#   85663NED  Cao-lonen, contractuele loonkosten en arbeidsduur -> yearlyWageIncrease (monthly)


# Importing necessary libraries
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import urlopen

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text





# CBS Open Data API configuration
CBS_BASE_URL = "https://opendata.cbs.nl/ODataApi/OData"

CPI_TABLE = "83136NED"
INCOME_TABLE = "83932NED"
WAGE_TABLE = "85663NED"

# First month to import, as YYYY-MM (can be overridden with ECONOMY_IMPORTER_START_MONTH).
# November 2022 is the first month of the supermarket price data.
START_MONTH = "2022-11"

# Base year of the stored CPI (this year's average = 100)
CPI_BASE_YEAR = 2015

# CBS marks periods as e.g. "2024MM03" (month), "2024JJ00" (year) or "2024KW01" (quarter)
MONTHLY_PERIOD_FILTER = "substringof('MM', Perioden)"
YEARLY_PERIOD_FILTER = "substringof('JJ', Perioden)"

# Income concepts in 83932NED and the database column each one fills
INCOME_CONCEPTS = {
    "Bruto inkomen": "averagegrossincome",
    "Besteedbaar inkomen": "averagedisposableincome",
    "Gestandaardiseerd inkomen": "averagestandardizedincome"
}

# 83932NED publishes income in units of 1 000 euro; the database stores euros
INCOME_UNIT_FACTOR = 1000

# Final database columns, in table order (PostgreSQL folds unquoted names to lower case)
final_columns = [
    "date",
    "cpi",
    "cpiyearlyrateofchange",
    "cpimonthlyrateofchange",
    "averagegrossincome",
    "averagedisposableincome",
    "averagestandardizedincome",
    "yearlywageincrease"
]

# Largest absolute value each DECIMAL column can hold, used to fail early with a clear error
column_limits = {
    "cpi": 999.99,                       # DECIMAL(5,2)
    "cpiyearlyrateofchange": 999.9,      # DECIMAL(4,1)
    "cpimonthlyrateofchange": 999.9,     # DECIMAL(4,1)
    "averagegrossincome": 999999999.9,   # DECIMAL(10,1)
    "averagedisposableincome": 999999999.9,
    "averagestandardizedincome": 999999999.9,
    "yearlywageincrease": 999.9          # DECIMAL(4,1)
}


# Function to download all pages of an endpoint from the CBS OData API
def get_cbs_data(table: str, endpoint: str, params: dict | None = None) -> pd.DataFrame:
    url = f"{CBS_BASE_URL}/{table}/{endpoint}"
    if params:
        # quote (not quote_plus) so padded CBS keys such as 'A045600   ' keep their spaces
        url = f"{url}?{urlencode(params, quote_via=quote)}"

    all_rows = []

    while url:
        with urlopen(url, timeout=60) as response:
            result = json.load(response)

        all_rows.extend(result.get("value", []))
        url = result.get("odata.nextLink") or result.get("@odata.nextLink")

    return pd.DataFrame(all_rows)



# Function to find the CBS key that belongs to a category title in a dimension
def get_category_key(table: str, dimension: str, title: str) -> str:
    categories = get_cbs_data(table, dimension)
    matches = categories[
        categories["Title"].astype(str).str.strip().str.casefold()
        == title.strip().casefold()
    ]

    if matches.empty:
        raise ValueError(f"CBS category '{title}' not found in {table}/{dimension}")

    # The raw key is returned on purpose: CBS pads some keys with spaces and
    # $filter only matches the padded form
    return matches.iloc[0]["Key"]

# Function to find the key of a topic (data column), optionally inside a topic group
def get_topic_key(properties: pd.DataFrame, title: str, group: str | None = None) -> str:
    titles = properties["Title"].fillna("").astype(str).str.strip()
    topics = properties[(properties["Type"] == "Topic") & (titles == title)]

    if group is not None:
        groups = properties[
            (properties["Type"] == "TopicGroup") & (titles == group)
        ]
        if groups.empty:
            raise ValueError(f"CBS topic group '{group}' not found")
        topics = topics[topics["ParentID"] == groups.iloc[0]["ID"]]

    if topics.empty:
        location = f" in group '{group}'" if group else ""
        raise ValueError(f"CBS topic '{title}'{location} not found")

    return topics.iloc[0]["Key"]



# Function to turn a yearly CBS period key ("2024JJ00") into its year (2024)
def period_to_year(periods: pd.Series) -> pd.Series:
    return periods.astype(str).str.strip().str[:4].astype(int)



# Function to turn a monthly CBS period key ("2024MM03") into a monthly period (2024-03)
def period_to_month(periods: pd.Series) -> pd.Series:
    periods = periods.astype(str).str.strip()
    return pd.to_datetime(periods.str[:4] + "-" + periods.str[6:8] + "-01").dt.to_period("M")





# Function to download the monthly CPI and compute its rate of change on a year earlier
def load_cpi(start_year: int) -> pd.DataFrame:
    properties = get_cbs_data(CPI_TABLE, "DataProperties")

    # 83136NED has one index column per base year (1969=100 ... 2025=100). Each column
    # only covers part of the history, so they are chained into one series below.
    base_columns = {}
    for _, row in properties[properties["Type"] == "Topic"].iterrows():
        match = re.search(r"Consumentenprijsindex (\d{4})=100", str(row["Title"]))
        if match:
            base_columns[int(match.group(1))] = row["Key"]

    if not base_columns:
        raise ValueError(f"No CPI index columns found in CBS table {CPI_TABLE}")

    # One extra year is downloaded: the rate of change compares each month with
    # the same month a year earlier
    data = get_cbs_data(
        CPI_TABLE,
        "TypedDataSet",
        params={"$filter": f"{MONTHLY_PERIOD_FILTER} and Perioden ge '{start_year - 1}'"}
    )
    data["month"] = period_to_month(data["Perioden"])
    data = data.set_index("month").sort_index()

    # Newest base first: that is the base CBS currently publishes new figures in.
    # Bases without any values in the downloaded months are left out.
    bases = [base_columns[base] for base in sorted(base_columns, reverse=True)]
    indexes = data[bases].apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    bases = list(indexes.columns)

    # CHAIN THE BASES ONTO CPI_BASE_YEAR = 100: use that base where CBS publishes it,
    # and fill the other months (e.g. after CBS stopped publishing it) with another
    # base, rescaled by the ratio of the averages over the months both have in common
    if CPI_BASE_YEAR not in base_columns:
        raise ValueError(f"CBS table {CPI_TABLE} has no CPI with base {CPI_BASE_YEAR}=100")
    target = base_columns[CPI_BASE_YEAR]
    if target not in indexes.columns:
        raise ValueError(f"CPI {CPI_BASE_YEAR}=100 has no values from {start_year - 1}")

    cpi = indexes[target].copy()
    for other in bases:
        if other == target:
            continue
        overlap = cpi.notna() & indexes[other].notna()
        if not overlap.any():
            raise ValueError(f"CPI column {other} does not overlap with {target}")
        factor = cpi[overlap].mean() / indexes[other][overlap].mean()
        cpi = cpi.fillna(indexes[other] * factor)

    # RATES OF CHANGE on a year earlier (the official CBS inflation figure) and on the
    # previous month: computed within a single base that has both months, so the
    # chaining and rounding above cannot distort them. The CPI_BASE_YEAR series is
    # tried first so the rates match the stored CPI; other bases only fill months it
    # does not cover.
    def rate_of_change(months_back: int) -> pd.Series:
        rates = pd.Series(index=indexes.index, dtype="float64")
        for column in [target] + [base for base in bases if base != target]:
            earlier = indexes[column].copy()
            earlier.index = earlier.index + months_back
            change = (indexes[column] / earlier.reindex(indexes.index) - 1) * 100
            rates = rates.fillna(change)
        # + 0.0 turns a rounded -0.0 into 0.0
        return rates.round(1) + 0.0

    cpi_data = pd.DataFrame({
        "cpi": cpi.round(2),
        "cpiyearlyrateofchange": rate_of_change(12),
        "cpimonthlyrateofchange": rate_of_change(1)
    })
    return cpi_data[cpi_data.index.year >= start_year]



# Function to download yearly average incomes of all private households
# (CBS only publishes these per year)
def load_income(start_year: int) -> pd.DataFrame:
    properties = get_cbs_data(INCOME_TABLE, "DataProperties")
    average_income_key = get_topic_key(properties, "Gemiddeld inkomen")

    filters = [
        YEARLY_PERIOD_FILTER,
        f"Perioden ge '{start_year}'",
        f"Inkomensklassen eq '{get_category_key(INCOME_TABLE, 'Inkomensklassen', 'Totaal')}'",
        "KenmerkenVanHuishoudens eq "
        f"'{get_category_key(INCOME_TABLE, 'KenmerkenVanHuishoudens', 'Particuliere huishoudens')}'"
    ]
    data = get_cbs_data(
        INCOME_TABLE,
        "TypedDataSet",
        params={
            "$filter": " and ".join(filters),
            "$select": f"Inkomensbegrippen,Perioden,{average_income_key}"
        }
    )

    # Translate the income-concept keys into database column names
    concepts = get_cbs_data(INCOME_TABLE, "Inkomensbegrippen")
    concepts["Title"] = concepts["Title"].astype(str).str.strip()
    missing = set(INCOME_CONCEPTS) - set(concepts["Title"])
    if missing:
        raise ValueError(f"Income concepts not found in {INCOME_TABLE}: {sorted(missing)}")
    key_to_column = {
        row["Key"].strip(): INCOME_CONCEPTS[row["Title"]]
        for _, row in concepts.iterrows()
        if row["Title"] in INCOME_CONCEPTS
    }

    data["column"] = data["Inkomensbegrippen"].str.strip().map(key_to_column)
    data = data.dropna(subset=["column"])
    data["year"] = period_to_year(data["Perioden"])
    data["value"] = pd.to_numeric(data[average_income_key], errors="coerce") * INCOME_UNIT_FACTOR

    income = data.pivot(index="year", columns="column", values="value")
    return income.reindex(columns=list(INCOME_CONCEPTS.values())).round(1)

# Function to download the monthly increase of collective (cao) wages on a year
# earlier, for the whole economy
def load_wage_increase(start_year: int) -> pd.DataFrame:
    properties = get_cbs_data(WAGE_TABLE, "DataProperties")
    wage_key = get_topic_key(
        properties,
        "Cao-lonen per maand incl.bijz.beloningen",
        group="Ontwikkeling t.o.v. een jaar eerder"
    )

    filters = [
        MONTHLY_PERIOD_FILTER,
        f"Perioden ge '{start_year}'",
        f"CaoSectoren eq '{get_category_key(WAGE_TABLE, 'CaoSectoren', 'Totaal cao-sectoren')}'",
        "BedrijfstakkenBranchesSBI2008 eq "
        f"'{get_category_key(WAGE_TABLE, 'BedrijfstakkenBranchesSBI2008', 'A-U Alle economische activiteiten')}'",
        f"Versie eq '{get_category_key(WAGE_TABLE, 'Versie', 'Huidige cijfers')}'"
    ]
    data = get_cbs_data(
        WAGE_TABLE,
        "TypedDataSet",
        params={"$filter": " and ".join(filters), "$select": f"Perioden,{wage_key}"}
    )

    data["month"] = period_to_month(data["Perioden"])
    data["yearlywageincrease"] = pd.to_numeric(data[wage_key], errors="coerce").round(1)
    return data.set_index("month")[["yearlywageincrease"]]



# Function to determine the latest month to import from today's date. CBS publishes
# a month's figures in the following month, so the current month is never complete.
def get_latest_month(today: date | None = None) -> pd.Period:
    today = today or date.today()
    return pd.Period(today, freq="M") - 1



# Function to combine all sources into rows that match the EconomyStatistics table
def load_economy_statistics(start_month: pd.Period | None = None,
                            latest_month: pd.Period | None = None) -> pd.DataFrame:
    start_month = start_month or pd.Period(START_MONTH, freq="M")
    latest_month = latest_month or get_latest_month()

    # The CBS tables are downloaded per year; months before the start month are
    # removed below
    start_year = start_month.year
    monthly = (
        load_cpi(start_year)
        .join(load_wage_increase(start_year), how="outer")
        .sort_index()
    )

    # The CBS 'Perioden ge' filter only reduces the download and is not applied
    # reliably by every table, so the start month is enforced here.
    # Months after the latest month are left out.
    monthly = monthly[
        (monthly.index >= start_month) & (monthly.index <= latest_month)
    ].copy()

    # Income only exists per year: every month gets the value of its own year
    # (months in a year CBS has not published yet stay NULL)
    monthly["year"] = monthly.index.year
    combined = monthly.join(load_income(start_year), on="year")

    # Keep only months with at least one value
    value_columns = final_columns[1:]
    combined = combined.dropna(subset=value_columns, how="all")

    # The table stores a monthly value in a DATE column, represented by the 1st
    combined["date"] = [date(month.year, month.month, 1) for month in combined.index]
    return combined.reset_index(drop=True)[final_columns]



# Function to check the quality of the combined data
def check_data_quality(df: pd.DataFrame):
    print("Data Quality Report:")
    print("Total months:", len(df), f"({df['date'].min():%Y-%m} to {df['date'].max():%Y-%m})")
    print("Duplicated dates:", df["date"].duplicated().sum())
    for column in final_columns[1:]:
        present = df.loc[df[column].notna(), "date"]
        span = f"{present.min():%Y-%m} to {present.max():%Y-%m}" if len(present) else "none"
        print(f"  {column}: {df[column].notna().sum()} values ({span})")

    # Fail before touching the database if a value would not fit its DECIMAL column
    for column, limit in column_limits.items():
        too_large = df[df[column].abs() > limit]
        if not too_large.empty:
            raise ValueError(
                f"{len(too_large)} value(s) in {column} exceed the column limit of {limit}"
            )



# Function to read the months that are currently stored in the database
def load_stored_statistics(db_conn, start_month: pd.Period) -> pd.DataFrame:
    query = text(f"""
        SELECT {", ".join(final_columns)}
        FROM economystatistics
        WHERE date >= :start_date
        ORDER BY date
    """)
    with db_conn.connect() as conn:
        stored = pd.read_sql(query, conn, params={"start_date": date(start_month.year, start_month.month, 1)})

    # PostgreSQL returns DECIMAL values as Decimal objects; compare them as floats
    stored["date"] = pd.to_datetime(stored["date"]).dt.date
    for column in final_columns[1:]:
        stored[column] = pd.to_numeric(stored[column], errors="coerce").astype("float64")
    return stored



# Function to find the months that are missing from the database or differ from CBS
def find_outdated_months(latest: pd.DataFrame, stored: pd.DataFrame) -> pd.DataFrame:
    merged = latest.merge(
        stored, on="date", how="left", suffixes=("", "_stored"), indicator=True
    )
    is_new = merged["_merge"] == "left_only"

    # A stored month is outdated when any value differs from the latest CBS value
    # (two missing values count as equal)
    is_changed = pd.Series(False, index=merged.index)
    for column in final_columns[1:]:
        latest_value = merged[column]
        stored_value = merged[f"{column}_stored"]
        same = (latest_value.isna() & stored_value.isna()) | (
            (latest_value - stored_value).abs() < 1e-9
        )
        is_changed |= ~same
    is_changed &= ~is_new

    print("Comparison with the database:")
    print("  Months stored:", len(stored))
    print("  New months:", is_new.sum(),
          [f"{d:%Y-%m}" for d in merged.loc[is_new, "date"]])
    print("  Changed months:", is_changed.sum(),
          [f"{d:%Y-%m}" for d in merged.loc[is_changed, "date"]])

    return merged.loc[is_new | is_changed, final_columns].reset_index(drop=True)



# Function to find the project's .env file by walking up from this script
def find_env_file() -> Path | None:
    for folder in Path(__file__).resolve().parents:
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
    return None





# Main execution
if __name__ == "__main__":

    # Locally the settings come from the project's .env; in Docker, compose's env_file sets them
    env_file = find_env_file()
    if env_file:
        load_dotenv(env_file)

    # Read database connection settings
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. Please set them in the .env file.")

    db_host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
    db_user = os.environ["DB_USER"]
    db_password = os.environ["DB_PASSWORD"]
    db_port = os.environ.get("DB_PORT", "5432")
    start_month = pd.Period(os.environ.get("ECONOMY_IMPORTER_START_MONTH", START_MONTH), freq="M")

    latest_month = get_latest_month()

    # Download, combine and validate the CBS data before touching the database
    print(
        f"Downloading monthly economy statistics from CBS, "
        f"from {start_month} up to {latest_month}..."
    )
    economy = load_economy_statistics(start_month, latest_month)
    if economy.empty:
        sys.exit("CBS returned no economy statistics. Import not performed.")
    check_data_quality(economy)

    # Opening a connection to the PostgreSQL database
    db_conn = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    # Compare the latest CBS data with what is stored and keep only outdated months
    stored = load_stored_statistics(db_conn, start_month)
    outdated = find_outdated_months(economy, stored)
    if outdated.empty:
        print("[INFO] Stored economy statistics are up to date. Nothing to import.")
        sys.exit(0)

    # NaN is not valid SQL; send missing values as NULL
    records = outdated.astype(object).where(outdated.notna(), None).to_dict("records")

    # Insert new months and refresh changed ones in one transaction. CBS revises
    # preliminary figures (e.g. the latest income year), so a changed month is updated.
    upsert = text(f"""
        INSERT INTO economystatistics ({", ".join(final_columns)})
        VALUES ({", ".join(":" + column for column in final_columns)})
        ON CONFLICT (date) DO UPDATE SET
            {", ".join(f"{column} = EXCLUDED.{column}" for column in final_columns[1:])}
    """)

    with db_conn.begin() as conn:
        conn.execute(upsert, records)

    print(f"{len(records)} outdated months of economy statistics inserted or updated successfully.")
