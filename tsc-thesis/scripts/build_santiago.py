#!/usr/bin/env python3
"""Construye el escenario de un corredor real de Santiago desde OpenStreetMap.

Uso típico (bounding box del corredor Providencia, a ajustar):

    python scripts/build_santiago.py \
        --bbox -70.6250,-33.4300,-70.5950,-33.4180 \
        --out scenarios/providencia --period 0.8

QUÉ HACE ESTE SCRIPT Y QUÉ NO
-----------------------------
Automatiza la parte mecánica: descarga OSM, convierte a red SUMO con
`netconvert` y genera una demanda sintética plausible con `randomTrips.py`.

NO produce un escenario calibrado. La red importada de OSM siempre tiene
errores de conectividad, carriles y fases semafóricas, y la demanda generada
es aleatoria, no la real. El trabajo de tesis está justamente en los dos
pasos que este script no puede hacer solo:

  1. Depuración de la red en `netedit`: conectividad entre arcos, número de
     carriles, movimientos permitidos, prioridades, estructura de fases.
  2. Calibración de la demanda contra volúmenes observados.

Regla práctica: si la red no simula sin advertencias con demanda baja, no
tiene sentido comparar controladores sobre ella — las diferencias medidas
serán artefactos de la geometría, no de los algoritmos.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tsc.sumo_env  # noqa: F401  (fija SUMO_HOME)

TOOLS = os.path.join(os.environ["SUMO_HOME"], "tools")
# La API oficial de OSM es más estable que los espejos de Overpass y suele
# estar permitida donde Overpass no lo está. Límites: bbox de 0,25 grados
# cuadrados y 50 000 nodos — un corredor cabe de sobra, una comuna entera no.
# Si recibes HTTP 400, la caja es demasiado grande: pártela.
SOURCES = [
    "https://api.openstreetmap.org/api/0.6/map?bbox={}",
    "https://overpass-api.de/api/map?bbox={}",
]


def download_osm(bbox: str, dest: str) -> None:
    last = None
    for tpl in SOURCES:
        url = tpl.format(bbox)
        print(f"Descargando OSM…\n  {url}")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  OK  {dest} ({os.path.getsize(dest) / 1e6:.1f} MB)")
            return
        except Exception as exc:
            print(f"  falló: {exc}")
            last = exc
    raise SystemExit(
        f"No se pudo descargar OSM ({last}). Si es HTTP 400, reduce el bbox."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", help="min_lon,min_lat,max_lon,max_lat")
    ap.add_argument("--osm", help="archivo .osm ya descargado (alternativa a --bbox)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--period", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--keep-geo-boundary",
        help="min_lon,min_lat,max_lon,max_lat — recorta la red al corredor. "
             "Descarga una caja generosa y recorta con esto: los arcos del "
             "borde necesitan contexto para conectar bien.",
    )
    args = ap.parse_args()

    if not args.bbox and not args.osm:
        ap.error("se requiere --bbox o --osm")

    os.makedirs(args.out, exist_ok=True)
    osm = args.osm or os.path.join(args.out, "map.osm")
    net = os.path.join(args.out, "net.net.xml")
    routes = os.path.join(args.out, "routes.rou.xml")

    if not args.osm:
        download_osm(args.bbox, osm)

    print("Convirtiendo a red SUMO…")
    subprocess.run(
        [
            "netconvert",
            "--osm-files", osm,
            "-o", net,
            "--geometry.remove", "true",        # simplifica geometría redundante
            "--roundabouts.guess", "true",
            "--ramps.guess", "true",
            "--junctions.join", "true",         # fusiona intersecciones partidas de OSM
            "--junctions.join-dist", "20",
            "--tls.guess-signals", "true",
            "--tls.discard-simple", "true",
            "--tls.join", "true",
            "--tls.default-type", "static",
            "--remove-edges.isolated", "true",
            "--keep-edges.by-vclass", "passenger",
            "--no-turnarounds", "true",
            "--output.street-names", "true",
        ] + (
            ["--keep-edges.in-geo-boundary", args.keep_geo_boundary]
            if args.keep_geo_boundary else []
        ),
        check=True,
    )

    print("Generando demanda sintética inicial…")
    subprocess.run(
        [
            sys.executable, os.path.join(TOOLS, "randomTrips.py"),
            "-n", net,
            "-o", os.path.join(args.out, "trips.trips.xml"),
            "-r", routes,
            "--begin", "0", "--end", str(args.end),
            "--period", str(args.period),
            "--seed", str(args.seed),
            "--fringe-factor", "20",
            "--validate",
        ],
        check=True,
    )

    print(f"\nOK  red={net}\n    rutas={routes}")
    print(
        "\nSIGUIENTE PASO OBLIGATORIO — no comparar controladores todavía:\n"
        f"  1. netedit {net}\n"
        "     revisar conectividad, carriles, movimientos y fases semafóricas.\n"
        "  2. Verificar que simula limpio:\n"
        f"     sumo -n {net} -r {routes} --no-warnings false --duration-log.statistics\n"
        "  3. Calibrar la demanda contra volúmenes observados antes de\n"
        "     interpretar cualquier diferencia entre controladores."
    )


if __name__ == "__main__":
    main()
