FROM python:3.12-slim

# Show Python print statements immediately in Docker logs (this tells python not to accumulate all the prints in a buffer (temporal memory) when executed inside a Docker container, but to show them immediately in the logs)
ENV PYTHONUNBUFFERED=1

WORKDIR /project/code/importer/static
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY staticdata_loading_database.py .

CMD [ "python3", "staticdata_loading_database.py" ]
