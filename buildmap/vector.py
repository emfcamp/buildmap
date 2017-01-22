from __future__ import absolute_import
import json
import logging
import os
import time
from sqlalchemy import text
from .util import iterate_hcl


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
        self.log.info("Exporting vector layers...")

        try:
            os.mkdir(self.output_dir)
        except OSError:
            pass

        for layer_name, layer in self.config['vector_layer'].items():
            self.log.info("Exporting vector layer %s...", layer_name)
            self.generate_layer(layer_name, layer['source_layers'])

        self.generate_layer_index()

        self.log.info("Vector layer generation complete in %.2f seconds", time.time() - start_time)

    def parse_text_style(self, encoded):
        # LABEL(f:"Arial",t:"A/V",s:2g,p:5,c:#000026)
        # LABEL(f:"Arial",t:"track 3 \"test\"",s:4g,p:5,c:#000026)
        if encoded[0:6] != "LABEL(":
            return None
        index = 6
        style = {}
        while True:
            if encoded[index] == ')':
                break
            pos = encoded.find(':', index)
            key = encoded[index:pos]
            index = pos + 1
            if encoded[index] == '"':
                i = index + 1
                value = ""
                while i < len(encoded):
                    if encoded[i:i + 2] == "\\\\":
                        value += "\\"
                        i += 2
                    elif encoded[i:i + 2] == "\\\"":
                        value += "\""
                        i += 2
                    elif encoded[i] == "\"":
                        break
                    else:
                        value += encoded[i]
                        i += 1
                index = i + 2
            else:
                pos = encoded.find(',', index)
                if pos == -1:
                    value = encoded[index:-1]
                    index += len(value)
                else:
                    value = encoded[index:pos]
                    index = pos + 1
            style[key] = value
        return style

    def generate_layer(self, name, source_layers):
        attributes = self.buildmap.known_attributes | set(['entityhandle', 'subclasses'])

        attributes_str = ",".join(attributes)
        if len(attributes) > 0:
            attributes_str += ','
        query = """SELECT layer, text, ogr_style, %s ST_AsGeoJSON(ST_Transform(wkb_geometry, 4326)) AS geojson
                    FROM site_plan WHERE layer = ANY (:layers)""" % attributes_str

        result = []

        for feature in self.run_query(query, layers=source_layers):
            gj = {"type": "Feature",
                  "geometry": json.loads(feature['geojson']),
                  "properties": {}}
            gj['properties']['layer'] = feature['layer']
            if feature['text'] is not None:
              gj['properties']['text'] = feature['text']
              style = self.parse_text_style(feature['ogr_style'])
              size_string_raw = style['s']
              pos = size_string_raw.find('g')
              size_string = size_string_raw[0:pos]
              size = float(size_string)
              gj['properties']['text_size'] = size
              if 'a' in style:
                gj['properties']['text_rotation'] = float(style['a'])
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
            json.dump(geojson, fp, indent=4)

    def generate_layer_index(self):
        vector_layers = []
        for layer_name, layer in self.config['vector_layer'].items():
            vector_layers.append({"name": layer_name,
                                  "source": "%s.json" % layer_name,
                                  "visible": layer.get('visible', "true") == "true"})

        data = {"layers": vector_layers, "styles": self.generate_styles()}
        with open(os.path.join(self.config['web_directory'], 'vector_layers.json'), 'w') as fp:
            json.dump(data, fp, indent=4)

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
