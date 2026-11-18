#!/usr/bin/env python3
"""Empareja los cruces del inventario UOCT 2023 con los semáforos de una red SUMO.

Para cada cruce UOCT del área busca el nodo semaforizado más cercano de la red.
  tls          : hay un semáforo de la red a <= --radio-tls m (se usa ese)
  nodo_sin_tls : no hay semáforo cerca, pero sí un cruce de la red a <= --radio-nodo m
                 -> candidato a semaforizar con `netconvert --tls.set`
  sin_nodo     : no hay cruce de la red cerca (calle filtrada, paso a desnivel, error)

Uso:
  python scripts/emparejar_uoct.py --net scenarios/las_condes_providencia/net.net.xml \
      --uoct data/uoct/semaforos_uoct_rm_2023.geojson \
      --area scenarios/las_condes_providencia/comunas.geojson \
      --comunas "LAS CONDES,PROVIDENCIA,VITACURA/LAS CONDES" --out scenarios/las_condes_providencia
Escribe uoct_match.json (detalle por cruce), tls_uoct.json (semáforo -> códigos UOCT)
y tls_set.txt (nodos vehiculares a semaforizar).
"""
import argparse, json, math, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME en el repo)
except ImportError:
    pass
import sumolib
from shapely.geometry import shape, Point


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", required=True)
    ap.add_argument("--uoct", required=True)
    ap.add_argument("--area", required=True, help="GeoJSON FeatureCollection con un polígono por comuna (properties.comuna)")
    ap.add_argument("--comunas", required=True, help="etiquetas de comuna UOCT a incluir aunque caigan en el borde")
    ap.add_argument("--radio-tls", type=float, default=40.0)
    ap.add_argument("--radio-nodo", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net = sumolib.net.readNet(a.net, withPrograms=True)
    pol = {f["properties"]["comuna"]: shape(f["geometry"]) for f in json.load(open(a.area, encoding="utf-8"))["features"]}
    etiquetas = {c.strip().upper() for c in a.comunas.split(",")}
    uo = []
    for f in json.load(open(a.uoct, encoding="utf-8"))["features"]:
        r = dict(f["properties"]); r["lon"], r["lat"] = f["geometry"]["coordinates"]
        geo = next((c for c, g in pol.items() if g.contains(Point(r["lon"], r["lat"]))), None)
        if geo or r["comuna"].upper() in etiquetas:
            r["comuna_geo"] = geo or "borde"; uo.append(r)
    tlsn = []
    for t in net.getTrafficLights():
        for n in {c[0].getEdge().getToNode() for c in t.getConnections()}:
            tlsn.append((*n.getCoord(), t.getID()))
    nodos = [(*n.getCoord(), n.getID()) for n in net.getNodes() if n.getType() != "dead_end"]

    def cerca(x, y, lst):
        b = min(lst, key=lambda t: (t[0] - x) ** 2 + (t[1] - y) ** 2)
        return b[2], math.hypot(b[0] - x, b[1] - y)

    res, usados = Counter(), defaultdict(list)
    for r in uo:
        x, y = net.convertLonLat2XY(r["lon"], r["lat"])
        tid, d = cerca(x, y, tlsn); r["d_tls"] = round(d, 1)
        if d <= a.radio_tls:
            r["match"], r["tls"] = "tls", tid; usados[tid].append(r["codigo"])
        else:
            nid, dn = cerca(x, y, nodos); r["nodo"], r["d_nodo"] = nid, round(dn, 1)
            r["match"] = "nodo_sin_tls" if dn <= a.radio_nodo else "sin_nodo"
        res[(r["match"], "peatonal" if r["peatonal"] else "vehicular")] += 1
    os.makedirs(a.out, exist_ok=True)
    json.dump(uo, open(os.path.join(a.out, "uoct_match.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(usados, open(os.path.join(a.out, "tls_uoct.json"), "w"), indent=1)
    nuevos = sorted({r["nodo"] for r in uo if r["match"] == "nodo_sin_tls" and not r["peatonal"]})
    open(os.path.join(a.out, "tls_set.txt"), "w").write(",".join(nuevos))
    print(f"Cruces UOCT del área: {len(uo)} ({sum(not r['peatonal'] for r in uo)} vehiculares)")
    for k, v in sorted(res.items()):
        print(f"  {k[0]:13s} {k[1]:10s} {v}")
    print(f"Semáforos de la red: {len(net.getTrafficLights())}; con cruce UOCT: {len(usados)}; "
          f"sin UOCT: {len(net.getTrafficLights()) - len(usados)}")
    print(f"Nodos vehiculares a semaforizar (tls_set.txt): {len(nuevos)}")


if __name__ == "__main__":
    main()
