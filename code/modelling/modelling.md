# moddeling container

## Description
This service/container is responsible for all of the descriptive, predictive and prescriptive data moddeling that is required for the food security dashboard. As such it has to run after the importers, but before the vizualisation container/service can actually display anything usefull.

## Expected Input Files & Variables
The script expects the following CSV files to be located in the directory :
* none

* DB_HOST
* DB_NAME
* DB_USER
* DB_PASSWORD

## Dependencies
The required Python packages are listed in code/moddeling/requirements.txt

For local execution, they can be installed from the project root using:
(Be sure to make the database available to your local applications by exposing the port 5432 in the docker-compose.yml as commented out!)

python -m pip install -r code/importer/static/requirements.txt

When using Docker, the dependencies are installed automatically when building the importer image.

## Expected environment variables:
The database connection settings are loaded from a .env file located in the project root(look at .env.sample and copy used values into .env). :
* DB_HOST: (currently) PostgreSQL server hostname.
* DB_NAME: Database name.
* DB_USER: Database username.
* DB_PASSWORD: Database password.

## Code Structure
The script is organized into four main sections:
* @MatthijsOord

## Docker configuration
The moddeling container is configured as a separate service named moddeling in docker-compose.yaml.

Its Dockerfile is located in code/importer/static/Dockerfile.

The Dockerfile sets the working directory inside the container to:

/app

## Running the Script

@MatthijsOord please consider requirements here.

#### Protection Against Repeated Imports (RENAME IF REQUIRED)

@MatthijsOord please think about the moddeling container and if it needs something simmilar...