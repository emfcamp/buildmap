import logging
from ..main import BuildMap
from ..mapdb import MapDB


class Exporter(object):
    """Base class for exporters"""

    def __init__(self, buildmap: BuildMap, config, db: MapDB):
        self.log = logging.getLogger(self.__class__.__name__)
        self.buildmap = buildmap
        self.config = config
        self.db = db

    def export(self):
        raise NotImplementedError()
