def parse_attributes(rawcodevalues: list) -> dict:
    """Given a `rawcodevalues` array from a DB table produced by ogr2ogr,
    extract the DXF extended attributes and return them as a dict.
    """

    attributes = {}

    for attr in rawcodevalues:
        attr_id, val = attr.split(" ", 1)
        if attr_id == "1000" and ":" in val:
            key, val = val.split(":", 1)
            attributes[key.lower()] = val.replace("-", " ")

    return attributes
