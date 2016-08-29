from __future__ import absolute_import
import json
import logging
import os
import shutil
import time
from sqlalchemy import text

from util import write_file


class GeoJSONExport(object):
    def __init__(self, buildmap, config, db):
        self.log = logging.getLogger(__name__)
        self.buildmap = buildmap
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.base_path, 'temp')
        self.db = db
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def run_query(self, query, **kwargs):
        return self.db.execute(text(query), **kwargs).fetchall()

    def run(self):
        start_time = time.time()
        self.log.info("Exporting GeoJSON layers...")

        attributes = ",".join(self.buildmap.known_attributes)

        source_layers = ["Power - 16-1", "Power - 32-1", "Power - 32-3", "Power - 63-3", "Power - 125-3",
                         "Power - Distro"]

        query = """SELECT layer, %s, ST_AsGeoJSON(ST_Transform(wkb_geometry, 4326)) AS geojson
                    FROM site_plan WHERE layer = ANY (:layers)""" % attributes

        result = []

        for feature in self.run_query(query, layers=source_layers):
            gj = {"type": "Feature",
                  "geometry": json.loads(feature['geojson']),
                  "properties": {}}
            gj['properties']['layer'] = feature['layer']
            for attr in self.buildmap.known_attributes:
                if attr in feature and feature[attr] is not None:
                    gj['properties'][attr] = feature[attr]
            result.append(gj)

        with open(os.path.join(self.config.output_directory, 'test.json'), 'w') as fp:
            json.dump(result, fp)
        self.log.info("GeoJSON Generation complete in %.2f seconds", time.time() - start_time)
