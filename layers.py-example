mapfile = '1141-6006-1-gmc-cropped.dxf'

#
# The configuration below describes an ordered list of layers visible on the map server.
# The order is the order in which the layers appear in the layer selection settings on
# the map server, as well as the rendering order; layers containing transparent areas,
# like Fields, should be at the beginning to avoid overlaying an area on top of other data.
#
# Each map-visible layer is a tuple of a name (visible in the layer selection settings)
# together with an unordered set of input sources.
#
# An input source consists of an input file (currently only .dxf files are supported,
# but this can be changed if we're going to add data from NOC and Power) along with a
# set of layers defined in that file, together with layout data describing how to render
# the data in this layer. The following fields are defined for an input source:
#
# - file:           The source filename. No full path is necessary, search paths are
#                   defined elsewhere.
# - layers:         The selected layers from the source file, specified as a set of
#                   regular expressions of which a source layer needs to match one.
# - color, width:   The color and width used to render LINE data in this data source.
#                   Width is measured in pixels, color is specified as 'rrggbb' or 'rrggbbaa'.
# - fill:           The color used to render AREA data in this data source.
# - text, fontSize: The color and font size used to render text labels in the data source.
#                   Font sizes are in a scale roughly compatible with those specified in QCad.
#

layers = [
	('Fields', [
		{
			'file': mapfile,
			'layers': ['FIELD.*'],
			'color': '008000',
			'width': '3',
			'fill': '00ff0080',
			'text': '000000',
			'fontSize': 10,
		}
	]),
	('Tents', [
		{
			'file': mapfile,
			'layers': ['T .*', 'T[0-9]'],
			'color': 'ffff00',
			'width': '2',
			'fill': 'ffff00c0',
		}
	]),
	('Roads', [
		{
			'file': mapfile,
			'layers': ['V[0-9][0-9] .*'],
			'color': '808080',
			'width': '2',
		},
		{
			'file': mapfile,
			'layers': ['bouwweg', 'event roads'],
			'color': 'ff0000',
			'width': '1',
		}
	]),
	('Ditches', [
		{
			'file': mapfile,
			'layers': ['W[0-9][0-9] .*'],
			'color': '0000ff',
			'width': '2',
		}
	]),
	('Power', [
		{
			'file': mapfile,
			'layers': ['aggregaten'],
			'color': 'ff8000',
			'width': '1',
			'fill': 'ff8000',
		}
	]),
	('Toilets', [
		{
			'file': mapfile,
			'layers': ['toilet'],
			'color': '000000',
			'width': '1',
		}
	]),
	('Border', [
		{
			'file': mapfile,
			'layers': ['border'],
			'color': '000000',
			'width': '3',
		}
	]),
]
