#************************************************************************************
#------------------------------- STATIC DATA LOADER---------------------------------*
#************************************************************************************


# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from pathlib import Path
import os
from dotenv import load_dotenv
import openpyxl



# Get the project root directory from this script
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Folder containing the data
INPUT_DATA_DIR = PROJECT_DIR / "data" / "raw" 

# Folder containing the cleaned and processed data
OUTPUT_DATA_DIR = PROJECT_DIR / "data" / "processed" 

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



# Function to read the csv files in chunks
def reader_supermarket(supermarket: str, chunksize: int = 250):
    # Return an iterator that reads the CSV chunk by chunk
    return pd.read_csv(INPUT_DATA_DIR / f"{supermarket}.csv", chunksize=chunksize) 



# Function to transform the supermarket dataset
def transform_supermarket(supermarket: str, df: pd.DataFrame) -> pd.DataFrame:

    # Identifying all the date columns using regex (DYYYY_MM_DD)
    date_columns = df.filter(regex = r"^D\d{4}_\d{2}_\d{2}$").columns.tolist()

    # Getting the supermarket mapping columns dictionary
    mappings = column_mappings[supermarket]

    # Selecting the original columns that exist in AH file
    original_columns = [col for col in mappings.values()]

    # Handle Lidl' need of cat2
    if supermarket == "Lidl":
        original_columns = original_columns + ["cat2"]

    # Filtering the df to keep only necessary columns and dates
    df = df[original_columns + date_columns]

    # Renaming the original columns to the final names
    df = df.rename(columns = {original:final for final, original in mappings.items()})

    # Handle Lidl's two category columns
    if supermarket == "Lidl":
        df["Product_Category"] = (df["Product_Category"].fillna("").astype(str).str.strip()
                                + " &&& " +
                                df["cat2"].fillna("").astype(str).str.strip()
                                ).str.strip()
        
    # Transform datecolumns into rows
    df_long = pd.melt(df, id_vars = [col for col, original in mappings.items()],
                  value_vars = date_columns,
                   var_name = "Date",
                    value_name = "Price")

    # Adding supermarket information
    df_long["Supermarket"] = supermarket
    df_long["Supermarket_ID"] = supermarket_ids[supermarket]

    # Ordering the columns according to the final column ordering list
    df_long = df_long[final_columns]

    return df_long



# Function that receives a properly formatted datachunk and applies preprocessing and cleaning steps to it
def preprocess_supermarket(df_long: pd.DataFrame) -> pd.DataFrame:

    # Make a copy to avoid modifying the original dataframe
    df_clean = df_long.copy()

    # Convert prices to numeric values (unconvertable values become NaN)
    df_clean["Price"] = pd.to_numeric(df_clean["Price"], errors = "coerce")

    # Convert the current date string values ("DYYYY_MM_DD") to datetime values
    df_clean["Date"] = pd.to_datetime(df_clean["Date"], format = "D%Y_%m_%d", errors = "coerce")

    # Remove rows that contain missing values either in Price or Date columns
    df_clean = df_clean.dropna(subset = ["Date", "Price"])

    # Remove rows that contain negative price values
    df_clean = df_clean[df_clean["Price"] >= 0]
    
    return df_clean





# Testing the reading and transformation of supermarket data
for supermarket in supermarkets:

    print(f"\nSupermarket: {supermarket}")

    # Read the CSV in chunks
    for chunk_number, datachunk in enumerate(reader_supermarket(supermarket, chunksize=250), start=1):

        # Transform the current chunk into long format
        df_long = transform_supermarket(supermarket, datachunk)

        # Apply preprocessing and cleaning
        df_clean = preprocess_supermarket(df_long)

        # Check how many rows were removed during preprocessing
        removed_rows = len(df_long) - len(df_clean)

        print(f"\nChunk {chunk_number}:")
        print(f"Original CSV: {datachunk.shape}")
        print(f"Long format: {df_long.shape}")
        print(f"After cleaning: {df_clean.shape}")
        print(f"Removed rows: {removed_rows}")
        print(df_clean.head(3))

        # Only test the first two chunks of each supermarket
        if chunk_number == 2:
            break


    
# Stop the script here when running for testing ---------------------------------------------------------------------
import sys 
sys.exit()



# Testing the transformation for all supermarkets
output_file = PROJECT_DIR / "code" / "importer" / "static" / "output_test.xlsx"
with pd.ExcelWriter(output_file, engine = "openpyxl") as writer:
    for supermarket in supermarkets:
        df_long = transform_supermarket(supermarket, nrows = 5)
        df_long.to_excel(writer, sheet_name = supermarket, index = False)

print("Excel file created")

#--------------------------------------------------------------





# Making the structure with a test invented dataset
df_test = pd.DataFrame({
    "product_id": [1, 2, 3],
    "product_name": ["Milk", "Bread", "Eggs"],
    "price": [1.50, 2.20, 3.00]
})


# This command reads the .env file and loads the variables into the python environment
load_dotenv(PROJECT_DIR / ".env")

# Read database connection settings
db_host = "localhost" # os.environ["DB_HOST"]
db_name = os.environ["DB_NAME"] # this command allows python to access env variables that are loaded
db_user = os.environ["DB_USER"]
db_password = os.environ["DB_PASSWORD"]



# Opening a connection to the PostgreSQL database
db_conn = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}")


# Creating a test table and inserting the data-frame
df_test.to_sql("test_products", db_conn, if_exists="replace", index=False)

print("Data loaded successfully!")

# Read the table into a pandas data-frame
mytable = pd.read_sql("SELECT * FROM test_products;", db_conn)
print(mytable)