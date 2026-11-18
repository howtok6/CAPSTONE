#!/usr/bin/env python3
"""Dónde se traba la red: teletransportes de SUMO agrupados por cruce y por causa.

SUMO saca a un vehículo de la red cuando lleva --espera segundos sin avanzar y
anota la causa en el registro de advertencias:

    jam        cola detenida: falta de capacidad o bloqueo aguas abajo
    yield      no logra entrar al cruce: prioridades o conflicto de giros
    wrong lane no puede cambiarse a la pista que necesita: conexiones o pistas mal
               importadas desde OSM (es casi siempre un error de la red)

Corre una hora con los planes fijos de la red y agrupa los teletransportes por el
cruce al final del arco donde ocurrieron. Los cruces que concentran `wrong lane` o
`yield` son los que hay que revisar primero. Los arcos internos de un cruce se
cuentan en ese cruce.

    python scripts/puntos_bloqueo.py --scenario scenarios/las_condes_providencia \
        --rutas scenarios/las_condes_providencia/demand/eval/routes_eod_valle_s00.rou.xml
Escribe <escenario>/bloqueos_<nombre de las rutas>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)
except ImportError:
    import sumo
    os.environ.setdefault("SUMO_HOME", sumo.SUMO_HOME)
import sumolib  # noqa: E402

PATRON = re.compile(r"Teleporting vehicle '[^']+'; waited too long \(([^)]+)\), lane='([^']+)'")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--net", default=None, help="red a probar (por defecto <escenario>/net.net.xml)")
    ap.add_argument("--fin", type=int, default=3600)
    ap.add_argument("--espera", type=int, default=300, help="s detenido antes de teletransportar")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--sumo-extra", default="", help='opciones adicionales de SUMO, p. ej. "--ignore-junction-blocker 20"')
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net_file = a.net or os.path.join(a.scenario, "net.net.xml")
    log = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
    t0 = time.perf_counter()
    p = subprocess.run([sumolib.checkBinary("sumo"), "-n", net_file, "-r", a.rutas, "--begin", "0",
                        "--end", str(a.fin), "--time-to-teleport", str(a.espera), "--no-step-log", "true",
                        "--duration-log.statistics", "true", "--error-log", log, *a.sumo_extra.split()],
                       capture_output=True, text=True)
    seg = time.perf_counter() - t0
    registro = open(log, encoding="utf-8", errors="replace").read()
    os.unlink(log)
    eventos = PATRON.findall(registro)  # solo del registro: SUMO también los repite en stderr
    texto = p.stdout + p.stderr
    net = sumolib.net.readNet(net_file)
    por_cruce = defaultdict(Counter)
    for causa, lane in eventos:
        edge = lane.rsplit("_", 1)[0]
        if edge.startswith(":"):  # pista interna del cruce: ":<cruce>_<n>"
            nodo = edge[1:].rsplit("_", 1)[0]
        else:
            try:
                nodo = net.getEdge(edge).getToNode().getID()
            except KeyError:
                nodo = "?" + edge
        por_cruce[nodo][causa] += 1
    filas = []
    for nodo, c in por_cruce.items():
        fila = {"nodo": nodo, "total": sum(c.values()), **dict(c)}
        if net.hasNode(nodo):
            n = net.getNode(nodo)
            fila["lon"], fila["lat"] = [round(v, 5) for v in net.convertXY2LonLat(*n.getCoord())]
            fila["calles"] = sorted({e.getName() for e in n.getIncoming() if e.getName()})[:4]
            fila["semaforo"] = n.getType() == "traffic_light"
        filas.append(fila)
    filas.sort(key=lambda f: -f["total"])
    est = {}
    for k, nombre in (("Inserted", "insertados"), ("Running", "en_red_al_final"), ("Waiting", "sin_entrar_al_final"),
                      ("Teleports", "teletransportes")):
        m = re.findall(rf"\b{k}: ([\d.]+)", texto)
        if m:
            est[nombre] = float(m[-1])
    r = {"red": net_file, "rutas": a.rutas, "espera_s": a.espera, "sumo_extra": a.sumo_extra,
         "segundos_computo": round(seg),
         "estadisticas": est, "por_causa": dict(Counter(c for c, _ in eventos)),
         "cruces_con_bloqueo": len(filas), "cruces": filas[: a.top]}
    out = a.out or os.path.join(a.scenario, f"bloqueos_{os.path.basename(a.rutas).replace('.rou.xml', '')}.json")
    json.dump(r, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in r.items() if k != "cruces"}, ensure_ascii=False))
    for f in filas[:15]:
        print(f"  {f['total']:5d}  {f.get('jam', 0):4d} jam {f.get('yield', 0):4d} yield {f.get('wrong lane', 0):4d} pista"
              f"  {f['nodo'][:40]:40s} {', '.join(f.get('calles', []))[:70]}")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
