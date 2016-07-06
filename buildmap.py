import datetime
import os
from os import path
import shutil
import subprocess
import logging
import time

import psycopg2
import json
from collections import defaultdict
from jinja2 import Environment, PackageLoader

import config
from util import sanitise_layer, runCommands

logging.basicConfig(level=logging.INFO)


def parse_connection_string(cstring):
    return dict(item.split('=') for item in cstring.split(' '))


def write_file(name, data):
    with open(name, 'w') as fp:
        fp.write(data)


class BuildMap(object):

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.base_path, 'temp')
        self.db = psycopg2.connect(self.config.postgres_connstring)
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def import_dxf(self, dxf, table_name):
        """ Import the DXF into Postgres into the specified table name, overwriting the existing table. """
        self.log.info("Importing %s into PostGIS table %s...", dxf, table_name)
        subprocess.check_call(['ogr2ogr',
                               '-s_srs', 'epsg:%s' % self.config.source_projection,
                               '-t_srs', 'epsg:%s' % self.config.source_projection,
                               '-sql', 'SELECT *, OGR_STYLE FROM entities',
                               '-nln', table_name,
                               '-f', 'PostgreSQL',
                               '-overwrite',
                               'PG:%s' % self.config.postgres_connstring,
                               dxf])

    def clean_layers(self):
        cur = self.db.cursor()
        for table_name in self.config.source_files.keys():
            # Fix newlines in labels
            cur.execute("UPDATE %s SET text = replace(text, '^J', '\n')" % table_name)
            # Remove "SOLID" labels from fills
            cur.execute("UPDATE %s SET text = NULL WHERE text = 'SOLID'" % table_name)
        cur.execute("COMMIT")
        cur.close()

    def extract_attributes(self):
        """ Extract DXF extended attributes into columns so we can use them in Mapnik"""
        cur = self.db.cursor()
        for table_name in self.config.source_files.keys():
            known_attributes = set()
            attributes = defaultdict(list)
            cur.execute("BEGIN")
            cur.execute("SELECT ogc_fid, extendedentity FROM %s WHERE extendedentity IS NOT NULL" %
                        table_name)
            for record in cur:
                for attr in record[1].split(' '):
                    try:
                        name, value = attr.split(':', 1)
                    except ValueError:
                        # This is ambiguous to parse, I think it's GDAL's fault for cramming them
                        # into one field
                        self.log.error("Cannot extract attributes as an attribute field contains a space: %s",
                                       record[1])
                        return
                    known_attributes.add(name)
                    attributes[record[0]].append((name, value))

            # TODO: sanitise attribute names. There's a lot of SQL injection here.
            for attr_name in known_attributes:
                cur.execute("ALTER TABLE %s ADD COLUMN %s TEXT" % (table_name, attr_name))

            for ogc_fid, attrs in attributes.iteritems():
                for name, value in attrs:
                    cur.execute("UPDATE %s SET \"%s\" = '%s' WHERE ogc_fid = %s" %
                                (table_name, name.lower(), value, ogc_fid))

            cur.execute("COMMIT")

    def get_source_layers(self):
        """ Get a list of source layers. Returns a list of (tablename, layername) tuples """
        # Load in the layer ordering file if it exists
        layer_order = []
        layer_order_file = path.join(self.config.styles, 'layer_order')
        if path.isfile(layer_order_file):
            with open(layer_order_file, 'r') as f:
                layer_order = [line.strip() for line in f.readlines()]

        cur = self.db.cursor()
        results = []
        for table_name in self.config.source_files.keys():
            cur.execute("SELECT DISTINCT layer FROM %s" % table_name)
            file_layers = [row[0] for row in cur.fetchall()]

            # Add layers without a defined order to the bottom of the layer order stack
            for layer in file_layers:
                if layer not in layer_order:
                    results.append((table_name, layer))

            # Now add ordered layers on top of those
            for layer in layer_order:
                if layer in file_layers:
                    results.append((table_name, layer))
        cur.close()
        return results

    def get_layer_css(self):
        """ Return the paths of all CSS files (which correspond to destination layers)"""
        contents = [path.join(self.config.styles, fname)
                    for fname in os.listdir(self.config.styles) if '.mss' in fname]
        return [f for f in contents if path.isfile(f)]

    def write_mml_file(self, mss_file, source_layers):
        conn_info = parse_connection_string(self.config.postgres_connstring)
        layers = []
        for source_layer in source_layers:
            data_source = {
                'extent': self.config.extents,
                'table': "(SELECT * FROM %s WHERE layer='%s') as %s" % (source_layer[0],
                                                                        source_layer[1], source_layer[0]),
                'type': 'postgis',
                'dbname': conn_info['dbname']
            }
            if 'user' in conn_info:
                data_source['user'] = conn_info['user']

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
               'srs': '+init=epsg:%s' % self.config.dest_projection,
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

    def generate_tilecache_cfg(self, dest_layers, temp_tiles_dir):
        tilecache_config = os.path.join(self.temp_dir, 'tilecache.cfg')
        env = Environment(loader=PackageLoader('buildmap', 'templates'))
        template = env.get_template('tilecache.jinja')
        write_file(tilecache_config,
                   template.render(layers=dest_layers,
                                   config=config, cache_directory=temp_tiles_dir))
        return tilecache_config

    def generate_layers_js(self, layer_names):
        env = Environment(loader=PackageLoader('buildmap', 'templates'))
        template = env.get_template('layers-js.jinja')
        write_file(os.path.join(self.config.output_directory, 'layers.js'),
                   template.render(layers=layer_names, config=config))

    def build_map(self):
        start_time = time.time()
        self.log.info("Generating map...")
        tilesDir = self.config.output_directory + "/tiles"
        tempTilesDir = tilesDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        oldTilesDir = tilesDir + "-old"

        #  Import each source DXF file into PostGIS
        for table_name, dxf in self.config.source_files.iteritems():
            self.import_dxf(dxf, table_name)

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

        #  Call magnacarto to build a Mapnik .xml file from each destination layer .mml file.
        dest_layers = {}
        for layer_name, mml_file in mml_files:
            dest_layers[layer_name] = self.generate_mapnik_xml(layer_name, mml_file)

        #  Generate tilecache configuration
        self.log.info("Generating 'tilecache.cfg'...")
        tilecache_config = self.generate_tilecache_cfg(dest_layers, tempTilesDir)

        #  Execute tilecache on all layers
        commands = []
        for layer in dest_layers.keys():
            commands.append("%s -c %s '%s' %s" % (config.tilecache_seed_binary, tilecache_config,
                                                  layer, len(config.resolutions)))
        self.log.info("Generating tiles...")
        runCommands(commands)

        self.log.info("Moving new tiles into place...")
        shutil.rmtree(oldTilesDir, True)
        if os.path.exists(tilesDir):
            shutil.move(tilesDir, oldTilesDir)
        shutil.move(tempTilesDir, tilesDir)

        self.log.info("Writing 'layers.js'...")
        self.generate_layers_js(dest_layers.keys())

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)

if __name__ == '__main__':
    bm = BuildMap(config)
    bm.build_map()
