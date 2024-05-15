# flake8: noqa
queries = {
    #    "TentCentres": """SELECT tent AS name,
    # tent_size,
    # split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS lat,
    # split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS long,
    # ST_AsKML(ST_Centroid(wkb_geometry)) AS kml
    # FROM site_plan
    # WHERE tent IS NOT NULL
    # ORDER BY name ASC""",
    "TentCorners": """
 SELECT name, corner_lat, corner_long, ST_AsKML(ST_SetSRID(ST_MakePoint(corner_long, corner_lat), 4326)) AS kml FROM (SELECT DISTINCT tent AS name,
ST_Y(ST_Transform((ST_DumpPoints(wkb_geometry)).geom, 4326)) AS   corner_lat,
ST_X(ST_Transform((ST_DumpPoints(wkb_geometry)).geom, 4326)) AS   corner_long
   FROM site_plan
   WHERE tent IS NOT NULL
   ORDER BY name ASC) a;""",
    "Datenklo": """SELECT dk_name AS name,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS long,
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml
 FROM site_plan
 WHERE layer = 'NOC ... DK'""",
    #    "NOC": """SELECT emfnet AS name,
    # split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS lat,
    # split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS long,
    # ST_AsKML(ST_Centroid(wkb_geometry)) AS kml
    # FROM site_plan
    # WHERE emfnet is not NULL
    # ORDER BY name ASC""",
    "Power": """SELECT name AS name,
 distro AS type,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS long,
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml
 FROM site_plan
 WHERE distro IS NOT NULL
 ORDER BY name ASC""",
    "Festoons": """SELECT
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS start_long,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS end_long,
 ST_AsKML(wkb_geometry) AS kml
 FROM site_plan
 WHERE layer = 'Lighting ... Festoon'""",
    "PathsTrackway": """SELECT
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS start_long,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS end_long,
 ST_AsKML(wkb_geometry) AS kml
 FROM site_plan
 WHERE layer = 'Paths ... Trackway'""",
    "PathsFire": """SELECT
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS start_long,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS end_long,
 ST_AsKML(wkb_geometry) AS kml
 FROM site_plan
 WHERE layer = 'Paths ... Fire'""",
    "HerasInternal": """SELECT
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS start_long,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) AS end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) AS end_long,
 ST_AsKML(wkb_geometry) AS kml
 FROM site_plan
 WHERE layer = 'Heras (internal)'""",
}
