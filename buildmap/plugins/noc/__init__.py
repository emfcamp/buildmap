import logging
import time
from collections import namedtuple
import os.path
import pydotplus as pydot  # type: ignore
import csv
from sqlalchemy.sql import text
from datetime import date

Switch = namedtuple('Switch', ['name'])


class Link:
    def __init__(self, from_switch, to_switch, type, length, cores):
        self.from_switch = from_switch
        self.to_switch = to_switch
        self.type = type
        self.length = length
        self.cores = cores


class LogicalLink:
    def __init__(self, from_switch, to_switch, type, total_length, couplers):
        self.from_switch = from_switch
        self.to_switch = to_switch
        self.type = type
        self.total_length = total_length
        self.couplers = couplers


class NocPlugin(object):
    BUFFER = 1
    UPDOWN_LENGTH = 6  # How many metres to add per and up-and-down a festoon pole
    COLOUR_HEADER = 'lightcyan1'
    COLOUR_COPPER = 'slateblue4'
    COLOUR_FIBRE = 'goldenrod'
    LENGTH_COPPER_NOT_CCA = 30
    LENGTH_COPPER_WARNING = 70
    LENGTH_COPPER_CRITICAL = 90

    def __init__(self, buildmap, _config, opts, db):
        self.log = logging.getLogger(__name__)
        self.db = db
        self.opts = opts
        self.buildmap = buildmap
        self.switch_layer = None
        self.link_layers = {}
        self.switches = {}
        self.links = []
        self.processed_links = set()
        self.processed_switches = set()
        self.logical_links = []
        self.warnings = []

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
                self.link_layers[layer[0]] = name_sub.lower()

        if self.switch_layer and len(self.link_layers) > 0:
            return True
        else:
            self.log.error("Unable to locate all required NOC layers. Layers discovered: %s" % layers)
            return False

    def _warning(self, msg):
        self.log.warning(msg)
        self.warnings.append(msg)

    def get_switches(self):
        self.log.info("Loading switches")
        for row in self.db.execute(text("SELECT * FROM site_plan WHERE layer = :layer"),
                                   layer=self.switch_layer):
            if 'switch' not in row or row['switch'] is None:
                self._warning("Switch name not found in entity 0x%s on %s layer" % (row['entityhandle'], self.switch_layer))
            yield Switch(row['switch'])

    def _find_switch_from_link(self, edge_entityhandle, edge_layer, edge_ogc_fid, start_or_end):
        node_sql = text("""SELECT switch.switch AS switch
                            FROM site_plan AS edge, site_plan AS switch
                            WHERE edge.ogc_fid=:edge_ogc_fid
                            AND switch.layer = ANY(:switch_layers)
                            AND ST_Buffer(switch.wkb_geometry, :buf) && ST_""" + start_or_end.title() + """Point(edge.wkb_geometry)
                            """)
        switch_result = self.db.execute(node_sql, edge_ogc_fid=edge_ogc_fid, switch_layers=[self.switch_layer], buf=self.BUFFER)
        switch_rows = switch_result.fetchall()
        if len(switch_rows) < 1:
            self._warning("Link 0x%s on %s layer does not %s at a switch" % (edge_entityhandle, edge_layer, start_or_end))
            return None
        elif len(switch_rows) > 1:
            self._warning("Link 0x%s on %s layer %ss at multiple switches" % (edge_entityhandle, edge_layer, start_or_end))
            return None
        switch = switch_rows[0]['switch']
        return switch

    def get_links(self):
        """ Returns all the links """
        self.log.info("Loading links")

        sql = text("""SELECT layer,
                            round(ST_Length(wkb_geometry)::NUMERIC, 1) AS length,
                            cores,
                            updowns,
                            entityhandle,
                            ogc_fid
                        FROM site_plan
                        WHERE layer = ANY(:link_layers) 
                        AND ST_GeometryType(wkb_geometry) = 'ST_LineString'
                    """)
        for row in self.db.execute(sql, link_layers=list(self.link_layers.keys())):
            from_switch = self._find_switch_from_link(row['entityhandle'], row['layer'], row['ogc_fid'], 'start')
            to_switch = self._find_switch_from_link(row['entityhandle'], row['layer'], row['ogc_fid'], 'end')
            if not from_switch or not to_switch:
                continue

            # self.log.info("Link from %s to %s" % (from_switch, to_switch))

            type = self.link_layers[row['layer']]
            length = row['length']
            if row['updowns'] is not None:
                length += int(row['updowns']) * self.UPDOWN_LENGTH

            if row['cores']:
                cores = int(row['cores'])
            else:
                self._warning("%s link from %s to %s had no cores, assuming 1" % (type.title(), from_switch, to_switch))
                cores = 1

            yield Link(from_switch, to_switch, type, length, cores)

    def order_links_from_switch(self, switch_name):
        if switch_name in self.processed_switches:
            self._warning("Switch %s has an infinite loop of links!" % switch_name)
            return

        self.processed_switches.add(switch_name)

        # find links that have us as their *to_switch* and swap them if they haven't already been swapped by a parent
        for link in self.links:
            if link.to_switch == switch_name:
                if link not in self.processed_links:
                    link.to_switch, link.from_switch = link.from_switch, link.to_switch

        # Now repeat for any switch we're connected to
        for link in self.links:
            if link.from_switch == switch_name:
                self.processed_links.add(link)  # Mark it as being correctly ordered
                self.order_links_from_switch(link.to_switch)

    def _validate_child_link_cores(self, switch_name):
        cores = 1  # One for the local fibre-served switch
        for link in self.links:
            if link.type == 'fibre' and link.from_switch == switch_name:
                child_switch_cores = self._validate_child_link_cores(link.to_switch)
                if link.cores != child_switch_cores:
                    self._warning("Link from %s to %s requires %d cores but has %d" % (switch_name, link.to_switch, child_switch_cores, link.cores))
                cores += child_switch_cores

        return cores

    def _make_logical_link(self, switch_name, logical_link):
        # Find our uplink. Assumption: only one uplink (fine for layer 2 design).
        # Physical links have already been ordered by this point so that "from_switch" is the core end.
        for link in self.links:
            if link.to_switch == switch_name:
                # print("Uplink from %s is to %s" % (switch_name, link.from_switch))

                # If we're extending:
                if logical_link.type is not None:
                    # If it's copper and it's not our first link, we're done, we can't extend any further.
                    # if link.type == 'copper' and :
                    #     return

                    # We can't extend to a different medium
                    if link.type != logical_link.type:
                        self.log.info("Can't extend %s uplink from %s onto %s link from %s back to %s" %
                                      (logical_link.type, logical_link.to_switch, link.type, link.to_switch, link.from_switch))
                        return

                # Extend to this switch
                logical_link.from_switch = link.from_switch
                logical_link.type = link.type
                logical_link.total_length += link.length
                logical_link.couplers += 1
                # print("Extend back from %s to %s, type %s, length now %d with %d couplers" %
                #       (logical_link.to_switch, link.from_switch, logical_link.type, logical_link.total_length, logical_link.couplers))

                # If it's fibre, we can try to continue extending
                if logical_link.type == 'fibre':
                    self._make_logical_link(link.from_switch, logical_link)

                return

    def generate_plan(self):
        for switch in self.get_switches():
            self.switches[switch.name] = switch

        for link in self.get_links():
            self.links.append(link)

        # Order links so that they go away from the core
        root_switch = self.switches[self.opts.get('core')]
        self.processed_switches = set()
        self.processed_links = set()
        self.order_links_from_switch(root_switch.name)

        # Validate that all fibre links have sufficient cores for all downstream links
        # Each incoming fibre to a switch should have (1+sum(child_fibre_links.cores))

        self._validate_child_link_cores(root_switch.name)

        # Create the logical links
        # We assume that any switch that is fibre in and fibre out is simply patched through with a coupler,
        # collapsing the two physical links into a single logical one
        #
        # Note that we can't assume it is fibre all the way back to the core, e.g. in 2018 this string is 3 logical links:
        # ESNORE [fibre] SWDKG1 [fibre] SWDKE2 [copper] SWWORKSHOP1 [fibre] SWDKF1
        #        ----------------------        --------             -------
        # We might in the future also need a way to put a "break" in here for fibre aggregation switches, e.g.
        # ESNORE [single core fibre] SWMIDDLE [8 single fibres] 8xDKs

        # So for every switch
        # (a) If incoming is copper, a single logical link to its immediate parent
        # (b) If incoming is fibre, a single logical link to the highest parent that is either core or doesn't itself have incoming fibre

        for switch_name in self.switches:
            if switch_name != root_switch.name:
                logical_link = LogicalLink(None, switch_name, None, 0, -1)
                self._make_logical_link(switch_name, logical_link)
                if logical_link.type is None:
                    self.log.error("Unable to trace logical uplink for %s", switch_name)
                    return False

                self.logical_links.append(logical_link)

        return True

    def _title_label(self, name, subheading):
        label = '<<table border="0" cellspacing="0" cellborder="1" cellpadding="5">'
        label += '<tr><td bgcolor="{}"><b>{}</b></td></tr>'.format(self.COLOUR_HEADER, name)
        label += '<tr><td>{}</td></tr>'.format(subheading)
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

    def _physical_link_label_and_colour(self, link):
        open = ''
        close = ''
        label = '<'
        if link.type == 'fibre':
            label += '{} cores'.format(link.cores)
            colour = self.COLOUR_FIBRE
        elif link.type == 'copper':
            length = float(link.length)
            if link.cores and int(link.cores) > 1:
                label += '<b>{}x</b> '.format(link.cores)

            label += self.get_link_medium(link)

            colour = self.COLOUR_COPPER
            if length > self.LENGTH_COPPER_CRITICAL:
                open += '<font color="red">'
                close = '</font>' + close
            elif length > self.LENGTH_COPPER_WARNING:
                open += '<font color="orange">'
                close = '</font>' + close
        else:
            self.log.error("Invalid type %s for link between %s and %s", link.type, link.from_switch, link.to_switch)
            return None, None

        label += '<br/>' + open
        label += '{}m'.format(str(link.length))
        label += close + '>'
        return colour, label

    def _logical_link_label_and_colour(self, logical_link):
        # open = ''
        # close = ''
        label = '<'
        label += '{}m'.format(str(logical_link.total_length)) + " " + logical_link.type

        if logical_link.type == 'fibre':
            if logical_link.couplers == 0:
                label += ' (direct)'
            else:
                label += ' ({} coupler{})'.format(logical_link.couplers, '' if logical_link.couplers == 1 else 's')
            colour = self.COLOUR_FIBRE
        elif logical_link.type == 'copper':
            # length = float(logical_link.length)
            # if logical_link.cores and int(logical_link.cores) > 1:
            #     label += '<b>{}x</b> '.format(logical_link.cores)
            # label += self.get_link_medium(logical_link)

            colour = self.COLOUR_COPPER
        else:
            self.log.error("Invalid type %s for link between %s and %s", logical_link.type, logical_link.from_switch, logical_link.to_switch)
            return None, None

        # label += '<br/>' + open
        # label += close
        label += '>'
        return colour, label

    def _create_base_dot(self, subheading):
        dot = pydot.Dot("NOC", graph_type='digraph', strict=True)
        dot.set_prog('neato')
        dot.set_node_defaults(shape='none', fontsize=14, margin=0, fontname='Arial')
        dot.set_edge_defaults(fontsize=13, fontname='Arial')
        # dot.set_page('11.7,8.3!')
        # dot.set_margin(0.5)
        # dot.set_ratio('fill')
        dot.set_rankdir('LR')
        dot.set_fontname('Arial')
        dot.set_nodesep(0.3)
        # dot.set_splines('line')

        sg = pydot.Cluster()  # 'physical', label='Physical')
        # sg.set_color('gray80')
        sg.set_style('invis')
        # sg.set_labeljust('l')
        dot.add_subgraph(sg)

        title = pydot.Node('title', shape='none', label=self._title_label(self.opts.get('name'), subheading))
        title.set_pos('0,0!')
        title.set_fontsize(18)
        dot.add_node(title)

        return dot, sg

    def create_physical_dot(self):
        self.log.info("Generating physical graph")
        dot, sg = self._create_base_dot("NOC Physical")

        for switch in self.switches.values():
            node = pydot.Node(switch.name, label=self._switch_label(switch))
            sg.add_node(node)

        for link in self.links:
            edge = pydot.Edge(link.from_switch, link.to_switch)

            colour, label = self._physical_link_label_and_colour(link)
            if label is None:
                return None

            # edge.set_tailport('{}-{}'.format(edgedata['current'], edgedata['phases']))
            edge.set_headport('input')
            edge.set_label(label)
            edge.set_color(colour)
            sg.add_edge(edge)

        return dot

    def create_logical_dot(self):
        self.log.info("Generating logical graph")
        dot, sg = self._create_base_dot("NOC Logical")

        for switch in self.switches.values():
            node = pydot.Node(switch.name, label=self._switch_label(switch))
            sg.add_node(node)

        for logical_link in self.logical_links:
            edge = pydot.Edge(logical_link.from_switch, logical_link.to_switch)

            colour, label = self._logical_link_label_and_colour(logical_link)
            if label is None:
                return None

            # edge.set_tailport('{}-{}'.format(edgedata['current'], edgedata['phases']))
            edge.set_headport('input')
            edge.set_label(label)
            edge.set_color(colour)
            sg.add_edge(edge)

        return dot

    def get_link_medium(self, link):
        if link.type == 'copper':
            length = float(link.length)
            if length <= self.LENGTH_COPPER_NOT_CCA:
                return "CCA"
        return link.type.title()

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info("NOC layers detected. Switches: '%s', Links: %s",
                      self.switch_layer, list(self.link_layers.keys()))

        start = time.time()
        if not self.generate_plan():
            return
        self.log.info("Plan generated in %.2f seconds", time.time() - start)

        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config['web_directory']),
            "noc"
        )

        if not os.path.isdir(out_path):
            os.makedirs(out_path)

        # switches.csv
        with open(os.path.join(out_path, 'switches.csv'), 'w') as switches_file:
            writer = csv.writer(switches_file)
            writer.writerow(['Switch-Name'])
            for switch in sorted(self.switches.values()):
                writer.writerow(switch)

        # links.csv
        with open(os.path.join(out_path, 'links.csv'), 'w') as links_file:
            writer = csv.writer(links_file)
            writer.writerow(['From-Switch', 'To-Switch', 'Type', 'Subtype', 'Length', 'Cores'])
            for link in self.links:
                writer.writerow([link.from_switch, link.to_switch, link.type, self.get_link_medium(link),
                                 link.length, link.cores])

        # links-logical.csv
        with open(os.path.join(out_path, 'links-logical.csv'), 'w') as links_file:
            writer = csv.writer(links_file)
            writer.writerow(['From-Switch', 'To-Switch', 'Type', 'Total-Length', 'Couplers'])
            for logical_link in self.logical_links:
                writer.writerow([logical_link.from_switch, logical_link.to_switch, logical_link.type,
                                 logical_link.total_length, logical_link.couplers])

        # warnings.txt
        with open(os.path.join(out_path, 'warnings.txt'), 'w') as warnings_file:
            warnings_file.writelines("\n".join(self.warnings))

        # stats.txt
        with open(os.path.join(out_path, 'stats.txt'), 'w') as stats_file:
            couplers = 0
            for logical_link in self.logical_links:
                if logical_link.type == 'fibre':
                    couplers += logical_link.couplers
            stats_file.write("Fibre couplers: %d\n" % (couplers))

        # noc-physical.pdf
        physical_dot = self.create_physical_dot()
        if not physical_dot:
            return
        with open(os.path.join(out_path, 'noc-physical.pdf'), 'wb') as f:
            f.write(physical_dot.create_pdf())

        # noc-logical.pdf
        logical_dot = self.create_logical_dot()
        if not logical_dot:
            return
        with open(os.path.join(out_path, 'noc-logical.pdf'), 'wb') as f:
            f.write(logical_dot.create_pdf())
