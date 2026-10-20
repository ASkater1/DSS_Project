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

Video link: No video has been created yet.
Link to the codebase: https://github.com/ASkater1/DSS_Project (private)
Dataset: Currently  the first dataset is still built into the front-end (certain things are still dummy data, other things fetched and processed). 
    This is because the data ingestion pipelines have not yet been finished. They are still in active development.
Other links:
  - Shared folder for concepts, collaborative presentation creation etc. https://drive.google.com/drive/folders/1gpxfyCjhmbWBgDvh1Wtg4tS-DpGB5sZP

Data collection and preparation
    The data collection and preparation is currently still done in the front end with dummy data, but the 'staticdata_loading_database.py' will be run in a separate container service, once development is finished.
    This file will be the intializer for static datasets. This is still in active development.
    The importer for live datasets still needs to be developed.

Data sources
    Currently we use the following data sources:
    * Supermarket historical product data: Provides historical information on prices, ingredients, nutrients, and supplier/label data for products sold by four major Dutch supermarkets (Albert Heijn, Jumbo, PLUS and Lidl). https://research.vu.nl/en/datasets/supermarket-product-data
    -> all other datasources are currently mocked.

Existing indicators and visualizations.
    -   Tab1 --> Overview
        -   Supermarket chains --> Amount of supermarket chains contained in dataset
        -   Combined market share --> % of marketshare contained in dataset
        -   Average basket price --> Average price of a basket of groceries at the supermarkets contained in the dataset
        -   Market share and basket price --> Visualizes the basket price of each of the included supermarkets. 
    -   Tab2 --> Prices
        -   Average basket price --> Average price of a basket of groceries at the supermarkets contained in the dataset
        -   Lowest basket price --> Lowest price of a basket of groceries at the supermarkets contained in the dataset
        -   Highest basket price --> Highest price of a basket of groceries at the supermarkets contained in the dataset
        -   Price development over time --> Basket price development per supermarket over time
        -   Price comparison --> Table containing all products in the dataset, allows for easy filtering to see comparison of a single product.
        -   Average product price by category --> Contains product prices per category of grocies (Fruit, Bread, Potatoes)
    -   Tab3 --> Economy
        -   CPI --> CPI or Consumer Price Index involves the amount of money consumers can pay for their groceries. 
                The base value (100) was set in 2015 and an increase in this value represent a variable increase to 2015.
        -   Monthly rate of Change in CPI --> This visualizes CPI change per month. Giving users the ability to track CPI development montly
        -   CPI mothly rate of change vs disposable income --> This visualzation shows the CPI development vs the average disposable income
                This aims to show the developement of the CPI in relation to the development of disposable income.
    - Tab4 --> Municipality
        -   Average accessibility score -> gives context, what is a "normal" accessibility
        -   Average distance to closest supermarket -> shows the baseline to compare the supermarket accessibility to.
        -   Supermarket Accessibility by Municipality -> Choropleth map of supermarket accessibility per municipality (adjusted against the population of that municipality)
                This helps identify municipalities with relatively low accessibility scores