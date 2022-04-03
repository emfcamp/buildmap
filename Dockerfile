FROM python:3.9-slim-bullseye

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz git build-essential libpq-dev && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN pip install git+https://github.com/emfcamp/powerplan.git@48ae217c2c6384653d4db066373bffdc1114598c#egg=powerplan
RUN pip install -e /buildmap

ENV PROJ_NETWORK ON
ENTRYPOINT ["/usr/local/bin/buildmap"]
