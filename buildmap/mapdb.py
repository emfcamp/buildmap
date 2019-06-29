from collections import defaultdict
import logging
import sqlalchemy
import re
from time import sleep
from shapely import wkt
from sqlalchemy.sql import text


class MapDB(object):
    """ Wrap common PostGIS operations.

        Before you get all annoyed about me not using bind variables here,
        you can't use them for table names, and the entire database is throwaway.
    """

    # Regex to match common embedded DXF text formatting codes. Probably not exhaustive.
    # c.f. http://www.cadforum.cz/cadforum_en/text-formatting-codes-in-mtext-objects-tip8640
    MTEXT_FORMAT_REGEX = r"(\\[A-Za-z]([A-Za-z0-9\.\|]+;))*"

    def __init__(self, url):
        self.log = logging.getLogger(self.__class__.__name__)
        self.url = sqlalchemy.engine.url.make_url(url)

    def connect(self):
        engine = sqlalchemy.create_engine(self.url)

        # Retry connection indefinitely, to aid running in Docker
        connected = False
        while not connected:
            try:
                self.conn = engine.connect()
                connected = True
            except sqlalchemy.exc.OperationalError as e:
                self.log.error(
                    "Error connecting to database (%s) - waiting to retry: %s.",
                    self.url,
                    e,
                )
                sleep(5)

        if (
            len(
                self.execute(
                    text("SELECT * FROM pg_extension WHERE extname = 'postgis'")
                ).fetchall()
            )
            == 0
        ):
            self.log.error("Database %s does not have PostGIS installed", self.url)
            return False

        self.log.info("Connected to PostGIS database %s", self.url)
        return True

    def extract_attributes(self, table):
        """ Extract DXF extended attributes into columns so we can use them in Mapnik"""
        with self.conn.begin():
            return self.extract_attributes_for_table(table)

    def extract_attributes_for_table(self, table_name):
        """ Extract the DXF's XDATA attributes into individual columns.

            When GDAL imports a DXF into PostGIS, it stuffs all the attributes
            into the "extendedentity" column. This function attempts to extract
            them nicely so we can use them.
        """
        known_attributes = set()
        attributes = defaultdict(list)
        result = self.conn.execute(
            text(
                """SELECT ogc_fid, extendedentity FROM %s
                                        WHERE extendedentity IS NOT NULL"""
                % table_name
            )
        )
        for record in result:
            # Curly braces surround some sets of attributes for some reason.
            attrs = record[1].strip(" {}")
            try:
                for attr in attrs.split(" "):
                    # Some DXFs seem to separate keys/values with :, some with =
                    if ":" in attr:
                        name, value = attr.split(":", 1)
                    elif "=" in attr:
                        name, value = attr.split("=", 1)
                    else:
                        continue

                    # Replace the dot character with underscore, as it's not valid in SQL
                    name = name.replace(".", "_")
                    known_attributes.add(name)
                    attributes[record[0]].append((name, value))
            except ValueError:
                # This is ambiguous to parse, I think it's GDAL's fault for cramming them
                # into one field
                self.log.error(
                    "Cannot extract attributes as an attribute field contains a space: %s",
                    attrs,
                )
                continue

        for attr_name in known_attributes:
            self.conn.execute(
                text("ALTER TABLE %s ADD COLUMN %s TEXT" % (table_name, attr_name))
            )

        for ogc_fid, attrs in attributes.items():
            for name, value in attrs:
                self.conn.execute(
                    text(
                        "UPDATE %s SET %s = :value WHERE ogc_fid = :fid"
                        % (table_name, name.lower())
                    ),
                    value=value,
                    fid=ogc_fid,
                )
        return known_attributes

    def get_bounds(self, table_name, srs=4326):
        """ Fetch the bounding box of all rows within a table. """
        # Performance note: it's neater to transform coordinates to the target SRS before
        # running ST_Extent, as it doesn't require us knowing what the table SRS is, but
        # this is obviously much slower. It doesn't seem to be an issue so far though.
        res = self.conn.execute(
            text(
                "SELECT ST_AsEWKT(ST_Extent(ST_Transform(wkb_geometry, %s))) FROM %s"
                % (srs, table_name)
            )
        ).first()
        return wkt.loads(res[0])

    def create_bounding_layer(self, table_name, bbox, srid=4326):
        """ Create a new table containing a single row representing the bounding box
            of the map. This can be used by renderers to mask off any background layers
            behind our map.

            `bbox` should be a shapely Polygon
        """
        with self.conn.begin():
            self.conn.execute(text('DROP TABLE IF EXISTS "%s"' % table_name))
            self.conn.execute(
                text(
                    """CREATE TABLE "%s" (
                                        id SERIAL PRIMARY KEY,
                                        wkb_geometry geometry(POLYGON, %s))
                                   """
                    % (table_name, srid)
                )
            )
            self.conn.execute(
                text(
                    """INSERT INTO "%s" (wkb_geometry) VALUES (
                                   ST_SetSRID('%s'::geometry, %s))
                                   """
                    % (table_name, bbox.wkt, srid)
                )
            )

    def clean_layers(self, table_name):
        """ Tidy up some mess in Postgres which ogr2ogr makes when importing DXFs. """
        with self.conn.begin():
            # Fix newlines in labels
            self.conn.execute(
                text("UPDATE %s SET text = replace(text, '^J', '\n')" % table_name)
            )
            # Remove "SOLID" labels from fills
            self.conn.execute(
                text("UPDATE %s SET text = NULL WHERE text = 'SOLID'" % table_name)
            )
            # Strip formatting codes from text
            self.conn.execute(
                text(
                    "UPDATE %s SET text = regexp_replace(text, '%s', '')"
                    % (table_name, self.MTEXT_FORMAT_REGEX)
                )
            )
            # Convert closed linestrings to polygons
            self.conn.execute(
                text(
                    """UPDATE %s SET wkb_geometry = ST_MakePolygon(wkb_geometry)
                                      WHERE ST_IsClosed(wkb_geometry)
                                      AND ST_GeometryType(wkb_geometry) = 'ST_LineString'
                                      AND ST_NumPoints(wkb_geometry) > 3"""
                    % table_name
                )
            )
            # Force geometries to use right-hand rule
            self.conn.execute(
                text(
                    "UPDATE %s SET wkb_geometry = ST_ForceRHR(wkb_geometry)"
                    % table_name
                )
            )
            # Drop the "subclasses" column which contains the original DXF geometry type.
            # This could be misleading after the above transformations, and using
            # ST_GeometryType is better practice anyway.
            self.conn.execute(
                text("ALTER TABLE %s DROP COLUMN subclasses" % table_name)
            )
            # Create layer index to speed up querying
            self.conn.execute(
                text("CREATE INDEX %s_layer on %s(layer)" % (table_name, table_name))
            )
            self.clean_weird_unicode(table_name)

        self.conn.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("VACUUM ANALYZE %s" % table_name)
        )

    def clean_weird_unicode(self, table_name):
        """ Sometimes text comes through as strange unicode in the format "\\U+00f6".
            Probably AutoCAD's fault.
        """
        MATCH_REGEX = r"\\U\+([0-9a-f]{4})"
        result = self.conn.execute(
            text(
                "SELECT ogc_fid, text FROM {} WHERE text ~ :regex".format(
                    table_name
                )
            ),
            regex=MATCH_REGEX,
        )
        for row in result:
            cleaned_text = re.sub(MATCH_REGEX, lambda r: chr(int(r[1], 16)), row[1])
            self.conn.execute(
                text(
                    "UPDATE {} SET text = :text WHERE ogc_fid = :fid".format(
                        table_name
                    )
                ),
                text=cleaned_text,
                fid=row[0],
            )

    def prefix_handles(self, table_name, prefix):
        """ Prefix entity handles to avoid collisions with multiple DXF files. """
        with self.conn.begin():
            self.conn.execute(
                text(
                    "UPDATE %s SET entityhandle = '%s' || entityhandle"
                    % (table_name, prefix)
                )
            )

    def get_layer_type(self, table_name, layer_name):
        with self.conn.begin():
            sql = """SELECT DISTINCT ST_GeometryType(geom) FROM (
                        SELECT (ST_Dump(wkb_geometry)).geom AS geom
                            FROM {table} WHERE layer = '{layer}'
                            and st_geometrytype(wkb_geometry) = 'ST_GeometryCollection'
                        UNION ALL SELECT wkb_geometry AS geom
                            FROM {table} WHERE layer = '{layer}'
                            AND st_geometrytype(wkb_geometry) != 'ST_GeometryCollection'
                    ) AS t""".format(
                table=table_name, layer=layer_name
            )
            result = self.conn.execute(text(sql))
            return [row[0] for row in result]

    def get_layers(self, table_name):
        res = self.conn.execute(text("SELECT DISTINCT layer FROM %s" % table_name))
        return [row[0] for row in res]

    def get_columns(self, table_name):
        """ Return a list of columns for the given table """
        result = self.conn.execute(
            text(
                """SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table"""
            ),
            table=table_name,
        )
        return [row[0] for row in result]

    def execute(self, query, *args, **kwargs):
        return self.conn.execute(query, *args, **kwargs)
