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
		
		output.append("""
echo Generating shapefile '%s-lines.shp'...;
ogr2ogr -skipfailures -where \"LAYER = '%s'\" '%s-lines.shp' '%s' -nlt LINESTRING 2>/dev/null
""" % (outputTemplate, layerName, outputTemplate, sourceFile))
		
		output.append("""
echo Generating shapefile '%s-areas.shp'...;
ogr2ogr -skipfailures -where \"LAYER = '%s'\" '%s-areas.shp' '%s' -nlt POLYGON 2>/dev/null
""" % (outputTemplate, layerName, outputTemplate, sourceFile))
		
		output.append("""
echo Generating shapefile '%s-points.shp'...;
ogr2ogr -skipfailures -where \"LAYER = '%s'\" '%s-points.shp' '%s' -nlt POINT 2>/dev/null;
ogr2ogr -f CSV -skipfailures -sql 'SELECT *, OGR_STYLE FROM entities WHERE LAYER = "%s"' '%s-points-data.csv' '%s' -nlt POINT 2>/dev/null;
ogr2ogr -f CSV '%s-points-orig.csv' '%s-points.shp';
fixlabels.py '%s-points-orig.csv' '%s-points-data.csv' '%s-points-fixed.csv';
ogr2ogr '%s-points-fixed.shp' '%s-points-fixed.csv' 2>/dev/null;
cp '%s-points-fixed.dbf' '%s-points.dbf'
""" % (outputTemplate, layerName, outputTemplate, sourceFile, layerName, outputTemplate, sourceFile, outputTemplate, outputTemplate, outputTemplate, outputTemplate, outputTemplate, outputTemplate, outputTemplate, outputTemplate, outputTemplate))
		
		
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

def opaque(layer):
	for input in layer["input"]:
		if 'fill' in input:
			return True
	return False


layerMap = {}
for layer in layers.layers:
	layerMap[layer["title"]] = layer

mergeLayerIndex = 0
mergeLayers = []

insertPoint = 0
insertPointFixed = False

for layerSet in layers.layerSets:
	name = 'Merge-%d' % mergeLayerIndex
	mergeLayer = { 'title': name, 'input': [], 'enabled': True, 'hidden': True }
	mergeLayerIndex += 1
	for layer in layerSet:
		mergeLayer['input'].extend(layerMap[layer]['input'])
		if 'enabled' in layerMap[layer] and not layerMap[layer]['enabled']:
			mergeLayer['enabled'] = False
		layerMap[layer]['mergeLayer'] = name
		if opaque(layerMap[layer]) and not insertPointFixed:
			insertPoint += 1
		else:
			insertPointFixed = True
	if mergeLayer['enabled']:
		for layer in layerSet:
			layerMap[layer]['enabled'] = False
	mergeLayers.append(mergeLayer)
layers.layers[insertPoint:insertPoint] = mergeLayers


mapDir = tempfile.mkdtemp("-buildmap")
os.chdir(mapDir)

tilesDir = config.wwwDirectory + "/tiles"
tempTilesDir = tilesDir + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
oldTilesDir = tilesDir + "-old"


mapFile = map.header()
tilecacheFile = tilecache.header(tempTilesDir)
htmlFile = html.header()
layersDefFile = ''


generated = []


commands = []
for layer in layers.layers:
	mapLayers = []
	for component in layer['input']:
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
				if sourceLayer not in generated:
					commands += makeShapeFiles(sourcePath, sourceLayer, filename)
					generated.append(sourceLayer)
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
					mapFile += map.pointLayer(identifier, filename, sourceLayer, component['text'], component['fontSize'] if 'fontSize' in component else None)
					mapLayers.append(identifier)
	tilecacheFile += tilecache.layer(layer['title'], mapLayers, mapDir)
	htmlFile += html.layer(layer['title'], layer['title'], 'enabled' not in layer or layer['enabled'], 'hidden' in layer and layer['hidden'], layer['mergeLayer'] if 'mergeLayer' in layer else None)
	layerNames = [layer['title']]
	if 'aliases' in layer:
		layerNames += layer['aliases']
	layersDefFile += ','.join(layerNames) + '\n'
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
for layer in layers.layers:
	commands.append("tilecache_seed.py '%s' %s" % (layer['title'], len(config.resolutions)))
print "Generating tiles..."
runCommands(commands)

shutil.rmtree(oldTilesDir, True)
if os.path.exists(tilesDir):
	shutil.move(tilesDir, oldTilesDir)
shutil.move(tempTilesDir, tilesDir)

print "Writing 'layers.def'..."
layersDefStream = open(config.wwwDirectory + '/layers.def', 'w')
layersDefStream.write(layersDefFile)
layersDefStream.close()

print "Writing 'index.html'..."
htmlStream = open(config.wwwDirectory + '/index.html', 'w')
htmlStream.write(htmlFile)
htmlStream.close()

os.chdir("/")
shutil.rmtree(mapDir, True)
shutil.rmtree(oldTilesDir, True)
