FROM python:3.7
WORKDIR /buildmap
COPY . /buildmap
RUN pip install -e /buildmap
