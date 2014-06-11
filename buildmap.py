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

from collections import defaultdict

class BuildMap(object):

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.generated_layers = set()  # Layers for which we've already generated shapefiles

    def find_layer(self, layer_regex, source_path):
        for source_layer in fileLayers(source_path):
            if re.match(layer_regex + "$", source_layer):
                return source_layer
        return None

    def import_layers(self, layers):
        """ Given a layer config, import the layers, copying the layer data from DXF to shapefile"""
        self.map_layers = defaultdict(list)
        for layer in layers:
            for component in layer['input']:
                component_layers = list(self.import_layer_component(component))
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
            yield parse_layer_config(filename, source_layer, component)

    def layer_names(self, layers):
        """ Yield all possible layer names and aliases """
        for layer in layers:
            yield layer['title']
            if 'aliases' in layer:
                for alias in layer['aliases']:
                    yield alias

    def generate_layer_shapefile(self, source_path, source_layer, filename):
        if source_layer not in self.generated_layers:
            runCommands(makeShapeFiles(source_path, source_layer, filename))
            self.generated_layers.add(source_layer)

    def write_file(self, name, data):
        with open(name, 'w') as fp:
            fp.write(data)

    def build_map(self, mapDir, layers):
        self.log.info("Generating map...")
        os.chdir(mapDir)
        tilesDir = self.config.output_directory + "/tiles"
        tempTilesDir = tilesDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        oldTilesDir = tilesDir + "-old"

        self.import_layers(layers)

        self.log.info("Generating mapfile...")
        self.write_file('buildmap.map', map.render_mapfile(self.map_layers, self.config))

        self.log.info("Generating 'tilecache.cfg'...")
        self.write_file('tilecache.cfg', tilecache.render_tilecache_file(self.map_layers, config))

        for filename in config.mapExtraFiles:
            shutil.copy(filename, ".")

        return
        commands = []
        for layer in layers.layers:
            commands.append("tilecache_seed.py '%s' %s" % (layer['title'], len(config.resolutions)))
        print "Generating tiles..."
        runCommands(commands)

        shutil.rmtree(oldTilesDir, True)
        if os.path.exists(tilesDir):
            shutil.move(tilesDir, oldTilesDir)
        shutil.move(tempTilesDir, tilesDir)

        print "Writing 'layers.def'..."
        layersDefStream = open(config.output_directory + '/layers.def', 'w')
        layersDefStream.write(layersDefFile)
        layersDefStream.close()

        #print "Writing 'index.html'..."
        #htmlStream = open(config.output_directory + '/index.html', 'w')
        #htmlStream.write(htmlFile)
        #htmlStream.close()

        os.chdir("/")
        shutil.rmtree(mapDir, True)
        shutil.rmtree(oldTilesDir, True)

if __name__ == '__main__':
    #mapDir = tempfile.mkdtemp("-buildmap")
    #build_map(mapDir)
    bm = BuildMap(config)
    bm.build_map('/Users/russ/emf/buildmap/test', layers.layers)
