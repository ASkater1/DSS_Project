# Shared Category Importer


## Description
This script is responsible for giving every product one category from a shared category list, so that product categories can be compared between the four supermarkets: Albert Heijn, Jumbo, Lidl and Plus.

Every supermarket stores its product categories in its own format and with its own names. For example, dairy is called "Zuivel, eieren" at AH, "Zuivel, eieren, boter" at Jumbo and "Zuivel eieren boter" at Plus, and AH keeps cheese, meat and fish separate where Plus combines them into "Kaas vleeswaren tapas" and "Vlees kip vis vega". Most Lidl products only have German Open Food Facts labels. Without a shared list, the average price of a category cannot be compared between supermarkets.

The script reads every product with its supermarket, decides its shared category, and stores the result in two places in the PostgreSQL database:
· Categories: Table that stores the shared categories, with an ID, a name, whether it is a food category, and a description.

· Products.categoryId: Column that links every product to its shared category.

The shared list contains 25 categories: 21 food groups (for example Zuivel & eieren, Kaas, Vlees & kip, Vis, Frisdrank, sappen & water) and 4 non-food groups (Drogisterij & verzorging, Huishouden, Huisdier, Overig non-food). Products are grouped by what they are, not by where a supermarket places them: frozen fish counts as Vis, frozen pizza as Maaltijden & salades, and coffee creamer as Koffie & thee at every supermarket.

The script also repairs category text that was imported with a wrong character encoding (for example "oliÃ«n" becomes "oliën") before it is matched.


## Expected Input Files & Variables
The script expects the following files to be located in the same directory as the script, code/importer/categories :
* shared_categories.csv: the shared category list, with the columns name, is_food and description.
* category_mapping.csv: links a category path of a supermarket to a shared category, with the columns supermarket, level_1, level_2, level_3 and shared_category.
* lidl_label_rules.csv: keyword rules for Lidl's German Open Food Facts labels, with the columns priority, pattern, shared_category and explanation.

These files are the place to change the categorisation. The Python script does not need to be changed to add a category, fix a mapping or add a rule.

The script also has variables that can be adapted beforehand:
* GENERIC_LIDL_LABELS: Open Food Facts labels that are ignored because they are too broad to say anything about the product, such as "Pflanzliche Lebensmittel und Getränke".


## Dependencies
The required Python packages are listed in code/importer/categories/requirements.txt .

For local execution, they can be installed from the project root using:

python -m pip install -r code/importer/categories/requirements.txt

When using Docker, the dependencies are installed automatically when building the importer image.


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
The script is organized into four main sections:
* Imports and configuration: imports the necessary Python libraries and defines the file locations, the Lidl label separator, the ignored Lidl labels and the database schema the script needs.
* Text functions: repair the character encoding, clean category names and split a category path into levels, using the format of each supermarket.
* Categorisation functions: read and check the three definition files, assign a shared category to every product, and print a report.
* Main execution: reads the products from the database, assigns their categories, and writes the shared categories and the category of every product in one transaction.

**Note: Category path formats**: Every supermarket stores its category path differently, so the path is split into levels per supermarket:
* AH: Home\Producten\Zuivel, eieren\Yoghurt en skyr\... gives the levels Zuivel, eieren / Yoghurt en skyr / ...
* Plus: Zuivel eieren boter\Verse zuivel\Yoghurt gives Zuivel eieren boter / Verse zuivel / Yoghurt
* Jumbo: Zuivel, eieren, boter ; Yoghurt en kwark ; ... gives Zuivel, eieren, boter / Yoghurt en kwark / ...
* Lidl: Home/Eten & drinken/Kaas & Zuivel &&& Milchprodukte, ... gives Eten & drinken / Kaas & Zuivel, followed by the Open Food Facts labels after &&&

**Note: Matching the mapping**: The most specific row in category_mapping.csv wins. A row with only level_1 filled in applies to the whole main category, and rows with level_2 (or level_3) override it for a subcategory. For example, all of AH's "Zuivel, eieren" is Zuivel & eieren, except "Koffiemelk", which is Koffie & thee. Matching ignores upper and lower case and extra spaces.

**Note: Lidl**: About 84% of Lidl products only have German Open Food Facts labels, and Lidl's own web category is sometimes wrong (a herring fillet is listed under "Chips & snoep"). For Lidl the keyword rules in lidl_label_rules.csv are therefore tried first, in order of priority, and the first matching rule wins. Specific rules come before broad ones, for example cheese before spreads so a cheese spread counts as cheese. Lidl's web category in category_mapping.csv is only used when no rule matches. The rules are less precise than the mapping of the other supermarkets: a check against the Lidl products that also have a Dutch web category suggests that roughly 80 to 85% of Lidl products are categorised correctly.

**Note: Checks**: Before touching the database, the script checks that every category used in the mapping and the rules exists in shared_categories.csv, and that no category path is mapped twice. After categorising, it warns about mapping rows whose category path does not occur in the products (usually a spelling mistake) and lists the most common paths that did not receive a category.

**Note: Database transaction**: The shared categories and the category of every product are written in one database transaction, so they are either all saved or not at all.

**Note: Progress logging**: The script prints a report with the number and percentage of categorised products per supermarket and the number of products per shared category and supermarket. This is shown in the Docker logs thanks to the PYTHONUNBUFFERED setting in the Dockerfile.


## Docker configuration
The category importer is configured as a separate service named category_importer in docker-compose.yaml.

Its Dockerfile is located in code/importer/categories/Dockerfile.

The Dockerfile sets the working directory to:

/app

It copies the script and the three definition files into the image, so a changed mapping only requires rebuilding the image.

The importer depends on the PostgreSQL database being healthy and on the static importer completing successfully, because it needs the products to be loaded first.

The importer uses restart: "no" because it is a data-loading process rather than a continuously running service.


## Running the Script
From the project root, make sure Docker Desktop is running and that the .env file is available.

 _Option 1: Start the complete application:_
 docker compose up --build

This starts the PostgreSQL database, runs the static importer, then the category importer.


_Option 2: Run only the category importer:_
docker compose up -d database
docker compose run --rm --build --no-deps category_importer
The first command starts PostgreSQL. The second builds the importer image and runs the Python script in a temporary container, without starting the other importers (the products must already be in the database).
The --rm option removes this temporary container after execution. It does not remove the PostgreSQL database or its stored data.


#### Changing the categorisation
To change which shared category a product gets, edit category_mapping.csv or lidl_label_rules.csv and run the importer again (Option 2). To add a shared category, add it to shared_categories.csv first.

After a change, check the report in the output: the number of products per category, the warning about mapping rows that match nothing, and the list of paths without a category.


#### Running the importer again
The importer is safe to run as often as needed. It adds or updates the shared categories by name and only changes the category of products whose category is different from what is stored, so a second run without changes updates nothing. New products added by the live importer get a category the next time the importer runs.

The importer never deletes products. A shared category that is removed from shared_categories.csv stays in the Categories table until it is removed by hand.


#### Existing databases
initdb.sql creates the Categories table and the Products.categoryId column for a new database. Because initdb.sql only runs when a database is first created, the importer also creates the table and the column itself when they are missing (CREATE TABLE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS), so it works on existing databases without deleting them.


#### Import results
The importer was tested on a database with 47,020 products:
* AH, Jumbo and Plus: 100% of products received a shared category.
* Lidl: 99.6% (4,007 of 4,023) received a shared category. The 16 remaining products only have labels that say nothing about the product type, such as "en:Nutri-score: E".

A second run without changes updated no products.
