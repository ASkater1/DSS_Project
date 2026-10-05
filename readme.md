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
0. Make sure, you copied the .env.sample to .env and overwritten the personally needed configuration!
1. In the root repository folder use ´docker compose up´ (add a ´-d´ for starting in the background)
2. Once running you can access your dashboard via http://localhost:8501 (Or whatever port was specified in your .env)
