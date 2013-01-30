mapfile = '1141-6006-1-gmc-cropped.dxf'

# Fields
# Tents
# Roads
# Ditches
# Power
# Toilets

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
