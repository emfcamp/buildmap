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

def layer(name, shapefile, description):
	return """
  LAYER
    NAME '%s'
    TYPE LINE
    DUMP true
    DATA '%s-lines'
    METADATA
      'ows_title' '%s'
    END
    STATUS ON
    TRANSPARENCY 100
    PROJECTION
        "init=epsg:28992"
    END
    CLASS
       NAME '%s'
       STYLE
         WIDTH 0.91 
         OUTLINECOLOR 0 0 0
         COLOR 255 0 0
       END
    END
  END
""" % (name, shapefile, name, description)

def footer():
	return """
END
"""