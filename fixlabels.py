#!/usr/bin/python

import sys
import csv
import os
from shp import parseStyle


def getStyle(style):
    if len(style) == 0 or style[0] == '@':
        tools = {}
    else:
        tools = parseStyle(style)
    if 'LABEL' in tools:
        return tools['LABEL']
    else:
        return {}

def sanitizeText(text):
    while len(text) > 0 and text[0] == '\\':
        pos = text.find(';')
        if pos == -1:
            break
        text = text[pos + 1:]
    return text

datafile = open(sys.argv[2], 'r')
dataReader = csv.reader(datafile)
dataHeader = dataReader.next()
dataIndex = {}
for i in range(len(dataHeader)):
    dataIndex[dataHeader[i]] = i
data = {}
for row in dataReader:
    if row[dataIndex['SubClasses']] not in \
       ('AcDbEntity:AcDbText:AcDbText', 'AcDbEntity:AcDbMText'):
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
        text = sanitizeText(row[entityIndex['Text']])
        if id in data:
            outputWriter.writerow([layer, id, text, data[id]['size'], data[id]['angle'], data[id]['position']])
        else:
            outputWriter.writerow([layer, id, text, "", "", ""])
    entityfile.close()

outputfile.close()
