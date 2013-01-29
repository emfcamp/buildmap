import config

def header(cacheDirectory):
	return """
[cache]
type=Disk
base=%s

""" % cacheDirectory

def layer(name, mapFileLayers, mapDirectory):
	return """
[%s]
type=MapServerLayer
layers=%s
mapfile=ohm.map
debug=on
extension=png
resolutions=%s
srs=EPSG:28992
bbox=%s


""" % (name, ",".join(mapFileLayers), ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.extents)))

def footer():
	return ""
