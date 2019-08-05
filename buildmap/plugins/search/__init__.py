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
            cols = ["text"]
            # Add any translated columns
            cols += [
                attr
                for attr in self.buildmap.known_attributes[table]
                if attr.startswith("text_")
            ]

            q = self.db.execute(
                text(
                    """SELECT ST_AsText(ST_Transform(wkb_geometry, 4326)) AS geom, ogc_fid, %s
                        FROM %s
                        WHERE layer = '%s' AND text IS NOT NULL AND text != ''"""
                    % (",".join(cols), table, layer)
                )
            )
            for row in q:
                point = wkt.loads(row["geom"])
                record = {
                    "gid": row["ogc_fid"],
                    "layer": layer,
                    "position": [round(point.x, 5), round(point.y, 5)],
                }

                for col in cols:
                    record[col] = row[col].replace("-\n", "") if row[col] else None

                data.append(record)

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
