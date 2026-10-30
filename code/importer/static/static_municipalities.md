# Static Municipality Data Loader

## Description

This script downloads, processes and loads Dutch municipality data from the CBS Open Data API into the PostgreSQL `Municipalities` table.

The importer combines two CBS datasets:

* `80305ned`: proximity to facilities, used for the distance to the closest large supermarket and the number of large supermarkets within 1, 3 and 5 kilometres.
* `03759ned`: population by municipality, used for the population on 1 January of the selected year.

Only records with a CBS municipality code beginning with `GM` are kept. The datasets are combined using that municipality code and are prepared for insertion into the table created by `data/db/initdb.sql`.

## Imported Database Columns

The script fills the following fields:

* `municipalityId`: numeric CBS municipality code, with the `GM` prefix removed.
* `name`: municipality name supplied by CBS and cleaned for matching with PDOK names.
* `population`: population on 1 January of the selected year.
* `year`: selected year stored as 1 January because the database column has type `DATE`.
* `distanceClosestSupermarket`: average distance in kilometres to the closest large supermarket.
* `supermarketsWithin1KM`: average number of large supermarkets within 1 kilometre.
* `supermarketsWithin3KM`: average number of large supermarkets within 3 kilometres.
* `supermarketsWithin5KM`: average number of large supermarkets within 5 kilometres.

## Expected Input and Variables

The importer does not require local CSV files. It downloads data directly from `https://opendata.cbs.nl/ODataApi/OData` and follows CBS pagination links until all requested rows have been retrieved.

The configuration variables are:

* `YEAR`: default CBS reporting year, currently `2025`.
* `CBS_BASE_URL`: base URL of the CBS OData API.
* `inserting_chunksize`: maximum number of records sent to PostgreSQL per insertion batch.

The year and insertion size can optionally be overridden through environment variables:

* `MUNICIPALITIES_IMPORTER_YEAR`
* `STATIC_IMPORTER_INSERTING_CHUNKSIZE`

## Dependencies

The required Python packages are listed in `code/importer/static/requirements.txt`.

For local execution, install them from the project root using:

```text
python -m pip install -r code/importer/static/requirements.txt
```

The CBS request itself uses Python's standard library, so no additional HTTP package is required.

## Expected Environment Variables

The PostgreSQL connection settings are loaded from the `.env` file in the project root:

* `DB_HOST`: PostgreSQL server hostname.
* `DB_NAME`: database name.
* `DB_USER`: database username.
* `DB_PASSWORD`: database password.

## Code Structure

The script is organized into four main sections:

* Imports and configuration: defines the CBS URL, default year, insertion size and output columns.
* CBS helper functions: downloads paginated OData responses and finds metadata keys for categories and periods.
* Transformation functions: downloads accessibility and population data, keeps municipalities, combines both datasets, cleans names and prepares the database columns.
* Main execution: reads the environment, checks the destination table, downloads the CBS data and inserts it in one transaction.

The data-quality report prints the number of rows, duplicate municipality IDs and missing values before insertion.

## Running the Script

From the project root, make sure PostgreSQL is running, the `Municipalities` table has been created from `data/db/initdb.sql`, and the `.env` file contains valid database settings. Then run:

```text
python code/importer/static/staticdata_loading_database_municipalities.py
```

The machine must have internet access to the CBS API. The requested year must be available in both CBS datasets; otherwise, the importer stops with an explanatory error.

## Database Transaction

All municipality rows are inserted inside one database transaction. If an insertion fails, the transaction is rolled back instead of leaving a partly loaded municipality table.

The importer uses `if_exists="append"`; it does not delete or replace existing data.

## Protection Against Repeated Imports

The municipality loader is intended to run once on an empty `Municipalities` table. Before downloading the data, it executes:

```sql
SELECT COUNT(*) FROM municipalities
```

If records already exist, the import is cancelled with this message:

```text
[WARNING] Static municipality data already loaded. Import not performed.
```

This prevents accidental duplicate or conflicting municipality imports. To reload a different year, clear the table deliberately or revise the loading strategy first; the script never removes existing records automatically.

## Docker Note

The `static_importer` service in `docker-compose.yaml` runs both static importers in sequence. It first imports the supermarket CSV data and then imports the CBS municipality data. The municipality importer only starts if the supermarket importer finishes successfully.

Run both importers from the project root with:

```text
docker compose run --rm --build static_importer
```

The image contains both `staticdata_loading_database.py` and `staticdata_loading_database_municipalities.py`. Internet access is required during execution because the second script downloads data from the CBS API.

The PostgreSQL database uses a persistent Docker volume. Avoid running `docker compose down -v` unless you intentionally want to delete the database and all data stored in its volume.
