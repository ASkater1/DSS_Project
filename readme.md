# INFODSS Dashboard Group 4 - Food availability dashboard
## by:
- Jari van Polen
- Matthijs van Oord
- Tobias Buiten
- Tim Kläring
- Marc Avila Pedemonte
- Floris Smit

# Architecture of the Dashboard
The Dashboard application is divided into multiple "services"/containers with each having a specific task to focus on.
Some services like the data base can just be reused from publicly available images. Other services (Sub-Processes) are programmed by our group and their source code is in a sub-folder of the code directory, which contains all the data to run 
 * requirements.txt for a list of python librarys required during the actual run of the container.
 * Dockerfile describing how the application is put together before running it and which command is used to get it starting
 * app.py to contain the actual running part
 * <Subprocess>.md to contain a short summary of what the Process is actually doing, which environment variables it might access and what accesses are required for it.

## How to run the dashboard locally
### Requirements:
* Network Connection
* **Docker (+Compose)** installed
* installed **Python >3.12**
* **Make** installed

### Starting a development instance
1. run *make develop* inside a terminal in the root directory of the repository.
2. Once running you can access your dashboard via http://localhost:8501
>*The Development instance is configured in a Way, that allows it to rebuild/restart each container where a source code change was detected. You will need to keep the terminal running and can follow the log to see if your change was actually detected and the container rebuild.*

### Start order of the containers
The dashboard container is started last, so it never shows an empty database. It waits for:
* the *database* to be healthy
* the importers to be finished: *static_importer*, *static_municipalities_importer*, *category_importer*, *financial_importer* and *live*

*basket* and *modelling* are not waited for yet, as the dashboard does not use their data.
>*If one of the importers fails, the dashboard will not be started. Check the log of that importer with docker compose logs \<service name\>. You can still start the dashboard on its own with docker compose up -d --no-deps visualization.*

### Configuring the setup 
#### (optional with make installed!)
1. Run *make .env* to recreate a Environment variable set with the default values
2. Edit the .env file to your liking, if you dont want default password/user setups.

### All the other deployment stuff
You might try the terminal command *make help* to find all other available targets.