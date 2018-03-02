from __future__ import absolute_import
import toml
from os import path
from ..util import sanitise_layer
from . import Exporter


class TegolaExporter(Exporter):
    """ Generate config for Tegola, which is a Mapbox Vector Tiles server.

        There are some "impedance mismatches" here - mostly due to the fact that
        a MVT layer can only have a single geometry type, and must not be a
        GeometryCollection (which is what DXF blocks become).
    """

    PROVIDER_NAME = "buildmap"
    # Tegola only supports Web Mercator (3857) and WGS84 (4326), so we
    # need to transform explicitly
    SRID = 3857

    def export(self):
        dest_file = path.join(self.buildmap.temp_dir, "tegola.toml")
        with open(dest_file, "w") as fp:
            toml.dump(self.generate_tegola_config(), fp)

    def get_layers(self):
        source = self.buildmap.get_source_layers()
        for table_name, layer_name in source:
            types = self.db.get_layer_type(table_name, layer_name)

            if types == ['ST_GeometryCollection']:
                # This layer only contains GeometryCollections.
                # Let's assume they're LineStrings.
                yield (table_name, layer_name,
                       self.get_layer_sql(table_name, layer_name, collection_type=2))
            elif len(types) == 1:
                # A single simple type. This is the easy case.
                yield (table_name, layer_name, self.get_layer_sql(table_name, layer_name))
            elif 'ST_GeometryCollection' in types:
                # No idea what to do here yet, bail
                self.log.warn("Skipping layer '%s/%s' because it has multiple geometry types, "
                              "including GeometryCollection (%s)",
                              table_name, layer_name, ", ".join(types))
                continue
            else:
                # Multiple simple types. Split them into different layers.
                for typ in types:
                    type_alias = typ.lower().split('_')[1]
                    yield (table_name, layer_name + '_' + type_alias,
                           self.get_layer_sql(table_name, layer_name, type_filter=typ))

    def generate_tegola_config(self):
        provider = {
            "name": self.PROVIDER_NAME,
            "type": "postgis",
            "database": self.db.url.database,
            "host": self.db.url.host,
            "port": self.db.url.port,
            "user": self.db.url.username,
            "password": self.db.url.password,
            "srid": self.SRID,
            "max_connections": 20,
            "layers": []
        }

        layers = list(self.get_layers())

        for table_name, layer_name, sql in layers:
            provider["layers"].append({
                "name": sanitise_layer(layer_name),
                "sql": sql
            })

        m = {
            "name": "buildmap",
            "bounds": list(reversed(self.buildmap.get_extents())),
            "center": self.buildmap.get_center() + [float(self.config['zoom_range'][0])],
            "layers": []
        }

        if type(self.config['mapbox_vector_layer']) is dict and \
                'attribution' in self.config['mapbox_vector_layer']:
            m['attribution'] = self.config['mapbox_vector_layer']['attribution']

        for table_name, layer_name, _ in layers:
            m["layers"].append({
                "provider_layer": "%s.%s" % (self.PROVIDER_NAME, sanitise_layer(layer_name)),
                "min_zoom": self.config['zoom_range'][0],
                "max_zoom": self.config['zoom_range'][1]
            })

        data = {
            "cache": {
                "type": "file",
                "basepath": "/tmp/tegola"
            },
            "providers": [provider],
            "maps": [m]
        }
        return data

    def get_layer_sql(self, table_name, layer_name, collection_type=None, type_filter=None):
        """ collection_type is:
                1 - Point
                2 - Linestring
                3 - Polygon
        """
        field = 'wkb_geometry'

        if collection_type:
            field = 'ST_CollectionExtract(%s, %s)' % (field, collection_type)

        attrs = ""
        if len(self.buildmap.known_attributes[table_name]) > 0:
            attrs = ", " + ",".join(self.buildmap.known_attributes[table_name])

        sql = """SELECT ogc_fid AS gid,
                         ST_AsBinary(ST_Transform(%s, %s)) AS geom,
                         text,
                         entityhandle
                         %s
                  FROM %s
                  WHERE layer = '%s'
                  AND ST_Transform(wkb_geometry, %s) && !BBOX! """ % (
            field, self.SRID, attrs, table_name, layer_name, self.SRID)

        if type_filter:
            sql += "AND ST_GeometryType(wkb_geometry) = '%s'" % type_filter

        return sql
