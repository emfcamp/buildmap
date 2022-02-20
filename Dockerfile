FROM python:3.9-slim-bullseye

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz git build-essential libpq-dev && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN pip install git+git://github.com/emfcamp/powerplan.git@6f3d2bafdf276da4f0ec8436961139f48d673f9e#egg=powerplan
RUN pip install -e /buildmap

ENV PROJ_NETWORK ON
ENTRYPOINT ["/usr/local/bin/buildmap"]
