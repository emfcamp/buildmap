FROM python:3.7-stretch

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN pip install -e /buildmap

ENTRYPOINT ["/usr/local/bin/buildmap"]
