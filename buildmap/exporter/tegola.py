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
    # need to transform from our working CRS, which is not likely to be one of those.
    SRID = 3857

    def export(self):
        dest_file = path.join(self.buildmap.temp_dir, "tegola.toml")
        with open(dest_file, "w") as fp:
            toml.dump(self.generate_tegola_config(), fp)

    def get_layers(self):
        """ Generate `(tablename, layername, sql)` for each layer we want to render.

            MVT/Tegola only supports layers with a single geometry type, whereas DXF will
            happily let you have layers with multiple types. We try and output a layer per
            geometry type in this case, but this may not be possible.
        """
        source = self.buildmap.get_source_layers()
        for table_name, layer_name in source:
            types = self.db.get_layer_type(table_name, layer_name)

            if types == ['ST_GeometryCollection']:
                # This layer only contains GeometryCollections.
                # Let's assume they're LineStrings.
                yield (table_name, layer_name,
                       self.get_layer_sql(table_name, layer_name, 'ST_LineString', True))
            elif len(types) == 1:
                # A single simple type. This is the easy case.
                yield (table_name, layer_name, self.get_layer_sql(table_name, layer_name, types[0]))
            elif 'ST_GeometryCollection' in types and len(types) == 2:
                # This contains both collection and non-collection types.
                # Extract the non-collection type from the collection types.
                types.remove('ST_GeometryCollection')
                yield (table_name, layer_name,
                       self.get_layer_sql(table_name, layer_name, types[0], True))
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
                           self.get_layer_sql(table_name, layer_name, typ))

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
            "bounds": list(self.buildmap.get_bbox().bounds),
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

        # Add bounding box layer to config
        provider["layers"].append({
            "name": "bounding_box",
            "sql": """SELECT id AS gid, ST_AsBinary(ST_Transform(wkb_geometry, 3857)) AS geom
                        FROM bounding_box
                        WHERE ST_Transform(wkb_geometry, 3857) && !BBOX!
                   """
        })

        m["layers"].append({
            "provider_layer": "%s.bounding_box" % (self.PROVIDER_NAME),
            "min_zoom": self.config['zoom_range'][0],
            "max_zoom": self.config['zoom_range'][1]
        })

        # Construct config
        data = {
            "cache": {
                "type": "file",
                "basepath": "/tmp/tegola"
            },
            "providers": [provider],
            "maps": [m]
        }
        return data

    def get_layer_sql(self, table_name, layer_name, geometry_type, transform_collections=False):
        """ Generate the SQL for this layer.

            `geometry_type` is the PostGIS geometry type (e.g. 'ST_LineString')

            If `transform_collections` is True, we'll extract entities of the specified
            type from any ST_GeometryCollections (which are generated from DXF blocks).
        """
        geom_field = 'wkb_geometry'

        if transform_collections:
            # ST_CollectionExtract requires these magic numbers:
            type_map = {'ST_Point': 1, 'ST_LineString': 2, 'ST_Polygon': 3}
            geom_field = 'ST_CollectionExtract(%s, %s)' % (geom_field, type_map[geometry_type])

        additional_fields = []
        if len(self.buildmap.known_attributes[table_name]) > 0:
            additional_fields += self.buildmap.known_attributes[table_name]

        # Add derived fields based on geometry type
        if geometry_type == 'ST_LineString':
            additional_fields.append('round(ST_Length(%s)::numeric, 2) AS length' % geom_field)
        elif geometry_type == 'ST_Polygon':
            additional_fields.append('round(ST_Perimeter(%s)::numeric, 2) AS perimeter' % geom_field)
            additional_fields.append('round(ST_Area(%s)::numeric, 2) AS area' % geom_field)

        fields_txt = ""
        if len(additional_fields) > 0:
            fields_txt = ", " + ", ".join(additional_fields)

        sql = """SELECT ogc_fid AS gid,
                         ST_AsBinary(ST_Transform(%s, %s)) AS geom,
                         text,
                         entityhandle
                         %s
                  FROM %s
                  WHERE layer = '%s'
                  AND ST_Transform(wkb_geometry, %s) && !BBOX! """ % (
            geom_field, self.SRID, fields_txt, table_name, layer_name, self.SRID)

        if geometry_type and not transform_collections:
            sql += "AND ST_GeometryType(wkb_geometry) = '%s'" % geometry_type

        return sql
