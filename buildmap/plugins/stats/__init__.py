import os.path
from sqlalchemy import text
from jinja2 import Environment, PackageLoader, select_autoescape


class StatsPlugin(object):

    def __init__(self, buildmap, _config, opts, db):
        self.db = db
        self.buildmap = buildmap
        self.opts = opts
        self.env = Environment(
            loader=PackageLoader('buildmap.plugins.stats', 'templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def collect_stats(self):
        table = "site_plan"
        stats = {'length': [], 'count': [], 'area': []}

        for layer in self.opts.get('length', []):
            length = self.db.execute(text(
                "SELECT sum(ST_Length(wkb_geometry)) FROM %s WHERE layer = '%s'" %
                (table, layer)
            )).first()
            stats['length'].append((layer, length[0]))

        for layer in self.opts.get('count', []):
            count = self.db.execute(text(
                "SELECT count(*) FROM %s WHERE layer = '%s'" % (table, layer))).first()
            stats['count'].append((layer, count[0]))

        for name, conf in self.opts.get('area', {}).items():
            res = {"rows": []}
            for row in self.db.execute(text(conf['sql'])):
                res['rows'].append((row[1], row[0], row[0] / conf['density']))

            res['totals'] = (
                sum(row[1] for row in res['rows']),
                sum(row[2] for row in res['rows']),
            )
            stats['area'].append((name, res))

        return stats

    def run(self):
        stats = self.collect_stats()

        out_path = os.path.join(
            self.buildmap.resolve_path(self.buildmap.config['web_directory']),
            "stats"
        )

        try:
            os.makedirs(out_path)
        except FileExistsError:
            pass

        template = self.env.get_template("stats.html")
        with open(os.path.join(out_path, 'stats.html'), 'w') as f:
            f.write(template.render(stats=stats))
