import config

def header():
	return """<!DOCTYPE html>
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>OHM 2013 Geestmerambacht</title>
    <link rel="stylesheet" href="../theme/default/style.css" type="text/css">
    <link rel="stylesheet" href="style.css" type="text/css">
    <script src="lib/jquery-1.10.1.min.js"></script>
    <script src="lib/proj4js-combined.js"></script>
    <script src="lib/epsg28992.js"></script>
    <script src="lib/OpenLayers.js"></script>
    <script src="lib/ModifiedLayerSwitcher.js"></script>
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
            OpenLayers.Util.onImageLoadErrorColor = 'transparent';
            OpenLayers.Feature.prototype.popupClass = OpenLayers.Class(OpenLayers.Popup.FramedCloud, { 'autoSize': true, 'minSize': new OpenLayers.Size( 200, 100) });

            map = new OpenLayers.Map( 'map',
                  {
                    projection:"EPSG:28992",
                    maxExtent: new OpenLayers.Bounds(-285401.920, 22598.080, 595401.920, 903401.920),
                    // http://wiki.geonovum.nl/index.php/Eigenschappen_tiling_schema
                    // schalen:    12288000, 6144000,  3072000, 1536000, 768000,  384000,  192000, 96000,  48000,  24000, 12000, 6000,  3000,  1500
                    // resolution: 3440.640, 1720.320, 860.160, 430.080, 215.040, 107.520, 53.760, 26.880, 13.440, 6.720, 3.360, 1.680, 0.840, 0.420
                    resolutions: [3440.640, 1720.320, 860.160, 430.080, 215.040, 107.520, 53.760, 26.880, 13.440, 6.720, 3.360, 1.680, 0.840, 0.420, 0.210, 0.105],
                    units: 'm',
                    controls: []
                  }
            );
            map.addControl( new OpenLayers.Control.LayerSwitcher()  );
            map.addControl( new OpenLayers.Control.PanZoomBar() );
            map.addControl( new OpenLayers.Control.MouseDefaults() );
            map.addControl( new OpenLayers.Control.MousePosition({ displayProjection: new OpenLayers.Projection('EPSG:4326') }) );

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
                isBaseLayer: true,
            });

            map.addLayers([brt
"""


def layer(name, title, enabled, hidden, mergeLayer):
	return """
            , new OpenLayers.Layer.TileCache(
                '%s',
                '%s/tiles',
                '%s',
                {
                    singleTile:false,
                    resolutions: [%s],
                    serverResolutions: [%s],
                    maxExtent: new OpenLayers.Bounds(%s),
                    tileSize: new OpenLayers.Size(1024, 1024),
                    isBaseLayer: false,
                    visibility: %s,
                    displayInLayerSwitcher: %s,
                    %s
                }
            )
""" % (title, config.url, name, ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.resolutions)), ", ".join(map(str, config.extents)), 'true' if enabled else 'false', 'false' if hidden else 'true', ('mergeLayer: "%s"' % mergeLayer) if mergeLayer != None else '')


def footer():
	return """
            ]);

            wgs = new OpenLayers.Projection("EPSG:4326");
            rds = new OpenLayers.Projection("EPSG:28992")
            villagesLayer = new OpenLayers.Layer.Markers("Villages (Wiki)");
            map.addLayer(villagesLayer);
            jQuery.getJSON('cgi-bin/villages.json', function(data) {
                villages = data["results"];
                for (key in villages) {
                    (function(){
                        var name = villages[key]["fulltext"].substr(8);
                        var url = villages[key]["fullurl"];
                        lat = villages[key]["printouts"]["Village Location"][0]["lat"];
                        lon = villages[key]["printouts"]["Village Location"][0]["lon"];
                        var coordinate = new OpenLayers.LonLat(lon, lat);
                        var description = villages[key]["printouts"]["Village Description"][0];
                        coordinate.transform(wgs, rds);
                        size = new OpenLayers.Size(21,25);
                        offset = new OpenLayers.Pixel(-(size.w/2), -size.h);
                        marker = new OpenLayers.Marker(coordinate, new OpenLayers.Icon("lib/img/marker.png", size, offset));
                        marker.events.register('mousedown', marker, function (event) {
                            a = jQuery("<a/>");
                            a.attr("href", url);
                            a.text(name);
                            b = jQuery("<b/>");
                            a.appendTo(b);
                            p = jQuery("<p>");
                            p.text(description);
                            div = jQuery("<div/>");
                            b.appendTo(div);
                            p.appendTo(div);
                            popup = new OpenLayers.Popup.FramedCloud(event.id, coordinate, null, div.html(), null, true);
                            map.addPopup(popup);
                            OpenLayers.Event.stop(event);
                        });
                        villagesLayer.addMarker(marker);
                    })();
                }
            });
            map.zoomToExtent(new OpenLayers.Bounds(111573, 522775, 112628, 523527));

        } </script>
  </head>
  <body onload="init()">
    <div id="map" sstyle="width:800px;height:400px;"></div>
  </body>
</html>
"""
