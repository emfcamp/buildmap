import os.path
import json
from sqlalchemy import text


class TranslatePlugin(object):
    """Translate or modify map text."""

    def __init__(self, buildmap, _config, opts, db):
        self.db = db
        self.buildmap = buildmap
        self.opts = opts

    def update_translation_file(self, table, file_name):
        try:
            with open(file_name, "r") as f:
                data = json.load(f)
        except IOError:
            data = {}

        for layer in self.opts.get("layers", []):
            q = self.db.execute(
                text(
                    "SELECT text FROM %s WHERE layer = '%s' AND text != ''"
                    % (table, layer)
                )
            )
            for row in q:
                if row[0] not in data:
                    data[row[0]] = row[0]

        with open(file_name, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data

    def insert_translations(self, table, lang, translations):
        trans_col = "text_{}".format(lang)
        self.db.execute(
            text(
                "ALTER TABLE {table} ADD COLUMN {col} TEXT".format(
                    table=table, col=trans_col
                )
            )
        )

        for orig, translated in translations.items():
            self.db.execute(
                text(
                    "UPDATE {table} SET {col} = :translated WHERE text = :orig".format(
                        table=table, col=trans_col
                    )
                ),
                translated=translated,
                orig=orig,
            )

        self.buildmap.known_attributes[table].add(trans_col)

    def run(self):
        table = "site_plan"
        for lang in self.opts.get("languages", []):
            trans_file = os.path.join(
                self.buildmap.base_path, "translations_{}.json".format(lang)
            )
            data = self.update_translation_file(table, trans_file)
            self.insert_translations(table, lang, data)
