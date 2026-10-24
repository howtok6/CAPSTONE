#!/usr/bin/env python3
"""Descarga el eje Alameda -> Providencia -> Apoquindo desde OSM y calcula su franja.

1. Baja el eje en recuadros desde la API principal de OSM (la misma fuente de las
   redes anteriores; Overpass suele saturarse). Si un recuadro supera el límite
   de nodos de la API, lo parte en dos y reintenta.
2. Toma las calles del eje dentro de los límites comunales (Santiago, Providencia
   y Las Condes): al poniente se corta en Matucana (lon -70.6790), límite de
   Santiago con Estación Central calculado con los polígonos de OSM el 22-oct;
   Providencia y Apoquindo están completas dentro de sus comunas.
3. Calcula una franja de --buffer metros a cada lado y la escribe como polígono
   para `netconvert --keep-edges.in-geo-boundary` y como GeoJSON.

Uso:
    python scripts/download_axis_osm.py --out scenarios/eje_comunal [--buffer 150]
Luego:
    python scripts/build_santiago.py --osm <lista de recuadros> --keep-geo-boundary <polígono>
(el script imprime la línea exacta).

Decisión registrada en docs/07-decision-escenario.md.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from pyproj import Transformer
from shapely.geometry import LineString, mapping
from shapely.ops import transform, unary_union

API = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}"
EJE = {"Avenida Libertador Bernardo O'Higgins", "Avenida Providencia", "Avenida Apoquindo"}
LIMITE_PONIENTE = -70.6790  # Matucana: límite Santiago / Estación Central sobre la Alameda
# Recuadros (oeste, sur, este, norte) que cubren el eje con margen; ver docs/07
RECUADROS = [
    (-70.6820, -33.4565, -70.6560, -33.4395),
    (-70.6580, -33.4505, -70.6280, -33.4250),
    (-70.6300, -33.4325, -70.5985, -33.4100),
    (-70.6010, -33.4225, -70.5700, -33.4030),
    (-70.5720, -33.4145, -70.5410, -33.4000),
]


def bajar(caja, destino, nivel=0) -> list[str]:
    """Descarga un recuadro; si la API lo rechaza por tamaño, lo divide."""
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return [destino]
    url = API.format(*caja)
    req = urllib.request.Request(url, headers={"User-Agent": "tesis-semaforos-duoc/1.0"})
    for intento in range(3):
        try:
            datos = urllib.request.urlopen(req, timeout=180).read()
            with open(destino, "wb") as f:
                f.write(datos)
            print(f"  {os.path.basename(destino)}: {len(datos) / 1e6:.1f} MB")
            return [destino]
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 509) and nivel < 3:  # demasiados nodos: partir en dos
                o, s, e, n = caja
                m = (o + e) / 2
                base = destino[:-4]
                return (bajar((o, s, m, n), base + "a.osm", nivel + 1)
                        + bajar((m, s, e, n), base + "b.osm", nivel + 1))
            print(f"  HTTP {ex.code} en {url}; reintento")
        except Exception as ex:  # noqa: BLE001
            print(f"  {ex}; reintento")
        time.sleep(10)
    raise SystemExit(f"No se pudo descargar {url}")


def lineas_del_eje(archivos) -> list:
    nodos, lineas, vistas = {}, [], set()
    for a in archivos:
        for el in ET.parse(a).getroot():
            if el.tag == "node":
                nodos[el.get("id")] = (float(el.get("lon")), float(el.get("lat")))
    for a in archivos:
        for w in ET.parse(a).getroot().iter("way"):
            tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
            if w.get("id") in vistas or tags.get("name") not in EJE or "highway" not in tags:
                continue
            vistas.add(w.get("id"))
            pts = [nodos[nd.get("ref")] for nd in w.iter("nd") if nd.get("ref") in nodos]
            pts = [p for p in pts if p[0] >= LIMITE_PONIENTE]
            if len(pts) >= 2:
                lineas.append(LineString(pts))
    return lineas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="carpeta del escenario")
    ap.add_argument("--buffer", type=float, default=150.0, help="metros a cada lado del eje")
    args = ap.parse_args()
    carpeta = os.path.join(args.out, "osm_tiles")
    os.makedirs(carpeta, exist_ok=True)

    print("Descargando recuadros del eje desde la API de OSM…")
    archivos = []
    for i, caja in enumerate(RECUADROS):
        archivos += bajar(caja, os.path.join(carpeta, f"tile{i}.osm"))
        time.sleep(2)  # cortesía con la API pública

    lineas = lineas_del_eje(archivos)
    if not lineas:
        raise SystemExit("No se encontraron calles del eje en los recuadros.")
    a_utm = Transformer.from_crs(4326, 32719, always_xy=True).transform
    a_geo = Transformer.from_crs(32719, 4326, always_xy=True).transform
    franja = unary_union([transform(a_utm, ln) for ln in lineas]).buffer(args.buffer)
    franja = franja.simplify(10)
    if franja.geom_type != "Polygon":  # tramos sueltos: se toma la envolvente convexa de cada parte
        franja = max(franja.geoms, key=lambda g: g.area)
        print("Aviso: la franja tenía partes separadas; se usa la mayor.")
    largo_km = sum(transform(a_utm, ln).length for ln in lineas) / 1000
    franja_geo = transform(a_geo, franja)

    coords = list(franja_geo.exterior.coords)
    poly = ",".join(f"{x:.6f},{y:.6f}" for x, y in coords)
    with open(os.path.join(args.out, "franja_poly.txt"), "w") as f:
        f.write(poly)
    with open(os.path.join(args.out, "franja.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "Feature", "properties": {"buffer_m": args.buffer,
                   "limite_poniente_lon": LIMITE_PONIENTE}, "geometry": mapping(franja_geo)}, f)

    lista = ",".join(sorted(glob.glob(os.path.join(carpeta, "*.osm"))))
    print(f"\nOK  {len(lineas)} calles del eje (~{largo_km:.1f} km de calzadas), "
          f"franja de {args.buffer:.0f} m con {len(coords)} vértices")
    print("Siguiente paso:")
    print(f'  python scripts/build_santiago.py --osm "{lista}" --out {args.out} '
          f'--keep-geo-boundary "$(cat {os.path.join(args.out, "franja_poly.txt")})"')


if __name__ == "__main__":
    main()
