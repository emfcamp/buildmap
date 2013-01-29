import config

def header():
	return """<!DOCTYPE html>
<html>
  <head>
    <!-- CACHING VERSION BY GMC -->
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>OHM 2013 Geesterambacht</title>
    <link rel="stylesheet" href="../theme/default/style.css" type="text/css">
    <link rel="stylesheet" href="style.css" type="text/css">
    <script src="lib/OpenLayers.js"></script>
    <style type="text/css">
     html {
        width: 100%;
        height: 100%;
        font-family: 'Lucida Grande', Verdana, Geneva, Lucida, Arial, Helvetica, sans-serif;
     }
     body {
        width: 100%;
        height: 100%;
        margin: 0px;
     }
     #map {
        width: 100%;
        height: 100%;
     } 
    </style>
    <script type="text/javascript">
        var map, layer
        function init(){
            OpenLayers.DOTS_PER_INCH=90.7143
            OpenLayers.ImgPath = "http://js.mapbox.com/theme/dark/";
            map = new OpenLayers.Map( 'map',
                  {
                    projection:"EPSG:28992",
                    maxExtent: new OpenLayers.Bounds(-285401.920, 22598.080, 595401.920, 903401.920),
                    // http://wiki.geonovum.nl/index.php/Eigenschappen_tiling_schema
                    // schalen:    12288000, 6144000,  3072000, 1536000, 768000,  384000,  192000, 96000,  48000,  24000, 12000, 6000,  3000,  1500
                    // resolution: 3440.640, 1720.320, 860.160, 430.080, 215.040, 107.520, 53.760, 26.880, 13.440, 6.720, 3.360, 1.680, 0.840, 0.420
                    resolutions: [3440.640, 1720.320, 860.160, 430.080, 215.040, 107.520, 53.760, 26.880, 13.440, 6.720, 3.360, 1.680, 0.840, 0.420],
                    units: 'm',
                    controls: []
                  }
            );
            map.events.register('moveend', map, 
               function(){
                      // $('scale').innerHTML='Schaal 1:'+parseInt(map.getScale());
                      // $('zoom').innerHTML='Zoom '+map.getZoom();
                      // $('resolution').innerHTML='Resolutie '+map.getResolution();
            });
            map.addControl( new OpenLayers.Control.LayerSwitcher()  );
            map.addControl( new OpenLayers.Control.PanZoomBar() );
            map.addControl( new OpenLayers.Control.MouseDefaults() );
            //map.addControl( new OpenLayers.Control.LoadingPanel() );
            //map.addControl( new OpenLayers.Control.Attribution() );
            //map.addControl( new OpenLayers.Control.ScaleLine() );

	    nlr = new OpenLayers.Layer.WMS(
                'nlr luchtfoto mapserver',
                'http://gdsc.nlr.nl/wms/dkln2006',
                {
                    layers: 'dkln2006-1m',
                    format: "image/png"
                },
                {
                    singleTile:false,
                    isBaseLayer:true,
                    attribution:'Kaartgegevens: TODO '
                }
            );

            var matrixIds = new Array(26);
            for (var i=0; i<26; ++i) {
            matrixIds[i] = 'EPSG:28992:' + i;
            }
            brt = new OpenLayers.Layer.WMTS({
                name: 'BRT Achtergrondkaart (wmts)',
                url: 'http://geodata.nationaalgeoregister.nl/wmts/',
                layer: 'brtachtergrondkaart',
                style: null,
                format: 'image/png8',
                matrixSet: 'EPSG:28992',
                matrixIds: matrixIds,
                isBaseLayer: true}
            );

            map.addLayers([nlr, brt
"""


def layer(name, title):
	return """
            , new OpenLayers.Layer.TileCache(
                '%s',
                //'%s/tilecache',
                'http://floep.redlizard.nl/tilecache/',
                '%s',
                {
                    singleTile:false,
                    resolutions: [%s],
                    serverResolutions: [%s],
                    maxExtent: new OpenLayers.Bounds(%s),
                    isBaseLayer: false,
                }
            )
""" % (title, config.url, name, ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.extents)))
	return """
            , new OpenLayers.Layer.WMS(
                '%s',
                '%s/tilecache/tilecache.cgi',
                {
                    transparent:true, format: "image/png",
                    layers: '%s'
                },
                {
                    singleTile:false,
                    //resolutions: [%s],
                    //maxExtent: new OpenLayers.Bounds(%s),
                }
            )
""" % (title, config.url, name, ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.extents)))


def footer():
	return """
            ]);
            map.zoomToExtent(new OpenLayers.Bounds( 111631.9,522846.501218,112975.9,523518.501218 )); // GeesterAmbacht

        } </script>
  </head>
  <body onload="init()">
    <!--<h1 id="title">Geesterambacht</h1>-->
    <div id="map" sstyle="width:800px;height:400px;"></div>

  </body>
</html>
"""
