import re


def sanitise_layer(name):
    if name is None:
        return ''
    name = re.sub(r"[- (\.\.\.)]+", "_", name.lower())
    name = re.sub(r"[\(\)]", "", name)
    name = name.strip("_")
    return name


def write_file(name, data):
    with open(name, "w") as fp:
        fp.write(data)
