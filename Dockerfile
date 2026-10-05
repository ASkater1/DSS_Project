FROM python:3.12-slim

WORKDIR /app
COPY code/requirements.txt ./
RUN pip3 install -r ./requirements.txt
#COPY app.py .
CMD [ "streamlit", "run", "app.py" ]