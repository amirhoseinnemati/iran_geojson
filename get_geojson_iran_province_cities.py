import requests
import json
import osm2geojson
import time

# Define the Overpass API query
overpass_url = "http://overpass-api.de/api/interpreter"
max_retries = 3  # Number of retry attempts
retry_delay = 2  # Delay in seconds between retries

# Initialize GeoJSON collections
cities_geojson = {
    "type": "FeatureCollection",
    "features": []
}

provinces_geojson = {
    "type": "FeatureCollection",
    "features": []
}

# First, fetch provinces (admin_level=4 for Iran provinces)
print('Fetching provinces from Iran...')

provinces_query = '''
[out:json][timeout:90];
area["ISO3166-1"="IR"]["admin_level"="2"]->.iran;
(
  rel["admin_level"="4"](area.iran);
);
out body;
>;
out skel qt;
'''

retry_round = 1
while retry_round <= max_retries:
    print(f'\n=== Province Fetch Attempt {retry_round} ===\n')

    try:
        response = requests.get(overpass_url, params={'data': provinces_query}, timeout=90)
        response.raise_for_status()

        if not response.text:
            print(f'Empty response, will retry...')
            time.sleep(retry_delay)
            retry_round += 1
            continue

        data = json.loads(response.text)
        geojson = osm2geojson.json2geojson(data)

        for feature in geojson.get('features', []):
            if feature.get('geometry', {}).get('type') == 'Point':
                continue

            properties = feature.get('properties', {})
            if 'tags' in properties:
                tags = properties.pop('tags')
                properties.update(tags)

            provinces_geojson['features'].append(feature)

        print(f'✓ Downloaded {len(provinces_geojson["features"])} provinces')
        break

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f'Error: {e}, will retry...')
        time.sleep(retry_delay)
        retry_round += 1
        if retry_round > max_retries:
            print(f'\n⚠ Max retries ({max_retries}) exceeded for provinces.')
            break

# Query for cities in Iran
# Get all city and town boundaries regardless of admin_level
overpass_query = '''
[out:json][timeout:90];
area["ISO3166-1"="IR"]["admin_level"="2"]->.iran;
(
  rel["place"="city"](area.iran);
  rel["place"="town"](area.iran);
  way["place"="city"](area.iran);
  way["place"="town"](area.iran);
);
out body;
>;
out skel qt;
'''

print('Fetching cities from Iran...')

# Create initial list of attempts
failed_attempts = [0]  # Start with one attempt
retry_round = 1

while failed_attempts:
    print('\n=== Attempt {retry_round} ===\n')

    success = False

    # Send the query to the Overpass API
    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, timeout=90)
        response.raise_for_status()  # Raise an error for bad status codes

        # Check if response is empty
        if not response.text:
            print(f'Empty response, will retry...')
            time.sleep(retry_delay)
            retry_round += 1
            if retry_round > max_retries:
                print(f'\n⚠ Max retries ({max_retries}) exceeded.')
                break
            continue

        # Parse the response
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            print(f'JSON decode error: {e}, will retry...')
            time.sleep(retry_delay)
            retry_round += 1
            if retry_round > max_retries:
                print(f'\n⚠ Max retries ({max_retries}) exceeded.')
                break
            continue

        # Convert the data to GeoJSON format
        geojson = osm2geojson.json2geojson(data)

        # Extract tags from nested structure and merge into properties
        for feature in geojson.get('features', []):
            # Skip Point geometries - we only want areas/polygons
            if feature.get('geometry', {}).get('type') == 'Point':
                continue

            properties = feature.get('properties', {})

            # Extract tags from nested tags object
            if 'tags' in properties:
                tags = properties.pop('tags')  # Remove the nested tags key
                # Merge all tag keys directly into properties
                properties.update(tags)

            # Add feature to master collection
            cities_geojson['features'].append(feature)

        print(f'✓ Downloaded {len(geojson.get("features", []))} cities')
        success = True
        break

    except requests.exceptions.RequestException as e:
        print(f'Request error: {e}, will retry...')
        time.sleep(retry_delay)
        retry_round += 1
        if retry_round > max_retries:
            print(f'\n⚠ Max retries ({max_retries}) exceeded.')
            break
        continue

# Save separate GeoJSON files
if provinces_geojson['features']:
    print(f'\n=== Saving Provinces ===')
    print(f'Total provinces: {len(provinces_geojson["features"])}')

    with open('iran_provinces.geojson', 'w', encoding='utf-8') as f:
        f.write(json.dumps(provinces_geojson, ensure_ascii=False, indent=2))

    print('✓ Saved to iran_provinces.geojson')

if cities_geojson['features']:
    print(f'\n=== Saving Cities ===')
    print(f'Total cities: {len(cities_geojson["features"])}')

    with open('iran_cities.geojson', 'w', encoding='utf-8') as f:
        f.write(json.dumps(cities_geojson, ensure_ascii=False, indent=2))

    print('✓ Saved to iran_cities.geojson')

# Create merged file with provinces as base layer and cities on top
merged_geojson = {
    "type": "FeatureCollection",
    "features": []
}

# Add provinces first (base layer)
for feature in provinces_geojson['features']:
    feature['properties']['layer'] = 'province'
    merged_geojson['features'].append(feature)

# Add cities on top
for feature in cities_geojson['features']:
    feature['properties']['layer'] = 'city'
    merged_geojson['features'].append(feature)

if merged_geojson['features']:
    print(f'\n=== Saving Merged File ===')
    print(
        f'Total features: {len(merged_geojson["features"])} ({len(provinces_geojson["features"])} provinces + {len(cities_geojson["features"])} cities)')

    with open('iran_provinces_cities_merged_geo.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(merged_geojson, ensure_ascii=False, indent=2))

    print('✓ Saved to iran_provinces_cities_merged_geo.json')
else:
    print('\n⚠ No data collected. Files not created.')