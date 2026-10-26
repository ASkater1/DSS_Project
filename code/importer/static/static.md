# Static Data Loader

## Description
This script is responsible for reading, processing and loading the static product price data from four dutch supermarkets: Albert Heijn, Jumbo, Lidl and Plus, into a PostgreSQL database table.

The script reads the original CSV files in chunks to avoid loading the entire datasets into memory. Each chunk is then transformed into a common format, preprocessed and cleaned, and prepared for insertion into three related PostgreSQL database tables:
· Supermarkets: Table that stores the supermarket IDs, names, and market shares.

· Products: Stores product information, including product IDs, names, brands, and categories.

· SupermarketsProducts: Stores historical product prices, linking each product to a supermarket and a date.

This database tables are created beforehand using data/db/initdb.sql.

## Expected Input Files & Variables
The script expects the following CSV files to be located in the directory: data/raw :
* AH.csv
* Jumbo.csv
* Lidl.csv
* Plus.csv

The script also has variables that need to be properly defined beforehand (they already are, but they can be tunned):
* chunksize: Number of product rows read from each CSV file at a time, allowing the datasets to be processed incrementally, since the number of rows per each product is multiplied by the total date columns existing in each file. 
* inserting_chunksize: Maximum number of cleaned records inserted into the PostgreSQL per insertion iteration.

## Dependencies
The required Python packages are listed in code/importer/static/requirements.txt .

For local execution, they can be installed from the project root using:

python -m pip install -r code/importer/static/requirements.txt

When using Docker, the dependencies are installed automatically when building the importer image.

## Expected environment variables:
The PostgreSQL database connection settings are loaded from a .env file located in the project root. The expected database connection environment variables are the following:
* DB_HOST: PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password._
Each time the loader is executed will remove all the existing data in the PostgreSQL 

## Code Structure
The script is organized into four main sections:
* Imports: imports the Python necessary libraries.
* Configuration: defines settings, directories, mappings, parameter variables...
* Functions: defines the functions used in the whole pipeline of this loading: reading the data, transforming the data, processing the data, ensuring data-quality and preparing database tables.
* Main execution: coordinates the whole pipeline, so for each supermarket applies the defined functions and inserts the cleaned records into the corresponding PostgreSQL tables.

**Note**: Products are identified by their original product IDs. The script keeps track of product IDs already inserted during the current execution to avoid inserting the same product multiple times across different chunks, to load only unique products in the Products table of the database. 

Each chunk is inserted within a database transaction, so its database operations are committed together if they succeed.

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

To avoid running the importer automatically with the rest of the application, the service uses:

profiles:
  - import
restart: "no"

This means that a normal docker compose up -d does not start the static importer. It must be executed explicitly.

## Running the Script

From the project root, make sure Docker Desktop is running and that the CSV files and .env file are available.

Start the PostgreSQL database:
First,ostart r the all the container. There are two options: 

_Option 1: Start only the database:_ 
_Option 2: Start all default application services:_ docker compose up -d
The second option starts the database and visualization services, but not the static importer, because it belongs to the import profile. Then execute the static importer:

, in either case, explicitaly
docker compose run --rm --build static_importer
****
This command builds the importer image if necessary, starts a temporary importer container, waits for the database to become healthy, and runs the Python script.

The --rm option removes the temporary importer container when execution finishes. It does not remove the PostgreSQL database or its stored data.

The complete import can take a considerable amount of time, depending on computer performance (36 min approx).

#### Protection Against Repeated Imports

The static data loader is intended to run once on an initially empty database.
 
If it isn't started on an empty database, the import is cancelled with the following message:
 "Static supermarket data already loaded. Import cancelled."
This prevents accidental repeated imports into an already populated database.
 
Important: The importer currently does not delete or replace existing database data. The PostgreSQL database is stored in a persistent Docker volume. Avoid running docker compose down -v unless you intentionally want to delete the database and all data stored in its volume.