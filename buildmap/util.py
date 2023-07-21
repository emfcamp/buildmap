import re


def sanitise_layer(name):
    name = re.sub(r"[- (\.\.\.)]+", "_", name.lower())
    name = re.sub(r"[\(\)]", "", name)
    name = name.strip("_")
    return name


def write_file(name, data):
    with open(name, "w") as fp:
        fp.write(data)


def build_options(options: dict) -> list[str]:
    """Build a list of command-line options for ogr2ogr from a dict containing those options.

    Allows multiple options with multiple values such as:
    ```
    {
        "-config": [
            ["DXF_ENCODING", "UTF-8"],
            ["DXF_INCLUDE_RAW_CODE_VALUES", "TRUE"]
        ]
    }
    ```
    """
    for k, v in options.items():
        if v is None:
            yield k
        elif isinstance(v, list):
            for i in v:
                yield k
                if isinstance(i, list):
                    for j in i:
                        yield j
                else:
                    yield i
        else:
            yield k
            yield v
