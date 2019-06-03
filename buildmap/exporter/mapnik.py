from __future__ import absolute_import
import os
from os import path
import distutils.spawn
import subprocess
import shutil
import json

from ..util import sanitise_layer
from . import Exporter


class MapnikExporter(Exporter):
    """ Take .mss (CartoCSS) files, transform them into Mapnik XML with Magnacarto,
        and render them with Tilestache.

        This one is a bit of a beast. """

    def export(self):
        #  Fetch source layer list from PostGIS
        source_layers = self.buildmap.get_source_layers()

        #  For each CartoCSS file (dest layer), generate a .mml file with all source layers
        mml_files = []
        for mss_file in self.get_layer_css():
            mml_files.append(self.write_mml_file(mss_file, source_layers))

        # Copy marker files to temp dir
        if self.config["symbol_path"] is not None:
            shutil.copytree(
                self.buildmap.resolve_path(self.config["symbol_path"]),
                path.join(self.buildmap.temp_dir, "symbols"),
            )

        #  Call magnacarto to build a Mapnik .xml file from each destination layer .mml file.
        self.dest_layers = {}
        # dest_layers is saved for use if preseed() is called
        for layer_name, mml_file in mml_files:
            self.dest_layers[layer_name] = self.generate_mapnik_xml(
                layer_name, mml_file
            )

    def get_layer_css(self):
        """ Return the paths of all CSS files (which correspond to destination layers)"""
        files = []
        for layer in self.config["raster_layer"]:
            files.append(
                path.join(
                    self.buildmap.resolve_path(self.config["stylesheet_path"]),
                    layer["stylesheet"],
                )
            )
        return [f for f in files if path.isfile(f)]

    def mml_layer(self, query, name):
        """ Generate a layer structure for a MML file"""
        data_source = {
            "extent": list(reversed(self.buildmap.get_bbox().bounds)),
            "table": query,
            "type": "postgis",
            "dbname": self.db.url.database,
        }
        if self.db.url.host:
            data_source["host"] = self.db.url.host
        if self.db.url.username:
            data_source["user"] = self.db.url.username
        if self.db.url.password:
            data_source["password"] = self.db.url.password

        layer_struct = {
            "name": sanitise_layer(name),
            "id": sanitise_layer(name),
            "srs": "+init=%s" % self.config["source_projection"],
            "extent": list(reversed(self.buildmap.get_bbox().bounds)),
            "Datasource": data_source,
        }
        return layer_struct

    def write_mml_file(self, mss_file, source_layers):
        layers = []
        for table_name, layer_name in source_layers:
            l = self.mml_layer(
                """(SELECT *, round(ST_Length(wkb_geometry)::numeric, 1) AS line_length
                                FROM %s WHERE layer='%s') as %s"""
                % (table_name, layer_name, table_name),
                layer_name,
            )
            layers.append(l)

            custom_layers = self.config["source_file"][table_name].get(
                "custom_layer", {}
            )
            for name, custom_layer in custom_layers.items():
                query = custom_layer["query"].format(table=table_name)
                sql = "(%s) AS %s" % (query, name)
                l = self.mml_layer(sql, name)
                layers.append(l)

        mml = {
            "Layer": layers,
            "Stylesheet": [path.basename(mss_file)],
            "srs": "+init=%s" % self.buildmap.dest_projection,
            "name": path.basename(mss_file),
        }

        # Magnacarto doesn't seem to resolve .mss paths properly so copy the stylesheet to our temp dir.
        shutil.copyfile(
            mss_file, path.join(self.buildmap.temp_dir, path.basename(mss_file))
        )

        dest_layer_name = path.splitext(path.basename(mss_file))[0]
        dest_file = path.join(self.buildmap.temp_dir, dest_layer_name + ".mml")
        with open(dest_file, "w") as fp:
            json.dump(mml, fp, indent=2, sort_keys=True)

        return (dest_layer_name, dest_file)

    def generate_mapnik_xml(self, layer_name, mml_file):
        # TODO: magnacarto error handling
        output = subprocess.check_output(["magnacarto", "-mml", mml_file])

        output_file = path.join(self.buildmap.temp_dir, layer_name + ".xml")
        with open(output_file, "w") as fp:
            fp.write(output)

        return output_file

    def generate_tilestache_config(self, dest_layers):
        tilestache_config = {
            "cache": {
                "name": "Disk",
                "path": self.config["tile_cache_dir"],
                "dirs": "portable",
            },
            "layers": {},
        }

        w, s, e, n = self.buildmap.get_bbox().bounds
        center = self.buildmap.get_center()
        for layer_name, xml_file in dest_layers.items():
            tilestache_config["layers"][layer_name] = {
                "provider": {"name": "mapnik", "mapfile": xml_file},
                "metatile": {"rows": 4, "columns": 4, "buffer": 64},
                "bounds": {
                    "low": self.config["zoom_range"][0],
                    "high": self.config["zoom_range"][1],
                    "north": n,
                    "east": e,
                    "south": s,
                    "west": w,
                },
                "preview": {
                    "lat": center.y,
                    "lon": center.x,
                    "zoom": self.config["zoom_range"][0],
                    "ext": "png",
                },
            }

        # Add a vector/GeoJSON layer for each DXF
        for source_table in self.config["source_file"].keys():
            tilestache_config["layers"]["vector_%s" % source_table] = {
                "provider": {
                    "name": "vector",
                    "driver": "PostgreSQL",
                    "parameters": {
                        "dbname": self.db.url.database,
                        "user": self.db.url.username,
                        "host": self.db.url.host,
                        "port": self.db.url.port,
                        "table": source_table,
                    },
                }
            }

        with open(path.join(self.buildmap.temp_dir, "tilestache.json"), "w") as fp:
            json.dump(tilestache_config, fp)

    def generate_layers_config(self):
        layers = []
        for layer in self.config["raster_layer"]:
            layers.append((layer["name"], layer))

        layers = sorted(layers, key=lambda l: l[1].get("z-index", 0))

        layer_list = []
        for layer in layers:
            layer_list.append(
                {
                    "name": layer[0],
                    "path": path.splitext(path.basename(layer[1]["stylesheet"]))[0],
                    "visible": layer[1].get("visible", "true") == "true",
                }
            )

        result = {
            "extents": list(reversed(self.buildmap.get_bbox().bounds)),
            "base_url": self.config.get("base_url", "/"),
            "zoom_range": self.config["zoom_range"],
            "layers": layer_list,
        }

        with open(os.path.join(self.config["web_directory"], "config.json"), "w") as fp:
            json.dump(result, fp)

    def preseed(self):
        """ Pre-generate tiles with Tilestache """
        self.log.info("Preseeding layers %s", self.dest_layers.keys())
        for filename in ("tilestache-seed.py", "tilestache-seed"):
            tilestache_seed = distutils.spawn.find_executable(filename)
            if tilestache_seed is not None:
                break

        zoom_levels = [
            str(l)
            for l in range(
                self.config["zoom_range"][0], self.config["zoom_range"][1] + 1
            )
        ]
        for layer in self.dest_layers:
            subprocess.call(
                [tilestache_seed, "-x", "-b"]
                + [str(c) for c in list(reversed(self.buildmap.get_bbox().bounds))]
                + [
                    "-c",
                    path.join(self.buildmap.temp_dir, "tilestache.json"),
                    "-l",
                    layer,
                ]
                + zoom_levels
            )
