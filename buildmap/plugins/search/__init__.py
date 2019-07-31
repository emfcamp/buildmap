import os.path
import json
from sqlalchemy import text
from shapely import wkt


class SearchPlugin(object):
    """ Generate a JSON search index file to power JS search """

    def __init__(self, buildmap, _config, opts, db):
        self.db = db
        self.buildmap = buildmap
        self.opts = opts

    def get_data(self):
        data = []
        table = "site_plan"

        for layer in self.opts.get("layers", []):
            q = self.db.execute(
                text(
                    "SELECT ST_AsText(ST_Transform(wkb_geometry, 4326)), ogc_fid, text FROM %s WHERE layer = '%s'"
                    % (table, layer)
                )
            )
            for row in q:
                point = wkt.loads(row[0])
                data.append(
                    {
                        "gid": row[1],
                        "layer": layer,
                        "position": [point.x, point.y],
                        "name": row[2],
                    }
                )

        return data

    def run(self):
        data = self.get_data()

        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config["web_directory"]), "search"
        )

        try:
            os.makedirs(out_path)
        except FileExistsError:
            pass

        with open(os.path.join(out_path, "search.json"), "w") as f:
            json.dump(data, f)
