from __future__ import absolute_import
import yaml
import json
import logging
import os
from os import path
import time
from sqlalchemy import text

# SQL function to create polygons from closed linestrings
SQL_FUNCTIONS = ["""CREATE OR REPLACE FUNCTION close_linestrings(geom geometry) RETURNS geometry AS $$
BEGIN
  IF ST_IsClosed(geom) THEN
    RETURN ST_MakePolygon(geom);
  ELSE
    RETURN geom;
  END IF;
END;
$$ LANGUAGE plpgsql;"""]


class GeoJSONExport(object):
    def __init__(self, buildmap, config, db):
        self.log = logging.getLogger(__name__)
        self.buildmap = buildmap
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.db = db
        self.output_dir = os.path.join(self.config.output_directory, 'vector')

    def run_query(self, query, **kwargs):
        return self.db.execute(text(query), **kwargs).fetchall()

    def run(self):
        start_time = time.time()
        self.log.info("Exporting GeoJSON layers...")

        for func in SQL_FUNCTIONS:
            self.db.execute(text(func))

        try:
            os.mkdir(self.output_dir)
        except OSError:
            pass

        layer_file = path.join(self.config.styles, 'vector.yaml')
        if not path.isfile(layer_file):
            self.log.error("Can't find vector layer list (%s).", layer_file)
            return
        with open(layer_file, 'r') as f:
            layers = yaml.load(f)

        for layer_name, source_layers in layers.items():
            self.log.info("Exporting vector layer %s...", layer_name)
            self.generate_layer(layer_name, source_layers)

        self.generate_layer_index(layers)

        self.log.info("GeoJSON Generation complete in %.2f seconds", time.time() - start_time)

    def generate_layer(self, name, source_layers):
        attributes = self.buildmap.known_attributes | set(['entityhandle', 'subclasses'])

        attributes_str = ",".join(attributes)
        if len(attributes) > 0:
            attributes_str += ','
        query = """SELECT layer, %s ST_AsGeoJSON(ST_Transform(close_linestrings(wkb_geometry), 4326)) AS geojson
                    FROM site_plan WHERE layer = ANY (:layers)""" % attributes_str

        result = []

        for feature in self.run_query(query, layers=source_layers):
            gj = {"type": "Feature",
                  "geometry": json.loads(feature['geojson']),
                  "properties": {}}
            gj['properties']['layer'] = feature['layer']
            for attr in attributes:
                if attr in feature and feature[attr] is not None:
                    gj['properties'][attr] = feature[attr]
            result.append(gj)

        geojson = {
            'type': 'FeatureCollection',
            'crs': {
                'type': 'name',
                'properties': {
                    'name': 'EPSG:4326'
                }
            },
            'features': result
        }

        with open(os.path.join(self.output_dir, '%s.json' % name), 'w') as fp:
            json.dump(geojson, fp)

    def generate_layer_index(self, layers):
        vector_layers = []
        for layer_name in layers.keys():
            vector_layers.append({"name": layer_name,
                                  "source": "%s.json" % layer_name})
        with open(os.path.join(self.config.output_directory, 'vector_layers.json'), 'w') as fp:
            json.dump(vector_layers, fp)
