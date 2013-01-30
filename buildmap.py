import datetime
import os
import re
import shutil
import subprocess
import tempfile

import map
import tilecache
import html

import config
import layers

def sanitize(filename):
	output = ''
	for c in filename:
		if c.isalnum():
			output += c
		else:
			output += '_'
	return output

def findFile(filename):
	for directory in config.directories:
		fullPath = directory + '/' + filename
		if os.path.isfile(fullPath):
			return fullPath
	return None

fileLayerCache = {}
def fileLayers(filename):
	if filename not in fileLayerCache:
		proc = os.popen("ogrinfo '%s' -al | grep -E '  Layer \\(String\\) = .*' | sed -e 's/  Layer (String) = //' | sort | uniq" % filename, "r")
		layers = []
		for line in proc:
			layer = line.strip("\n")
			if len(layer) > 0:
				layers.append(layer)
		proc.close()
		fileLayerCache[filename] = layers
	return fileLayerCache[filename]

def makeShapeFiles(sourceFile, layerName, outputTemplate):
	if sourceFile.lower()[-4:] == ".dxf":
		output = []
		for (type, suffix) in [('POINT', 'points'), ('LINESTRING', 'lines'), ('POLYGON', 'areas')]:
			filename = "%s-%s.shp" % (outputTemplate, suffix)
			output.append("echo Generating shapefile '%s'...; ogr2ogr -skipfailures -where \"LAYER = '%s'\" '%s' '%s' -nlt %s 2>/dev/null" % (filename, layerName, filename, sourceFile, type))
		return output
	else:
		raise Exception("Unsupported source file format: '%s'" % sourceFile)
	

def runCommands(commands):
	processes = {}
	while len(commands) > 0 or len(processes) > 0:
		if len(commands) > 0 and len(processes) < config.threads:
			process = subprocess.Popen(commands[0], shell = True)
			del commands[0]
			processes[process.pid] = process
		if len(commands) == 0 or len(processes) >= config.threads:
			(pid, status) = os.wait()
			if pid in processes:
				del processes[pid]

mapDir = tempfile.mkdtemp("-buildmap")
os.chdir(mapDir)

tilesDir = config.wwwDirectory + "/tiles"
tempTilesDir = tilesDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
oldTilesDir = tilesDir + "-old"


mapFile = map.header()
tilecacheFile = tilecache.header(tempTilesDir)
htmlFile = html.header()


commands = []
for (layerName, layer) in layers.layers:
	mapLayers = []
	for component in layer:
		sourcePath = findFile(component['file'])
		if sourcePath == None:
			raise Exception("Couldn't find souce file '%s'" % component['file'])
		for sourceLayer in fileLayers(sourcePath):
			match = False
			for regex in component['layers']:
				if re.match(regex + "$", sourceLayer):
					match = True
					break
			if match:
				filename = "%s-%s" % (sanitize(component['file']), sanitize(sourceLayer))
				commands += makeShapeFiles(sourcePath, sourceLayer, filename)
				mapLayer = sanitize(sourceLayer)
				
				if 'color' in component:
					identifier = mapLayer + "-lines"
					mapFile += map.lineLayer(identifier, filename, sourceLayer, component['color'], component['width'])
					mapLayers.append(identifier)
				if 'fill' in component:
					identifier = mapLayer + "-areas"
					mapFile += map.areaLayer(identifier, filename, sourceLayer, component['fill'])
					mapLayers.append(identifier)
				if 'text' in component:
					identifier = mapLayer + "-points"
					mapFile += map.pointLayer(identifier, filename, sourceLayer, component['text'], component['fontSize'])
					mapLayers.append(identifier)
	tilecacheFile += tilecache.layer(layerName, mapLayers, mapDir)
	htmlFile += html.layer(layerName, layerName)
runCommands(commands)

mapFile += map.footer()
tilecacheFile += tilecache.footer()
htmlFile += html.footer()

print "Generating mapfile 'ohm.map'..."
mapStream = open('ohm.map', 'w')
mapStream.write(mapFile)
mapStream.close()

print "Generating 'tilecache.cfg'..."
tilecacheStream = open('tilecache.cfg', 'w')
tilecacheStream.write(tilecacheFile)
tilecacheStream.close()

for filename in config.mapExtraFiles:
	shutil.copy(filename, ".")

commands = []
for (layerName, layer) in layers.layers:
	commands.append("tilecache_seed.py '%s' %s" % (layerName, len(config.resolutions)))
print "Generating tiles..."
runCommands(commands)

shutil.rmtree(oldTilesDir, True)
if os.path.exists(tilesDir):
	shutil.move(tilesDir, oldTilesDir)
shutil.move(tempTilesDir, tilesDir)

print "Writing 'index.html'..."
htmlStream = open(config.wwwDirectory + '/index.html', 'w')
htmlStream.write(htmlFile)
htmlStream.close()

os.chdir("/")
shutil.rmtree(mapDir, True)
shutil.rmtree(oldTilesDir, True)
