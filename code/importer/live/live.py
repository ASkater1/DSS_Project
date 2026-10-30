#************************************************************************************
#------------------------------- STATIC DATA LOADER---------------------------------*
#************************************************************************************


# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import text





# Get the project root directory from this script (using environment variable so inside docker it will be able to get the route)
PROJECT_DIR = Path(__file__).resolve()
# List of supermarkets
supermarkets = ["AH", "Jumbo", "Lidl", "Plus"]

# Final table columns
final_columns = ["Supermarket", "Supermarket_ID", "Product_Category", "Product_Name", "Product_ID", "Brand_Product", "Quantity_Value_Product", "Quantity_Unit_Product", "Date", "Price"]

# Dictionary that maps each column of the raw datasets to the final columns
column_mappings = {
    "AH": {"Product_ID": "prod_id",
           "Product_Name": "prod_desc",
           "Product_Category": "cat",
           "Brand_Product": "supplier",
           "Quantity_Value_Product": "quantity_value",
           "Quantity_Unit_Product": "quantity_unit"
           },

    "Jumbo": {"Product_ID": "prod_id",
           "Product_Name": "prod_desc",
           "Product_Category": "cat",
           "Brand_Product": "supplier",
           "Quantity_Value_Product": "quantity_value",
           "Quantity_Unit_Product": "quantity_unit"
           },

    "Lidl": {"Product_ID": "prod_id",
           "Product_Name": "prod_desc",
           "Product_Category": "cat1", # can incorporate cat2 in the code later
           "Brand_Product": "supplier",
           "Quantity_Value_Product": "quantity_value",
           "Quantity_Unit_Product": "quantity_unit"
           },

    "Plus": {"Product_ID": "prod_id",
           "Product_Name": "prod_desc",
           "Product_Category": "cat",
           "Brand_Product": "supplier",
           "Quantity_Value_Product": "quantity_value",
           "Quantity_Unit_Product": "quantity_unit"
           }
}

# Dictionary that assigns a unique ID to each Supermarket
supermarket_ids = {"AH": 1, "Jumbo": 2, "Lidl": 3, "Plus": 4}






# Main execution
if __name__ == "__main__":

    # Reading the .env file and loading the variables into the python environment
    load_dotenv(PROJECT_DIR / ".env")

    # Read database connection settings
    db_host = os.environ["DB_HOST"] if "DB_HOST" in os.environ else exit("DB_HOST environment variable not set. Please set it in the .env file.")
    db_name = os.environ["DB_NAME"] if "DB_NAME" in os.environ else exit("DB_NAME environment variable not set. Please set it in the .env file.")
    db_user = os.environ["DB_USER"] if "DB_USER" in os.environ else exit("DB_USER environment variable not set. Please set it in the .env file.")
    db_password = os.environ["DB_PASSWORD"] if "DB_PASSWORD" in os.environ else exit("DB_PASSWORD environment variable not set. Please set it in the .env file.")
    print(f"DB login information: postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}")
    exit


    # Opening a connection to the PostgreSQL database 
    #db_conn = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}")