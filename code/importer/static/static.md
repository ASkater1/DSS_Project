# Static Data Loader


## Description
This script is responsible for reading, processing and loading the static product price data from four dutch supermarkets: Albert Heijn, Jumbo, Lidl and Plus, into a PostgreSQL database table.

The script reads the original CSV files in chunks to avoid loading the entire datasets into memory. Each chunk is then transformed into a common format, preprocessed and cleaned, and prepared for insertion into three related PostgreSQL database tables:
· Supermarkets: Table that stores the supermarket IDs, names, and market shares.

· Products: Stores product information, including product IDs, names, brands, and categories. Also product amounts with the fields value and units of measure.

· SupermarketsProducts: Stores historical product prices, linking each product to a supermarket and a date.

This database tables are created beforehand using data/db/initdb.sql.

To reduce unnecessary storage, the importer only stores the first available price and subsequent price changes for each product within each supermarket, instead of storing repeated daily prices when the price remains unchanged for different dates.


## Expected Input Files & Variables
The script expects the following CSV files to be located in the directory: data/raw :
* AH.csv
* Jumbo.csv
* Lidl.csv
* Plus.csv

The script also has variables that can be adapted beforehand:
* chunksize: Number of product rows read from each CSV file at a time, allowing the datasets to be processed incrementally, since the number of rows per each product is multiplied by the total date columns existing in each file. 
* inserting_chunksize: Maximum number of cleaned records inserted into the PostgreSQL per insertion iteration.

The default values are 250 and 5000 respectively. Both can be overridden through environment variables.


## Dependencies
The required Python packages are listed in code/importer/static/requirements.txt .

For local execution, they can be installed from the project root using:

python -m pip install -r code/importer/static/requirements.txt

When using Docker, the dependencies are installed automatically when building the importer image.


## Expected environment variables:
The PostgreSQL database connection settings are loaded from a .env file located in the project root, or passed to the container through Docker Compose. 
The expected database connection environment variables are the following:
* DB_HOST: PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password.

The following optional variables can also be configured:
* STATIC_IMPORTER_CHUNKSIZE_INTERNAL: Number of CSV product rows processed per chunk (default: 250).
* STATIC_IMPORTER_INSERTING_CHUNKSIZE: Number of records inserted per PostgreSQL batch (default: 5000).
These parameters allow the importer to be adjusted according to the available memory and database performance without modifying the Python script.


## Code Structure
The script is organized into four main sections:
* Imports: imports the Python necessary libraries.
* Configuration: defines settings, directories, mappings, parameter variables...
* Functions: defines the functions used in the whole pipeline of this loading: reading the data, transforming the data, processing the data, ensuring data-quality and preparing database tables.
* Main execution: coordinates the whole pipeline, so for each supermarket applies the defined functions and inserts the cleaned records into the corresponding PostgreSQL tables.

**Note: Unique Product Tracking**: Products are identified by their original product IDs. The script keeps track of product IDs already inserted during the current execution to prevent inserting the same product multiple times across different chunks, to load only unique products in the Products table of the database. 

**Note: Historical price optimization**: For each product and supermarket, price records are sorted chronologically and compared with the previous available price using pandas groupby() and shift(). Only the first observed price and subsequent changes are retained.

Since each original CSV row contains the complete historical price series of a unique product, this filtering can be performed independently within each chunk.

**Note: Database transactions**: Each chunk is inserted within a database transaction, so its database operations are committed together if they succeed.

**Note: Progress logging**: The script prints data-quality reports and chunk completion messages during execution, allowing users to monitor the import progress through Docker logs. This is possible thanks to the "PYTHONUNBUFFERED" setting in the dockerfile to allow python release the prints during the docker logs, instead of keeping them in a buffer and printing when done.


## Docker configuration
The static importer is configured as a separate service named static_importer in docker-compose.yaml.

Its Dockerfile is located in code/importer/static/Dockerfile.

The Dockerfile sets the working directory to:

/project/code/importer/static

This preserves the expected relative directory structure used by the Python script to locate the project root.

The CSV files are made available inside the container through a Docker Compose bind mount:

volumes:
  - ./data/raw:/project/data/raw:ro

The :ro option makes the CSV directory read-only inside the container.

The importer also depends on the PostgreSQL database being healthy before starting.

The importer uses restart: "no" because it is a one-time data-loading process rather than a continuously running service.

Unlike the previous configuration, the importer no longer uses a Docker Compose profile. It is started automatically as part of the normal application startup.

The visualization service also depends on the importer completing successfully.


## Running the Script
From the project root, make sure Docker Desktop is running and that the CSV files and .env file are available.

 _Option 1: Start the complete application:_ 
 docker compose up --build

This starts the PostgreSQL database, executes the static importer if the database has not yet been populated, and starts the Streamlit dashboard once the importer finishes successfully.

The command also displays container logs directly in the terminal.


_Option 2: Run only the static importer:_ 
docker compose up -d database
docker compose run --rm --build static_importer
The first command starts PostgreSQL. The second builds the importer image and runs the Python script in a temporary container.
The --rm option removes this temporary container after execution. It does not remove the PostgreSQL database or its stored data.


#### Rebuilding the Database
When changes to the database schema or importer require a completely new import, the development database can be recreated using:
docker compose down -v
docker compose up --build
**Be careful**: docker compose down -v removes the project Docker volumes, including the persistent PostgreSQL databaee. This permanently deletes the database data and should be only used when a full reset is intended. 


#### Protection Against Repeated Imports
The static data loader is intended to run once on an initially empty database.

Before importing, the script checks whether the supermarkets table already contains records.

If supermarket data is found, the importer skips the import and exits successfully, preventing repeated insertion into an already populated database.

This also allows the normal Docker Compose startup process to be used again without reimporting the historical data every time.
 
Important: The importer does not delete or replace existing data. Its current protection mechanism checks for the presence of supermarket records, rather than verifying whether a previous import was fully completed. Therefore, an interrupted import may require a database reset before it can be restarted from the beginning.



#### Import results and performance
The updated importer was tested with a complte historical import of all supermarket products and prices.

The number of records in the supermarketproducts table was reduced from 19 million records to 131 thousand records.

The approximated importing time was reduced from 36 minutes in a standard portable computer to 9 minutes.