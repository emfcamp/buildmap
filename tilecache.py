import config

def header():
	return """
[cache]
type=Disk
base=%s

""" % config.cacheDirectory

def layer(name, mapFileLayers):
	return """
[%s]
type=MapServerLayer
layers=%s
mapfile=%s/ohm.map
debug=on
extension=png
resolutions=%s
srs=EPSG:28992
bbox=%s


""" % (name, ",".join(mapFileLayers), config.mapDirectory, ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.extents)))

def footer():
	return ""
