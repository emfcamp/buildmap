FROM python:3.9-slim-bullseye

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz git build-essential libpq-dev && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN git clone https://github.com/emfcamp/powerplan.git /powerplan
RUN pip install -e /powerplan
RUN pip install -e /buildmap

ENV PROJ_NETWORK ON
ENTRYPOINT ["/usr/local/bin/buildmap"]
