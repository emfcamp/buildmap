import json
import sys
import logging
import os
import errno
import shutil
import subprocess
import time
import argparse
import importlib
from json.decoder import JSONDecodeError
from collections import defaultdict
from shapely.geometry import MultiPolygon, Polygon

from .util import sanitise_layer
from .mapdb import MapDB
from . import plugins  # noqa


def run():
    """Console script entry point"""
    logging.basicConfig(level=logging.INFO)
    bm = BuildMap()
    bm.run()


class BuildMap(object):
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        parser = argparse.ArgumentParser(description="Mapping workflow processor")
        parser.add_argument(
            "--preseed",
            dest="preseed",
            action="store_true",
            help="Preseed the tile cache",
        )
        parser.add_argument(
            "--static",
            dest="static",
            metavar="FILE",
            help="""Export the map to a static PDF file at FILE
                                    (specify the layer with --layer)""",
        )
        parser.add_argument(
            "--layer",
            dest="layer",
            metavar="NAME",
            help="Choose which raster layer to export statically",
        )
        parser.add_argument(
            "config",
            nargs="+",
            help="""A list of config files. Later files override earlier ones, and
                                  relative paths in all config files are resolved relative to the
                                  path of the first file.""",
        )
        self.args = parser.parse_args()

        self.config = self.load_config(self.args.config)
        self.db = MapDB(self.config["db_url"])
        self.bbox = None

        # Resolve any relative paths with respect to the first config file
        self.base_path = os.path.dirname(os.path.abspath(self.args.config[0]))
        self.temp_dir = self.resolve_path(self.config["output_directory"])
        self.known_attributes = defaultdict(set)
        shutil.rmtree(self.temp_dir, True)
        try:
            os.makedirs(self.temp_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    def load_config(self, config_files):
        config = {}
        for filename in config_files:
            try:
                with open(filename, "r") as fp:
                    config.update(json.load(fp))
            except JSONDecodeError as e:
                raise Exception("Error loading config file {}: {}".format(filename, e))
        return config

    def resolve_path(self, path):
        return os.path.normpath(os.path.join(self.base_path, path))

    def import_dxf(self, dxf, table_name):
        """Import the DXF into Postgres into the specified table name, overwriting the existing table."""
        if not os.path.isfile(dxf):
            raise Exception("Source DXF file %s does not exist" % dxf)

        self.log.info("Importing %s into PostGIS table %s...", dxf, table_name)
        try:
            subprocess.check_call(
                [
                    "ogr2ogr",
                    "--config",
                    "DXF_ENCODING",
                    "UTF-8",
                    "--config",
                    "DXF_INCLUDE_RAW_CODE_VALUES",
                    "TRUE",
                    "-s_srs",
                    self.config["source_projection"],
                    "-t_srs",
                    self.config["source_projection"],
                    "-sql",
                    "SELECT *, OGR_STYLE FROM entities",
                    "-nln",
                    table_name,
                    "-f",
                    "PostgreSQL",
                    "-lco",
                    "GEOMETRY_NAME=wkb_geometry",
                    "-overwrite",
                    f"PG:{self.db.url.render_as_string(False)}?application_name=buildmap",
                    dxf,
                ]
            )
        except OSError as e:
            self.log.error("Unable to run ogr2ogr: %s", e)
            sys.exit(1)

    def get_source_layers(self):
        """Get a list of source layers. Returns a list of (tablename, layername) tuples.

        Each layer name should only appear once in the result, even if it's present in
        multiple files.
        """
        results = []
        seen_layers = set()

        for table_name, source_file in self.config["source_file"].items():
            layer_order = source_file.get("layers", {})
            rename_layers = source_file.get("rename_layers", {})
            file_layers = self.db.get_layers(table_name)

            for layer in layer_order:
                layer = rename_layers.get(layer, layer)
                if layer in file_layers and layer not in seen_layers:
                    seen_layers.add(layer)
                    results.append((table_name, layer))

        for table_name, source_file in self.config["source_file"].items():
            rename_layers = source_file.get("rename_layers", {})
            file_layers = self.db.get_layers(table_name)
            # If we're configured to auto-import layers, add layers without a
            # defined order to the bottom of the layer order stack
            if source_file.get("auto_import_layers", False):
                for layer in file_layers:
                    layer = rename_layers.get(layer, layer)
                    if layer not in seen_layers:
                        seen_layers.add(layer)
                        results.insert(0, (table_name, layer))

        return results

    def get_bbox(self):
        """Return bounding box of the map, as a shapely Polygon in WGS84 coordinates.

        `bbox.bounds` will return the extents as minx, miny, maxx, maxy
        (W, S, E, N).
        """
        if self.bbox:
            return self.bbox
        elif "extents" in self.config:
            # Extents config is reversed
            n, e, s, w = self.config["extents"]
            self.bbox = Polygon([(e, n), (e, s), (w, s), (w, n), (e, n)])
        else:
            # Combine extents of all tables
            bboxes = []
            for table_name in self.config["source_file"].keys():
                bboxes.append(self.db.get_bounds(table_name))
            self.bbox = MultiPolygon(bboxes).envelope
        return self.bbox

    def get_center(self):
        """Return the center of the map, in WGS84 coordinates (lon, lat)"""
        centroid = self.get_bbox().centroid
        return list(centroid.coords[0])

    def run(self):
        if not self.db.connect():
            return

        start_time = time.time()
        self.log.info("Generating map...")

        if self.args.static:
            # If we're rendering to a static file, keep the source projection intact
            self.dest_projection = self.config["source_projection"]
        else:
            # If we're rendering to the web, we want to use Web Mercator
            self.dest_projection = "epsg:3857"

        self.build_map()
        self.log.info(
            "Layer IDs: %s",
            ", ".join(
                sorted(sanitise_layer(layer[1]) for layer in self.get_source_layers())
            ),
        )
        for table, attrs in self.known_attributes.items():
            self.log.info("Known attributes for %s: %s", table, ", ".join(attrs))

        self.log.info("Generation complete in %.2f seconds", time.time() - start_time)

    def build_map(self):
        #  Import each source DXF file into PostGIS
        for table_name, source_file_data in self.config["source_file"].items():
            if "path" not in source_file_data:
                self.log.error("No path found for source %s", table_name)
                return
            path = self.resolve_path(source_file_data["path"])
            self.import_dxf(path, table_name)

        self.log.info(
            "Map bounds (N, E, S, W): %s", list(reversed(self.get_bbox().bounds))
        )

        source_srid = self.config["source_projection"].split(":")[1]

        # Do some data transformation on the PostGIS table
        self.log.info("Transforming data...")
        self.db.create_bounding_layer("bounding_box", self.get_bbox())

        for table, tconfig in self.config["source_file"].items():
            # Remove entities which don't intersect the provided bounding box.
            # If there's a manually-supplied bounding box this allows us to strip out stuff which we don't want,
            # such as construction objects placed outside the map
            self.db.execute(
                f"""DELETE FROM {table} WHERE
                    NOT ST_Intersects(
                        wkb_geometry,
                        ST_Transform((SELECT wkb_geometry FROM bounding_box LIMIT 1), {source_srid})
                    )"""
            )
            for layer in tconfig.get("combine_lines", []):
                self.db.combine_lines(table, layer)
            self.db.clean_layers(table)
            if "handle_prefix" in tconfig:
                self.db.prefix_handles(table, tconfig["handle_prefix"])
            for layer in tconfig.get("force_polygon", []):
                self.db.force_polygon(table, layer)
            for layer in tconfig.get("smooth", []):
                self.db.smooth(table, layer)
            for layer_src, layer_dst in tconfig.get("rename_layers", {}).items():
                self.db.rename_layer(table, layer_src, layer_dst)
            self.known_attributes[table] |= self.db.extract_attributes(table)

        for plugin, opts in self.config.get("plugins", {}).items():
            try:
                pluginmod = importlib.import_module("." + plugin, "buildmap.plugins")
                self.log.info("Running plugin %s...", plugin)
            except ImportError as e:
                self.log.exception("Plugin %s not loaded: %s", plugin, e)
                continue
            plugincls = getattr(pluginmod, plugin.capitalize() + "Plugin")
            plugincls(self, self.config, opts, self.db).run()

        # Exporters are imported on demand here, so that modules required by a
        # single exporter don't prevent buildmap from running if that exporter is
        # unused
        self.log.info("Running exporters...")
        mapnik_exporter = None
        exporters = []

        if "vector_layer" in self.config:
            from .exporter.geojson import GeoJSONExporter

            exporters.append(GeoJSONExporter(self, self.config, self.db))

        if "raster_layer" in self.config:
            from .exporter.mapnik import MapnikExporter

            mapnik_exporter = MapnikExporter(self, self.config, self.db)
            exporters.append(mapnik_exporter)

        if "mapbox_vector_layer" in self.config:
            from .exporter.tegola import TegolaExporter

            exporters.append(TegolaExporter(self, self.config, self.db))

        self.log.info(
            "Exporting with: %s", ",".join(e.__class__.__name__ for e in exporters)
        )

        for exporter in exporters:
            exporter.export()

        if self.args.preseed and mapnik_exporter is not None:
            mapnik_exporter.preseed()

    def generate_static(self, dest_layers):
        from .static import StaticExporter

        for layer_name, mapnik_xml in dest_layers.items():
            if layer_name.lower() == self.args.layer.lower():
                StaticExporter(self.config).export(mapnik_xml, self.args.static)
                break
        else:
            self.log.error("Requested static layer (%s) not found", self.args.layer)
            return
