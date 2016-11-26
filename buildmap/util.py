# encoding=utf-8
import re


def sanitise_layer(name):
    name = re.sub(r'[- (\.\.\.)]+', '_', name.lower())
    name = re.sub(r'[\(\)]', '', name)
    return name


def iterate_hcl(obj):
    """ A list of objects in HCL can either be a dict or a list of
        dicts, for some ridiculous reason."""
    if type(obj) is list:
        for i in obj:
            for k, v in i.items():
                yield k, v
    else:
        for k, v in obj.items():
            yield k, v


def write_file(name, data):
    with open(name, 'w') as fp:
        fp.write(data)
