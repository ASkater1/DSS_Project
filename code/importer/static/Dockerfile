FROM python:3.12-slim

WORKDIR /project/code/importer/static
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY staticdata_loading_database.py .
CMD [ "python3", "staticdata_loading_database.py" ]