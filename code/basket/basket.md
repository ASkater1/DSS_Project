# Basket Selector


## Description
This script selects the products that belong to the essential basket and marks them in the Products table of the PostgreSQL database.

The basket follows the food groups of the CBS consumer price index (ECOICOP v2, group 01 food and non-alcoholic drinks): https://www.cbs.nl/nl-nl/longread/diversen/2026/de-ecoicopv2-indeling/010000-voedingsmiddelen-en-alcoholvrije-dranken

Every product is checked against a list of rules, one rule per CBS food group (rice, bread, milk, cheese, eggs...). If a product matches a rule, two columns are filled in:
· isBasketProduct: TRUE if the product is part of the basket.

· basketcode: the CBS code of the food group it belongs to (for example 011110 for rice).

The dashboard uses these columns for the average basket price and the basket charts.


## Expected Input Files & Variables
The script expects the following file in the same directory: code/basket :
* cpi_basket_rules.csv

Each row is one basket rule with the columns:
* code: CBS code of the food group.
* name: Name of the food group.
* category: Shared category the product must have (from the category importer).
* include: Words of which at least one must be in the product name, separated by |.
* exclude: Words that may not be in the product name, separated by |.
* quantity and unit: Reference amount of the product (read in, but not used for the selection yet).

To change the basket, only this CSV needs to be changed.


## Dependencies
The required Python packages are listed in code/basket/requirements.txt .

For local execution, they can be installed from the project root using:

python -m pip install -r code/basket/requirements.txt

When using Docker, the dependencies are installed automatically when building the basket image.


## Expected environment variables:
The PostgreSQL database connection settings are loaded from a .env file located in the project root, or passed to the container through Docker Compose.
* DB_HOST: PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password.


## Code Structure
The script is organized into three main sections:
* Imports: imports the necessary Python libraries.
* Configuration: reads the basket rules from cpi_basket_rules.csv.
* Main execution: reads all products with their shared category, checks them against the rules and marks the selected products in the database.

**Note: Matching**: A product is selected when its shared category is the same as the category of the rule, its name contains one of the include words and none of the exclude words. The rules are checked in order and a product gets the first rule that matches.

**Note: Clean selection**: Before marking the new selection, isBasketProduct and basketcode are reset for every product. So every run starts with an empty basket, and products that no longer match are removed.

**Note: Shared categories**: The rules use the shared categories, so the category importer has to be finished first. Docker Compose takes care of this order.


## Docker configuration
The basket selector is configured as a separate service named basket in docker-compose.yaml.

Its Dockerfile is located in code/basket/Dockerfile and copies basket.py and cpi_basket_rules.csv into /app.

The service waits until the database is healthy and the static importer and category importer have finished successfully. It uses restart: "no" because it runs once.


## Running the Script
From the project root, make sure Docker Desktop is running and the .env file is available.

docker compose up -d database
docker compose run --rm --build basket

The script prints the number of rules, the categories used and the number of selected basket products.

The script can be run again at any time: it always replaces the previous selection.
