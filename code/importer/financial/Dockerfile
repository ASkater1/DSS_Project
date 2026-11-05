FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY financial_importer.py .

CMD [ "python3", "financial_importer.py" ]
