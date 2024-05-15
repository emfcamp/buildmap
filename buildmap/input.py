from pathlib import Path
import typing

if typing.TYPE_CHECKING:
    from .main import BuildMap


class Input:
    def __init__(self, buildmap: "BuildMap", table_name: str, layer_config: dict):
        self.buildmap = buildmap
        self.table = table_name
        self.local_path = None
        if "path" not in layer_config:
            raise ValueError(f"Layer {table_name} is missing path")
        self.config = layer_config

    @property
    def path(self):
        path = self.config["path"]
        # check if path is a URL
        if path.startswith("http://") or path.startswith("https://"):
            if self.local_path:
                return self.local_path
            else:
                self.local_path = self.buildmap.download(path)
                return self.local_path

        path = self.buildmap.resolve_path(path)
        if not path.is_file():
            raise Exception("Source file %s does not exist" % path)
        return path

    @property
    def file_type(self):
        suffix = self.path.suffix[1:].lower()
        if suffix == "json":
            suffix = "geojson"
        return suffix
