INFODSS Dashboard Group X
- Jari van Polen
- Matthijs van Oord
- Tobias Buiten
- Tim Kläring
- Marc Avila Pedemonte
- Floris Smit

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

### Configuring the setup
1. Run *make .env* to recreate a Environment variable set with the default values
2. Edit the .env file to your liking, if you dont want default password/user setups.

### All the other deployment stuff
You might try the terminal command *make help* to find all other available targets.