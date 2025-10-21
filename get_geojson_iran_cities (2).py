import requests
import json
import osm2geojson
import time

# Define the Overpass API query
overpass_url = "http://overpass-api.de/api/interpreter"
overpass_query = """
[out:json][timeout:120];
area["ISO3166-1"="IR"]->.ir;
(
  node["place"~"city|town"](area.ir);
  way["place"~"city|town"](area.ir);
  relation["place"~"city|town"](area.ir);
);
out geom;
"""

# Define Overpass endpoints with fallbacks
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def fetch_overpass_json(query, endpoints=ENDPOINTS, max_retries=3):
    last_error = None
    for endpoint in endpoints:
        for attempt in range(max_retries):
            try:
                resp = requests.post(endpoint, data={"data": query}, timeout=300)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code} from {endpoint}: {resp.text[:200]}"
                    time.sleep(2 * (attempt + 1))
                    continue
                try:
                    return resp.json()
                except json.JSONDecodeError:
                    last_error = f"Non-JSON response from {endpoint}: {resp.text[:200]}"
                    time.sleep(2 * (attempt + 1))
                    continue
            except requests.RequestException as e:
                last_error = str(e)
                time.sleep(2 * (attempt + 1))
                continue
    raise RuntimeError(f"Failed to fetch Overpass data: {last_error}")

# Send the query to the Overpass API (robust with fallbacks)
data = fetch_overpass_json(overpass_query)

# Convert the data to GeoJSON format
geojson = osm2geojson.json2geojson(data)
master_geojson = {"type": "FeatureCollection", "features": []}


# Extract tags from nested structure and merge into properties
for feature in geojson.get("features", []):
    # Include all geometries (Points and Polygons)

    properties = feature.get("properties", {})

    # Extract tags from nested tags object
    if "tags" in properties:
        tags = properties.pop("tags")  # Remove the nested tags key
        # Merge all tag keys directly into properties
        properties.update(tags)

    # Add feature to master collection
    master_geojson["features"].append(feature)

# Save the GeoJSON data to a file with UTF-8 encoding
with open(
    "/Users/nima/DataTeam/Projects/Metabase_Map/iran_cities_geo.json",
    "w",
    encoding="utf-8",
) as f:
    f.write(json.dumps(master_geojson, ensure_ascii=False, indent=2))
