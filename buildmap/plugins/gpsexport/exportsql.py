queries = {
    "TentCentres": """SELECT tent as name, 
 tent_size,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as long, 
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml 
 FROM site_plan 
 WHERE tent IS NOT NULL
 ORDER by name ASC""",
    "TentCorners": """
 SELECT name, corner_lat, corner_long, ST_AsKML(ST_SetSRID(ST_MakePoint(corner_long, corner_lat), 4326)) AS kml FROM (SELECT DISTINCT tent as name,
ST_Y(ST_Transform((ST_DumpPoints(wkb_geometry)).geom, 4326)) as   corner_lat,
ST_X(ST_Transform((ST_DumpPoints(wkb_geometry)).geom, 4326)) as   corner_long
   FROM site_plan
   WHERE tent IS NOT NULL
   ORDER by name ASC) a;
    """,
    "Datenklo": """SELECT dk_name as name,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as long, 
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml 
 FROM site_plan 
 WHERE dk_name is not NULL
 ORDER by name ASC""",
    "NOC": """SELECT emfnet as name,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as long,  
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml 
 FROM site_plan 
 WHERE emfnet is not NULL
 ORDER by name ASC""",
    "Power": """SELECT distro_name as name,
 power_distro as type,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_Centroid(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as long,  
 ST_AsKML(ST_Centroid(wkb_geometry)) AS kml 
 FROM site_plan 
 WHERE distro_name is not NULL
 ORDER by name ASC""",
    "Festoons": """SELECT 
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as start_long, 
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as end_long, 
 ST_AsKML(wkb_geometry) as kml
 FROM site_plan 
 WHERE layer = 'Lighting - Festoon'""",
    "PathsEuromat": """SELECT 
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as start_long, 
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as end_long, 
 ST_AsKML(wkb_geometry) as kml
 FROM site_plan 
 WHERE layer = 'Paths - Euromat'""",
    "PathsFireLane": """SELECT 
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as start_long, 
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as end_long, 
 ST_AsKML(wkb_geometry) as kml
 FROM site_plan 
 WHERE layer = 'Paths - Fire Lane'""",
    "FenceHeras": """SELECT 
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as start_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_StartPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as start_long, 
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 1) as end_lat,
 split_part(ST_AsLatLonText(ST_Transform(ST_EndPoint(wkb_geometry), 4326), 'DD.DDDDDD'), ' ', 2) as end_long, 
 ST_AsKML(wkb_geometry) as kml
 FROM site_plan 
 WHERE layer = 'Fence (Heras)'""",
}
