
# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from pathlib import Path
import os
from dotenv import load_dotenv



# Get the project root directory from this script
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Folder containing the data
INPUT_DATA_DIR = PROJECT_DIR / "data" / "raw" 

# Folder containing the cleaned and processed data
OUTPUT_DATA_DIR = PROJECT_DIR / "data" / "processed" 

# List of supermarkets
supermarkets = ["AH", "Jumbo", "Lidl", "Plus"]

# Reading the official data
for supermarket in supermarkets:
    df = pd.read_csv(INPUT_DATA_DIR / f"{supermarket}.csv")
    print(f"Supermarket: {supermarket}")
    print("Number of columns: ", len(df.columns))
    #print("Column names: ", df.columns.tolist())

    #df.to_csv(OUTPUT_DATA_DIR / f"{supermarket}_processed.csv")


# Stop the script here for testing ---------------------------------------------------------------------
import sys
sys.exit()




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
# create_engine("postgresql+psycopg2://myuser:mypassword@localhost:5432/mydatabase")

# Other option to do it:
# db_url = URL.create(
#     "postgresql+psycopg2",
#     username=db_user,
#     password=db_password,
#     host=db_host,
#     port=5432,
#     database=db_name
# )


# Creating a test table and inserting the data-frame
df_test.to_sql(
    "test_products",
    db_conn,
    if_exists="replace",
    index=False
)

print("Data loaded successfully!")


# Read the table into a pandas data-frame
mytable = pd.read_sql("SELECT * FROM test_products;", db_conn)
print(mytable)




