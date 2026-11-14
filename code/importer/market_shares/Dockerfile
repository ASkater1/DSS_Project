FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY market_shares_importer.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "market_shares_importer.py"]