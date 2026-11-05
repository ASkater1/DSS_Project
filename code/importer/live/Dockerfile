FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY live.py .
CMD [ "python3", "live.py" ]