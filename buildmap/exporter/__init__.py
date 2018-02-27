import logging


class Exporter(object):
    """ Base class for exporters """
    def __init__(self, buildmap, config, db):
        self.log = logging.getLogger(self.__class__.__name__)
        self.buildmap = buildmap
        self.config = config
        self.db = db

    def export(self):
        raise NotImplementedError()
