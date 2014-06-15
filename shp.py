# coding=utf-8
""" Functions to help deal with parsing shapefiles """
import string


def parseTool(style):
    if style[0] != "(":
        raise Exception("Couldn't parse tool string: missing starting bracket")
    style = style[1:]
    fields = {}
    while len(style) > 0 and style[0] != ")":
        i = 0
        while i < len(style) and style[i] in string.ascii_letters:
            i += 1
        key = style[0:i]
        if style[i] != ":":
            raise Exception("Couldn't parse tool string: missing colon")
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
        elif style[0] in string.ascii_letters or style[0] in string.digits or style[0] in '#.-':
            i = 1
            while style[i] not in ',)':
                i += 1
            value = style[0:i]
            style = style[i:]
        else:
            raise Exception("Couldn't parse tool string")
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
