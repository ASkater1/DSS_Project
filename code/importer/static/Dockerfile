FROM python:3.12-slim

WORKDIR /project/code/importer/static
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY staticdata_loading_database.py .
COPY staticdata_loading_database_municipalities.py .

CMD [ "sh", "-c", "python3 staticdata_loading_database.py && python3 staticdata_loading_database_municipalities.py" ]
