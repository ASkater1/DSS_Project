# How to run apps without the containerization part
1. make shure the database is running with `docker compose up -d database` from the project root

2. create a virtual environment to install the dependencys into (Execute inside the actual code folder!) via `python -m venv ./.venv/`

3. activate venv via `.venv\Scripts\activate` (Scripts=bin under linux!)

4. install dependencys via `pip install -r code/builder/requirements.txt`

5. source the .env file

5. run application via `python3.15? app.py` -> should connect to db 