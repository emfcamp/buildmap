# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals
import logging
import mapnik


class StaticExporter(object):
    """ Export static maps to PDF """

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config

    def export(self, mapnik_xml, output_file):
        self.log.info(
            "Exporting %s to %s. Mapnik version %s",
            mapnik_xml,
            output_file,
            mapnik.mapnik_version_string(),
        )

        mapnik_map = mapnik.Map(2000, 2000)
        mapnik.load_map(mapnik_map, mapnik_xml.encode("utf-8"))
        mapnik_map.zoom_all()
        mapnik.render_to_file(mapnik_map, output_file, b"pdf")
