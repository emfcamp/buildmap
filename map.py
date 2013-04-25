import config

def header():
	return """
MAP
  NAME "QGIS-MAP"
  # Map image size
  SIZE 100 100
  UNITS meters

  #EXTENT 180704.803177 424586.548223 182738.463915 425826.740912
  #EXTENT 111111 523387 112560 522748
  #EXTENT 111928.73 522982.39 112114.05 523290.68
  FONTSET './fonts.txt'
  SYMBOLSET './symbols.txt'
  PROJECTION
    'proj=sterea'
    'lat_0=52.15616055555555'
    'lon_0=5.38763888888889'
    'k=0.9999079'
    'x_0=155000'
    'y_0=463000'
    'ellps=bessel'
    'towgs84=565.417,50.3319,465.552,-0.398957,0.343988,-1.8774,4.0725'
    'units=m'
    'no_defs'
  END

  # Background color for the map canvas -- change as desired
  IMAGECOLOR 255 255 255
  IMAGEQUALITY 95
  IMAGETYPE agg
  TRANSPARENT on

  OUTPUTFORMAT
    NAME agg
    DRIVER AGG/PNG
    IMAGEMODE RGBA
  END

  # Legend
  LEGEND
    IMAGECOLOR 255 255 255
    STATUS ON
    KEYSIZE 18 12
    LABEL
      TYPE BITMAP
      SIZE MEDIUM
      COLOR 0 0 89
    END
  END

  # Web interface definition. Only the template parameter
  # is required to display a map. See MapServer documentation
  WEB
    # Set IMAGEPATH to the path where MapServer should
    # write its output.
    IMAGEPATH '/tmp/'

    # Set IMAGEURL to the url that points to IMAGEPATH
    # as defined in your web server configuration
    IMAGEURL '/tmp/'

    # WMS server settings
    METADATA
      'ows_title'           'QGIS-MAP'
      'ows_onlineresource'  'http://localhost/cgi-bin/mapserv?map=ohm.map'
      'ows_srs'             'EPSG:28992'
      'ows_enable_request'  '*'
    END

    #Scale range at which web interface will operate
    # Template and header/footer settings
    # Only the template parameter is required to display a map. See MapServer documentation
    #TEMPLATE 'fooOnlyForWMSGetFeatureInfo'
  END
"""

def parseColor(color):
	red = int(color[0:2], 16)
	green = int(color[2:4], 16)
	blue = int(color[4:6], 16)
	if len(color) > 6:
		alpha = int(color[6:8], 16)
	else:
		alpha = 255
	return (red, green, blue, int(alpha * 100 / 255.0))

def lineLayer(name, shapefile, description, color, width):
	(red, green, blue, alpha) = parseColor(color)
	return """
  LAYER
    NAME '%s'
    TYPE LINE
    DATA '%s-lines'
    STATUS ON
    TRANSPARENCY %s
    PROJECTION
        "init=epsg:28992"
    END
    CLASS
       NAME '%s'
       STYLE
         WIDTH %s
         COLOR %s %s %s
       END
    END
  END
""" % (name, shapefile, alpha, description, width, red, green, blue)

def areaLayer(name, shapefile, description, color):
	(red, green, blue, alpha) = parseColor(color)
	return """
  LAYER
    NAME '%s'
    TYPE POLYGON
    DATA '%s-areas'
    STATUS ON
    TRANSPARENCY %s
    PROJECTION
        "init=epsg:28992"
    END
    CLASS
       NAME '%s'
       STYLE
         COLOR %s %s %s
       END
    END
  END
""" % (name, shapefile, alpha, description, red, green, blue)

def pointLayer(name, shapefile, description, color, size):
	(red, green, blue, alpha) = parseColor(color)
	return """
  LAYER
    NAME '%s'
    TYPE POINT
    DATA '%s-points'
    STATUS ON
    TRANSPARENCY %s
    PROJECTION
        "init=epsg:28992"
    END
    LABELITEM 'Text'
    SYMBOLSCALEDENOM 2500
    CLASS
      NAME '%s'
      LABEL
        FONT arial
        TYPE truetype
        SIZE %s
        COLOR %s %s %s
        POSITION lr
        FORCE true
        ANTIALIAS true
        PARTIALS false
      END
    END
  END
""" % (name, shapefile, alpha, description, size, red, green, blue)

def footer():
	return """
END
"""