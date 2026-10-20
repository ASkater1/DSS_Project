Team 04 - Food availability dashboard

Running the dashboard
    Run 'Docker compose up --build' and the dashboard will open in localhost:8501

Video link: No video has been created yet
Link to the codebase: "INSERT GITLAB LINK HERE"
Dataset: Currently  the dataset is still built into the front-end (certain things dummy data, other things fetched and processed). 
    This is because the data loaders have not yet been finished. They are still in active development.
Other links: "ADD IF WE HAVE THESE"

Data collection and preparation
    The data collection and preparation is currently still done in the front end with dummy data, but the 'staticdata_loading_database.py'
    file will be the intializer for static datasets. This is still in active development.
    The importer for live datasets still needs to be developed.

Data sources
    Currently we use the following data sources:
    INSERT DATA sources

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