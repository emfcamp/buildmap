import logging
import time
import re
import powerplan
import os.path
from powerplan.diagram import to_dot
from powerplan.bom import generate_bom_html
from collections import namedtuple
from sqlalchemy.sql import text

Connection = namedtuple("Connection", ["name", "I", "phases"])
Distro = namedtuple("Distro", ["fid", "type", "name", "load"])
Generator = namedtuple("Generator", ["fid", "type", "name"])


def get_key(row, name):
    if name in row:
        return row[name]
    return None


class PowerPlugin(object):
    BUFFER = 1

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
            text("SELECT * FROM site_plan WHERE layer = :layer"),
            layer=self.distro_layer,
        ):
            yield Distro(
                row["ogc_fid"],
                get_key(row, "distro"),
                get_key(row, "name"),
                get_key(row, "load"),
            )

    def get_outbound_connections(self, ogc_fid):
        """Given the feature ID of a power network node, return all nodes which are connected to it,
        along with the layer that connection is in. An edge (cable) is deemed to be connected to a
        node if it ends within the "buffer" defined in self.BUFFER - this is in source CRS units
        which should be meters."""

        sql = text(
            """SELECT end_node.ogc_fid, edge.layer,
                            round(ST_Length(edge.wkb_geometry)::NUMERIC, 1) AS length
                        FROM site_plan AS edge, site_plan AS start_node, site_plan AS end_node
                        WHERE edge.layer = ANY(:connection_layers) AND end_node.layer = ANY(:distro_layers)
                        AND start_node.ogc_fid = :start_fid
                        AND ST_GeometryType(edge.wkb_geometry) = 'ST_LineString' AND
                            (ST_Buffer(start_node.wkb_geometry, :buf) && ST_StartPoint(edge.wkb_geometry)
                            AND ST_Buffer(end_node.wkb_geometry, :buf) && ST_EndPoint(edge.wkb_geometry)
                            OR ST_Buffer(start_node.wkb_geometry, :buf) && ST_EndPoint(edge.wkb_geometry)
                            AND ST_Buffer(end_node.wkb_geometry, :buf) && ST_StartPoint(edge.wkb_geometry))
                    """
        )
        for row in self.db.execute(
            sql,
            connection_layers=list(self.connection_layers.keys()),
            distro_layers=[self.distro_layer],
            start_fid=ogc_fid,
            buf=self.BUFFER,
        ):
            yield row[0], row[1], row[2]  # End node FID, connection layer, length

    def generate_plan(self):
        if self.opts.get("spec_dir"):
            spec = powerplan.EquipmentSpec(self.opts["spec_dir"])
        else:
            spec = None

        plan = powerplan.Plan(name=self.opts.get("name"), spec=spec)

        nodes = {}  # Index of all nodes
        tree_nodes = []  # List of initial nodes to traverse

        for gen in self.get_generators():
            node = powerplan.Generator(name=gen.name, type=gen.type, id=gen.fid)
            plan.add_node(node)
            nodes[gen.fid] = node
            tree_nodes.append((node, gen.fid))

        for dist in self.get_distros():
            # FIXME: Better way to detect AMF panels
            if dist.type == "125AMF-EVENT":
                node = powerplan.AMF(name=dist.name, type=dist.type, id=dist.fid)
            else:
                node = powerplan.Distro(name=dist.name, type=dist.type, id=dist.fid)
            plan.add_node(node)
            nodes[dist.fid] = node

            if dist.load:
                load = powerplan.Load(name=dist.name + " Load", load=dist.load)
                plan.add_node(load)
                plan.add_connection(node, load)

        # Traverse the tree of nodes, starting with the set of generators.
        while len(tree_nodes) > 0:
            start_node, start_fid = tree_nodes.pop()

            for end_fid, layer, length in self.get_outbound_connections(start_fid):
                end_node = nodes[end_fid]
                if plan.graph.has_edge(end_node, start_node):
                    # Don't follow the connection we just came from.
                    continue

                connection = self.connection_layers[layer]

                if type(start_node) == powerplan.AMF and connection.I > 63:
                    # If this is an AMF we don't want to continue the wrong
                    # way onto the other grid.
                    # FIXME: Work out a better way to deal with AMFs here
                    continue

                tree_nodes.append((end_node, end_fid))

                plan.add_connection(
                    start_node, end_node, connection.I, connection.phases, length=length
                )

        return plan

    def create_index(self):
        # Extremely specific geo index time
        sql = text(
            """CREATE INDEX IF NOT EXISTS site_plan_geometry_buffer
                        ON site_plan USING GIST(ST_Buffer(wkb_geometry, :buf))
                        WHERE layer = :distro_layer"""
        )
        self.db.execute(sql, buf=self.BUFFER, distro_layer=self.distro_layer)

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info(
            "Power layers detected. Generators: '%s', Distro: '%s', Connections: %s",
            self.generator_layer,
            self.distro_layer,
            list(self.connection_layers.keys()),
        )

        start = time.time()
        self.create_index()
        plan = self.generate_plan()
        self.log.info("Plan generated in %.2f seconds", time.time() - start)

        start = time.time()
        errors = plan.validate()
        if len(errors) > 0:
            self.log.warning("Power plan has validation errors:")
            for err in errors:
                self.log.warning("\t" + str(err))

        plan.generate()

        self.log.info("Plan validated in %.2f seconds", time.time() - start)

        dot = to_dot(plan)

        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config["web_directory"]), "power"
        )

        try:
            os.makedirs(out_path)
        except FileExistsError:
            pass

        with open(os.path.join(out_path, "power-plan.pdf"), "wb") as f:
            f.write(dot.create_pdf())

        for grid in plan.grids():
            dot = to_dot(grid, False)
            with open(
                os.path.join(out_path, "power-plan-%s.pdf" % grid.name), "wb"
            ) as f:
                f.write(dot.create_pdf())

        with open(os.path.join(out_path, "power-bom.html"), "w") as f:
            f.write(generate_bom_html(plan))

        self.log.info("Power plans output to %s", out_path)
