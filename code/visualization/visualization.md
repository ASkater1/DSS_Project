# Dashboard (Visualization)


## Description
This service is responsible for displaying the Food Security Dashboard: the Streamlit website that can be opened in a web browser at http://localhost:8501.

The dashboard reads all its data from the PostgreSQL database and presents it on four pages, chosen in a fixed sidebar on the left:
· Overview: Shows the number of supermarket chains, their combined market share and the price of the essential basket per supermarket.

· Prices: Allows users to compare supermarket prices, search for individual products and follow a price index per category over time.

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
* LONG_CACHE_TTL: Number of seconds the result of the slow price index query is kept in memory.
* SEARCH_LIMIT: Maximum number of products returned by the product search.
* MIN_PRICE_RATIO and MAX_PRICE_RATIO: price ratios (this month's price divided by the previous one) outside these limits are ignored by the price index.
* MIN_COMPARABLE_PRODUCTS: months based on fewer comparable products are shown as less reliable in the price index chart.

The default values are 3600 (1 hour), 21600 (6 hours), 200, 0.5 and 2.0, and 10 respectively.


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
* Imports and configuration: imports the necessary Python libraries and defines the cache durations, the search limit, the price index settings and the fallback SQL expression for top-level categories.
* Helper functions: opens the database connection, runs a query and returns the result as a DataFrame, and converts database decimals to numbers.
* Data loading functions: one function per type of data used by the dashboard:
  * load_supermarkets(): supermarket IDs, names and market shares.
  * load_economy_statistics(): one row per month with the CPI, both CPI rates of change, the incomes and the wage increase.
  * load_municipalities(): population and supermarket accessibility per municipality.
  * load_price_index_links(): the monthly price change of the same products per supermarket and category, the basis of the price index.
  * chain_price_index(): turns those monthly changes into a price index for one category (or All food) and the selected supermarkets, with 100 in the first month shown, and returns a comparison series (the CPI or cao wages, given as Date and Value) rescaled to the same base month. A supermarket whose data starts later starts at the comparison level of its first month.
  * wage_level_from_yearly_increase(): builds a monthly cao wage level from the stored yearly cao wage increase, for the wage comparison chart. This function does not query the database, so changing the category or supermarkets is immediate.
  * load_monthly_basket_prices(): essential basket price per month and supermarket.
  * search_products(): latest known price of every product whose name contains the search text.

The app.py script is organized into two main sections:
* Sidebar: the dashboard title, four page tiles (Overview, Prices, Economy, Municipalities) in a 2 x 2 grid and, below a Filters heading, the filters of the selected page.
* Data loading: loads only the data the selected page needs through data_access.py, and stops with an error message if the database cannot be reached.
* Dashboard pages: one section per page that adds its filters to the sidebar, filters the loaded data and builds the metrics, charts and tables.

**Note: Page tiles**: The pages are chosen with four tiles at the top of the sidebar, each with an icon. The tile of the selected page is highlighted in the dashboard's accent colour (a Streamlit "primary" button); the other tiles are plain. The selected page is kept in st.session_state, so it stays selected when a filter changes, and the dashboard opens on Overview. Clicking a tile selects the page through an on_click callback before the page reruns, so the right tile is highlighted straight away. The tile size is set with a small CSS rule at the top of app.py; the icons are part of the tile labels, because the Streamlit version used (1.37) has no icon parameter on buttons.

**Note: Sidebar and filters**: Every filter is placed in the sidebar, below the page tiles, and only the filters of the selected page are shown:
* Overview: date range.
* Prices: date range, supermarkets and category. The product search stays on the page, next to its results.
* Economy: date range.
* Municipalities: no filters.

The date range filter is the same render_date_filter() function on every page, placed in the sidebar; each page keeps its own date range.

**Note: Date range filter**: The date range is chosen with a two-way slider: the left handle sets the start date and the right handle the end date. By default the slider covers the whole period of the data on that page (the first and the last month in the data). Below the slider, a Start date and an End date field always show the selected dates; a date can also be typed or picked from a calendar there. The slider and the two fields are kept in sync through on_change callbacks: moving the slider updates the fields, and typing a date moves the slider. When the typed start date is after the end date, an error is shown and the page shows no data until this is corrected. Streamlit forgets the state of filters that are not shown, so a page's date range returns to the whole period after switching to another page and back. The sidebar cannot be collapsed: a small CSS rule at the top of app.py hides Streamlit's collapse arrow, so the filters always stay visible. On narrow screens such as phones, Streamlit still shows the sidebar as a menu.

The pages replace the tabs the dashboard used before. With tabs, Streamlit builds every tab at once and cannot tell the code which tab is open, so the sidebar could not show the filters of the open tab only.

**Note: Caching**: Streamlit re-runs the complete app.py on every click, filter change or search. Every data loading function is therefore cached with st.cache_data, so the database is only queried again when the cache has expired (CACHE_TTL or LONG_CACHE_TTL). Without the cache, every interaction would run all queries again.

**Note: Aggregation in the database**: The SupermarketsProducts table can contain millions of price records, which is far too much to send to the dashboard. The price functions therefore aggregate inside PostgreSQL and only return small summary tables (about 2,800 rows for the price index). The price index query is given 512 MB of PostgreSQL work memory for that query only, which made it about 2.5 times faster.

**Note: Price index**: The Prices page shows a price index per category instead of an average price. An average price jumps whenever a supermarket's data suddenly contains more or different products (for example Jumbo in November 2024, when 6,000 cheaper products were added), even if no price changed. The index only compares the same products, in the same way CBS calculates the CPI:
* Each product's prices are averaged per month.
* Every month, each product's price is divided by its price in its previous month with a price. Ratios below MIN_PRICE_RATIO or above MAX_PRICE_RATIO are ignored as probable data errors or pack-size changes.
* Per supermarket and category, the monthly change is the geometric mean of those ratios, so a product that doubles in price and one that halves cancel each other out.
* The index is 100 in the base month and multiplies the monthly changes from there. A new product only counts from its second month, so new products do not cause jumps.
* All food combines all food categories, so non-food products such as shampoo do not affect it.

Only price changes can be compared between supermarkets, not price levels, so all lines start at 100 in the same base month: the first month shown. With the date slider covering the whole period (the default) this is November 2022, the first month of the supermarket price data; when the date range filter of the Prices page starts later, that month becomes the base month. A supermarket whose data starts after the base month (Lidl, from November 2025) starts at the CPI level of its own first month and follows its own price changes from there; a note above the chart says which supermarkets start later. Its level therefore shows how its prices moved compared with general inflation since it started, not how it compares with the other supermarkets before that month.

**Note: CPI line**: The price index chart also shows the consumer price index (CPI, all goods and services, from the EconomyStatistics table) as a grey line, so supermarket price changes can be compared with general inflation. The CPI is rescaled to 100 in the same base month as the supermarket lines: the CPI of each month divided by the CPI of the base month, times 100. The CPI level is used instead of the stored monthly rates of change, because those are rounded to one decimal and would add up rounding errors. The economy statistics start in November 2022, the same month as the supermarket price data, so the CPI is available for every base month and for the starting month of every supermarket. Note that the CPI covers all goods and services (including energy, rent and services), while the supermarket index only covers supermarket products.

**Note: Cao wage line**: Below the CPI chart, the Prices page shows the same price index compared with collective (cao) wages, so price changes can be compared with wage growth. The wage line is built by wage_level_from_yearly_increase() in data_access.py from the YearlyWageIncrease column, which is not changed for this: each month the wage level grows by the twelfth root of that month's yearly increase (4.7% per year becomes about 0.38% per month). The line is then rescaled to 100 in the same base month as the supermarket lines. This is an estimate: CBS raises cao wages mostly in January and July, so the real cao wage index rises in steps, while this line spreads each increase evenly over the year and can differ from the real index by up to about 3 points along the way (about 1 point at the end of the chart). The chart's caption says it is an estimate. An exact line would need the cao wage index level (CBS table 85663NED) as an extra column in the EconomyStatistics table.

Both charts are drawn by the same function, draw_price_index_chart() in app.py, which takes the comparison line, its name and its caption text.

**Note: Months without price changes**: Parts of the price data contain copied prices, where every product has the same price as on the day before (for example all Plus prices after 16 July 2024). A month without any price change keeps the index at the level of the month before, so the line continues flat; the tooltip then says "no price changes this month". Months without any data for a supermarket (Plus in March and April 2024) are bridged with a straight line between the months before and after.

**Note: Reliability**: A month based on fewer than MIN_COMPARABLE_PRODUCTS comparable products is shown with a lighter dot, and the tooltip says how many products it is based on. This mostly concerns Jumbo and Plus categories before mid-2024, when their data contained only a few hundred products.

**Note: Shared categories**: Products are grouped by the shared categories in the Categories table, which are filled by the category importer (see code/importer/categories/category_importer.md). Because every supermarket uses the same 25 categories, the price index chart on the Prices page can compare supermarkets directly. Products without a shared category are shown as Onbekend. The category filter only lists the categories of the selected supermarkets.

When the database does not have shared categories yet (no Categories table or no Products.categoryId column), the dashboard falls back to each supermarket's own top-level category, using the TOP_CATEGORY_SQL expression:
* AH: Home\Producten\Zuivel, eieren\Yoghurt en skyr\... becomes Zuivel, eieren
* Plus: Zuivel eieren boter\Verse zuivel\Yoghurt becomes Zuivel eieren boter
* Jumbo: Koek, snoep, chocolade en chips ; Chocolade ; ... becomes Koek, snoep, chocolade en chips
* Lidl: Home/Eten & drinken/Kaas & Zuivel &&& ... becomes Kaas & Zuivel

These fallback categories are not comparable between supermarkets. Category paths in any other format become Overig.

**Note: Comparing supermarkets**: The price index shows how fast prices change at each supermarket, not which supermarket is cheaper: an index of 110 at two supermarkets means both became 10% more expensive, whatever their prices were. The essential basket is meant for comparing the price of identical products.

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
Every page only loads the data it needs, so the Overview, Economy and Municipalities pages open immediately. The first time the Prices page is opened, the price index is calculated from all price records. With 19 million price records this takes up to a minute (about 45 seconds when tested); a spinner is shown in the meantime. After that, the result is kept in memory for 6 hours (LONG_CACHE_TTL), and the Prices page also responds immediately.

The other queries take less than a second together. The product search takes about one second.

When the database only contains price changes, as produced by the current static importer, the price queries have far fewer records to read and the first load is faster.
