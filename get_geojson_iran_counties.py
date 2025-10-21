import requests
import json
import osm2geojson
import time

# Define the Overpass API query
overpass_url = "http://overpass-api.de/api/interpreter"
max_retries = 3  # Number of retry attempts
retry_delay = 2  # Delay in seconds between retries

# Initialize a master GeoJSON collection
master_geojson = {
    "type": "FeatureCollection",
    "features": []
}

# Create initial list of provinces to process
failed_provinces = list(range(0, 31))
retry_round = 1

while failed_provinces:
    print(f'\n=== Retry Round {retry_round} ===')
    print(f'Processing {len(failed_provinces)} provinces: {failed_provinces}\n')

    new_failed_provinces = []

    for i in failed_provinces:
        overpass_query = f'''
        [out:json];
        area["ISO3166-2"="IR-{i:02d}"]->.province;
        rel["admin_level"="5"](area.province);
        out body;
        >;
        out skel qt;
        '''

        # Send the query to the Overpass API
        try:
            response = requests.get(overpass_url, params={'data': overpass_query}, timeout=60)
            response.raise_for_status()  # Raise an error for bad status codes

            # Check if response is empty
            if not response.text:
                print(f'Empty response for IR-{i:02d}, will retry...')
                new_failed_provinces.append(i)
                continue

            # Parse the response
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as e:
                print(f'JSON decode error for IR-{i:02d}: {e}, will retry...')
                new_failed_provinces.append(i)
                continue

            # Convert the data to GeoJSON format
            geojson = osm2geojson.json2geojson(data)

            # Extract tags from nested structure and merge into properties
            for feature in geojson.get('features', []):
                # Skip Point geometries
                if feature.get('geometry', {}).get('type') == 'Point':
                    continue

                properties = feature.get('properties', {})

                # Extract tags from nested tags object
                if 'tags' in properties:
                    tags = properties.pop('tags')  # Remove the nested tags key
                    # Merge all tag keys directly into properties
                    properties.update(tags)

                # Add feature to master collection
                master_geojson['features'].append(feature)

            print(f'✓ Downloaded IR-{i:02d} ({len(geojson.get("features", []))} features)')

        except requests.exceptions.RequestException as e:
            print(f'Request error for IR-{i:02d}: {e}, will retry...')
            new_failed_provinces.append(i)
            continue

        # Add delay between requests to avoid rate limiting
        time.sleep(retry_delay)

    # Update failed provinces list for next round
    failed_provinces = new_failed_provinces
    retry_round += 1

    # If there are still failed provinces and we haven't exceeded max retries, wait before next round
    if failed_provinces and retry_round <= max_retries:
        print(f'\nWaiting {retry_delay} seconds before next retry round...')
        time.sleep(retry_delay)
    elif failed_provinces and retry_round > max_retries:
        print(f'\n⚠ Max retries ({max_retries}) exceeded. Failed provinces: {failed_provinces}')
        break

# Save the merged GeoJSON data to a single file with UTF-8 encoding
print(f'\n=== Finalization ===')
print(f'Merging all features into single GeoJSON file...')
print(f'Total features: {len(master_geojson["features"])}')

with open('iran_counties.geojson', 'w', encoding='utf-8') as f:
    f.write(json.dumps(master_geojson, ensure_ascii=False, indent=2))

print('✓ Saved to iran_counties.geojson')