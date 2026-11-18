"""Captura velocidades reales de TomTom (Traffic Flow, flowSegmentData) en puntos fijos del escenario.

Uso:
    python scripts/tomtom_muestreo.py --scenario scenarios/las_condes_providencia [--n 120]

* La primera vez elige una muestra estratificada de arcos de la red (vías troncales/primarias,
  secundarias y terciarias dentro de las comunas, >= 80 m, separadas >= 250 m) y la guarda en
  data/tomtom/puntos_<escenario>.json. Las capturas siguientes reutilizan exactamente esos puntos,
  para comparar franjas horarias y días sobre la misma base.
* Cada captura queda en data/tomtom/<escenario>/flujo_<AAAAmmdd_HHMM>.json (+ .csv) con la hora local,
  la franja (punta mañana / valle / punta tarde / otra) y, por punto: velocidad actual, velocidad a
  flujo libre, tiempos de viaje, confianza y clase funcional (FRC) del segmento TomTom.
* La clave se lee de la variable TOMTOM_API_KEY o del .env de la API de Benja (gitignored). Nunca se
  imprime ni se guarda: los errores se informan solo con el código HTTP.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

import sumolib
from shapely.geometry import Point, shape
from shapely.ops import unary_union

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DEFECTO = os.path.join(os.path.dirname(RAIZ), "CAPSTONE-dev-benja", "santiago-traffic-api", ".env")
URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/{zoom}/json?point={lat:.6f},{lon:.6f}&unit=KMPH&key={key}"
ESTRATOS = {  # tipo OSM del arco -> estrato
    "highway.motorway": "troncal", "highway.trunk": "troncal", "highway.primary": "troncal",
    "highway.secondary": "secundaria", "highway.tertiary": "terciaria",
}


def clave(env_file: str) -> str:
    k = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not k and os.path.exists(env_file):
        for linea in open(env_file, encoding="utf-8"):
            if linea.strip().startswith("TOMTOM_API_KEY="):
                k = linea.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        sys.exit("Falta TOMTOM_API_KEY (variable de entorno o --env).")
    return k


def franja(t: dt.datetime) -> str:
    h = t.hour + t.minute / 60
    if t.weekday() >= 5:
        return "fin_de_semana"
    if 7 <= h < 9:
        return "punta_manana"
    if 10 <= h < 12.5 or 14.5 <= h < 17:
        return "valle"
    if 17.5 <= h < 20:
        return "punta_tarde"
    return "otra"


def elegir_puntos(scenario: str, n: int, semilla: int) -> list[dict]:
    net = sumolib.net.readNet(os.path.join(scenario, "net.net.xml"))
    comunas = unary_union([shape(f["geometry"]) for f in
                           json.load(open(os.path.join(scenario, "comunas.geojson"), encoding="utf-8"))["features"]])
    candidatos: dict[str, list] = {e: [] for e in set(ESTRATOS.values())}
    for e in net.getEdges():
        est = ESTRATOS.get(e.getType())
        if not est or e.getLength() < 80 or e.getFunction() == "internal":
            continue
        forma = e.getShape()
        x, y = sumolib.geomhelper.positionAtShapeOffset(forma, e.getLength() / 2)
        lon, lat = net.convertXY2LonLat(x, y)
        if comunas.contains(Point(lon, lat)):
            candidatos[est].append({"edge": e.getID(), "calle": e.getName(), "estrato": est, "tipo": e.getType(),
                                    "largo_m": round(e.getLength(), 1), "vmax_kmh": round(e.getSpeed() * 3.6, 1),
                                    "x": x, "y": y, "lat": round(lat, 6), "lon": round(lon, 6)})
    rnd = random.Random(semilla)
    puntos: list[dict] = []
    cuota = {"troncal": n * 4 // 10, "secundaria": n * 35 // 100}
    cuota["terciaria"] = n - sum(cuota.values())
    for est in ("troncal", "secundaria", "terciaria"):
        lista = candidatos[est][:]
        rnd.shuffle(lista)
        tomados = 0
        for c in lista:
            if tomados >= cuota[est]:
                break
            if all((c["x"] - p["x"]) ** 2 + (c["y"] - p["y"]) ** 2 >= 250 ** 2 for p in puntos):
                puntos.append(c)
                tomados += 1
    for i, p in enumerate(puntos):
        p["id"] = i
    return puntos


def consultar(key: str, p: dict, zoom: int) -> dict:
    url = URL.format(zoom=zoom, lat=p["lat"], lon=p["lon"], key=key)
    for intento in range(3):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                d = json.load(r)["flowSegmentData"]
            return {"frc": d.get("frc"), "v_actual_kmh": d.get("currentSpeed"), "v_libre_kmh": d.get("freeFlowSpeed"),
                    "tt_actual_s": d.get("currentTravelTime"), "tt_libre_s": d.get("freeFlowTravelTime"),
                    "confianza": d.get("confidence"), "cerrado": d.get("roadClosure")}
        except urllib.error.HTTPError as e:  # sin la URL: lleva la clave
            if e.code in (429, 503) and intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            return {"error": f"HTTP {e.code}"}
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            if intento < 2:
                time.sleep(1)
                continue
            return {"error": type(e).__name__}
    return {"error": "sin respuesta"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--zoom", type=int, default=15)
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--env", default=ENV_DEFECTO)
    ap.add_argument("--solo-puntos", action="store_true", help="solo elegir/mostrar la muestra, sin consultar")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    esc = os.path.basename(os.path.normpath(a.scenario))
    os.makedirs(os.path.join(RAIZ, "data", "tomtom", esc), exist_ok=True)
    f_puntos = os.path.join(RAIZ, "data", "tomtom", f"puntos_{esc}.json")
    if os.path.exists(f_puntos):
        puntos = json.load(open(f_puntos, encoding="utf-8"))["puntos"]
    else:
        puntos = elegir_puntos(a.scenario, a.n, a.semilla)
        json.dump({"_meta": {"escenario": esc, "n": len(puntos), "semilla": a.semilla,
                             "criterio": "estratificado troncal 40% / secundaria 35% / terciaria 25%, >=80 m, >=250 m entre puntos"},
                   "puntos": puntos}, open(f_puntos, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    print(f"{len(puntos)} puntos {dict(Counter(p['estrato'] for p in puntos))} -> {f_puntos}")
    if a.solo_puntos:
        return
    key = clave(a.env)
    ahora = dt.datetime.now()
    filas = []
    for p in puntos:
        r = consultar(key, p, a.zoom)
        filas.append({k: p[k] for k in ("id", "edge", "calle", "estrato", "lat", "lon", "vmax_kmh")} | r)
        time.sleep(0.12)
    ok = [f for f in filas if "error" not in f]
    meta = {"escenario": esc, "hora_local": ahora.isoformat(timespec="minutes"), "dia_semana": ahora.strftime("%A"),
            "franja": franja(ahora), "zoom": a.zoom, "consultas": len(filas), "ok": len(ok),
            "errores": dict(Counter(f["error"] for f in filas if "error" in f))}
    if ok:
        meta["v_actual_media_kmh"] = round(sum(f["v_actual_kmh"] for f in ok) / len(ok), 1)
        meta["indice_congestion_medio"] = round(sum(f["v_actual_kmh"] / f["v_libre_kmh"] for f in ok if f["v_libre_kmh"]) / len(ok), 3)
    base = os.path.join(RAIZ, "data", "tomtom", esc, f"flujo_{ahora:%Y%m%d_%H%M}")
    json.dump({"_meta": meta, "puntos": filas}, open(base + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as fh:
        campos = sorted({k for f in filas for k in f}, key=lambda k: list(filas[0]).index(k) if k in filas[0] else 99)
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(json.dumps(meta, ensure_ascii=False))
    print(f"OK -> {base}.json")


if __name__ == "__main__":
    main()
