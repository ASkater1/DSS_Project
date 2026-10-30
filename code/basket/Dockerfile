FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY basket.py .
CMD [ "python3", "modelling.py" ]