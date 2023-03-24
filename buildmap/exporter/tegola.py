import toml
import re
from os import path
from ..util import sanitise_layer
from . import Exporter


def strip_srid(srid):
    return int(srid.replace("epsg:", ""))


class TegolaExporter(Exporter):
    """Generate config for Tegola, which is a Mapbox Vector Tiles server.

    There are some "impedance mismatches" here - mostly due to the fact that
    a MVT layer can only have a single geometry type (I believe this is a Mapbox
    GL requirement rather than a format restriction), and does not support
    GeometryCollections (which is what DXF blocks become).
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
        """Generate `(tablename, layername, type, sql)` for each layer we want to render.

        MVT/Tegola only supports layers with a single geometry type, whereas DXF will
        happily let you have layers with multiple types. We output a layer per
        geometry type in this case.
        """
        source = self.buildmap.get_source_layers()
        seen = set()
        for table_name, layer_name in reversed(source):
            # the get_layer_type function will return all the component types of a GeometryCollection.
            # We can handle those in get_layer_sql
            types = self.db.get_layer_type(table_name, layer_name)
            if len(types) == 1:
                typename = types[0].split("_")[1]
                layer_name_typ = layer_name + "_" + typename.lower()
                if sanitise_layer(layer_name_typ) in seen:
                    continue
                seen.add(sanitise_layer(layer_name_typ))
                yield (
                    table_name,
                    layer_name_typ,
                    typename,
                    self.get_layer_sql(table_name, layer_name, types[0]),
                )
            else:
                # Multiple simple types. Split them into different layers.
                for typ in types:
                    typename = typ.split("_")[1]
                    layer_name_typ = layer_name + "_" + typename.lower()
                    if sanitise_layer(layer_name_typ) in seen:
                        continue
                    seen.add(sanitise_layer(layer_name_typ))
                    yield (
                        table_name,
                        layer_name_typ,
                        typename,
                        self.get_layer_sql(table_name, layer_name, typ),
                    )

    def generate_tegola_config(self):
        provider = {
            "name": self.PROVIDER_NAME,
            "type": "postgis",
            "database": self.db.url.database,
            "host": self.db.url.host,
            "port": self.db.url.port,
            "user": self.db.url.username,
            "password": self.db.url.password or "",
            "srid": self.SRID,
            "max_connections": 20,
            "layers": [],
        }

        layers = list(self.get_layers())

        for table_name, layer_name, typename, sql in layers:
            provider["layers"].append(
                {
                    "name": sanitise_layer(layer_name),
                    "sql": sql,
                    "geometry_type": typename,
                }
            )

        m = {
            "name": "buildmap",
            # Apply a 0.5 degree buffer to bounds Tegola is allowed to serve.
            # This restricts the amount of empty tiles will cache while allowing some margin.
            "bounds": list(self.buildmap.get_bbox().buffer(0.5).bounds),
            "center": self.buildmap.get_center() + [float(16)],
            "layers": [],
        }

        if (
            type(self.config["mapbox_vector_layer"]) is dict
            and "attribution" in self.config["mapbox_vector_layer"]
        ):
            m["attribution"] = self.config["mapbox_vector_layer"]["attribution"]

        for table_name, layer_name, _, _ in layers:
            m["layers"].append(
                {
                    "provider_layer": "%s.%s"
                    % (self.PROVIDER_NAME, sanitise_layer(layer_name)),
                    "min_zoom": self.config["zoom_range"][0],
                    "max_zoom": self.config["zoom_range"][1],
                }
            )

        # Add bounding box layer to config. Bounding box in DB is in EPSG:4326
        provider["layers"].append(
            {
                "name": "bounding_box",
                "sql": """SELECT id AS gid,
                        ST_AsBinary(ST_Transform(wkb_geometry, {out_proj})) AS geom
                        FROM bounding_box
                        WHERE wkb_geometry && ST_Transform(!BBOX!, 4326)
                   """.format(
                    out_proj=self.SRID
                ),
                "geometry_type": "Polygon",
            }
        )

        m["layers"].append(
            {
                "provider_layer": "%s.bounding_box" % (self.PROVIDER_NAME),
                "min_zoom": self.config["zoom_range"][0],
                "max_zoom": self.config["zoom_range"][1],
            }
        )

        # Construct config
        data = {
            "cache": {"type": "file", "basepath": "/tmp/tegola"},
            "providers": [provider],
            "maps": [m],
        }

        if "uri_prefix" in self.config:
            data["webserver"] = {"uri_prefix": self.config["uri_prefix"]}

        return data

    def get_layer_sql(self, table_name, layer_name, geometry_type):
        """Generate the SQL for this layer.

        `geometry_type` is the PostGIS geometry type we want to extract
        (e.g. 'ST_LineString')

        We'll extract entities of the specified type from any ST_GeometryCollections
        (which are generated from DXF blocks).
        """
        geom_field = "wkb_geometry"
        fid_field = "ogc_fid"
        additional_fields = ["text", "entityhandle"] + list(
            self.buildmap.known_attributes[table_name]
        )

        for type_name in ("LineString", "Polygon"):
            if geometry_type == "ST_Multi{}".format(type_name):
                geometry_type = "ST_{}".format(type_name)

        type_map = {"ST_Point": 1, "ST_LineString": 2, "ST_Polygon": 3}

        # Return all table entries, plus the contents of all GeometryCollections.
        query = "(SELECT {fields} FROM {table}".format(
            fields=", ".join([geom_field, fid_field, "layer"] + additional_fields),
            table=table_name,
        )
        query += " UNION ALL "
        # It would be nicer to use ST_Dump here, but we can't simply split each GeometryCollection
        # into its component parts because MVT requires unique IDs, and we'll lose the connection between
        # map objects and DXF objects. ST_CollectionExtract will return MultiGeometries (which MVT does
        # support).
        query += """SELECT ST_CollectionExtract({geom_field}, {geom_type}) AS {geom_field},
                    {fields} FROM {table}
                    WHERE ST_GeometryType({geom_field}) = 'ST_GeometryCollection'""".format(
            geom_field=geom_field,
            geom_type=type_map[geometry_type],
            fields=", ".join([fid_field, "layer"] + additional_fields),
            table=table_name,
        )
        query += ") AS t"
        table_name = query

        # Add derived fields based on geometry type
        if geometry_type == "ST_LineString":
            additional_fields.append(
                "round(ST_Length(%s)::numeric, 1) AS length" % geom_field
            )
        elif geometry_type == "ST_Polygon":
            additional_fields.append(
                "round(ST_Perimeter(%s)::numeric, 1) AS perimeter" % geom_field
            )
            additional_fields.append(
                "round(ST_Area(%s)::numeric, 1) AS area" % geom_field
            )

        sql = """SELECT %s AS gid,
                         ST_AsBinary(ST_Transform(%s, %s)) AS geom,
                         %s
                  FROM %s
                  WHERE layer = '%s'
                  AND wkb_geometry && ST_Transform(!BBOX!, %s) """ % (
            fid_field,
            geom_field,
            self.SRID,
            ", ".join(additional_fields),
            table_name,
            layer_name,
            strip_srid(self.config["source_projection"]),
        )

        # Filter the result by the type of geometry we're looking for, taking into account MultiGeometries.
        type_synonyms = {
            "ST_LineString": ["ST_Line", "ST_LineString", "ST_MultiLineString"],
            "ST_Polygon": ["ST_Polygon", "ST_MultiPolygon"],
            "ST_Point": ["ST_Point", "ST_MultiPoint"],
        }

        sql += (
            "AND ST_GeometryType(wkb_geometry) IN ("
            + " ,".join("'" + t + "'" for t in type_synonyms[geometry_type])
            + ")"
        )

        # Tidy up the SQL string so it's more readable in the tegola config
        sql = re.sub(r"\s+", " ", sql)

        return sql
