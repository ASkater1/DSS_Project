

import requests
import json


geojson_url = (
        "https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/"
        "ogc/v1/collections/gemeentegebied/items"
        "?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FOGC%2F1.3%2FCRS84"
        "&f=json&limit=1000"
    )

response = requests.get(geojson_url, timeout=15)
response.raise_for_status()
geojson_data = response.json()

# write the geojson data to a file
with open("municipalities.geojson", "w") as f:
    json.dump(geojson_data, f)