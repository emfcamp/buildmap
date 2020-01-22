import logging
import time
import os.path
import pydotplus as pydot  # type: ignore
import csv
import html
from typing import Iterator
from sqlalchemy.sql import text
from datetime import date
from .data import LinkType, Switch, LogicalLink, Link
from .util import unit, get_col


class NocPlugin(object):

    # Tolerance for how close a link must be to a switch to consider that it connects (metres)
    BUFFER = 1

    # How many metres to add per and up-and-down a festoon pole
    UPDOWN_LENGTH = 6 * unit.meters

    # Colours for the output diagrams - https://graphviz.org/doc/info/colors.html
    COLOUR_HEADER = "lightcyan1"
    COLOUR_COPPER = "slateblue4"
    COLOUR_FIBRE = "goldenrod"

    # Copper links below this length are considered to be CCA
    LENGTH_COPPER_NOT_CCA = 30 * unit.meters

    # Copper links above these lengths will generate warnings or errors
    LENGTH_COPPER_WARNING = 70 * unit.meters
    LENGTH_COPPER_CRITICAL = 90 * unit.meters

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
        self.table = self.opts.get("table", "site_plan")
        self.table_columns = set(self.db.get_columns(self.table))

    def generate_layers_config(self):
        " Detect NOC layers in map. "
        self.log.info("Looking for NOC layers in table {}...".format(self.table))
        prefix = self.opts["layer_prefix"]
        layers = list(
            self.db.execute(
                self._sql(
                    "SELECT DISTINCT layer FROM {table} WHERE layer LIKE :prefix"
                ),
                prefix=prefix + "%",
            )
        )

        for layer in layers:
            name_sub = layer[0][len(prefix) :].strip()  # De-prefix the layer name

            if name_sub.lower() == self.opts.get("switch_layer", "switch").lower():
                self.switch_layer = layer[0]
            elif name_sub.lower() in [
                name.lower() for name in self.opts.get("copper_layers", ["copper"])
            ]:
                self.link_layers[layer[0]] = LinkType.Copper
            elif name_sub.lower() in [
                name.lower() for name in self.opts.get("fibre_layers", ["fibre"])
            ]:
                self.link_layers[layer[0]] = LinkType.Fibre

        if self.switch_layer is None:
            self.log.error("Unable to locate switch layer")
            return False

        if len(self.link_layers) == 0:
            self.log.error("Unable to locate any link layers")
            return False

        return True

    def _warning(self, msg):
        self.log.warning(msg)
        self.warnings.append(msg)

    def _sql(self, sql, cols=None):
        if cols:
            cols = ", ".join(set(cols) & self.table_columns)
        return text(sql.format(table=self.table, columns=cols))

    def get_switches(self):
        self.log.info("Loading switches")
        for row in self.db.execute(
            self._sql(
                """SELECT * FROM {table}
                    WHERE layer = :layer
                    AND ST_GeometryType(wkb_geometry) = 'ST_Point'"""
            ),
            layer=self.switch_layer,
        ):
            if "switch" in row and row["switch"] is not None:
                name = row["switch"]
            else:
                self._warning(
                    "Switch name not found in entity 0x%s on %s layer"
                    % (row["entityhandle"], self.switch_layer)
                )
                name = row["entityhandle"]
            yield Switch(
                name,
                int(get_col(row, "cores_required", 1)),
                get_col(row, "deployed") == "true",
            )

    def _find_switch_from_link(
        self, edge_entityhandle, edge_layer, edge_ogc_fid, start_or_end
    ):
        col = "COALESCE(switch.switch, switch.entityhandle)"
        if "switch" not in self.table_columns:
            col = "switch.entityhandle"

        node_sql = self._sql(
            "SELECT "
            + col
            + """ AS switch
                            FROM {table} AS edge, {table} AS switch
                            WHERE edge.ogc_fid=:edge_ogc_fid
                            AND switch.layer = ANY(:switch_layers)
                            AND ST_GeometryType(switch.wkb_geometry) = 'ST_Point'
                            AND ST_Buffer(switch.wkb_geometry, :buf) && ST_"""
            + start_or_end.title()
            + """Point(edge.wkb_geometry)
                            """
        )
        switch_result = self.db.execute(
            node_sql,
            edge_ogc_fid=edge_ogc_fid,
            switch_layers=[self.switch_layer],
            buf=self.BUFFER,
        )
        switch_rows = switch_result.fetchall()
        if len(switch_rows) < 1:
            self._warning(
                "Link 0x%s on %s layer does not %s at a switch"
                % (edge_entityhandle, edge_layer, start_or_end)
            )
            return None
        elif len(switch_rows) > 1:
            self._warning(
                "Link 0x%s on %s layer %ss at multiple switches"
                % (edge_entityhandle, edge_layer, start_or_end)
            )
            return None

        switch_name = switch_rows[0]["switch"]
        return self.switches[switch_name]

    def get_links(self) -> Iterator[Link]:
        """ Returns all the links """
        self.log.info("Loading links")

        sql = self._sql(
            """SELECT *, round(ST_Length(wkb_geometry)::NUMERIC, 1) AS length
                        FROM {table}
                        WHERE layer = ANY(:link_layers)
                        AND ST_GeometryType(wkb_geometry) = 'ST_LineString'
                    """
        )
        for row in self.db.execute(sql, link_layers=list(self.link_layers.keys())):
            from_switch = self._find_switch_from_link(
                row["entityhandle"], row["layer"], row["ogc_fid"], "start"
            )
            to_switch = self._find_switch_from_link(
                row["entityhandle"], row["layer"], row["ogc_fid"], "end"
            )
            if not from_switch or not to_switch:
                continue

            # self.log.info("Link from %s to %s" % (from_switch, to_switch))

            type = self.link_layers[row["layer"]]
            length = row["length"] * unit.meter
            if "updowns" in row and row["updowns"] is not None:
                length += int(row["updowns"]) * self.UPDOWN_LENGTH

            if "cores" in row and row["cores"]:
                cores = int(row["cores"])
            else:
                self._warning(
                    "%s link from %s to %s had no cores, assuming 1"
                    % (type.value.title(), from_switch, to_switch)
                )
                cores = 1

            yield Link(
                from_switch=from_switch,
                to_switch=to_switch,
                type=type,
                length=length,
                cores=cores,
                deployed=get_col(row, "deployed") == "true",
                aggregated=get_col(row, "aggregated") is not None,
                fibre_name=get_col(row, "fiber"),
            )

    def order_links_from_switch(self, switch: Switch):
        if switch in self.processed_switches:
            self._warning("Switch %s has an infinite loop of links!" % switch)
            return

        self.processed_switches.add(switch)

        # find links that have us as their *to_switch* and swap them if they haven't already been swapped by a parent
        for link in self.links:
            if link.to_switch == switch:
                if link not in self.processed_links:
                    link.to_switch, link.from_switch = link.from_switch, link.to_switch

        # Now repeat for any switch we're connected to
        for link in self.links:
            if link.from_switch == switch:
                self.processed_links.add(link)  # Mark it as being correctly ordered
                self.order_links_from_switch(link.to_switch)

    def _validate_child_link_cores(self, switch: Switch):
        cores = switch.cores_required  # Cores required by the switch itself (usually 1)
        for link in self.links:
            if link.type == LinkType.Fibre and link.from_switch == switch:
                if link.aggregated:
                    # This link is aggregated so there's only one downstream core
                    child_switch_cores = 0
                    link.cores_used = 1
                else:
                    # Count the cores for all switches below this node in the tree
                    child_switch_cores = self._validate_child_link_cores(link.to_switch)
                    link.cores_used = child_switch_cores

                if link.cores < child_switch_cores:
                    self._warning(
                        "Link from %s to %s requires %d cores but only has %d"
                        % (switch.name, link.to_switch, child_switch_cores, link.cores)
                    )
                cores += child_switch_cores

        return cores

    def _make_logical_link(self, switch: Switch, logical_link: LogicalLink):
        # Find our uplink. Assumption: only one uplink (fine for layer 2 design).
        # Physical links have already been ordered by this point so that "from_switch" is the core end.
        for link in self.links:
            if link.to_switch == switch:
                # If we're extending:
                if logical_link.type is not None:

                    # We can't extend to a different medium
                    if link.type != logical_link.type:
                        self.log.info(
                            "Can't extend %s uplink from %s onto %s link from %s back to %s"
                            % (
                                logical_link.type,
                                logical_link.to_switch,
                                link.type,
                                link.to_switch,
                                link.from_switch,
                            )
                        )
                        return

                # Extend to this switch
                logical_link.from_switch = link.from_switch
                logical_link.type = link.type
                logical_link.physical_links.append(link)

                # If it's fibre, and the "aggregated" attribute isn't set, we try to
                # extend the logical link
                if logical_link.type == LinkType.Fibre and not link.aggregated:
                    self._make_logical_link(link.from_switch, logical_link)

                return

    def generate_plan(self):
        for switch in self.get_switches():
            self.switches[switch.name] = switch

        for link in self.get_links():
            self.links.append(link)

        # Order links so that they go away from the core
        if self.opts.get("core") and self.opts["core"] in self.switches:
            root_switch = self.switches[self.opts.get("core")]
        else:
            self._warning(
                "Specified core switch %s does not exist. Using first available switch as root."
                % self.opts.get("core")
            )
            root_switch = list(self.switches.values())[0]

        self.processed_switches = set()
        self.processed_links = set()
        self.order_links_from_switch(root_switch)

        # Validate that all fibre links have sufficient cores for all downstream links
        # Each incoming fibre to a switch should have (1+sum(child_fibre_links.cores))

        self._validate_child_link_cores(root_switch)

        # Create the logical links
        # We assume that any switch that is fibre in and fibre out is simply patched through with a coupler,
        # collapsing the two physical links into a single logical one
        #
        # Note that we can't assume it is fibre all the way back to the core,
        # e.g. in 2018 this string is 3 logical links:
        #
        # ESNORE [fibre] SWDKG1 [fibre] SWDKE2 [copper] SWWORKSHOP1 [fibre] SWDKF1
        #        ----------------------        --------             -------
        #
        # We might in the future also need a way to put a "break" in here for fibre aggregation switches, e.g.
        # ESNORE [single core fibre] SWMIDDLE [8 single fibres] 8xDKs

        # So for every switch
        # (a) If incoming is copper, a single logical link to its immediate parent
        # (b) If incoming is fibre, a single logical link to the highest parent that is either core or doesn't
        #     itself have incoming fibre

        for switch in self.switches.values():
            if switch != root_switch:
                logical_link = LogicalLink(None, switch, None)
                self._make_logical_link(switch, logical_link)
                if logical_link.type is None:
                    self._warning("Unable to trace logical uplink for %s" % switch)
                    continue

                self.logical_links.append(logical_link)

        return True

    def _title_label(self, name, subheading):
        label = '<<table border="0" cellspacing="0" cellborder="1" cellpadding="5">'
        label += '<tr><td bgcolor="{}"><b>{}</b></td></tr>'.format(
            self.COLOUR_HEADER, name
        )
        label += "<tr><td>{}</td></tr>".format(subheading)
        label += "<tr><td>{}</td></tr>".format(date.today().isoformat())
        label += "</table>>"
        return label

    def _switch_label(self, switch):
        " Label format for a switch. Using graphviz's HTML table support "

        label = '<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" color="grey30">\n'
        label += """<tr><td bgcolor="{colour}" colspan="2"><font point-size="16"><b>{name}</b></font></td>
                        </tr>""".format(
            name=switch.name, colour=self.COLOUR_HEADER
        )
        # <!--td bgcolor="{colour}"><font point-size="16">{type}</font></td-->
        # label += '<tr><td port="input"></td><td port="output"></td></tr>'
        label += "</table>>"
        return label

    def _physical_link_label_and_colour(self, link: Link):
        open = ""
        close = ""
        label = "<"

        if link.type == LinkType.Fibre:
            if link.fibre_name:
                label += html.escape(link.fibre_name) + ": "
            if link.cores_used != link.cores:
                label += str(link.cores_used) + "/"
            label += str(link.cores) + " " + ("cores" if link.cores > 1 else "core")
            if link.aggregated:
                label += "<br/>(aggregated)"
            colour = self.COLOUR_FIBRE
        elif link.type == LinkType.Copper:
            if link.cores and int(link.cores) > 1:
                label += "<b>{}x</b> ".format(link.cores)

            label += self.get_link_medium(link)

            colour = self.COLOUR_COPPER
            if link.length > self.LENGTH_COPPER_CRITICAL:
                open += '<font color="red">'
                close = "</font>" + close
            elif link.length > self.LENGTH_COPPER_WARNING:
                open += '<font color="orange">'
                close = "</font>" + close
        else:
            self.log.error(
                "Invalid type %s for link between %s and %s",
                link.type,
                link.from_switch,
                link.to_switch,
            )
            return None, None

        label += "<br/>" + open
        label += "{:~}".format(link.length.to_compact())
        label += close + ">"
        return colour, label

    def _logical_link_label_and_colour(self, logical_link: LogicalLink):
        # open = ''
        # close = ''
        label = "<"
        label += "{:~} {}<br />".format(
            logical_link.total_length.to_compact(), logical_link.type.value
        )

        if logical_link.type == LinkType.Fibre:
            if logical_link.couplers == 0:
                label += "Direct"
            else:
                label += "{} coupler{}".format(
                    logical_link.couplers, "" if logical_link.couplers == 1 else "s"
                )
            label += " {:~.2f}".format(logical_link.loss())
            colour = self.COLOUR_FIBRE
        elif logical_link.type == LinkType.Copper:
            # length = float(logical_link.length)
            # if logical_link.cores and int(logical_link.cores) > 1:
            #     label += '<b>{}x</b> '.format(logical_link.cores)
            # label += self.get_link_medium(logical_link)

            colour = self.COLOUR_COPPER
        else:
            self.log.error(
                "Invalid type %s for link between %s and %s",
                logical_link.type,
                logical_link.from_switch,
                logical_link.to_switch,
            )
            return None, None

        # label += '<br/>' + open
        # label += close
        label += ">"
        return colour, label

    def _create_base_dot(self, subheading):
        dot = pydot.Dot("NOC", graph_type="digraph", strict=True)
        dot.set_prog("neato")
        dot.set_node_defaults(shape="none", fontsize=14, margin=0, fontname="Arial")
        dot.set_edge_defaults(fontsize=13, fontname="Arial")
        # dot.set_page('11.7,8.3!')
        # dot.set_margin(0.5)
        # dot.set_ratio('fill')
        dot.set_rankdir("LR")
        dot.set_fontname("Arial")
        dot.set_nodesep(0.3)
        dot.set_splines("spline")

        sg = pydot.Cluster()  # 'physical', label='Physical')
        # sg.set_color('gray80')
        sg.set_style("invis")
        # sg.set_labeljust('l')
        dot.add_subgraph(sg)

        title = pydot.Node(
            "title",
            shape="none",
            label=self._title_label(self.opts.get("name"), subheading),
        )
        title.set_pos("0,0!")
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
            edge = pydot.Edge(link.from_switch.name, link.to_switch.name)

            colour, label = self._physical_link_label_and_colour(link)
            if label is None:
                return None

            # edge.set_headport('input') # not sure why head and tail are the wrong way around
            # edge.set_tailport('output')
            edge.set_label(label)
            edge.set_color(colour)
            if not link.deployed:
                edge.set("style", "dashed")
            sg.add_edge(edge)

        return dot

    def create_logical_dot(self):
        self.log.info("Generating logical graph")
        dot, sg = self._create_base_dot("NOC Logical")

        for switch in self.switches.values():
            node = pydot.Node(switch.name, label=self._switch_label(switch))
            sg.add_node(node)

        for logical_link in self.logical_links:
            edge = pydot.Edge(
                logical_link.from_switch.name, logical_link.to_switch.name
            )

            colour, label = self._logical_link_label_and_colour(logical_link)
            if label is None:
                return None

            # edge.set_headport('input') # not sure why head and tail are the wrong way around
            # edge.set_tailport('output')
            edge.set_label(label)
            edge.set_color(colour)
            if not logical_link.deployed:
                edge.set("style", "dashed")
            sg.add_edge(edge)

        return dot

    def get_link_medium(self, link: Link):
        if link.type == LinkType.Copper:
            if link.length <= self.LENGTH_COPPER_NOT_CCA:
                return "CCA"
        return link.type.value.title()

    def _write_stats(self, stats_file):
        # Physical links
        copper_count = fibre_count = fibre_cores = 0
        copper_length = 0 * unit.meter
        fibre_length = 0 * unit.meter
        fibre_core_length = 0 * unit.meter
        for link in self.links:
            if link.type == LinkType.Fibre:
                fibre_count += 1
                fibre_length += link.length
                fibre_cores += link.cores
                fibre_core_length += link.length * link.cores
            elif link.type == LinkType.Copper:
                copper_count += link.cores
                copper_length += link.length
        stats_file.write("Number of physical links: {}\n".format(len(self.links)))
        stats_file.write(
            "- Fibre: {} (Total {:~}, {} total cores, total strand length {:~})\n".format(
                fibre_count,
                fibre_length.to_compact(),
                fibre_cores,
                fibre_core_length.to_compact(),
            )
        )
        stats_file.write(
            "- Copper: {} (Total {:~})\n".format(
                copper_count, copper_length.to_compact()
            )
        )

        # Logical links
        copper_count = fibre_count = 0
        copper_length = 0 * unit.meter
        fibre_length = 0 * unit.meter
        couplers = 0
        for logical_link in self.logical_links:
            if logical_link.type == LinkType.Fibre:
                fibre_count += 1
                fibre_length += logical_link.total_length
                couplers += logical_link.couplers
            elif logical_link.type == LinkType.Copper:
                copper_count += 1
                copper_length += logical_link.total_length
        stats_file.write(
            "Number of logical links: {}\n".format(len(self.logical_links))
        )
        stats_file.write(
            "- Fibre: {} (Total {:~})\n".format(fibre_count, fibre_length.to_compact())
        )
        stats_file.write(
            "- Copper: {} (Total {:~})\n".format(
                copper_count, copper_length.to_compact()
            )
        )
        stats_file.write("- Fibre couplers: %d\n" % (couplers))

    def run(self):
        if not self.generate_layers_config():
            return
        self.log.info(
            "NOC layers detected. Switches: '%s', Links: %s",
            self.switch_layer,
            list(self.link_layers.keys()),
        )

        start = time.time()
        if not self.generate_plan():
            return
        self.log.info("Plan generated in %.2f seconds", time.time() - start)

        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config["web_directory"]), "noc"
        )

        if not os.path.isdir(out_path):
            os.makedirs(out_path)

        # switches.csv
        with open(os.path.join(out_path, "switches.csv"), "w") as switches_file:
            writer = csv.writer(switches_file)
            writer.writerow(["Switch-Name"])
            for switch in sorted(self.switches.values()):
                writer.writerow(switch.name)

        # links.csv
        with open(os.path.join(out_path, "links.csv"), "w") as links_file:
            writer = csv.writer(links_file)
            writer.writerow(
                ["From-Switch", "To-Switch", "Type", "Subtype", "Length", "Cores"]
            )
            for link in self.links:
                writer.writerow(
                    [
                        link.from_switch,
                        link.to_switch,
                        link.type,
                        self.get_link_medium(link),
                        link.length,
                        link.cores,
                    ]
                )

        # links-logical.csv
        with open(os.path.join(out_path, "links-logical.csv"), "w") as links_file:
            writer = csv.writer(links_file)
            writer.writerow(
                ["From-Switch", "To-Switch", "Type", "Total-Length", "Couplers"]
            )
            for logical_link in self.logical_links:
                writer.writerow(
                    [
                        logical_link.from_switch,
                        logical_link.to_switch,
                        logical_link.type,
                        logical_link.total_length,
                        logical_link.couplers,
                    ]
                )

        # warnings.txt
        with open(os.path.join(out_path, "warnings.txt"), "w") as warnings_file:
            warnings_file.writelines("\n".join(self.warnings))

        # stats.txt
        with open(os.path.join(out_path, "stats.txt"), "w") as stats_file:
            self._write_stats(stats_file)

        # noc-physical.pdf
        physical_dot = self.create_physical_dot()
        if not physical_dot:
            return
        with open(os.path.join(out_path, "noc-physical.pdf"), "wb") as f:
            f.write(physical_dot.create_pdf())

        # noc-logical.pdf
        logical_dot = self.create_logical_dot()
        if not logical_dot:
            return
        with open(os.path.join(out_path, "noc-logical.pdf"), "wb") as f:
            f.write(logical_dot.create_pdf())
