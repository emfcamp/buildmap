#!/usr/bin/python

import sys
import csv
import os
import string

def parseTool(style):
	if style[0] != "(": return None
	style = style[1:]
	fields = {}
	while len(style) > 0 and style[0] != ")":
		i = 0
		while i < len(style) and style[i] in string.ascii_letters:
			i += 1
		key = style[0:i]
		if style[i] != ":":
			return None
		style = style[i+1:]
		if style[0] == '"':
			value = ""
			i = 1
			while style[i] != '"':
				if style[i] == "\\":
					value += style[i + 1]
					i += 2
				else:
					value += style[i]
					i += 1
			style = style[i+1:]
		elif style[0] in string.ascii_letters or style[0] in string.digits or style[0] in '#.':
			i = 1
			while style[i] not in ',)':
				i += 1
			value = style[0:i]
			style = style[i:]
		else:
			return None
		fields[key] = value
		if style[0] == ",":
			style = style[1:]
	return (fields, style[1:])

def parseStyle(style):
	tools = {}
	while len(style) > 0:
		if style[0] == ";":
			style = style[1:]
			continue
		if style[0:3] == "PEN":
			tool = "PEN"
		elif style[0:5] == "BRUSH":
			tool = "BRUSH"
		elif style[0:6] == "SYMBOL":
			tool = "SYMBOL"
		elif style[0:5] == "LABEL":
			tool = "LABEL"
		else:
			return tools
		style = style[len(tool):]
		(data, style) = parseTool(style)
		tools[tool] = data
	return tools

def getStyle(style):
	if len(style) == 0 or style[0] == '@':
		tools = {}
	else:
		tools = parseStyle(style)
	if 'LABEL' in tools:
		return tools['LABEL']
	else:
		return {}

datafile = open(sys.argv[2], 'r')
dataReader = csv.reader(datafile)
dataHeader = dataReader.next()
dataIndex = {}
for i in range(len(dataHeader)):
	dataIndex[dataHeader[i]] = i
data = {}
for row in dataReader:
	if row[dataIndex['SubClasses']] != 'AcDbEntity:AcDbText:AcDbText':
		continue
	id = row[dataIndex['EntityHandle']]
	text = row[dataIndex['Text']]
	style = row[dataIndex['OGR_STYLE']]
	styleData = getStyle(style)
	if 's' in styleData and styleData['s'][-1:] == "g":
		size = float(styleData['s'][:-1])
	else:
		size = 1
	if 'a' in styleData:
		angle = float(styleData['a'])
	else:
		angle = 0
	if 'p' in styleData:
		position = ['ur', 'uc', 'ul', 'cr', 'cc', 'cl', 'lr', 'lc', 'll', 'ur', 'uc', 'ul'][int(styleData['p']) - 1]
	else:
		position = 'lr'
	data[id] = {'text': text, 'size': size, 'angle': angle, 'position': position}
datafile.close()

outputfile = open(sys.argv[3], 'w')
outputWriter = csv.writer(outputfile)
outputWriter.writerow(['Layer','EntityHand','Text','Size','Angle','Position'])

if os.path.exists(sys.argv[1]):
	entityfile = open(sys.argv[1], 'r')
	entityReader = csv.reader(entityfile)
	entityHeader = entityReader.next()
	entityIndex = {}
	for i in range(len(entityHeader)):
		entityIndex[entityHeader[i]] = i
	for row in entityReader:
		layer = row[entityIndex['Layer']]
		id = row[entityIndex['EntityHand']]
		text = row[entityIndex['Text']]
		if id in data:
			outputWriter.writerow([layer, id, text, data[id]['size'], data[id]['angle'], data[id]['position']])
		else:
			outputWriter.writerow([layer, id, text, "", "", ""])
	entityfile.close()

outputfile.close()
