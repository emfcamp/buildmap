from __future__ import absolute_import
import json
import logging
import os
import time
from sqlalchemy import text
from .util import iterate_hcl

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


class VectorExporter(object):
    def __init__(self, buildmap, config, db):
        self.log = logging.getLogger(__name__)
        self.buildmap = buildmap
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.db = db
        self.output_dir = os.path.join(self.config['web_directory'], 'vector')

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

        for layer_name, layer in self.config['vector_layer'].items():
            self.log.info("Exporting vector layer %s...", layer_name)
            self.generate_layer(layer_name, layer['source_layers'])

        self.generate_layer_index()

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

    def generate_layer_index(self):
        vector_layers = []
        for layer_name, layer in self.config['vector_layer'].items():
            vector_layers.append({"name": layer_name,
                                  "source": "%s.json" % layer_name,
                                  "visible": layer.get('visible', True)})

        data = {"layers": vector_layers, "styles": self.generate_styles()}
        with open(os.path.join(self.config['web_directory'], 'vector_layers.json'), 'w') as fp:
            json.dump(data, fp)

    def generate_styles(self):
        styles = []
        for layer_name, layer in self.config['vector_layer'].items():
            for source_layer, style in iterate_hcl(layer.get('layer_style', [])):
                if 'layers' in style:
                    for source_layer in style['layers']:
                        styles.append({
                            "match": {"layer": source_layer},
                            "style": style
                        })
                else:
                    styles.append({
                        "match": {"layer": source_layer},
                        "style": style
                    })
        return styles
