# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals

import json
import logging
import os
import shutil
import subprocess
import time
from collections import defaultdict
from os import path

import sqlalchemy
from sqlalchemy.sql import text

import config
from util import sanitise_layer


class BuildMap(object):
    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.db_url = sqlalchemy.engine.url.make_url(self.config.db_url)
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.base_path, 'output')
        self.known_attributes = set()
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def import_dxf(self, dxf, table_name):
        """ Import the DXF into Postgres into the specified table name, overwriting the existing table. """
        if not os.path.isfile(dxf):
            raise Exception("Source DXF file %s does not exist" % dxf)

        self.log.info("Importing %s into PostGIS table %s...", dxf, table_name)
        subprocess.check_call(['ogr2ogr',
                               '-s_srs', 'epsg:%s' % self.config.source_projection,
                               '-t_srs', 'epsg:%s' % self.config.source_projection,
                               '-sql', 'SELECT *, OGR_STYLE FROM entities',
                               '-nln', table_name,
                               '-f', 'PostgreSQL',
                               '-overwrite',
                               'PG:%s' % self.db_url,
                               dxf])

    def clean_layers(self):
        """ Tidy up some mess in Postgres which ogr2ogr makes when importing DXFs. """
        for table_name in self.config.source_files.keys():
            with self.db.begin():
                # Fix newlines in labels
                self.db.execute(text("UPDATE %s SET text = replace(text, '^J', '\n')" % table_name))
                # Remove "SOLID" labels from fills
                self.db.execute(text("UPDATE %s SET text = NULL WHERE text = 'SOLID'" % table_name))

    def extract_attributes(self):
        """ Extract DXF extended attributes into columns so we can use them in Mapnik"""
        for table_name in self.config.source_files.keys():
            with self.db.begin():
                self.extract_attributes_for_table(table_name)

    def extract_attributes_for_table(self, table_name):
        attributes = defaultdict(list)
        result = self.db.execute(text("""SELECT ogc_fid, extendedentity FROM %s
                                        WHERE extendedentity IS NOT NULL""" % table_name))
        for record in result:
            try:
                for attr in record[1].split(' '):
                    name, value = attr.split(':', 1)
                    self.known_attributes.add(name)
                    attributes[record[0]].append((name, value))
            except ValueError:
                # This is ambiguous to parse, I think it's GDAL's fault for cramming them
                # into one field
                self.log.error("Cannot extract attributes as an attribute field contains a space: %s",
                               record[1])
                continue

        for attr_name in self.known_attributes:
            self.db.execute(text("ALTER TABLE %s ADD COLUMN %s TEXT" % (table_name, attr_name)))

        for ogc_fid, attrs in attributes.iteritems():
            for name, value in attrs:
                self.db.execute(text("UPDATE %s SET %s = :value WHERE ogc_fid = :fid" %
                                     (table_name, name.lower())),
                                value=value, fid=ogc_fid)

    def get_source_layers(self):
        """ Get a list of source layers. Returns a list of (tablename, layername) tuples """
        # Load in the layer ordering file if it exists
        layer_order = []
        layer_order_file = path.join(self.config.styles, 'layer_order')
        if path.isfile(layer_order_file):
            with open(layer_order_file, 'r') as f:
                layer_order = [line.strip() for line in f.readlines()]

        results = []
        for table_name in self.config.source_files.keys():
            res = self.db.execute(text("SELECT DISTINCT layer FROM %s" % table_name))
            file_layers = [row[0] for row in res]

            # Add layers without a defined order to the bottom of the layer order stack
            for layer in file_layers:
                if layer not in layer_order:
                    results.append((table_name, layer))

            # Now add ordered layers on top of those
            for layer in layer_order:
                if layer in file_layers:
                    results.append((table_name, layer))
        return results

    def get_layer_css(self):
        """ Return the paths of all CSS files (which correspond to destination layers)"""
        contents = [path.join(self.config.styles, fname)
                    for fname in os.listdir(self.config.styles) if '.mss' in fname]
        return [f for f in contents if path.isfile(f)]

    def write_mml_file(self, mss_file, source_layers):
        layers = []
        for source_layer in source_layers:
            data_source = {
                'extent': self.config.extents,
                'table': """(SELECT *, round(ST_Length(wkb_geometry)::numeric, 1) AS line_length
                             FROM %s WHERE layer='%s') as %s""" % (source_layer[0],
                                                                   source_layer[1], source_layer[0]),
                'type': 'postgis',
                'dbname': self.db_url.database
            }
            if self.db_url.username:
                data_source['user'] = self.db_url.username

            layer_struct = {
                'name': sanitise_layer(source_layer[1]),
                'id': sanitise_layer(source_layer[1]),
                'srs': "+init=epsg:%s" % self.config.source_projection,
                'extent': self.config.extents,
                'Datasource': data_source
            }
            layers.append(layer_struct)

        mml = {'Layer': layers,
               'Stylesheet': [path.basename(mss_file)],
               'srs': '+init=epsg:3857',
               'name': path.basename(mss_file)
               }

        # Magnacarto doesn't seem to resolve .mss paths properly so copy the stylesheet to our temp dir.
        shutil.copyfile(mss_file, path.join(self.temp_dir, path.basename(mss_file)))

        dest_layer_name = path.splitext(path.basename(mss_file))[0]
        dest_file = path.join(self.temp_dir, dest_layer_name + '.mml')
        with open(dest_file, 'w') as fp:
            json.dump(mml, fp, indent=2, sort_keys=True)

        return (dest_layer_name, dest_file)

    def generate_mapnik_xml(self, layer_name, mml_file):
        # TODO: magnacarto error handling
        output = subprocess.check_output(['magnacarto', '-mml', mml_file])

        output_file = path.join(self.temp_dir, layer_name + '.xml')
        with open(output_file, 'w') as fp:
            fp.write(output)

        return output_file

    def generate_layers_config(self, layer_names):
        # keep the base layer at the bottom of the stack
        if 'base' in layer_names:
            layer_names.insert(0, layer_names.pop(layer_names.index('base')))

        result = {'base_url': self.config.urls[0],
                  'extents': self.config.extents,
                  'zoom_range': self.config.zoom_range,
                  'layers': layer_names}

        with open(os.path.join(self.config.output_directory, 'config.json'), 'w') as fp:
            json.dump(result, fp)

    def generate_tilestache_config(self, dest_layers):
        tilestache_config = {
            "cache": {
                "name": "Disk",
                "path": config.tilestache_cache_dir
            },
            "layers": {},
        }

        for layer_name, xml_file in dest_layers.items():
            tilestache_config['layers'][layer_name] = {
                "provider": {
                    "name": "mapnik",
                    "mapfile": xml_file,
                },
                "metatile": {
                    "rows": 4,
                    "columns": 4,
                    "buffer": 64
                },
                "bounds": {
                    "low": self.config.zoom_range[0],
                    "high": self.config.zoom_range[1],
                    "north": self.config.extents[0],
                    "east": self.config.extents[1],
                    "south": self.config.extents[2],
                    "west": self.config.extents[3]
                },
                "preview": {
                    "lat": (self.config.extents[0] + self.config.extents[2]) / 2,
                    "lon": (self.config.extents[1] + self.config.extents[3]) / 2,
                    "zoom": self.config.zoom_range[0],
                    "ext": "png"
                }
            }

        # Add a vector/GeoJSON layer for each DXF
        for source_table in self.config.source_files.keys():
            tilestache_config['layers']['vector_%s' % source_table] = {
                "provider": {
                    "name": "vector",
                    "driver": "PostgreSQL",
                    "parameters": {
                        "dbname": self.db_url.database,
                        "user": self.db_url.username,
                        "host": self.db_url.host,
                        "port": self.db_url.port,
                        "table": source_table
                    }
                }
            }

        with open(path.join(self.temp_dir, "tilestache.json"), "w") as fp:
            json.dump(tilestache_config, fp)

    def connect_db(self):
        engine = sqlalchemy.create_engine(self.db_url)
        try:
            self.db = engine.connect()
        except sqlalchemy.exc.OperationalError as e:
            self.log.error("Error connecting to database (%s): %s", self.db_url, e)
            return False
        self.log.info("Connected to PostGIS database %s", self.db_url)
        return True

    def build_map(self):
        if not self.connect_db():
            return
        start_time = time.time()
        self.log.info("Generating map...")

        #  Import each source DXF file into PostGIS
        try:
            for table_name, dxf in self.config.source_files.iteritems():
                self.import_dxf(dxf, table_name)
        except Exception as e:
            self.log.error(e)
            return

        # Do some data transformation on the PostGIS table
        self.log.info("Transforming data...")
        self.clean_layers()
        self.extract_attributes()

        self.log.info("Generating map configuration...")
        #  Fetch source layer list from PostGIS
        source_layers = self.get_source_layers()

        #  For each CartoCSS file (dest layer), generate a .mml file with all source layers
        mml_files = []
        for mss_file in self.get_layer_css():
            mml_files.append(self.write_mml_file(mss_file, source_layers))

        # Copy marker files to temp dir
        if self.config.markers is not None:
            shutil.copytree(self.config.markers, path.join(self.temp_dir, 'markers'))

        #  Call magnacarto to build a Mapnik .xml file from each destination layer .mml file.
        dest_layers = {}
        for layer_name, mml_file in mml_files:
            dest_layers[layer_name] = self.generate_mapnik_xml(layer_name, mml_file)

        self.generate_tilestache_config(dest_layers)
        self.generate_layers_config(dest_layers.keys())

        for plugin in self.config.plugins:
            self.log.info("Running plugin %s...", plugin.__name__)
            plugin(self, self.config, self.db).run()

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bm = BuildMap(config)
    bm.build_map()
