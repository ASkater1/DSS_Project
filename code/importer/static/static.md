# Static Data Loader

## Description
This script is responsible for reading, processing and loading the static product price data from four dutch supermarkets: Albert Heijn, Jumbo, Lidl and Plus, into a PostgreSQL database table.

The script reads the original CSV files in chunks to avoid loading the entire datasets into memory. Each chunk is then transformed into the required database table format, preprocessed and cleaned, and inserted into a PostgreSQL table.


## Expected Input Files & Variables
The script expects the following CSV files to be located in the directory: data/raw :
* AH.csv
* Jumbo.csv
* Lidl.csv
* Plus.csv

The script also has variables that need to be properly defined beforehand:
* table_name: Name of the target PostgreSQL table where the cleaned data will be inserted.
* chunksize: Number of product rows read from each CSV file at a time, allowing the datasets to be processed incrementally, since the number of rows per each product is multiplied by the total date columns existing in each file. 
* inserting_chunksize: Maximum number of cleaned records inserted into the PostgreSQL per insertion iteration.

## Dependencies
The required Python packages are listed in code/importer/static/requirements.txt .
They can be installed from the project root using:


python -m pip install -r code/importer/static/requirements.txt


## Expected environment variables:
The PostgreSQL database connection settings are loaded from a .env file located in the project root. The expected database connection environment variables are the following:
* DB_HOST: PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password.

**Note**: The current script uses localhost as the database host. The connection settings may need to be adjusted depending on the execution environment.


**Note**: The current script has the database connection parts commented since the PostgreSQL database table is not yet created. 

_The table to store this static data will need to have the same columns as the ones defined in the variable: final_columns_

_Each time the loader is executed will remove all the existing data in the PostgreSQL 
table and load again the data, to avoid loading duplicate records each time is executed_


## Code Structure
The script is organized into four main sections:
* Imports: imports the Python necessary libraries.
* Configuration: defines settings, directories, mappings, parameter variables...
* Functions: defines the functions used in the whole pipeline of this loading: reading the data, transforming the data, processing the data.
* Main execution: coordinates the whole pipeline, so for each supermarket applies the defined functions and inserts the cleaned records into the PostgreSQL table.

**Note**: The script processes only the first two chunks of each supermarket for testing purposes. The testing limit must be removed before running the complete data load.

## Running the Sript
From the project root, execute in terminal the following command:


python code/importer/static/staticdata_loading_database.py

