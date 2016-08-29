from __future__ import absolute_import
import csv
import datetime
import logging
import os
import shutil
import time
from jinja2 import Environment, PackageLoader
from sqlalchemy import text

from util import write_file
from . import exportsql


class GPSExport(object):
    def __init__(self, _, config, db):
        self.log = logging.getLogger(__name__)
        self.queries = exportsql.queries
        self.config = config
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.base_path, 'temp')
        self.db = db
        shutil.rmtree(self.temp_dir, True)
        os.makedirs(self.temp_dir)

    def run_query(self, query):
        return self.db.execute(text(query)).fetchall()

    def generate_kml(self, dir, name, places):
        if 'kml' not in places[0].keys():
            return
        env = Environment(loader=PackageLoader('buildmap', 'templates'))
        template = env.get_template('kml.jinja')
        write_file(os.path.join(dir, name + '.kml'),
                   template.render(places=places))
        if name in self.filesToList:
            self.filesToList[name].append('kml')
        else:
            self.filesToList[name] = ['kml']

    def generate_csv(self, dir, name, places):
        with open(os.path.join(dir, name + '.csv'), 'w') as csvfile:
            fieldnames = places[0].keys()
            fieldnames.sort()
            if 'name' in fieldnames:
                fieldnames.insert(0, fieldnames.pop(fieldnames.index('name')))
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for place in places:
                writer.writerow({k: v for k, v in place.items() if k in fieldnames})
            if name in self.filesToList:
                self.filesToList[name].append('csv')
            else:
                self.filesToList[name] = ['csv']

    def generate_html(self, dir, files):
        env = Environment(loader=PackageLoader('buildmap', 'templates'))
        template = env.get_template('export-html.jinja')
        write_file(os.path.join(dir, 'export.html'),
                   template.render(files=files))

    def run(self):
        start_time = time.time()
        self.log.info("Generating map GPS exports...")
        kmlDir = self.config.output_directory + "/kml"
        tempKmlDir = kmlDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        oldKmlDir = kmlDir + "-old"
        csvDir = self.config.output_directory + "/csv"
        tempCsvDir = csvDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        oldCsvDir = csvDir + "-old"

        results = {}

        self.log.info("Getting map data")
        for name, query in self.queries.iteritems():
            self.log.info("Fetching %s" % (name))
            results[name] = self.run_query(query)

        self.log.info("Generating kml/csv files...")
        os.mkdir(tempKmlDir)
        os.mkdir(tempCsvDir)
        self.filesToList = {}
        for name, places in results.iteritems():
            self.generate_kml(tempKmlDir, name, places)
            self.generate_csv(tempCsvDir, name, places)

        self.log.info("Moving new kml into place...")
        shutil.rmtree(oldKmlDir, True)
        if os.path.exists(kmlDir):
            shutil.move(kmlDir, oldKmlDir)
        shutil.move(tempKmlDir, kmlDir)

        self.log.info("Moving new csv into place...")
        shutil.rmtree(oldCsvDir, True)
        if os.path.exists(csvDir):
            shutil.move(csvDir, oldCsvDir)
        shutil.move(tempCsvDir, csvDir)

        self.log.info("Generaring html links page")
        self.generate_html(self.config.output_directory, self.filesToList)

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)
