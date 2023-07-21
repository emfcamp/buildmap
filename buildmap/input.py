import typing

if typing.TYPE_CHECKING:
    from .main import BuildMap


class Input:
    def __init__(self, buildmap: "BuildMap", table_name: str, layer_config: dict):
        self.table = table_name
        if "path" not in layer_config:
            raise ValueError(f"Layer {table_name} is missing path")
        self.path = buildmap.resolve_path(layer_config["path"])
        if not self.path.is_file():
            raise Exception("Source file %s does not exist" % self.path)

        self.config = layer_config

    @property
    def file_type(self):
        return self.path.suffix[1:].lower()
