import logging
import time
from collections import namedtuple
from pprint import pprint

import csv
from sqlalchemy.sql import text

Switch = namedtuple('Switch', ['name'])
Connection = namedtuple('Connection', ['from_switch', 'to_switch', 'type', 'length', 'cores'])


class NocPlugin(object):
    BUFFER = 1
    UPDOWN_LENGTH = 6  # How many metres to add per and up-and-down a festoon pole

    def __init__(self, _buildmap, _config, opts, db):
        self.log = logging.getLogger(__name__)
        self.db = db
        self.opts = opts
        self.switch_layer = None
        self.connection_layers = {}

        self.switches = {}
        self.connections = []

    def generate_layers_config(self):
        " Detect NOC layers in map. "
        prefix = self.opts['layer_prefix']
        layers = list(self.db.execute(text("SELECT DISTINCT layer FROM site_plan WHERE layer LIKE '%s%%'" %
                                           prefix)))

        for layer in layers:
            name_sub = layer[0][len(prefix):]  # De-prefix the layer name

            if name_sub.lower() == "switch":
                self.switch_layer = layer[0]
            elif name_sub.lower() in ['copper', 'fibre']:
                # conn = Connection(layer[0])
                self.connection_layers[layer[0]] = name_sub.lower()

        if self.switch_layer and len(self.connection_layers) > 0:
            return True
        else:
            self.log.warn("Unable to locate all required NOC layers. Layers discovered: %s", layers)
            return False

    def get_switches(self):
        self.log.info("Loading switches")
        for row in self.db.execute(text("SELECT * FROM site_plan WHERE layer = :layer"),
                                   layer=self.switch_layer):
            if 'switch' not in row or row['switch'] is None:
                self.log.warning("Switch name not found in entity 0x%s on %s layer" % (row['entityhandle'], self.switch_layer))
            yield Switch(row['switch'])

    def find_switch_from_connection(self, edge_entityhandle, edge_layer, edge_ogc_fid, start_or_end):
        node_sql = text("""SELECT switch.switch AS switch
                            FROM site_plan AS edge, site_plan AS switch
                            WHERE edge.ogc_fid=:edge_ogc_fid
                            AND switch.layer = ANY(:switch_layers)
                            AND ST_Buffer(switch.wkb_geometry, :buf) && ST_""" + start_or_end.title() + """Point(edge.wkb_geometry)
                            """)
        switch_result = self.db.execute(node_sql, edge_ogc_fid=edge_ogc_fid, switch_layers=[self.switch_layer], buf=self.BUFFER)
        switch_rows = switch_result.fetchall()
        if len(switch_rows) < 1:
            self.log.warning("Connection 0x%s on %s layer does not %s at a switch" % (edge_entityhandle, edge_layer, start_or_end))
            return None
        elif len(switch_rows) > 1:
            self.log.warning("Connection 0x%s on %s layer %ss at multiple switches" % (edge_entityhandle, edge_layer, start_or_end))
            return None
        switch = switch_rows[0]['switch']
        return switch

    def get_connections(self):
        """ Returns all the connections """
        self.log.info("Loading connections")

        sql = text("""SELECT layer,
                            round(ST_Length(wkb_geometry)::NUMERIC, 1) AS length,
                            cores,
                            updowns,
                            entityhandle,
                            ogc_fid
                        FROM site_plan
                        WHERE layer = ANY(:connection_layers) 
                        AND ST_GeometryType(wkb_geometry) = 'ST_LineString'
                    """)
        for row in self.db.execute(sql, connection_layers=list(self.connection_layers.keys())):
            from_switch = self.find_switch_from_connection(row['entityhandle'], row['layer'], row['ogc_fid'], 'start')
            to_switch = self.find_switch_from_connection(row['entityhandle'], row['layer'], row['ogc_fid'], 'end')
            if not from_switch or not to_switch:
                continue

            # self.log.info("Link from %s to %s" % (from_switch, to_switch))

            type = self.connection_layers[row['layer']]
            total_length = row['length']
            if row['updowns'] is not None:
                total_length += int(row['updowns']) * self.UPDOWN_LENGTH
            cores = row['cores']

            yield from_switch, to_switch, type, total_length, cores

    def generate_plan(self):

        for switch in self.get_switches():
            self.switches[switch.name] = switch

        for connection in self.get_connections():
            self.connections.append(connection)

        # Start from UPLINK

        # complain about switches with no links

        # return plan

    def create_index(self):
        # Extremely specific geo index time
        # does this conflict with the power index?
        sql = text("""CREATE INDEX IF NOT EXISTS site_plan_geometry_buffer
                        ON site_plan USING GIST(ST_Buffer(wkb_geometry, :buf))
                        WHERE layer = :switch_layer""")
        self.db.execute(sql, buf=self.BUFFER, switch_layer=self.switch_layer)

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info("NOC layers detected. Switches: '%s', Connections: %s",
                      self.switch_layer, list(self.connection_layers.keys()))

        start = time.time()
        self.create_index()
        plan = self.generate_plan()
        self.log.info("Plan generated in %.2f seconds", time.time() - start)

        with open('noc-switches.csv', 'w') as switches_file:
            writer = csv.writer(switches_file)
            writer.writerow(['Switch-Name'])
            for switch in sorted(self.switches.values()):
                writer.writerow(switch)

        with open('noc-links.csv', 'w') as links_file:
            writer = csv.writer(links_file)
            writer.writerow(['From-Switch', 'To-Switch', 'Type', 'Length', 'Cores'])
            for connection in self.connections:
                writer.writerow(connection)

        # dot = to_dot(plan)
        # with open('plan.pdf', 'wb') as f:
        #     f.write(dot.create_pdf())
