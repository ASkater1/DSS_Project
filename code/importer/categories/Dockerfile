FROM python:3.12-slim

# Print progress directly to the Docker logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY category_importer.py shared_categories.csv category_mapping.csv lidl_label_rules.csv ./

CMD [ "python3", "category_importer.py" ]
