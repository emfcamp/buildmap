# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals

import json
import logging
import os
import shutil
import subprocess
import time
import argparse
import hcl
import distutils.spawn
from os import path

from .util import sanitise_layer, iterate_hcl
from .vector import VectorExporter
from .static import StaticExporter
from .mapdb import MapDB


class BuildMap(object):
    def __init__(self):
        self.log = logging.getLogger(__name__)
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
        self.known_attributes = set()
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def load_config(self, config_files):
        config = {}
        for filename in config_files:
            with open(filename, 'r') as fp:
                config.update(hcl.load(fp))
        return config

    def resolve_path(self, path):
        return os.path.normpath(os.path.join(self.base_path, path))

    def import_dxf(self, dxf, table_name):
        """ Import the DXF into Postgres into the specified table name, overwriting the existing table. """
        if not os.path.isfile(dxf):
            raise Exception("Source DXF file %s does not exist" % dxf)

        self.log.info("Importing %s into PostGIS table %s...", dxf, table_name)
        subprocess.check_call(['ogr2ogr',
                               '-s_srs', self.config['source_projection'],
                               '-t_srs', self.config['source_projection'],
                               '-sql', 'SELECT *, OGR_STYLE FROM entities',
                               '-nln', table_name,
                               '-f', 'PostgreSQL',
                               '-overwrite',
                               'PG:%s' % self.db.url,
                               dxf])

    def get_source_layers(self):
        """ Get a list of source layers. Returns a list of (tablename, layername) tuples """
        results = []
        for table_name, source_file in self.config['source_file'].items():
            layer_order = source_file.get('layers', {})
            file_layers = self.db.get_layers(table_name)

            # If we're configured to auto-import layers, add layers without a
            # defined order to the bottom of the layer order stack
            if source_file.get('auto_import_layers', True):
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
        files = []
        for name, layer in self.config['raster_layer'].items():
            files.append(path.join(self.resolve_path(self.config['stylesheet_path']), layer['stylesheet']))
        return [f for f in files if path.isfile(f)]

    def mml_layer(self, query, name):
        data_source = {
            'extent': self.config['extents'],
            'table': query,
            'type': 'postgis',
            'dbname': self.db.url.database
        }
        if self.db.url.host:
            data_source['host'] = self.db.url.host
        if self.db.url.username:
            data_source['user'] = self.db.url.username
        if self.db.url.password:
            data_source['password'] = self.db.url.password

        layer_struct = {
            'name': sanitise_layer(name),
            'id': sanitise_layer(name),
            'srs': "+init=%s" % self.config['source_projection'],
            'extent': self.config['extents'],
            'Datasource': data_source
        }
        return layer_struct

    def write_mml_file(self, mss_file, source_layers):
        layers = []
        for table_name, layer_name in source_layers:
            l = self.mml_layer("""(SELECT *, round(ST_Length(wkb_geometry)::numeric, 1) AS line_length
                                FROM %s WHERE layer='%s') as %s""" % (table_name, layer_name, table_name),
                               layer_name)
            layers.append(l)

            custom_layers = self.config['source_file'][table_name].get('custom_layer', {})
            for name, custom_layer in iterate_hcl(custom_layers):
                query = custom_layer['query'].format(table=table_name)
                sql = "(%s) AS %s" % (query, name)
                l = self.mml_layer(sql, name)
                layers.append(l)

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

    def generate_layers_config(self):
        layers = []
        for name, layer in self.config['raster_layer'].items():
            layers.append((name, layer))

        layers = sorted(layers, key=lambda l: l[1].get('z-index', 0))

        layer_list = []
        for layer in layers:
            layer_list.append({'name': layer[0],
                               'path': path.splitext(path.basename(layer[1]['stylesheet']))[0],
                               'visible': layer[1].get('visible', True)})

        result = {'extents': self.config['extents'],
                  'zoom_range': self.config['zoom_range'],
                  'layers': layer_list}

        with open(os.path.join(self.config['web_directory'], 'config.json'), 'w') as fp:
            json.dump(result, fp)

    def generate_tilestache_config(self, dest_layers):
        tilestache_config = {
            "cache": {
                "name": "Disk",
                "path": self.config['tile_cache_dir'],
                "dirs": "portable"
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
                    "low": self.config['zoom_range'][0],
                    "high": self.config['zoom_range'][1],
                    "north": self.config['extents'][0],
                    "east": self.config['extents'][1],
                    "south": self.config['extents'][2],
                    "west": self.config['extents'][3]
                },
                "preview": {
                    "lat": (self.config['extents'][0] + self.config['extents'][2]) / 2,
                    "lon": (self.config['extents'][1] + self.config['extents'][3]) / 2,
                    "zoom": self.config['zoom_range'][0],
                    "ext": "png"
                }
            }

        # Add a vector/GeoJSON layer for each DXF
        for source_table in self.config['source_file'].keys():
            tilestache_config['layers']['vector_%s' % source_table] = {
                "provider": {
                    "name": "vector",
                    "driver": "PostgreSQL",
                    "parameters": {
                        "dbname": self.db.url.database,
                        "user": self.db.url.username,
                        "host": self.db.url.host,
                        "port": self.db.url.port,
                        "table": source_table
                    }
                }
            }

        with open(path.join(self.temp_dir, "tilestache.json"), "w") as fp:
            json.dump(tilestache_config, fp)

    def preseed(self, layers):
        self.log.info("Preseeding layers %s", layers)
        for filename in ('tilestache-seed', 'tilestache-seed.py'):
            tilestache_seed = distutils.spawn.find_executable(filename)
            if tilestache_seed is not None:
                break

        zoom_levels = [str(l) for l in range(self.config['zoom_range'][0], self.config['zoom_range'][1] + 1)]
        for layer in layers:
            subprocess.call([tilestache_seed, "-b"] + [str(c) for c in self.config['extents']] +
                            ["-c", path.join(self.temp_dir, "tilestache.json"), "-l", layer] +
                            zoom_levels)

    def run(self):
        if not self.db.connect():
            return

        start_time = time.time()
        self.log.info("Generating map...")
        dest_layers = self.build_map()
        if self.args.static and self.args.layer:
            self.generate_static(dest_layers)
        else:
            self.generate_tiles(dest_layers)
            self.log.info("Layer IDs: %s",
                          ", ".join(sanitise_layer(layer[1]) for layer in self.get_source_layers()))
            self.log.info("Known attributes: %s", ", ".join(self.known_attributes))

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)

    def build_map(self):
        #  Import each source DXF file into PostGIS
        try:
            for table_name, source_file_data in self.config['source_file'].iteritems():
                self.import_dxf(source_file_data['path'], table_name)
        except Exception as e:
            self.log.error(e)
            return

        # Do some data transformation on the PostGIS table
        self.log.info("Transforming data...")
        for table in self.config['source_file'].keys():
            self.db.clean_layers(table)
            self.known_attributes |= self.db.extract_attributes(table)

        self.log.info("Generating map configuration...")
        #  Fetch source layer list from PostGIS
        source_layers = self.get_source_layers()

        #  For each CartoCSS file (dest layer), generate a .mml file with all source layers
        mml_files = []
        for mss_file in self.get_layer_css():
            mml_files.append(self.write_mml_file(mss_file, source_layers))

        # Copy marker files to temp dir
        if self.config['symbol_path'] is not None:
            shutil.copytree(self.resolve_path(self.config['symbol_path']),
                            path.join(self.temp_dir, 'symbols'))

        #  Call magnacarto to build a Mapnik .xml file from each destination layer .mml file.
        dest_layers = {}
        for layer_name, mml_file in mml_files:
            dest_layers[layer_name] = self.generate_mapnik_xml(layer_name, mml_file)

        return dest_layers

    def generate_tiles(self, dest_layers):
        self.generate_tilestache_config(dest_layers)
        self.generate_layers_config()

        if 'vector_layer' in self.config:
            VectorExporter(self, self.config, self.db).run()

        for plugin in self.config.get('plugins', []):
            self.log.info("Running plugin %s...", plugin.__name__)
            plugin(self, self.config, self.db).run()

        if self.args.preseed:
            self.preseed(dest_layers)

    def generate_static(self, dest_layers):
        for layer_name, mapnik_xml in dest_layers.items():
            if layer_name.lower() == self.args.layer.lower():
                StaticExporter(self.config).export(mapnik_xml, self.args.static)
                break
        else:
            self.log.error("Requested static layer (%s) not found", self.args.layer)
            return
