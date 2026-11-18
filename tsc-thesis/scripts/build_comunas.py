#!/usr/bin/env python3
"""Red SUMO de comunas completas con los semáforos del inventario UOCT.

Pasos:
  1. Polígonos comunales desde Nominatim (OSM) -> comunas.geojson
  2. Área de la red: unión de las comunas + --buffer m, recortada con --recorte
     (Las Condes llega hasta la cordillera; sobre -70,488 no hay semáforos)
  3. OSM en recuadros desde la API principal (parte los que exceden el límite)
  4. netconvert con las mismas opciones de build_santiago.py, sin living_street,
     service ni track (pasajes y accesos: no aportan al tránsito de paso)
  5. Empareja la UOCT con los semáforos de la red, semaforiza con --tls.set los
     cruces UOCT que OSM no marcó y vuelve a emparejar
  6. resumen_red.json con tamaño, controlabilidad y cobertura UOCT

Uso:
    python scripts/importar_uoct.py --out data/uoct
    python scripts/build_comunas.py --comunas "Las Condes,Providencia" \
        --out scenarios/las_condes_providencia --uoct data/uoct/semaforos_uoct_rm_2023.geojson

No produce un escenario calibrado: falta demanda y depurar la red (ver resumen).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401  (fija SUMO_HOME)
except ImportError:
    pass
import sumolib  # noqa: E402

UA = {"User-Agent": "tesis-semaforos-duoc/1.0"}
API = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}"
NOMINATIM = "https://nominatim.openstreetmap.org/search?"
A_UTM = Transformer.from_crs(4326, 32719, always_xy=True)
A_GEO = Transformer.from_crs(32719, 4326, always_xy=True)
NETCONVERT_OPTS = [
    "--geometry.remove", "true", "--roundabouts.guess", "true", "--ramps.guess", "true",
    "--junctions.join", "true", "--junctions.join-dist", "20",
    "--tls.guess-signals", "true", "--tls.discard-simple", "true",
    "--tls.join", "true", "--tls.join-dist", "20", "--tls.default-type", "static",
    "--remove-edges.isolated", "true", "--keep-edges.by-vclass", "passenger",
    "--remove-edges.by-type", "highway.living_street,highway.service,highway.track",
    "--no-turnarounds", "true", "--output.street-names", "true", "--no-warnings", "true",
]


def a_utm(g):
    return shapely.transform(g, lambda c: np.column_stack(A_UTM.transform(c[:, 0], c[:, 1])))


def a_geo(g):
    return shapely.transform(g, lambda c: np.column_stack(A_GEO.transform(c[:, 0], c[:, 1])))


def poligonos(comunas, destino):
    if os.path.exists(destino):
        return destino
    feats = []
    for c in comunas:
        q = urllib.parse.urlencode({"q": f"{c}, Región Metropolitana, Chile", "format": "json",
                                    "polygon_geojson": 1, "featureType": "city", "limit": 3})
        res = json.load(urllib.request.urlopen(urllib.request.Request(NOMINATIM + q, headers=UA), timeout=60))
        r = next(x for x in res if x["osm_type"] == "relation" and x["geojson"]["type"] in ("Polygon", "MultiPolygon"))
        feats.append({"type": "Feature", "geometry": r["geojson"],
                      "properties": {"comuna": c.upper(), "osm_relation": r["osm_id"]}})
        print(f"  {c}: relación OSM {r['osm_id']}")
        time.sleep(1.5)  # política de uso de Nominatim
    json.dump({"type": "FeatureCollection", "features": feats}, open(destino, "w", encoding="utf-8"), ensure_ascii=False)
    return destino


def bajar(caja, destino, nivel=0):
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return [destino]
    req = urllib.request.Request(API.format(*caja), headers=UA)
    for _ in range(4):
        try:
            datos = urllib.request.urlopen(req, timeout=300).read()
            open(destino, "wb").write(datos)
            print(f"  {os.path.basename(destino)} {len(datos) / 1e6:.1f} MB", flush=True)
            return [destino]
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 509) and nivel < 5:  # demasiados nodos: partir en dos
                o, s, e, n = caja
                if e - o >= n - s:
                    m = (o + e) / 2
                    partes = [(o, s, m, n), (m, s, e, n)]
                else:
                    m = (s + n) / 2
                    partes = [(o, s, e, m), (o, m, e, n)]
                b = destino[:-4]
                return bajar(partes[0], b + "a.osm", nivel + 1) + bajar(partes[1], b + "b.osm", nivel + 1)
            print(f"  HTTP {ex.code}; reintento", flush=True)
        except Exception as ex:  # noqa: BLE001
            print(f"  {ex}; reintento", flush=True)
        time.sleep(10)
    raise SystemExit(f"No se pudo descargar {caja}")


def recuadros(bounds, paso):
    o, s, e, n = bounds
    xs = np.arange(o, e, paso)
    ys = np.arange(s, n, paso)
    return [(round(x, 5), round(y, 5), round(min(x + paso, e), 5), round(min(y + paso, n), 5))
            for x in xs for y in ys if min(x + paso, e) - x > 1e-4 and min(y + paso, n) - y > 1e-4]


def emparejar(args, net, out):
    script = os.path.join(os.path.dirname(__file__), "emparejar_uoct.py")
    subprocess.run([sys.executable, script, "--net", net, "--uoct", args.uoct,
                    "--area", os.path.join(args.out, "comunas.geojson"),
                    "--comunas", args.etiquetas_uoct, "--out", out], check=True)


def resumen(net_file, out):
    net = sumolib.net.readNet(net_file, withPrograms=True)
    verdes = []
    for t in net.getTrafficLights():
        for p in t.getPrograms().values():
            verdes.append(sum(1 for ph in p.getPhases()
                              if ("G" in ph.state or "g" in ph.state) and "y" not in ph.state))
    cortos = sum(1 for e in net.getEdges() if e.getLength() < 25
                 and e.getFromNode().getType() == "traffic_light" and e.getToNode().getType() == "traffic_light")
    match = json.load(open(os.path.join(out, "uoct_match.json"), encoding="utf-8"))
    tls_uoct = json.load(open(os.path.join(out, "tls_uoct.json")))
    r = {
        "arcos": len(net.getEdges()), "nodos": len(net.getNodes()),
        "km_pista": round(sum(e.getLength() * e.getLaneNumber() for e in net.getEdges()) / 1000),
        "tipos_de_via": dict(Counter(e.getType() for e in net.getEdges()).most_common()),
        "semaforos_red": len(net.getTrafficLights()),
        "semaforos_con_uoct": len(tls_uoct),
        "semaforos_no_controlables": sum(v < 2 for v in verdes),
        "arcos_menos_25m_entre_semaforos": cortos,
        "uoct": dict(Counter(f"{m['match']}_{'peatonal' if m['peatonal'] else 'vehicular'}" for m in match)),
    }
    json.dump(r, open(os.path.join(out, "resumen_red.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--comunas", required=True, help='p. ej. "Las Condes,Providencia"')
    ap.add_argument("--out", required=True)
    ap.add_argument("--uoct", required=True)
    ap.add_argument("--etiquetas-uoct", default=None,
                    help="comunas UOCT a incluir aunque caigan en el borde (por defecto, las mismas en mayúsculas)")
    ap.add_argument("--buffer", type=float, default=400.0, help="m alrededor de las comunas")
    ap.add_argument("--recorte", default="-70.641,-33.453,-70.488,-33.362",
                    help="min_lon,min_lat,max_lon,max_lat; vacío para no recortar")
    ap.add_argument("--paso", type=float, default=0.02, help="grados por recuadro de descarga")
    args = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    comunas = [c.strip() for c in args.comunas.split(",")]
    args.etiquetas_uoct = args.etiquetas_uoct or ",".join(c.upper() for c in comunas)
    os.makedirs(args.out, exist_ok=True)

    print("1. Polígonos comunales (Nominatim)…")
    fc = json.load(open(poligonos(comunas, os.path.join(args.out, "comunas.geojson")), encoding="utf-8"))
    union = unary_union([shape(f["geometry"]) for f in fc["features"]])

    print("2. Área de la red…")
    area = a_geo(a_utm(union).buffer(args.buffer).simplify(25))
    if args.recorte:
        area = area.intersection(box(*map(float, args.recorte.split(","))))
    if area.geom_type != "Polygon":
        area = max(area.geoms, key=lambda g: g.area)
    poly = ",".join(f"{x:.6f},{y:.6f}" for x, y in area.exterior.coords)
    open(os.path.join(args.out, "area_poly.txt"), "w").write(poly)
    json.dump({"type": "Feature", "properties": {"buffer_m": args.buffer, "recorte": args.recorte},
               "geometry": mapping(area)}, open(os.path.join(args.out, "area.geojson"), "w"))
    print(f"   {a_utm(area).area / 1e6:.1f} km²")

    print("3. OSM en recuadros…")
    carpeta = os.path.join(args.out, "osm_tiles")
    os.makedirs(carpeta, exist_ok=True)
    o, s, e, n = area.bounds
    archivos = []
    for i, caja in enumerate(recuadros((o - 0.004, s - 0.004, e + 0.004, n + 0.004), args.paso)):
        archivos += bajar(caja, os.path.join(carpeta, f"t{i:02d}.osm"))
        time.sleep(1)

    print("4. netconvert…")
    base = os.path.join(args.out, "net_base.net.xml")
    net = os.path.join(args.out, "net.net.xml")
    nc = sumolib.checkBinary("netconvert")
    subprocess.run([nc, "--osm-files", ",".join(archivos), "-o", base, *NETCONVERT_OPTS,
                    "--keep-edges.in-geo-boundary", poly], check=True)

    print("5. Emparejar con la UOCT y semaforizar faltantes…")
    previo = os.path.join(args.out, "uoct_previo")
    emparejar(args, base, previo)
    nuevos = open(os.path.join(previo, "tls_set.txt")).read().strip()
    cmd = [nc, "-s", base, "-o", net, "--tls.default-type", "static", "--no-warnings", "true"]
    subprocess.run(cmd + (["--tls.set", nuevos] if nuevos else []), check=True)
    emparejar(args, net, args.out)

    print("6. Resumen…")
    r = resumen(net, args.out)
    print(json.dumps({k: v for k, v in r.items() if k != "tipos_de_via"}, ensure_ascii=False, indent=1))
    print(f"\nOK  {net}\nSiguiente: python scripts/diagnose_net.py y demanda (no hay rutas todavía).")


if __name__ == "__main__":
    main()
