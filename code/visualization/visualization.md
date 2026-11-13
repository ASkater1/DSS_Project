# Dashboard (Visualization)


## Description
This service is responsible for displaying the Food Security Dashboard: the Streamlit website that can be opened in a web browser at http://localhost:8501.

The dashboard reads all its data from the PostgreSQL database and presents it in four tabs:
· Overview: Shows the number of supermarket chains, their combined market share and the price of the essential basket per supermarket.

· Prices: Allows users to compare supermarket prices, search for individual products and follow the average product price per category over time.

· Economy: Shows the monthly Consumer Price Index (CPI, 2015 = 100), the CPI change on the previous month and on a year earlier, and the average disposable income.

· Municipalities: Shows supermarket accessibility per Dutch municipality on a map, compared to population, and in a table.

The code is split into two files. app.py builds the pages and charts, and data_access.py forms the layer between the database and the dashboard: it runs every query and returns the results as pandas DataFrames. This way app.py does not contain any SQL, and changes to the database only require changes in data_access.py.

The database tables are created beforehand using data/db/initdb.sql and filled by the importers.


## Expected Input Files & Variables
The service does not need any data files, since it receives all data from the database.

At build time the following file is expected in the directory code/visualization :
* municipalities.geojson: a cached copy of the municipality borders from PDOK, used for the map. Without it, the borders would be downloaded every time the website is opened. A new copy can be created with municipality_geodata_dumper.py.

The data_access.py script also has variables that can be adapted beforehand:
* CACHE_TTL: Number of seconds the results of the quick queries are kept in memory before the database is queried again.
* LONG_CACHE_TTL: Number of seconds the result of the slow monthly category price query is kept in memory.
* SEARCH_LIMIT: Maximum number of products returned by the product search.

The default values are 3600 (1 hour), 21600 (6 hours) and 200 respectively.


## Dependencies
The required Python packages are listed in code/visualization/requirements.txt .

For local execution, they can be installed from the project root using:

python -m pip install -r code/visualization/requirements.txt

When using Docker, the dependencies are installed automatically when building the dashboard image.


## Expected environment variables:
The PostgreSQL database connection settings are loaded from a .env file located in the project root, or passed to the container through Docker Compose.
The expected database connection environment variables are the following:
* DB_HOST: PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password.

The following optional variable can also be configured:
* DB_PORT: PostgreSQL port (default: 5432).


## Code Structure
The data_access.py script is organized into three main sections:
* Imports and configuration: imports the necessary Python libraries and defines the cache durations, the search limit and the fallback SQL expression for top-level categories.
* Helper functions: opens the database connection, runs a query and returns the result as a DataFrame, and converts database decimals to numbers.
* Data loading functions: one function per type of data used by the dashboard:
  * load_supermarkets(): supermarket IDs, names and market shares.
  * load_economy_statistics(): one row per month with the CPI, both CPI rates of change, the incomes and the wage increase.
  * load_municipalities(): population and supermarket accessibility per municipality.
  * load_monthly_category_prices(): average product price per month, supermarket and top-level category.
  * load_monthly_basket_prices(): essential basket price per month and supermarket.
  * search_products(): latest known price of every product whose name contains the search text.

The app.py script is organized into two main sections:
* Data loading: loads all data through data_access.py and stops with an error message if the database cannot be reached.
* Dashboard tabs: one section per tab (Overview, Prices, Economy, Municipalities) that filters the loaded data and builds the metrics, charts and tables.

**Note: Caching**: Streamlit re-runs the complete app.py on every click, filter change or search. Every data loading function is therefore cached with st.cache_data, so the database is only queried again when the cache has expired (CACHE_TTL or LONG_CACHE_TTL). Without the cache, every interaction would run all queries again.

**Note: Aggregation in the database**: The SupermarketsProducts table can contain millions of price records, which is far too much to send to the dashboard. The price functions therefore aggregate inside PostgreSQL and only return small summary tables (about 2,700 rows for the monthly category prices). The monthly category price query is given 512 MB of PostgreSQL work memory for that query only, which made it about 2.5 times faster.

**Note: Monthly prices**: Each product is first averaged per month, and those product averages are then averaged per category, so that products that were recorded on more days do not count more heavily. This assumes that every product has a price record in every month. When the database only contains price changes (see the static importer), products whose price did not change during a month are missing from that month's average.

**Note: Shared categories**: Products are grouped by the shared categories in the Categories table, which are filled by the category importer (see code/importer/categories/category_importer.md). Because every supermarket uses the same 25 categories, the category chart on the Prices tab can compare supermarkets directly. Products without a shared category are shown as Onbekend. The category filter only lists the categories of the selected supermarkets.

When the database does not have shared categories yet (no Categories table or no Products.categoryId column), the dashboard falls back to each supermarket's own top-level category, using the TOP_CATEGORY_SQL expression:
* AH: Home\Producten\Zuivel, eieren\Yoghurt en skyr\... becomes Zuivel, eieren
* Plus: Zuivel eieren boter\Verse zuivel\Yoghurt becomes Zuivel eieren boter
* Jumbo: Koek, snoep, chocolade en chips ; Chocolade ; ... becomes Koek, snoep, chocolade en chips
* Lidl: Home/Eten & drinken/Kaas & Zuivel &&& ... becomes Kaas & Zuivel

These fallback categories are not comparable between supermarkets. Category paths in any other format become Overig.

**Note: Comparing category prices**: Even with shared categories, the average price of a category also depends on which products a supermarket sells: a chain with more premium products or larger packs has a higher average without being more expensive for the same product. The category chart shows price development and differences in the range, not the price of identical products. The essential basket is meant for comparing identical products.

**Note: Missing data**: When data is not available yet, the dashboard shows an explanation instead of an empty or made-up chart:
* Essential basket: the basket metrics and charts need products with isBasketProduct set to true in the Products table.
* Market share: shown as n/a while the marketshare column of the Supermarkets table is empty.
* Product quantity: the quantity column of the product search is only shown when the Products table has the quantity_value and quantity_units columns and they contain values.
* Income: CBS publishes household income per year, so every month shows the income of its year, and months without published income are left empty.


## Docker configuration
The dashboard is configured as a separate service named visualization in docker-compose.yaml, running in a container named dashboard.

Its Dockerfile is located in code/visualization/Dockerfile.

The Dockerfile sets the working directory to:

/app

It copies requirements.txt, municipalities.geojson, app.py and data_access.py into the image and starts the dashboard with streamlit run app.py.

The dashboard is published on port 8501:

ports:
  - '8501:8501'

The dashboard depends on the PostgreSQL database being healthy before starting.

The dashboard uses restart: always because it is a continuously running service, unlike the importers.

The service has a Docker Compose watch configuration: changes to the Python files are synchronised into the running container, which then restarts, and changes to the other files rebuild the image.


## Running the Script
From the project root, make sure Docker Desktop is running and that the .env file is available.

 _Option 1: Start the complete application:_
 docker compose up --build

This starts the PostgreSQL database, runs the importers and starts the Streamlit dashboard.


_Option 2: Run only the dashboard:_
docker compose up -d database
docker compose up -d --build visualization
The first command starts PostgreSQL. The second builds the dashboard image and starts the dashboard. Then open http://localhost:8501 in a web browser.


_Option 3: Run the dashboard with automatic reloading while developing:_
docker compose watch visualization
Changes to app.py or data_access.py are then applied to the running dashboard automatically.


#### First load and performance
The first time the dashboard is opened, the monthly category prices are calculated from all price records. With 19 million price records this took about 20 seconds; a spinner is shown in the meantime. After that, the result is kept in memory for 6 hours (LONG_CACHE_TTL), and the dashboard responds immediately.

The other queries take less than a second together. The product search takes about one second.

When the database only contains price changes, as produced by the current static importer, the price queries have far fewer records to read and the first load is faster.
