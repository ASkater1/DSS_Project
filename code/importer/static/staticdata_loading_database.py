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
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Folder containing the data
INPUT_DATA_DIR = PROJECT_DIR / "data" / "raw" 

# Folder containing the cleaned and processed data
OUTPUT_DATA_DIR = PROJECT_DIR / "data" / "processed" 


# Parameter to define the amount of instances to divide the processing of the dataframes
chunksize = 250

# Parameter to define the amount of instances to insert at a time into the SQL tables
inserting_chunksize = 5000

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
    print(f"Reading {supermarket}.CSV data in chunks of {chunksize} rows...")
    # Return an iterator that reads the CSV chunk by chunk
    return pd.read_csv(INPUT_DATA_DIR / f"{supermarket}.csv", chunksize=chunksize, dtype = {"prod_id": str}) 



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



# Function to check the quality of the cleaned supermarket data
def check_data_quality(df_clean: pd.DataFrame):

    # Counting of suspicious price values
    zero_prices = (df_clean["Price"] == 0).sum()
    prices_999 = (df_clean["Price"] == 999).sum()

    # Counting of missing product information
    missing_ids = df_clean["Product_ID"].isna().sum()
    missing_names = df_clean["Product_Name"].isna().sum()

    # Counting of duplicated product-date combinations
    duplicates = df_clean.duplicated(subset=["Supermarket_ID", "Product_ID", "Date"]).sum()

    # Printing the results
    print("Data Quality Report:")
    print("Total rows:", len(df_clean))
    print("Prices equal to 0:", zero_prices)
    print("Prices equal to 999:", prices_999)
    print("Missing Product IDs:", missing_ids)
    print("Missing Product Names:", missing_names)
    print("Duplicated product-date combinations:", duplicates)



# Function to prepare the three DataFrames matching the database tables
def prepare_database_tables(df_clean: pd.DataFrame):

    # Keeping only rows with the mandatory product information.
    df = df_clean.dropna(subset = ["Product_ID", "Product_Name", "Brand_Product", "Product_Category"]).copy()

    # Original supermarket IDs may contain letters or numbers: keep them as text.
    df["Product_ID"] = df["Product_ID"].astype(str).str.strip()
    df = df[df["Product_ID"] != ""]

    # SUPERMARKET 
    # Keeping the unique registers of supermarkets
    df_supermarkets = df[["Supermarket_ID", "Supermarket"]].drop_duplicates().rename(
        columns={"Supermarket_ID": "supermarketid", "Supermarket": "name"}
    )
    # Creating the marketshare feature (marketshare is not available in the CSV)
    df_supermarkets["marketshare"] = None


    # PRODUCTS
    # Keeping the unique registers of products
    df_products = df[["Product_ID", "Product_Name", "Brand_Product", "Product_Category"]].drop_duplicates(
        subset=["Product_ID"]
    ).rename(columns={
        "Product_ID": "productid",
        "Product_Name": "name",
        "Brand_Product": "brand",
        "Product_Category": "category"
    })
    df_products["isbasketproduct"] = None
    df_products["description"] = None
    df_products = df_products[["productid", "name", "isbasketproduct", "brand", "category", "description"]]


    # PRICES
    df_prices = df[["Supermarket_ID", "Product_ID", "Date", "Price"]].rename(columns={
        "Supermarket_ID": "supermarketid",
        "Product_ID": "productid",
        "Date": "date",
        "Price": "price"
    })
    df_prices = df_prices.drop_duplicates(subset=["supermarketid", "productid", "date"])
    df_prices["date"] = df_prices["date"].dt.date

    return df_supermarkets, df_products, df_prices






# Main execution
if __name__ == "__main__":

    # Reading the .env file and loading the variables into the python environment
    load_dotenv(PROJECT_DIR / ".env")

    # Read database connection settings
    db_host = os.environ["DB_HOST"] if "DB_HOST" in os.environ else exit("DB_HOST environment variable not set. Please set it in the .env file.")
    db_name = os.environ["DB_NAME"] if "DB_NAME" in os.environ else exit("DB_NAME environment variable not set. Please set it in the .env file.")
    db_user = os.environ["DB_USER"] if "DB_USER" in os.environ else exit("DB_USER environment variable not set. Please set it in the .env file.")
    db_password = os.environ["DB_PASSWORD"] if "DB_PASSWORD" in os.environ else exit("DB_PASSWORD environment variable not set. Please set it in the .env file.")
    chunksize = int(os.environ["STATIC_IMPORTER_CHUNKSIZE_INTERNAL"]) if "STATIC_IMPORTER_CHUNKSIZE_INTERNAL" in os.environ else chunksize
    inserting_chunksize = int(os.environ["STATIC_IMPORTER_INSERTING_CHUNKSIZE"]) if "STATIC_IMPORTER_INSERTING_CHUNKSIZE" in os.environ else inserting_chunksize
    print(f"Using chunksize of {chunksize} for reading CSVs and inserting_chunksize of {inserting_chunksize} for inserting into the database.")



    # Opening a connection to the PostgreSQL database 
    db_conn = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}")

    # SECURITY CHECK! Prevent running the static importer twice, to avoid creating duplicate data imports in the database
    with db_conn.connect() as conn:
        print("Checking if static supermarket data is already loaded in the database...")
        result = conn.execute(text("SELECT COUNT(*) FROM supermarkets"))
        if result.scalar() > 0:
            print("[WARNING] Static supermarket data already loaded. Import not performed.")
            exit()
        else:
            print("Static supermarket data not found in the database. Proceeding with import...")
    
    # Remembering product IDs inserted during this execution (to keep track of unique products for the product table)
    inserted_product_ids = set()
    

    # Testing the reading and transformation of supermarket data
    for supermarket in supermarkets:
        
        print(f"\nSupermarket: {supermarket}")

        # Read the CSV in chunks
        for chunk_number, datachunk in enumerate(reader_supermarket(supermarket, chunksize), start=1):

            # Transform the current chunk into long format
            df_long = transform_supermarket(supermarket, datachunk)

            # Apply preprocessing and cleaning
            df_clean = preprocess_supermarket(df_long)
            
            # Optional: get an idea of the data-quality of the df (comment if not wanted)
            check_data_quality(df_clean)

            
            # Prepare separate DataFrames for the three database tables.
            df_supermarkets, df_products, df_prices = prepare_database_tables(df_clean)

            # Keep only products that have not been inserted yet
            df_products = df_products[~df_products["productid"].isin(inserted_product_ids)]

            # Inserting all data for the current chunk in one transaction
            with db_conn.begin() as conn:
            
                # Insert supermarket data to supermarket table only in the first chunk of each supermarket
                if chunk_number == 1:
                    df_supermarkets.to_sql(
                        name="supermarkets",
                        con=conn,
                        if_exists="append",
                        index=False
                    )

            

                df_products.to_sql(
                    name="products",
                    con=conn,
                    if_exists="append",
                    index=False,
                    chunksize=inserting_chunksize
                )

                df_prices.to_sql(
                    name="supermarketsproducts",
                    con=conn,
                    if_exists="append",
                    index=False,
                    chunksize=inserting_chunksize
                )

            # Update the set to keep track of unique products after successful insertion
            inserted_product_ids.update(df_products["productid"])

            print(f"Chunk {chunk_number} inserted successfully.")

            # # Only test the first two chunks of each supermarket
            # if chunk_number == 2:
            #     break