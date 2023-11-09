from __future__ import absolute_import
import csv
import datetime
import logging
import os
import shutil
import time
from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy import text

# from util import write_file
def write_file(name, data):
    with open(name, "w") as fp:
        fp.write(data)


from . import exportsql


class GpsexportPlugin(object):
    def __init__(self, buildmap, _config, opts, db):
        self.log = logging.getLogger(__name__)
        self.queries = exportsql.queries
        self.db = db
        self.buildmap = buildmap
        self.opts = opts
        self.env = Environment(
            loader=PackageLoader("buildmap.plugins.gpsexport", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def run_query(self, query):
        return self.db.execute(text(query)).fetchall()

    def generate_kml(self, dir, name, places):
        if "kml" not in places[0].keys():
            return
        template = self.env.get_template("kml.jinja")
        write_file(os.path.join(dir, name + ".kml"), template.render(places=places))
        if name in self.filesToList:
            self.filesToList[name].append("kml")
        else:
            self.filesToList[name] = ["kml"]

    def generate_csv(self, dir, name, places):
        with open(os.path.join(dir, name + ".csv"), "w") as csvfile:
            fieldnames = list(places[0].keys())
            fieldnames.sort()
            if "name" in fieldnames:
                fieldnames.insert(0, fieldnames.pop(fieldnames.index("name")))
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for place in places:
                writer.writerow({k: v for k, v in place.items() if k in fieldnames})
            if name in self.filesToList:
                self.filesToList[name].append("csv")
            else:
                self.filesToList[name] = ["csv"]

    def generate_html(self, dir, files):
        template = self.env.get_template("export-html.jinja")
        write_file(
            os.path.join(dir, "export.html"),
            template.render(files=files, name=self.opts.get("name")),
        )

    def run(self):
        start_time = time.time()
        self.log.info("Generating map GPS exports...")

        out_path = self.buildmap.resolve_path(self.buildmap.config["web_directory"])

        kmlDir = out_path + "/kml"
        csvDir = out_path + "/csv"

        results = {}

        self.log.info("Getting map data")
        for name, query in self.queries.items():
            self.log.info("Fetching %s" % (name))
            results[name] = self.run_query(query)

        self.log.info("Generating kml/csv files...")

        if not os.path.isdir(kmlDir):
            os.makedirs(kmlDir)
        if not os.path.isdir(csvDir):
            os.makedirs(csvDir)

        self.filesToList = {}
        for name, places in results.items():
            self.generate_kml(kmlDir, name, places)
            self.generate_csv(csvDir, name, places)

        self.log.info("Generaring html links page")
        self.generate_html(out_path, self.filesToList)

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)
