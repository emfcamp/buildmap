FROM python:3.7

RUN apt-get update && \
	apt-get install -y gdal-bin && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN pip install -e /buildmap

ENTRYPOINT ["/usr/local/bin/buildmap"]
