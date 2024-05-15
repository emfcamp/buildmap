Buildmap
========

A GIS workflow pipeline for designing festivals. Buildmap has been
used for [Electromagnetic Field](https://www.emfcamp.org),
[Chaos Computer Club](https://ccc.de), and [IFCAT](https://ifcat.org)
hacker camps in Europe.

Buildmap takes a CAD site plan in DXF format and produces a clean
PostGIS geodatabase as well as a tileserver configuration for rendering
the map on the web. The recommended output format is [Mapbox
Vector Tiles](https://docs.mapbox.com/vector-tiles/reference/) via 
[Tegola](https://tegola.io/), for vector rendering with 
[Maplibre GL JS](https://maplibre.org/) or
[OpenLayers](https://openlayers.org/).

Buildmap has an extensible plugin system and [plugins exist](buildmap/plugins)
for power and network planning, statistics, in-browser search,
and translation.

It allows you to visualise complex, multi-layered site plans in a
simple way.

![Map of CCCamp 2019](/docs/cccamp2019.png?raw=true)

A Diagram
=========

![buildmap diagram](/docs/diagram.png?raw=true)

Installation
============

Docker is the preferred deployment method for buildmap as it is quite
sensitive to dependency versions. You can fetch the latest version
with `docker pull ghcr.io/emfcamp/buildmap:latest`.

Source Files
============

You will need at least one `.dxf` file to use as a source.

Web Viewer
==========

You will need a website with a javascript map viewer to view the
generated tiles. Both OpenLayers 3 and Maplibre GL JS work well.

Configuration
=============

You need to create two configuration files - one (local.conf) will contain
the host-specific configuration (paths and database details), the other
(map.conf) will contain the rendering configuration for your map.

Example config files can be found in the [config directory](/config).

Credits
=======

* [Russ Garrett](https://github.com/russss) ([Electromagnetic Field](https://www.emfcamp.org))
* [Redlizard](https://github.com/redlizard) (OHM2013 and SHA2017)

* [Raleway](https://github.com/impallari/Raleway) fonts are licensed under the SIL Open Font License, Version 1.1.
  This license is available at: http://scripts.sil.org/OFL
  Copyright (c) 2010, Matt McInerney (matt@pixelspread.com),  
  Copyright (c) 2011, Pablo Impallari (www.impallari.com|impallari@gmail.com),  
  Copyright (c) 2011, Rodrigo Fuenzalida (www.rfuenzalida.com|hello@rfuenzalida.com), with Reserved Font Name Raleway  