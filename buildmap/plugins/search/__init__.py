import json
from sqlalchemy import text
from shapely import wkt
from pathlib import Path
from ...main import BuildMap
from ...mapdb import MapDB


class SearchPlugin(object):
    """Generate a JSON search index file to power JS search"""

    def __init__(self, buildmap: BuildMap, _config, opts, db: MapDB):
        self.db = db
        self.buildmap = buildmap
        self.opts = opts

    def get_data(self):
        data = []

        for table, layer in self.buildmap.get_source_layers():
            if layer not in self.opts.get("layers", []):
                continue

            cols = ["text"] + self.opts.get("columns", [])
            # Add any translated columns
            cols += [
                attr
                for attr in self.buildmap.known_attributes[table]
                if attr.startswith("text_")
            ]
            # Filter out columns which don't exist in the table
            cols = set(cols) & set(self.buildmap.known_attributes[table])

            if len(cols) == 0:
                raise ValueError("No searchable columns for layer %s" % layer)

            if "text" not in cols:
                raise ValueError("No 'text' column for layer %s" % layer)

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

        out_path = self.buildmap.resolve_path(
            self.opts.get(
                "output_path",
                Path(self.buildmap.config["web_directory"]) / "search" / "search.json",
            )
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w") as f:
            json.dump(data, f)
