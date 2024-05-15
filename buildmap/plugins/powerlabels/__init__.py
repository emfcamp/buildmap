# Electromagnetic Field
# Auto generate power distro labeles form build maps DB
# Avery L7173
import logging
import time
import re
import powerplan
import os.path
from powerplan.diagram import to_dot
from powerplan.bom import generate_bom_html
from collections import namedtuple
from sqlalchemy.sql import text

import labels
from reportlab.graphics import shapes
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.lib import colors
from reportlab.lib.units import mm

Connection = namedtuple("Connection", ["name", "I", "phases"])
Distro = namedtuple("Distro", ["fid", "type", "name", "load", "lat", "long"])
Generator = namedtuple("Generator", ["fid", "type", "name"])


def get_key(row, name):
    if name in row:
        return row[name]
    return None


class PowerlabelsPlugin(object):
    # define the label paper (Avery L7173)
    specs = labels.Specification(210, 297, 2, 5, 99, 57, corner_radius=2)

    def __init__(self, buildmap, _config, opts, db):
        self.log = logging.getLogger(__name__)
        self.db = db
        self.opts = opts
        self.buildmap = buildmap
        self.generator_layer = None
        self.distro_layer = None
        self.connection_layers = {}

        self.generators = {}
        self.distros = {}

        resources_path = os.path.join(os.path.dirname(__file__), "resources")

        registerFont(
            TTFont("Raleway", os.path.join(resources_path, "Raleway-Regular.ttf"))
        )
        registerFont(
            TTFont("Raleway-Bold", os.path.join(resources_path, "Raleway-Bold.ttf"))
        )

        self.logo = os.path.join(resources_path, "logo-white.png")
        self.power = os.path.join(resources_path, "powerpower.png")

    def generate_layers_config(self):
        "Detect power layers in map."
        prefix = self.opts["layer_prefix"]
        layers = list(
            self.db.execute(
                text(
                    "SELECT DISTINCT layer FROM site_plan WHERE layer LIKE '%s%%'"
                    % prefix
                )
            )
        )

        for layer in layers:
            name_sub = layer[0][len(prefix) :]  # De-prefix the layer name

            # Attempt to match connection layers with the format "32" (32A 1ph) or "32-3" (32A 3ph)
            res = re.match(r"^([0-9]+)A?-?([0-9]+)?$", name_sub)
            if res:
                if res.group(2):
                    phases = int(res.group(2))
                else:
                    phases = 1
                conn = Connection(layer[0], int(res.group(1)), phases)
                self.connection_layers[conn.name] = conn
            elif name_sub.lower().startswith("generator"):
                # Generator layer starts with "Generator"
                self.generator_layer = layer[0]
            elif name_sub.lower().startswith("distro"):
                # Distro layer starts with "distro"
                self.distro_layer = layer[0]

        if (
            self.generator_layer
            and self.distro_layer
            and len(self.connection_layers) > 0
        ):
            return True
        else:
            self.log.warn(
                "Unable to locate all required power layers. Layers discovered: %s",
                layers,
            )
            return False

    def get_generators(self):
        for row in self.db.execute(
            text("SELECT * FROM site_plan WHERE layer = :layer"),
            layer=self.generator_layer,
        ):
            yield Generator(
                row["ogc_fid"], get_key(row, "generator"), get_key(row, "name")
            )

    def get_distros(self):
        for row in self.db.execute(
            text(
                "SELECT *, split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as lat, split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as long  FROM site_plan WHERE layer = :layer"
            ),
            layer=self.distro_layer,
        ):
            yield Distro(
                row["ogc_fid"],
                get_key(row, "distro"),
                get_key(row, "name"),
                get_key(row, "load"),
                get_key(row, "lat"),
                get_key(row, "long"),
            )

    # what goes on a label
    def draw_label(self, label, width, height, node):
        label.add(shapes.Image(4 * mm, 4 * mm, 17.49 * mm, 49 * mm, self.logo))
        label.add(
            shapes.String(
                26 * mm,
                125,
                node.name,
                fontName="Raleway-Bold",
                fontSize=18,
                fillColor=colors.purple,
            )
        )
        label.add(
            shapes.String(26 * mm, 95, node.type, fontName="Raleway", fontSize=16)
        )

        latlong = "{}, {}".format(node.lat, node.long)
        label.add(shapes.String(26 * mm, 75, latlong, fontName="Raleway", fontSize=14))
        label.add(
            shapes.String(
                26 * mm,
                57,
                "Load: {}".format(node.load),
                fontName="Raleway",
                fontSize=14,
            )
        )
        # label.add(shapes.Rect(26*mm, 35, 15, 15, fillColor=colors.white))
        label.add(
            shapes.String(26 * mm, 25, "Tested by:", fontName="Raleway", fontSize=14)
        )
        label.add(shapes.Line(50 * mm, 23, 85 * mm, 23))

        label.add(shapes.Image(92 * mm, 0.77 * mm, 3.39 * mm, 55.46 * mm, self.power))

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info(
            "Power layers detected. Generators: '%s', Distro: '%s', Connections: %s",
            self.generator_layer,
            self.distro_layer,
            list(self.connection_layers.keys()),
        )

        sheet = labels.Sheet(self.specs, self.draw_label, border=False)

        # draw each node as a label
        for node in self.get_distros():
            if node.name is None:
                self.log.warn("Skipping label for node %s with no name", node.fid)
                continue
            sheet.add_label(node)

        # save it
        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config["web_directory"]), "power"
        )

        try:
            os.makedirs(out_path)
        except FileExistsError:
            pass

        sheet.save(os.path.join(out_path, "power-node-labels.pdf"))
        self.log.info(
            "Power output {0:d} label(s) on {1:d} page(s).".format(
                sheet.label_count, sheet.page_count
            )
        )
