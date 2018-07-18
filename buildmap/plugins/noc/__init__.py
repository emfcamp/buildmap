import logging
import time
from collections import namedtuple

import pydotplus as pydot  # type: ignore
import csv
from sqlalchemy.sql import text
from datetime import date

Switch = namedtuple('Switch', ['name'])


class Connection:
    def __init__(self, from_switch, to_switch, type, length, cores):
        self.from_switch = from_switch
        self.to_switch = to_switch
        self.type = type
        self.length = length
        self.cores = cores


class NocPlugin(object):
    BUFFER = 1
    UPDOWN_LENGTH = 6  # How many metres to add per and up-and-down a festoon pole
    COLOUR_HEADER = 'lightcyan1'
    COLOUR_COPPER = 'slateblue4'
    COLOUR_FIBRE = 'goldenrod'
    LENGTH_COPPER_NOT_CCA = 30
    LENGTH_COPPER_WARNING = 70
    LENGTH_COPPER_CRITICAL = 90

    def __init__(self, _buildmap, _config, opts, db):
        self.log = logging.getLogger(__name__)
        self.db = db
        self.opts = opts
        self.switch_layer = None
        self.connection_layers = {}

        self.switches = {}
        self.connections = []
        self.processed_connections = set()
        self.processed_switches = set()

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

            yield Connection(from_switch, to_switch, type, total_length, cores)

    def generate_plan(self):
        for switch in self.get_switches():
            self.switches[switch.name] = switch

        for connection in self.get_connections():
            self.connections.append(connection)

        # Start from UPLINK

        # complain about switches with no links

        return True

    def order_links_from_switch(self, switch_name):
        if switch_name in self.processed_switches:
            self.log.warning("Switch %s has an infinite loop of connections!" % switch_name)
            return

        self.processed_switches.add(switch_name)

        # find connections that have us as their *to_switch* and swap them if they haven't already been swapped by a parent
        for connection in self.connections:
            if connection.to_switch == switch_name:
                if connection not in self.processed_connections:
                    connection.to_switch, connection.from_switch = connection.from_switch, connection.to_switch

        # Now repeat for any switch we're connected to
        for connection in self.connections:
            if connection.from_switch == switch_name:
                self.processed_connections.add(connection)  # Mark it as being correctly ordered
                self.order_links_from_switch(connection.to_switch)

    def _title_label(self, name):
        label = '<<table border="0" cellspacing="0" cellborder="1" cellpadding="5">'
        label += '<tr><td bgcolor="{}"><b>{}</b></td></tr>'.format(self.COLOUR_HEADER, name)
        label += '<tr><td>NOC Plan</td></tr>'
        label += '<tr><td>{}</td></tr>'.format(date.today().isoformat())
        label += '</table>>'
        return label

    def _switch_label(self, switch):
        " Label format for a switch. Using graphviz's HTML table support "

        label = '<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" color="grey30">\n'
        label += '''<tr><td bgcolor="{colour}"><font point-size="16"><b>{name}</b></font></td>
                        </tr>'''.format(
            name=switch.name, type='No type assigned', colour=self.COLOUR_HEADER)
        # <!--td bgcolor="{colour}"><font point-size="16">{type}</font></td-->
        label += '<tr><td port="input"></td></tr></table>>'
        return label

    def dot_add_switch(self, sg, switch):
        node = pydot.Node(switch.name, label=self._switch_label(switch))
        sg.add_node(node)

    def create_dot(self):
        self.log.info("Generating graph")

        dot = pydot.Dot("NOC", graph_type='digraph', strict=True)
        dot.set_node_defaults(shape='none', fontsize=14, margin=0, fontname='Arial')
        dot.set_edge_defaults(fontsize=13, fontname='Arial')
        # dot.set_page('11.7,8.3!')
        # dot.set_margin(0.5)
        # dot.set_ratio('fill')
        dot.set_rankdir('LR')
        dot.set_fontname('Arial')
        dot.set_nodesep(0.3)
        # dot.set_splines('line')

        sg = pydot.Cluster('physical', label='Physical')

        # Find our root switch
        root = self.switches['ESNORE']
        self.processed_switches = set()
        self.processed_connections = set()
        self.order_links_from_switch(root.name)

        for switch in self.switches.values():
            self.dot_add_switch(sg, switch)

        for connection in self.connections:
            edge = pydot.Edge(connection.from_switch, connection.to_switch)

            open = ''
            close = ''

            label = '<'
            if connection.type == 'fibre':
                label += '{} cores'.format(connection.cores)
                colour = self.COLOUR_FIBRE
            elif connection.type == 'copper':
                length = float(connection.length)
                if connection.cores and int(connection.cores) > 1:
                    label += '<b>{}x</b> '.format(connection.cores)

                if length > self.LENGTH_COPPER_NOT_CCA:
                    label += "Copper"
                else:
                    label += "CCA"

                colour = self.COLOUR_COPPER
                if length > self.LENGTH_COPPER_CRITICAL:
                    open += '<font color="red">'
                    close = '</font>' + close
                elif length > self.LENGTH_COPPER_WARNING:
                    open += '<font color="orange">'
                    close = '</font>' + close
            else:
                self.log.error("Invalid type %s for connection between %s and %s", connection.type, connection.from_switch, connection.to_switch)
                return None

            label += '<br/>' + open
            label += '{}m'.format(str(connection.length))
            label += close + '>'

            # edge.set_tailport('{}-{}'.format(edgedata['current'], edgedata['phases']))
            edge.set_headport('input')
            edge.set_label(label)
            edge.set_color(colour)
            sg.add_edge(edge)

        sg.set_color('gray80')
        sg.set_style('dashed')
        sg.set_labeljust('l')
        dot.add_subgraph(sg)

        title = pydot.Node('title', shape='none', label=self._title_label("Electromagnetic Field 2018"))
        title.set_pos('0,0!')
        title.set_fontsize(18)
        dot.add_node(title)

        return dot

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info("NOC layers detected. Switches: '%s', Connections: %s",
                      self.switch_layer, list(self.connection_layers.keys()))

        start = time.time()
        if not self.generate_plan():
            return
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
                writer.writerow([connection.from_switch, connection.to_switch, connection.type, connection.length, connection.cores])

        dot = self.create_dot()
        if not dot:
            return
        with open('noc-physical.pdf', 'wb') as f:
            f.write(dot.create_pdf())
