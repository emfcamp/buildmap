# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals
from collections import defaultdict
import logging
import sqlalchemy
from sqlalchemy.sql import text


class MapDB(object):
    """ Wrap common PostGIS operations """
    def __init__(self, url):
        self.log = logging.getLogger(__name__)
        self.url = sqlalchemy.engine.url.make_url(url)

    def connect(self):
        engine = sqlalchemy.create_engine(self.url)
        try:
            self.conn = engine.connect()
        except sqlalchemy.exc.OperationalError as e:
            self.log.error("Error connecting to database (%s): %s", self.url, e)
            return False
        self.log.info("Connected to PostGIS database %s", self.url)
        return True

    def extract_attributes(self, table):
        """ Extract DXF extended attributes into columns so we can use them in Mapnik"""
        with self.conn.begin():
            return self.extract_attributes_for_table(table)

    def extract_attributes_for_table(self, table_name):
        known_attributes = set()
        attributes = defaultdict(list)
        result = self.conn.execute(text("""SELECT ogc_fid, extendedentity FROM %s
                                        WHERE extendedentity IS NOT NULL""" % table_name))
        for record in result:
            # Curly braces surround some sets of attributes for some reason.
            attrs = record[1].strip(' {}')
            try:
                for attr in attrs.split(' '):
                    # Some DXFs seem to separate keys/values with :, some with =
                    if ':' in attr:
                        name, value = attr.split(':', 1)
                    elif '=' in attr:
                        name, value = attr.split('=', 1)
                    else:
                        continue

                    # Replace the dot character with underscore, as it's not valid in SQL
                    name = name.replace('.', '_')
                    known_attributes.add(name)
                    attributes[record[0]].append((name, value))
            except ValueError:
                # This is ambiguous to parse, I think it's GDAL's fault for cramming them
                # into one field
                self.log.error("Cannot extract attributes as an attribute field contains a space: %s",
                               attrs)
                continue

        for attr_name in known_attributes:
            self.conn.execute(text("ALTER TABLE %s ADD COLUMN %s TEXT" % (table_name, attr_name)))

        for ogc_fid, attrs in attributes.iteritems():
            for name, value in attrs:
                self.conn.execute(text("UPDATE %s SET %s = :value WHERE ogc_fid = :fid" %
                                  (table_name, name.lower())), value=value, fid=ogc_fid)
        return known_attributes

    def clean_layers(self, table_name):
        """ Tidy up some mess in Postgres which ogr2ogr makes when importing DXFs. """
        with self.conn.begin():
            # Fix newlines in labels
            self.conn.execute(text("UPDATE %s SET text = replace(text, '^J', '\n')" % table_name))
            # Remove "SOLID" labels from fills
            self.conn.execute(text("UPDATE %s SET text = NULL WHERE text = 'SOLID'" % table_name))

    def get_layers(self, table_name):
        res = self.conn.execute(text("SELECT DISTINCT layer FROM %s" % table_name))
        return [row[0] for row in res]

    def execute(self, query, **kwargs):
        return self.conn.execute(query, **kwargs)
