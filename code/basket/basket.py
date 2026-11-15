# ************************************************************************************
# ------------------------------- STATIC DATA LOADER---------------------------------*
# ************************************************************************************


# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import text
import csv

# Get the project root directory from this script (using environment variable so inside docker it will be able to get the route)
PROJECT_DIR = Path(__file__).resolve()
# List of supermarkets
supermarkets = ["AH", "Jumbo", "Lidl", "Plus"]

# Final table columns
final_columns = [
    "Supermarket",
    "Supermarket_ID",
    "Product_Category",
    "Product_Name",
    "Product_ID",
    "Brand_Product",
    "Quantity_Value_Product",
    "Quantity_Unit_Product",
    "Date",
    "Price",
]

# Dictionary that maps each column of the raw datasets to the final columns
column_mappings = {
    "AH": {
        "Product_ID": "prod_id",
        "Product_Name": "prod_desc",
        "Product_Category": "cat",
        "Brand_Product": "supplier",
        "Quantity_Value_Product": "quantity_value",
        "Quantity_Unit_Product": "quantity_unit",
    },
    "Jumbo": {
        "Product_ID": "prod_id",
        "Product_Name": "prod_desc",
        "Product_Category": "cat",
        "Brand_Product": "supplier",
        "Quantity_Value_Product": "quantity_value",
        "Quantity_Unit_Product": "quantity_unit",
    },
    "Lidl": {
        "Product_ID": "prod_id",
        "Product_Name": "prod_desc",
        "Product_Category": "cat1",  # can incorporate cat2 in the code later
        "Brand_Product": "supplier",
        "Quantity_Value_Product": "quantity_value",
        "Quantity_Unit_Product": "quantity_unit",
    },
    "Plus": {
        "Product_ID": "prod_id",
        "Product_Name": "prod_desc",
        "Product_Category": "cat",
        "Brand_Product": "supplier",
        "Quantity_Value_Product": "quantity_value",
        "Quantity_Unit_Product": "quantity_unit",
    },
}

# Dictionary that assigns a unique ID to each Supermarket
supermarket_ids = {"AH": 1, "Jumbo": 2, "Lidl": 3, "Plus": 4}

# basket criteria currently based on: https://www.cbs.nl/nl-nl/longread/diversen/2026/de-ecoicopv2-indeling/010000-voedingsmiddelen-en-alcoholvrije-dranken

RULES_DIR = Path(__file__).resolve().parent

cpi_basket_rules = {}

# read the criteria for a basket items from cpu_basket_rules.csv
with open(RULES_DIR / "cpi_basket_rules.csv", newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        cpi_basket_rules[row["code"]] = {
            "name": row["name"],
            "category": row["category"],
            "include": row["include"].split("|"),
            "exclude": row["exclude"].split("|") if row["exclude"] else [],
            "quantity": float(row["quantity"]) if row["quantity"] else None,
            "unit": row["unit"].strip().lower(),
        }

print(f"Loaded {len(cpi_basket_rules)} CPI basket rules")
print(f"Categories: {set(rule['category'] for rule in cpi_basket_rules.values())}")

# Main execution
if __name__ == "__main__":

    # Reading the .env file and loading the variables into the python environment
    load_dotenv(PROJECT_DIR / ".env")

    # Read database connection settings
    db_host = (
        os.environ["DB_HOST"]
        if "DB_HOST" in os.environ
        else exit(
            "DB_HOST environment variable not set. Please set it in the .env file."
        )
    )
    db_name = (
        os.environ["DB_NAME"]
        if "DB_NAME" in os.environ
        else exit(
            "DB_NAME environment variable not set. Please set it in the .env file."
        )
    )
    db_user = (
        os.environ["DB_USER"]
        if "DB_USER" in os.environ
        else exit(
            "DB_USER environment variable not set. Please set it in the .env file."
        )
    )
    db_password = (
        os.environ["DB_PASSWORD"]
        if "DB_PASSWORD" in os.environ
        else exit(
            "DB_PASSWORD environment variable not set. Please set it in the .env file."
        )
    )
    print(
        f"DB login information: postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    )

    # exit

    # Opening a connection to the PostgreSQL database
    db_conn = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    )

    with db_conn.begin() as conn:
        products = (
            conn.execute(
                text(
                    """SELECT p.productid, p.name, c.name AS shared_category, p.quantity_value, p.quantity_units
            FROM products p
            JOIN categories c ON p.categoryid = c.categoryid"""
                )
            )
            .mappings()
            .all()
        )
        selected_products = {} # create a dictionary for the products that will be in the basket.

        for product in products:
            name = product["name"].lower()

            for code, rule in cpi_basket_rules.items():

                if product["shared_category"] != rule["category"]:
                    continue

                if not any(word in name for word in rule["include"]):
                    continue

                if any(word in name for word in rule["exclude"]):
                    continue

                selected_products[product["productid"]] = code
                break
        
        
        for product_id, code in selected_products.items():
            conn.execute(
                text("""
                UPDATE products
                SET isbasketproduct = TRUE,
                    basketcode = :code
                WHERE productid = :product_id
            """),
                {"code": code, "product_id": product_id},
            )


    # print(f"Basket products selected: {selected_ids.scalar()}")
    print(f"Basket products selected: {len(selected_products)}")
