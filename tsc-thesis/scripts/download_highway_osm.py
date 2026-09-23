import requests
import sys

bbox = "-33.4550,-70.6850,-33.4150,-70.5950" # Overpass uses South, West, North, East

# Consulta Overpass QL para obtener SOLO calles y caminos (highways), evitando edificios y nodos inútiles
overpass_query = f"""
[out:xml][timeout:60];
(
  way["highway"]({bbox});
  node(w);
);
out body;
"""

url = "https://overpass-api.de/api/interpreter"
print("Descargando carreteras desde Overpass API...")
response = requests.post(url, data={'data': overpass_query})

if response.status_code == 200:
    with open("map_alameda.osm", "wb") as f:
        f.write(response.content)
    print("Guardado en map_alameda.osm (", len(response.content) // 1024, "KB )")
else:
    print("Error:", response.status_code, response.text)
