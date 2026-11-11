#************************************************************************************
#------------------------- ECONOMY STATISTICS DATA LOADER --------------------------*
#************************************************************************************
#
# Downloads yearly economic indicators for the Netherlands from the CBS Open Data API
# and loads them into the EconomyStatistics table (one row per year, dated 1 January).
#
#   83136NED  Consumentenprijzen; basisjaren vanaf 1969        -> CPI, CPIYearlyRateOfChange
#   83932NED  Inkomen van huishoudens; huishoudenskenmerken   -> average gross, disposable
#                                                                and standardized income
#   85663NED  Cao-lonen, contractuele loonkosten en arbeidsduur -> yearlyWageIncrease


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

# CBS marks yearly periods as e.g. "2024JJ00" (monthly: "2024MM01", quarterly: "2024KW01")
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
    "averagegrossincome",
    "averagedisposableincome",
    "averagestandardizedincome",
    "yearlywageincrease"
]

# Largest absolute value each DECIMAL column can hold, used to fail early with a clear error
column_limits = {
    "cpi": 999.99,                       # DECIMAL(5,2)
    "cpiyearlyrateofchange": 999.9,      # DECIMAL(4,1)
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





# Function to download the yearly CPI and compute its yearly rate of change
def load_cpi() -> pd.DataFrame:
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

    data = get_cbs_data(CPI_TABLE, "TypedDataSet", params={"$filter": YEARLY_PERIOD_FILTER})
    data["year"] = period_to_year(data["Perioden"])
    data = data.set_index("year").sort_index()

    # Newest base first: that is the base CBS currently publishes new figures in
    bases = [base_columns[base] for base in sorted(base_columns, reverse=True)]
    indexes = data[bases].apply(pd.to_numeric, errors="coerce")

    # CHAIN THE BASES: rescale each older base onto the newest one, using the
    # latest year both series have in common, and use it only where newer data is missing
    cpi = indexes[bases[0]].copy()
    for older in bases[1:]:
        overlap = cpi.notna() & indexes[older].notna()
        if not overlap.any():
            raise ValueError(f"CPI column {older} does not overlap with newer bases")
        link_year = overlap[overlap].index.max()
        factor = cpi[link_year] / indexes[older][link_year]
        cpi = cpi.fillna(indexes[older] * factor)

    # YEARLY RATE OF CHANGE: computed within the newest single base that has both
    # this year and last year, so the chaining and rounding above cannot distort it
    # (the previous row is only "last year" when the years are consecutive)
    consecutive = pd.Series(indexes.index, index=indexes.index).diff() == 1
    rates = pd.Series(index=indexes.index, dtype="float64")
    for column in bases:
        change = (indexes[column] / indexes[column].shift(1) - 1) * 100
        rates = rates.fillna(change.where(consecutive))

    return pd.DataFrame({
        "cpi": cpi.round(2),
        "cpiyearlyrateofchange": rates.round(1)
    })



# Function to download yearly average incomes of all private households
def load_income() -> pd.DataFrame:
    properties = get_cbs_data(INCOME_TABLE, "DataProperties")
    average_income_key = get_topic_key(properties, "Gemiddeld inkomen")

    filters = [
        YEARLY_PERIOD_FILTER,
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



# Function to download the yearly increase of collective (cao) wages, whole economy
def load_wage_increase() -> pd.DataFrame:
    properties = get_cbs_data(WAGE_TABLE, "DataProperties")
    wage_key = get_topic_key(
        properties,
        "Cao-lonen per maand incl.bijz.beloningen",
        group="Ontwikkeling t.o.v. een jaar eerder"
    )

    filters = [
        YEARLY_PERIOD_FILTER,
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

    data["year"] = period_to_year(data["Perioden"])
    data["yearlywageincrease"] = pd.to_numeric(data[wage_key], errors="coerce").round(1)
    return data.set_index("year")[["yearlywageincrease"]]



# Function to combine all sources into rows that match the EconomyStatistics table
def load_economy_statistics() -> pd.DataFrame:
    combined = (
        load_cpi()
        .join(load_income(), how="outer")
        .join(load_wage_increase(), how="outer")
        .sort_index()
    )

    # Keep only years with at least one value
    value_columns = final_columns[1:]
    combined = combined.dropna(subset=value_columns, how="all")

    # The table stores a yearly value in a DATE column, represented by 1 January
    combined["date"] = [date(int(year), 1, 1) for year in combined.index]
    return combined.reset_index(drop=True)[final_columns]



# Function to check the quality of the combined data
def check_data_quality(df: pd.DataFrame):
    print("Data Quality Report:")
    print("Total years:", len(df), f"({df['date'].min().year}-{df['date'].max().year})")
    print("Duplicated dates:", df["date"].duplicated().sum())
    for column in final_columns[1:]:
        present = df.loc[df[column].notna(), "date"]
        span = f"{present.min().year}-{present.max().year}" if len(present) else "none"
        print(f"  {column}: {df[column].notna().sum()} values ({span})")

    # Fail before touching the database if a value would not fit its DECIMAL column
    for column, limit in column_limits.items():
        too_large = df[df[column].abs() > limit]
        if not too_large.empty:
            raise ValueError(
                f"{len(too_large)} value(s) in {column} exceed the column limit of {limit}"
            )



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

    # Download, combine and validate the CBS data before connecting to the database
    print("Downloading economy statistics from CBS...")
    economy = load_economy_statistics()
    if economy.empty:
        sys.exit("CBS returned no economy statistics. Import not performed.")
    check_data_quality(economy)

    # NaN is not valid SQL; send missing values as NULL
    records = economy.astype(object).where(economy.notna(), None).to_dict("records")

    # Opening a connection to the PostgreSQL database
    db_conn = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    # Insert or refresh every year in one transaction. CBS revises preliminary figures
    # (e.g. the latest income year), so an existing year is updated instead of skipped.
    upsert = text(f"""
        INSERT INTO economystatistics ({", ".join(final_columns)})
        VALUES ({", ".join(":" + column for column in final_columns)})
        ON CONFLICT (date) DO UPDATE SET
            {", ".join(f"{column} = EXCLUDED.{column}" for column in final_columns[1:])}
    """)

    with db_conn.begin() as conn:
        conn.execute(upsert, records)

    print(f"{len(records)} years of economy statistics inserted or updated successfully.")
