FROM python:3.11-slim-bullseye

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz git build-essential libpq-dev spatialite-bin libsqlite3-mod-spatialite sqlite3 && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN git clone https://github.com/emfcamp/powerplan.git /powerplan
RUN pip install -e /powerplan
RUN pip install -e /buildmap

ENV PROJ_NETWORK ON
ENV PYTHONUNBUFFERED 1
ENTRYPOINT ["/usr/local/bin/buildmap"]
