# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals

import json
import sys
import logging
import os
import shutil
import subprocess
import time
import argparse
from collections import defaultdict
from shapely.geometry import MultiPolygon

from .util import sanitise_layer
from .mapdb import MapDB


class BuildMap(object):
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        parser = argparse.ArgumentParser(description="Mapping workflow processor")
        parser.add_argument('--preseed', dest='preseed', action='store_true',
                            help="Preseed the tile cache")
        parser.add_argument('--static', dest='static', metavar='FILE',
                            help="""Export the map to a static PDF file at FILE
                                    (specify the layer with --layer)""")
        parser.add_argument('--layer', dest='layer', metavar='NAME',
                            help="Choose which raster layer to export statically")
        parser.add_argument('config', nargs="+",
                            help="""A list of config files. Later files override earlier ones, and
                                  relative paths in all config files are resolved relative to the
                                  path of the first file.""")
        self.args = parser.parse_args()

        self.config = self.load_config(self.args.config)
        self.db = MapDB(self.config['db_url'])

        # Resolve any relative paths with respect to the first config file
        self.base_path = os.path.dirname(os.path.abspath(self.args.config[0]))
        self.temp_dir = self.resolve_path(self.config['output_directory'])
        self.known_attributes = defaultdict(set)
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def load_config(self, config_files):
        config = {}
        for filename in config_files:
            with open(filename, 'r') as fp:
                config.update(json.load(fp))
        return config

    def resolve_path(self, path):
        return os.path.normpath(os.path.join(self.base_path, path))

    def import_dxf(self, dxf, table_name):
        """ Import the DXF into Postgres into the specified table name, overwriting the existing table. """
        if not os.path.isfile(dxf):
            raise Exception("Source DXF file %s does not exist" % dxf)

        self.log.info("Importing %s into PostGIS table %s...", dxf, table_name)
        try:
            subprocess.check_call(['ogr2ogr',
                                   '-s_srs', self.config['source_projection'],
                                   '-t_srs', self.config['source_projection'],
                                   '-sql', 'SELECT *, OGR_STYLE FROM entities',
                                   '-nln', table_name,
                                   '-f', 'PostgreSQL',
                                   '-overwrite',
                                   'PG:%s' % self.db.url,
                                   dxf])
        except OSError as e:
            self.log.error("Unable to run ogr2ogr: %s", e)
            sys.exit(1)

    def get_source_layers(self):
        """ Get a list of source layers. Returns a list of (tablename, layername) tuples """
        results = []
        for table_name, source_file in self.config['source_file'].items():
            layer_order = source_file.get('layers', {})
            file_layers = self.db.get_layers(table_name)

            # If we're configured to auto-import layers, add layers without a
            # defined order to the bottom of the layer order stack
            if source_file.get('auto_import_layers', "true") == "true":
                for layer in file_layers:
                    if layer not in layer_order:
                        results.append((table_name, layer))

            # Now add ordered layers on top of those
            for layer in layer_order:
                if layer in file_layers:
                    results.append((table_name, layer))
        return results

    def get_extents(self):
        """ Return extents of the map, in WGS84 coordinates (north, east, south, west) """
        if 'extents' in self.config:
            return self.config['extents']
        else:
            # Combine extents of all tables
            bboxes = []
            for table_name in self.config['source_file'].keys():
                bboxes.append(self.db.get_bounds(table_name))
            bounds = MultiPolygon(bboxes).bounds
            # Bounds here are (minx, miny, maxx, maxy)
            return [bounds[3], bounds[2], bounds[1], bounds[0]]

    def run(self):
        if not self.db.connect():
            return

        start_time = time.time()
        self.log.info("Generating map...")

        if self.args.static:
            # If we're rendering to a static file, keep the source projection intact
            self.dest_projection = self.config['source_projection']
        else:
            # If we're rendering to the web, we want to use Web Mercator
            self.dest_projection = 'epsg:3857'

        self.build_map()
        self.log.info("Layer IDs: %s",
                      ", ".join(sanitise_layer(layer[1]) for layer in self.get_source_layers()))
        for table, attrs in self.known_attributes.items():
            self.log.info("Known attributes for %s: %s", table, ", ".join(attrs))

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)

    def build_map(self):
        #  Import each source DXF file into PostGIS
        for table_name, source_file_data in self.config['source_file'].iteritems():
            if 'path' not in source_file_data:
                self.log.error("No path found for source %s", table_name)
                return
            self.import_dxf(source_file_data['path'], table_name)

        self.extents = self.get_extents()
        self.log.info("Map extents (N,E,S,W): %s", self.extents)

        # Do some data transformation on the PostGIS table
        self.log.info("Transforming data...")
        for table, tconfig in self.config['source_file'].items():
            self.db.clean_layers(table)
            if 'handle_prefix' in tconfig:
                self.db.prefix_handles(table, tconfig['handle_prefix'])
            self.known_attributes[table] |= self.db.extract_attributes(table)

        self.log.info("Running exporters...")
        mapnik_exporter = None
        exporters = []

        # Exporters are imported on demand here, so that modules required by a
        # single exporter don't prevent buildmap from running if that exporter is
        # unused

        if 'vector_layer' in self.config:
            from .exporter.geojson import GeoJSONExporter
            exporters.append(GeoJSONExporter(self, self.config, self.db))

        if 'raster_layer' in self.config:
            from .exporter.mapnik import MapnikExporter
            mapnik_exporter = MapnikExporter(self, self.config, self.db)
            exporters.append(mapnik_exporter)

        if 'mapbox_vector_layer' in self.config:
            from .exporter.tegola import TegolaExporter
            exporters.append(TegolaExporter(self, self.config, self.db))

        self.log.info("Exporting with: %s", ",".join(e.__class__.__name__ for e in exporters))

        for exporter in exporters:
            exporter.export()

        for plugin in self.config.get('plugins', []):
            self.log.info("Running plugin %s...", plugin.__name__)
            plugin(self, self.config, self.db).run()

        if self.args.preseed and mapnik_exporter is not None:
            mapnik_exporter.preseed()

    def generate_static(self, dest_layers):
        from .static import StaticExporter
        for layer_name, mapnik_xml in dest_layers.items():
            if layer_name.lower() == self.args.layer.lower():
                StaticExporter(self.config).export(mapnik_xml, self.args.static)
                break
        else:
            self.log.error("Requested static layer (%s) not found", self.args.layer)
            return
