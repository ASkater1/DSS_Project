#************************************************************************************
#------------------------- MUNICIPALITY STATIC DATA LOADER--------------------------*
#************************************************************************************


# Importing necessary libraries
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text





# Get the project root directory from this script (inside Docker this resolves to /project)
PROJECT_DIR = Path(__file__).resolve().parents[3]

# CBS Open Data API configuration
CBS_BASE_URL = "https://opendata.cbs.nl/ODataApi/OData"
YEAR = 2025

# Parameter to define the amount of instances to insert at a time into the SQL table
inserting_chunksize = 5000

# Final columns returned by the CBS data-loading functions
final_columns = [
    "MunicipalityID",
    "Name",
    "Population",
    "Year",
    "DistanceClosestSupermarket",
    "SupermarketsWithin1KM",
    "SupermarketsWithin3KM",
    "SupermarketsWithin5KM"
]





# Function to download all pages of an endpoint from the CBS OData API
def get_cbs_data(table: str, endpoint: str, params: dict | None = None) -> pd.DataFrame:
    url = f"{CBS_BASE_URL}/{table}/{endpoint}"
    if params:
        url = f"{url}?{urlencode(params)}"

    all_rows = []

    while url:
        with urlopen(url, timeout=60) as response:
            result = json.load(response)

        all_rows.extend(result.get("value", []))
        url = result.get("odata.nextLink") or result.get("@odata.nextLink")

    return pd.DataFrame(all_rows)



# Function to find the CBS key that belongs to a category title
def get_category_key(df: pd.DataFrame, title: str):
    matches = df[
        df["Title"].astype(str).str.strip().str.casefold()
        == title.strip().casefold()
    ]

    if matches.empty:
        raise ValueError(f"CBS category not found: {title}")

    return matches.iloc[0]["Key"]



# Function to find the CBS period key for the requested year
def get_period_key(table: str, year: int):
    periods = get_cbs_data(table, "Perioden")

    matches = periods[
        periods["Title"].astype(str).str.strip().str.startswith(str(year))
    ]

    if matches.empty:
        raise ValueError(f"No data period for {year} in CBS table {table}")

    return matches.iloc[0]["Key"]



# Function to download and combine municipality accessibility and population data
def load_municipalities(year: int = YEAR) -> pd.DataFrame:

    # SUPERMARKET ACCESSIBILITY
    accessibility_table = "80305ned"

    properties = get_cbs_data(
        accessibility_table, "DataProperties"
    ).reset_index(drop=True)
    titles = properties["Title"].fillna("").astype(str).str.strip()

    # Find the distance to the closest large supermarket field
    distance_rows = properties[titles == "Afstand tot grote supermarkt"]
    if distance_rows.empty:
        raise ValueError("Supermarket distance field not found in CBS metadata")
    distance_key = distance_rows.iloc[0]["Key"]

    # Find the 1, 3 and 5 kilometre fields below the supermarket-count group
    group_indexes = properties.index[titles == "Aantal grote supermarkten"]
    if len(group_indexes) == 0:
        raise ValueError("Supermarket count group not found in CBS metadata")

    group_index = group_indexes[0]
    bands = properties.iloc[group_index + 1:group_index + 4]
    expected_bands = {
        "Binnen 1 km": "SupermarketsWithin1KM",
        "Binnen 3 km": "SupermarketsWithin3KM",
        "Binnen 5 km": "SupermarketsWithin5KM"
    }

    band_columns = {}
    for _, row in bands.iterrows():
        title = str(row["Title"]).strip()
        if title in expected_bands:
            band_columns[row["Key"]] = expected_bands[title]

    if len(band_columns) != 3:
        raise ValueError(
            "Could not identify the 1, 3 and 5 km supermarket fields in CBS metadata"
        )

    accessibility_columns = {
        distance_key: "DistanceClosestSupermarket",
        **band_columns
    }
    accessibility_period = get_period_key(accessibility_table, year)

    accessibility_data = get_cbs_data(
        accessibility_table,
        "TypedDataSet",
        params={
            "$filter": f"Perioden eq '{accessibility_period}'",
            "$select": ",".join(["RegioS", *accessibility_columns.keys()]),
            "$top": 10000
        }
    )
    accessibility_data = accessibility_data[
        accessibility_data["RegioS"].str.startswith("GM", na=False)
    ].copy()
    accessibility_data = accessibility_data.rename(columns=accessibility_columns)

    # POPULATION
    population_table = "03759ned"
    population_properties = get_cbs_data(population_table, "DataProperties")
    population_key = get_category_key(
        population_properties, "Bevolking op 1 januari"
    )
    population_period = get_period_key(population_table, year)

    dimensions = {
        "Geslacht": "Totaal mannen en vrouwen",
        "Leeftijd": "Totaal",
        "BurgerlijkeStaat": "Totaal burgerlijke staat"
    }
    population_filters = [f"Perioden eq '{population_period}'"]

    for dimension, title in dimensions.items():
        categories = get_cbs_data(population_table, dimension)
        category_key = get_category_key(categories, title)
        population_filters.append(f"{dimension} eq '{category_key}'")

    population_data = get_cbs_data(
        population_table,
        "TypedDataSet",
        params={
            "$filter": " and ".join(population_filters),
            "$select": f"RegioS,{population_key}",
            "$top": 10000
        }
    )
    population_data = population_data[
        population_data["RegioS"].str.startswith("GM", na=False)
    ].copy()
    population_data = population_data.rename(columns={population_key: "Population"})

    # MUNICIPALITY NAMES
    regions = get_cbs_data(accessibility_table, "RegioS")
    regions = regions[
        regions["Key"].str.startswith("GM", na=False)
    ][["Key", "Title"]].copy()
    regions = regions.rename(columns={"Key": "RegioS", "Title": "Name"})

    # COMBINE THE DATA
    municipalities = accessibility_data.merge(
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
        municipalities["RegioS"].str.replace("GM", "", regex=False).astype(int)
    )
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
            "Beek (L)": "Beek"
        })
    )
    municipalities["Year"] = year
    municipalities = municipalities[final_columns].copy()

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

    return municipalities.sort_values("Name").reset_index(drop=True)



# Function to check the quality of the combined municipality data
def check_data_quality(municipalities: pd.DataFrame):
    print("Data Quality Report:")
    print("Total municipalities:", len(municipalities))
    print("Duplicated municipality IDs:", municipalities["MunicipalityID"].duplicated().sum())
    print("Missing municipality names:", municipalities["Name"].isna().sum())
    print("Missing population values:", municipalities["Population"].isna().sum())
    print(
        "Missing supermarket accessibility values:",
        municipalities[
            [
                "DistanceClosestSupermarket",
                "SupermarketsWithin1KM",
                "SupermarketsWithin3KM",
                "SupermarketsWithin5KM"
            ]
        ].isna().any(axis=1).sum()
    )



# Function to prepare the DataFrame so its columns and values match the database table
def prepare_database_table(municipalities: pd.DataFrame) -> pd.DataFrame:
    df_municipalities = municipalities.dropna(
        subset=["MunicipalityID", "Name"]
    ).copy()
    df_municipalities = df_municipalities.drop_duplicates(
        subset=["MunicipalityID"]
    )

    # The database stores an annual value in a DATE column, represented by 1 January
    df_municipalities["Year"] = pd.to_datetime(
        df_municipalities["Year"].astype(str) + "-01-01",
        errors="coerce"
    ).dt.date
    df_municipalities = df_municipalities.dropna(subset=["Year"])

    df_municipalities = df_municipalities.rename(columns={
        "MunicipalityID": "municipalityid",
        "Name": "name",
        "Population": "population",
        "Year": "year",
        "DistanceClosestSupermarket": "distanceclosestsupermarket",
        "SupermarketsWithin1KM": "supermarketswithin1km",
        "SupermarketsWithin3KM": "supermarketswithin3km",
        "SupermarketsWithin5KM": "supermarketswithin5km"
    })

    return df_municipalities[
        [
            "municipalityid",
            "name",
            "population",
            "year",
            "distanceclosestsupermarket",
            "supermarketswithin1km",
            "supermarketswithin3km",
            "supermarketswithin5km"
        ]
    ]





# Main execution
if __name__ == "__main__":

    # Reading the .env file and loading the variables into the Python environment
    load_dotenv(PROJECT_DIR / ".env")

    # Read database connection settings
    db_host = os.environ["DB_HOST"] if "DB_HOST" in os.environ else exit("DB_HOST environment variable not set. Please set it in the .env file.")
    db_name = os.environ["DB_NAME"] if "DB_NAME" in os.environ else exit("DB_NAME environment variable not set. Please set it in the .env file.")
    db_user = os.environ["DB_USER"] if "DB_USER" in os.environ else exit("DB_USER environment variable not set. Please set it in the .env file.")
    db_password = os.environ["DB_PASSWORD"] if "DB_PASSWORD" in os.environ else exit("DB_PASSWORD environment variable not set. Please set it in the .env file.")
    year = int(os.environ.get("MUNICIPALITIES_IMPORTER_YEAR", YEAR))
    inserting_chunksize = int(os.environ.get("STATIC_IMPORTER_INSERTING_CHUNKSIZE", inserting_chunksize))

    print(
        f"Loading CBS municipality data for {year} and using an inserting_chunksize "
        f"of {inserting_chunksize}."
    )

    # Opening a connection to the PostgreSQL database
    db_conn = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    )

    # SECURITY CHECK! Prevent running the importer twice and creating duplicate data
    with db_conn.connect() as conn:
        print("Checking if static municipality data is already loaded in the database...")
        result = conn.execute(text("SELECT COUNT(*) FROM municipalities"))
        if result.scalar() > 0:
            print("[WARNING] Static municipality data already loaded. Import not performed.")
            exit()
        else:
            print("Static municipality data not found in the database. Proceeding with import...")

    # Download, combine and validate the CBS data
    municipalities = load_municipalities(year)
    if municipalities.empty:
        exit("CBS returned no municipality data. Import not performed.")

    check_data_quality(municipalities)
    df_municipalities = prepare_database_table(municipalities)

    # Insert all municipality data in one database transaction
    with db_conn.begin() as conn:
        df_municipalities.to_sql(
            name="municipalities",
            con=conn,
            if_exists="append",
            index=False,
            chunksize=inserting_chunksize
        )

    print(f"{len(df_municipalities)} municipalities inserted successfully.")
