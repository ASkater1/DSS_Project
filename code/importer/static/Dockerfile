FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY staticdata_loading_database.py .
CMD [ "python3", "staticdata_loading_database.py" ]