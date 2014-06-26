import datetime
import os
import re
import shutil
import tempfile
import logging

import map
import tilecache
import html

import config
import layers

from util import sanitize, findFile, fileLayers, makeShapeFiles, runCommands, parse_layer_config

from collections import OrderedDict

logging.basicConfig(level=logging.INFO)

def write_file(name, data):
    with open(name, 'w') as fp:
        fp.write(data)


class BuildMap(object):

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.base_path, 'temp')
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)
        self.generated_layers = set()  # Layers for which we've already generated shapefiles

    def find_layer(self, layer_regex, source_path):
        for source_layer in fileLayers(source_path):
            if re.match(layer_regex + "$", source_layer):
                return source_layer
        return None

    def import_layers(self, layers):
        """ Given a layer config, import the layers, copying the layer data from DXF to shapefile"""
        self.map_layers = OrderedDict()
        for layer in layers:
            for component in layer['input']:
                component_layers = list(self.import_layer_component(component))
                if layer['title'] not in self.map_layers:
                    self.map_layers[layer['title']] = []
                self.map_layers[layer['title']] += component_layers

    def import_layer_component(self, component):
        for layer_regex in component['layers']:
            source_path = findFile(component['file'])
            if source_path is None:
                raise Exception("Couldn't find source file '%s'" % component['file'])

            source_layer = self.find_layer(layer_regex, source_path)
            if source_layer is None:
                logging.warn("Couldn't find configured layer %s in DXF files", layer_regex)
                continue
            filename = "%s-%s" % (sanitize(component['file']), sanitize(source_layer))
            self.generate_layer_shapefile(source_path, source_layer, filename)
            for config in parse_layer_config(filename, source_layer, component):
                yield config

    def layer_names(self, layers):
        """ Yield all possible layer names and aliases """
        for layer in layers:
            yield layer['title']
            if 'aliases' in layer:
                for alias in layer['aliases']:
                    yield alias

    def generate_layer_shapefile(self, source_path, source_layer, filename):
        if source_layer not in self.generated_layers:
            runCommands(makeShapeFiles(source_path, source_layer, filename, self.temp_dir))
            self.generated_layers.add(source_layer)

    def build_map(self, layers):
        self.log.info("Generating map...")
        tilesDir = self.config.output_directory + "/tiles"
        tempTilesDir = tilesDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        oldTilesDir = tilesDir + "-old"

        self.import_layers(layers)

        self.log.info("Generating mapfile...")
        write_file(os.path.join(self.temp_dir, 'buildmap.map'),
                   map.render_mapfile(self.map_layers, self.config))

        self.log.info("Generating 'tilecache.cfg'...")
        write_file(os.path.join(self.temp_dir, 'tilecache.cfg'),
                   tilecache.render_tilecache_file(self.map_layers, config, tempTilesDir))

        base_path = os.path.dirname(os.path.abspath(__file__))
        for filename in config.mapExtraFiles:
            shutil.copy(os.path.join(base_path, filename), self.temp_dir)

        commands = []
        tilecache_config = os.path.join(self.temp_dir, 'tilecache.cfg')
        for layer in layers:
            commands.append("%s -c %s '%s' %s" % (config.tilecache_seed_binary, tilecache_config,
                                                  layer['title'], len(config.resolutions)))
        self.log.info("Generating tiles...")
        runCommands(commands)

        shutil.rmtree(oldTilesDir, True)
        if os.path.exists(tilesDir):
            shutil.move(tilesDir, oldTilesDir)
        shutil.move(tempTilesDir, tilesDir)

        self.log.info("Writing 'layers.def'...")
        write_file(os.path.join(self.config.output_directory, 'layers.def'),
                   ",".join(self.layer_names(layers)))

        self.log.info("Writing 'layers.js'...")
        write_file(os.path.join(self.config.output_directory, 'layers.js'),
                   html.render_html_file(layers, self.map_layers, config))

if __name__ == '__main__':
    bm = BuildMap(config)
    bm.build_map(layers.layers)
