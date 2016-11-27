# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals
import logging
from buildmap.main import BuildMap

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bm = BuildMap()
    bm.run()
