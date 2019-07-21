# First build LibreDWG as a separate stage
FROM buildpack-deps:stretch AS libredwg
RUN apt-get update && apt-get install -y texinfo && apt-get clean
RUN git clone --branch 0.8 https://github.com/LibreDWG/libredwg /build
WORKDIR /build
RUN sh ./autogen.sh && ./configure && make && make install

FROM python:3.7-stretch
COPY --from=libredwg /usr/local/bin/* /usr/bin/
COPY --from=libredwg /usr/local/lib/libredwg* /usr/lib/
RUN ldconfig

RUN apt-get update && \
	apt-get install -y gdal-bin graphviz && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /buildmap
COPY . /buildmap
RUN pip install -e /buildmap

ENTRYPOINT ["/usr/local/bin/buildmap"]
