
# Importing necessary libraries
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from pathlib import Path
import os


# Get the project root directory from this script
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Folder containing the data
DATA_DIR = PROJECT_DIR / "data" / "raw" # or processed

# List of supermarkets
supermarkets = ["AH", "Jumbo", "Lidl", "Plus"]

# Reading the official data
# yet to-do


# Making the structure with a test invented dataset
df_test = pd.DataFrame({
    "product_id": [1, 2, 3],
    "product_name": ["Milk", "Bread", "Eggs"],
    "price": [1.50, 2.20, 3.00]
})


# Read database connection settings
db_host = os.environ["DB_HOST"]
db_name = os.environ["DB_NAME"]
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




