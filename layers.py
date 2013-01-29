mapfile = '20121205-ga-test.dxf'

layers = {
	'velden' : [(mapfile, 'FIELD.*')],
	'bebouwing' : [(mapfile, 'B[0-9][0-9] .*')],
	'tenten' : [(mapfile, 'T.*')],
	'wegen' : [(mapfile, 'bouwweg.*'), (mapfile, 'event roads'), (mapfile, 'rijplaten'), (mapfile, 'temp bridges')],
	'border' : [(mapfile, 'border')],
	'hill' : [(mapfile, 'hill')],
}
