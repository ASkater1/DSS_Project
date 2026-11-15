Team 04 - Food availability dashboard
by:
- Jari van Polen
- Matthijs van Oord
- Tobias Buiten
- Tim Kläring
- Marc Avila Pedemonte
- Floris Smit

#Please also look at the provided readme.md
Running the dashboard
    0. Unzip all the files or clone the repository from git.science.uu.nl
    1. Create the required environment file .env (Sample could be copied over from .env.sample)
    2. Run 'docker compose up --build' and the dashboard will open in http://localhost:8501

Start order of the containers
    The dashboard is started as the last container, so it does not show an empty database. It waits for:
    -   database --> has to be healthy
    -   static_importer, static_municipalities_importer, market_shares_importer, category_importer, financial_importer, product_link_importer and basket --> have to be finished
    If one of the importers fails, the dashboard will not start. Check the logs with 'docker compose logs <service name>'
    or start only the dashboard with 'docker compose up -d --no-deps visualization'.

Video link: No video has been created yet.
Link to the codebase: https://github.com/ASkater1/DSS_Project (private)
Dataset: The data is loaded into a PostgreSQL database by the importer containers. The dashboard only reads from this database.
Other links:
  - Shared folder for concepts, collaborative presentation creation etc. https://drive.google.com/drive/folders/1gpxfyCjhmbWBgDvh1Wtg4tS-DpGB5sZP

Data collection and preparation
    Every container has its own folder in /code with a .md file that explains it in more detail.
    -   static_importer --> loads the supermarket CSV files (data/raw) and only stores the first price and the price changes per product
    -   static_municipalities_importer --> downloads the supermarket accessibility and population per municipality from CBS
    -   market_shares_importer --> loads the yearly market share of AH, Jumbo, Lidl and Plus
    -   category_importer --> gives every product one shared category, so categories can be compared between supermarkets
    -   product_link_importer --> links the same products between supermarkets (data/raw/product_linking.csv)
    -   financial_importer --> downloads the monthly CPI, food CPI, cao wages and household income from CBS. Only new or changed months are stored.
    -   basket --> marks the products of the essential basket, based on the CBS food groups of the CPI
    -   visualization --> the Streamlit dashboard. The calculations (price index, predictions) are done in data_access.py

Data sources
    Currently we use the following data sources:
    * Supermarket historical product data: Provides historical information on prices, ingredients, nutrients, and supplier/label data for products sold by four major Dutch supermarkets (Albert Heijn, Jumbo, PLUS and Lidl). https://research.vu.nl/en/datasets/supermarket-product-data
    * CBS Open Data (StatLine): CPI (83136NED), food CPI (86141NED), household income (83932NED), cao wages (85663NED), supermarket accessibility (80305NED) and population (03759NED). https://opendata.cbs.nl
    * Market shares (NielsenIQ): Yearly market shares of the Dutch supermarkets 2021-2025. https://www.fmcgopleidingen.nl/inzichten/marktaandelen-supermarkt-nielseniq/
    * PDOK (Kadaster): Municipality borders for the map. https://api.pdok.nl

Existing indicators and visualizations.
    -   Tab1 --> Overview
        -   Supermarket chains --> Amount of supermarket chains contained in dataset
        -   Combined market share --> % of marketshare contained in dataset
        -   Average basket price --> Average price of a basket of groceries at the supermarkets contained in the dataset
        -   Market share per supermarket --> Market share of each supermarket per year, and of all other supermarkets together
        -   Food prices compared with household income --> Food CPI and disposable household income, both 100 in the first month
        -   Basket price as a share of household income --> Basket price of each supermarket as % of the monthly disposable income
    -   Tab2 --> Prices
        -   Average basket price --> Average price of a basket of groceries at the supermarkets contained in the dataset
        -   Lowest basket price --> Lowest price of a basket of groceries at the supermarkets contained in the dataset
        -   Highest basket price --> Highest price of a basket of groceries at the supermarkets contained in the dataset
        -   Price development over time --> Basket price development per supermarket over time
        -   Price comparison --> Table with the linked products and their latest price per supermarket
        -   Price index compared with CPI --> Price change of the same products per supermarket compared with the CPI.
                Dashed lines are predictions (linear regression) for at most 6 months.
        -   Price index compared with cao wages --> The same price index compared with the cao wages
        -   Price change per category --> % price change of the same products per food category and supermarket
    -   Tab3 --> Economy
        -   Food prices vs a year earlier --> Change of the food CPI compared with the same month a year earlier
        -   All prices (inflation) vs a year earlier --> Change of the CPI compared with the same month a year earlier
        -   CPI --> CPI or Consumer Price Index shows the price level of all goods and services.
                The base value (100) was set in 2015 and an increase in this value represent a variable increase to 2015.
        -   Monthly rate of Change in CPI --> This visualizes CPI change per month. Giving users the ability to track CPI development montly
    - Tab4 --> Municipality
        -   Average accessibility score -> gives context, what is a "normal" accessibility
        -   Average distance to closest supermarket -> shows the baseline to compare the supermarket accessibility to.
        -   Lowest accessibility score -> the municipality with the least supermarkets nearby
        -   Supermarket Accessibility by Municipality -> Choropleth map of the accessibility score per municipality
                The score counts the supermarkets within 1 km (x1), 1-3 km (x0.75) and 3-5 km (x0.5)
        -   Municipality Comparison -> Accessibility score compared to the population of each municipality
                This helps identify municipalities with relatively low accessibility scores
        -   Municipality Data -> Table with the values behind the map and the comparison
