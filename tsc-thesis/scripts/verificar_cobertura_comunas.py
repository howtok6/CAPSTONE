#!/usr/bin/env python3
"""¿Están Las Condes y Providencia completamente habilitadas? Chequeo por comuna.

Revisa, para cada comuna del escenario (comunas.geojson), cada capa que la tesis y la app usan:

    red          km de calles para autos y cobertura de una grilla de 200 m (punto con una calle
                 a menos de 100 m); los huecos esperables son parques y cerros
    semáforos    inventario UOCT vehicular emparejado con un semáforo de la red, semáforos de la
                 red, controlados por los agentes (tls_eje.json) y con plan Webster por perfil
    demanda      viajes que salen o llegan a la comuna en cada perfil de demanda
    app          calles con velocidad en la tabla de tiempos (backend/datos/tiempos_area.json)

    python scripts/verificar_cobertura_comunas.py --scenario scenarios/las_condes_providencia

Escribe results/cobertura_comunas.json y una tabla en pantalla.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tsc.sumo_env  # noqa: E402,F401 (fija SUMO_HOME)
import sumolib  # noqa: E402
from shapely.geometry import Point, shape  # noqa: E402
from shapely.prepared import prep  # noqa: E402

PERFILES = ["eod_valle", "eod_punta_manana", "eod_punta_tarde"]
GRILLA_M = 200
RADIO_M = 100


def comunas_xy(scenario: str, net) -> dict:
    """Polígono de cada comuna en coordenadas de la red (metros)."""
    g = json.load(open(os.path.join(scenario, "comunas.geojson"), encoding="utf-8"))
    out = {}
    for f in g["features"]:
        geom = f["geometry"]
        anillos = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
        xy = {"type": "Polygon", "coordinates": [[net.convertLonLat2XY(lon, lat) for lon, lat in anillo]
                                                  for anillo in anillos[:1]]}
        out[f["properties"]["comuna"]] = shape(xy)
    return out


def comuna_de(polis: dict, x: float, y: float) -> str | None:
    p = Point(x, y)
    for nombre, (poli, _) in polis.items():
        if poli.contains(p):
            return nombre
    return None


def medio(e) -> tuple:
    forma = e.getShape()
    return forma[len(forma) // 2]


def red(net, polis) -> dict:
    km = collections.Counter()
    for e in net.getEdges():
        if e.allows("passenger") and e.getFunction() != "internal":
            c = comuna_de(polis, *medio(e))
            if c:
                km[c] += e.getLength() / 1000
    out = {}
    # Las Condes llega a la precordillera (lon -70,43), donde OSM no tiene calles para autos:
    # la red termina en el último arco de OSM. Se informa también la cobertura dentro del
    # recuadro de la red, que es la parte urbanizada.
    (_, _), (bx1, _) = net.getBBoxXY()
    for nombre, (poli, preparado) in polis.items():
        x0, y0, x1, y1 = poli.bounds
        total = cubiertos = 0
        dentro = dentro_ok = 0
        huecos = []
        y = y0
        while y <= y1:
            x = x0
            while x <= x1:
                if preparado.contains(Point(x, y)):
                    total += 1
                    cerca = [e for e, _ in net.getNeighboringEdges(x, y, RADIO_M) if e.allows("passenger")]
                    if x <= bx1:
                        dentro += 1
                        dentro_ok += bool(cerca)
                    if cerca:
                        cubiertos += 1
                    else:
                        lon, lat = net.convertXY2LonLat(x, y)
                        huecos.append([round(lat, 5), round(lon, 5)])
                x += GRILLA_M
            y += GRILLA_M
        out[nombre] = {"km_calles_autos": round(km[nombre], 1), "puntos_grilla": total,
                       "puntos_con_calle": cubiertos, "cobertura_pct": round(100 * cubiertos / max(total, 1), 1),
                       "lon_este_red": round(net.convertXY2LonLat(bx1, y0)[0], 3),
                       "puntos_zona_urbana": dentro,
                       "cobertura_zona_urbana_pct": round(100 * dentro_ok / max(dentro, 1), 1),
                       "huecos_muestra": huecos[:: max(1, len(huecos) // 15)]}
    return out


def semaforos(scenario: str, net, polis) -> dict:
    eje = set(json.load(open(os.path.join(scenario, "tls_eje.json"), encoding="utf-8"))["eje"])
    planes = {}
    for p in PERFILES:
        ruta = os.path.join(scenario, f"webster_plan_{p}.json")
        if os.path.exists(ruta):
            planes[p] = set(json.load(open(ruta, encoding="utf-8")))
    por = collections.defaultdict(lambda: collections.Counter())
    comuna_tls = {}
    for t in net.getTrafficLights():
        nodos = {c[0].getEdge().getToNode() for c in t.getConnections()}
        if not nodos:
            continue
        x = sum(n.getCoord()[0] for n in nodos) / len(nodos)
        y = sum(n.getCoord()[1] for n in nodos) / len(nodos)
        c = comuna_de(polis, x, y) or "fuera (borde)"
        comuna_tls[t.getID()] = c
        por[c]["red"] += 1
        por[c]["controlados_agente"] += t.getID() in eje
        for p, ids in planes.items():
            por[c][f"plan_webster_{p}"] += t.getID() in ids
    uoct = json.load(open(os.path.join(scenario, "uoct_match.json"), encoding="utf-8"))
    sin = collections.defaultdict(list)
    for u in uoct:
        if u["peatonal"]:
            continue
        c = {"LAS CONDES": "LAS CONDES", "PROVIDENCIA": "PROVIDENCIA"}.get(u["comuna_geo"], "fuera (borde)")
        por[c]["uoct_vehicular"] += 1
        if u["match"] == "tls":
            por[c]["uoct_emparejados"] += 1
        else:
            sin[c].append({"codigo": u["codigo"], "cruce": f"{u['acceso_1']} / {u['acceso_2']}",
                           "lat": u["lat"], "lon": u["lon"], "motivo": u["match"]})
    return {c: dict(v, uoct_sin_semaforo=sin.get(c, [])) for c, v in por.items()}, comuna_tls


def demanda(scenario: str, net, polis) -> dict:
    cache = {}

    def comuna_arco(e):
        if e not in cache:
            cache[e] = comuna_de(polis, *medio(net.getEdge(e))) if net.hasEdge(e) else None
        return cache[e]

    out = {}
    for p in PERFILES:
        ruta = os.path.join(scenario, "demand", f"routes_{p}.rou.xml")
        if not os.path.exists(ruta):
            continue
        sale, llega, total = collections.Counter(), collections.Counter(), 0
        for _, el in ET.iterparse(ruta):
            if el.tag == "vehicle":
                r = el.find("route")
                if r is not None:
                    arcos = r.get("edges", "").split()
                    if arcos:
                        total += 1
                        sale[comuna_arco(arcos[0]) or "fuera"] += 1
                        llega[comuna_arco(arcos[-1]) or "fuera"] += 1
                el.clear()
        out[p] = {"viajes": total, "salen": dict(sale), "llegan": dict(llega)}
    return out


def app(tabla_ruta: str, net, polis) -> dict:
    if not os.path.exists(tabla_ruta):
        return {"estado": f"falta {tabla_ruta}"}
    t = json.load(open(tabla_ruta, encoding="utf-8"))
    por = collections.defaultdict(collections.Counter)
    for c in t["calles"]:
        if not net.hasEdge(c["id"]):
            continue
        com = comuna_de(polis, *medio(net.getEdge(c["id"]))) or "fuera (borde)"
        por[com]["calles"] += 1
        for franja, ctrl in c["vel"].items():
            for k in ctrl:
                por[com][f"{franja}/{k}"] += 1
    return {"escenario": t.get("escenario"), "generado": t.get("generado"),
            "franjas": t.get("franjas"), "por_comuna": {k: dict(v) for k, v in por.items()}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    ap.add_argument("--tabla-app", default=os.path.join("..", "backend", "datos", "tiempos_area.json"))
    ap.add_argument("--salida", default=os.path.join("results", "cobertura_comunas.json"))
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net = sumolib.net.readNet(os.path.join(a.scenario, "net.net.xml"), withPrograms=False)
    polis = {k: (v, prep(v)) for k, v in comunas_xy(a.scenario, net).items()}
    r = {"escenario": os.path.basename(os.path.normpath(a.scenario))}
    r["red"] = red(net, polis)
    r["semaforos"], _ = semaforos(a.scenario, net, polis)
    r["demanda"] = demanda(a.scenario, net, polis)
    r["app"] = app(a.tabla_app, net, polis)
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    json.dump(r, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("RED")
    for c, v in r["red"].items():
        print(f"  {c:12s} {v['km_calles_autos']:7.1f} km  grilla {v['puntos_con_calle']}/{v['puntos_grilla']}"
              f" = {v['cobertura_pct']}%  (al poniente de lon {v['lon_este_red']}: {v['cobertura_zona_urbana_pct']}%)")
    print("SEMÁFOROS")
    for c, v in sorted(r["semaforos"].items()):
        print(f"  {c:14s} " + "  ".join(f"{k}={n}" for k, n in v.items() if k != "uoct_sin_semaforo")
              + f"  uoct_sin_semaforo={len(v['uoct_sin_semaforo'])}")
    print("DEMANDA")
    for p, v in r["demanda"].items():
        print(f"  {p:18s} viajes={v['viajes']}  salen={v['salen']}  llegan={v['llegan']}")
    print("APP")
    print(json.dumps(r["app"].get("por_comuna", r["app"]), ensure_ascii=False))
    print(f"OK {a.salida}")


if __name__ == "__main__":
    main()
