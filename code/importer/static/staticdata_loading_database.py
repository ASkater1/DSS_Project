#************************************************************************************
#------------------------------- STATIC DATA LOADER---------------------------------*
#************************************************************************************


# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
import os
from dotenv import load_dotenv





# Get the project root directory from this script
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Folder containing the data
INPUT_DATA_DIR = PROJECT_DIR / "data" / "raw" 

# Folder containing the cleaned and processed data
OUTPUT_DATA_DIR = PROJECT_DIR / "data" / "processed" 

# Name of the table where to insert the data in the PostgreSQL Database
table_name = "name_of_the_table"  # still need to put the final name whenever is created

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





# Main execution
if __name__ == "__main__":

    # # Reading the .env file and loading the variables into the python environment
    # load_dotenv(PROJECT_DIR / ".env")

    # # Read database connection settings
    # db_host = os.environ["DB_HOST"] # "localhost"  
    # db_name = os.environ["DB_NAME"] # this command allows python to access env variables that are loaded
    # db_user = os.environ["DB_USER"]
    # db_password = os.environ["DB_PASSWORD"]

    # # Opening a connection to the PostgreSQL database 
    # db_conn = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/{db_name}")

    # # Clear the existing static data before starting a new load
    # with db_conn.begin() as conn:
    #     conn.exec_driver_sql(f"TRUNCATE TABLE {table_name};")

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

            # Inserting the cleaned dataframes to the PostgreSQL table
            # df_clean.to_sql(name = table_name, con = db_conn, if_exists = "append", index = False, chunksize = inserting_chunksize)


            # Only test the first two chunks of each supermarket
            if chunk_number == 2:
                break


# To make quick test: Read the table into a pandas data-frame
# mytable = pd.read_sql(f"SELECT * FROM {table_name};", db_conn)
# print(mytable)