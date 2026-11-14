FROM python:3.12-slim

WORKDIR /project/code/importer/product_links
COPY requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY product_link_importer.py ./

CMD ["python3", "product_link_importer.py"]
