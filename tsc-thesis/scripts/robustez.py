#!/usr/bin/env python3
"""Prepara las dos perturbaciones de robustez (OE6) sobre un perfil ya evaluado.

    python scripts/robustez.py --scenario scenarios/las_condes_providencia --perfil eod_punta_tarde --replicas 5

Crea dos perfiles nuevos dentro del mismo escenario, con las mismas réplicas de evaluación
(semillas) que el perfil base, para que la comparación sea pareada:

* `<perfil>_cierre`: cierre de la pista derecha de Av. Providencia (sentido único al poniente)
  entre Los Leones y Pedro de Valdivia (~700 m), desde los 900 s hasta el final. Se aplica con un
  `rerouter`/`closingLaneReroute` en `robustez_cierre.add.xml`, que se carga con la variable
  de entorno TSC_SUMO_EXTRA="-a <archivo>" (la leen sumo_env.py y eval_rl.py). La red no
  cambia, así que los semáforos, Webster y los modelos siguen valiendo.
* `<perfil>_alza`: alza súbita del 30 % de la demanda desde los 1.800 s. Se suma a cada
  réplica base una demanda extra (escala 0,3 × la base, mismo speedFactor) de la que se
  conservan solo las salidas posteriores a 1.800 s.

Los controladores no se reajustan a la perturbación: Webster usa el plan del perfil base.
Después: baselines_paralelo.ps1 -Perfil <perfil>_cierre (con TSC_SUMO_EXTRA) y <perfil>_alza,
y eval_rl.py del modelo IPPO en ambos (ver robustez.ps1).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)
except ImportError:
    pass
import sumolib  # noqa: E402

# Av. Providencia (un sentido, al poniente) entre Los Leones y Pedro de Valdivia
CIERRE = {"calle": "Avenida Providencia", "lon_min": -70.6130, "lon_max": -70.6060, "lat": -33.4215,
          "tolerancia_lat": 0.004}


def tramos_cierre(net_file: str) -> list[dict]:
    net = sumolib.net.readNet(net_file)
    out = []
    for e in net.getEdges():
        if (e.getName() != CIERRE["calle"] or e.getFunction() == "internal"
                or sum(l.allows("passenger") for l in e.getLanes()) < 2):
            continue
        (x0, y0), (x1, y1) = e.getFromNode().getCoord(), e.getToNode().getCoord()
        if x1 >= x0:  # Providencia es de un sentido, hacia el poniente
            continue
        lon, lat = net.convertXY2LonLat((x0 + x1) / 2, (y0 + y1) / 2)
        if CIERRE["lon_min"] <= lon <= CIERRE["lon_max"] and abs(lat - CIERRE["lat"]) <= CIERRE["tolerancia_lat"]:
            # La pista 0 de Providencia es Solo Bus (sin autos en la demanda): cerrarla no tuvo ningún
            # efecto (corrida del 24-nov). Se cierra una pista de autos del medio: la de la derecha
            # lleva los virajes a la derecha y la de la izquierda los de la izquierda, y cerrarlas
            # deja rutas sin conexión (SUMO aborta: "no valid route").
            autos = [l for l in e.getLanes() if l.allows("passenger")]
            pista = autos[len(autos) // 2]
            out.append({"arco": e.getID(), "pista": pista.getID(), "indice": pista.getIndex(),
                        "pistas": e.getLaneNumber(),
                        "pistas_autos": sum(l.allows("passenger") for l in e.getLanes()),
                        "largo_m": round(e.getLength(), 1)})
    return out


def escribir_cierre(scenario: str, tramos: list[dict], desde: int, hasta: int) -> str:
    add = ET.Element("additional")
    r = ET.SubElement(add, "rerouter", id="cierre_providencia", edges=" ".join(t["arco"] for t in tramos))
    iv = ET.SubElement(r, "interval", begin=str(desde), end=str(hasta))
    for t in tramos:
        ET.SubElement(iv, "closingLaneReroute", id=t["pista"], disallow="all")
    ET.indent(add)
    ruta = os.path.abspath(os.path.join(scenario, "robustez_cierre.add.xml"))
    ET.ElementTree(add).write(ruta, encoding="utf-8", xml_declaration=True)
    return ruta


def juntar(base: str, extra: str, desde: float, salida: str) -> tuple[int, int]:
    raiz = ET.parse(base).getroot()
    tipos = {v.get("id") for v in raiz.iter("vType")}
    vehiculos = [v for v in raiz if v.tag in ("vehicle", "trip", "flow")]
    agregados = 0
    for v in ET.parse(extra).getroot():
        if v.tag == "vType" and v.get("id") in tipos:
            continue
        if v.tag in ("vehicle", "trip") and float(v.get("depart")) >= desde:
            v.set("id", "alza_" + v.get("id"))
            vehiculos.append(v)
            agregados += 1
    vehiculos.sort(key=lambda v: float(v.get("depart")))
    nuevo = ET.Element("routes")
    nuevo.extend([v for v in raiz.iter("vType")] + vehiculos)
    ET.ElementTree(nuevo).write(salida, encoding="utf-8", xml_declaration=True)
    return len(vehiculos) - agregados, agregados


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--perfil", default="eod_punta_tarde")
    ap.add_argument("--replicas", type=int, default=5)
    ap.add_argument("--escala", type=float, default=0.18, help="escala de la demanda base")
    ap.add_argument("--speed-factor", type=float, default=0.7)
    ap.add_argument("--alza", type=float, default=0.30)
    ap.add_argument("--alza-desde", type=int, default=1800)
    ap.add_argument("--cierre-desde", type=int, default=900)
    ap.add_argument("--fin", type=int, default=3600)
    ap.add_argument("--solo-cierre", action="store_true", help="rehace solo el adicional del cierre")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ev = os.path.join(a.scenario, "demand", "eval")
    plan = os.path.join(a.scenario, f"webster_plan_{a.perfil}.json")
    informe = {"perfil_base": a.perfil, "replicas": a.replicas}

    # Cierre de pista
    tramos = tramos_cierre(os.path.join(a.scenario, "net.net.xml"))
    if not tramos:
        sys.exit("No se encontraron tramos para el cierre: revisa CIERRE")
    add = escribir_cierre(a.scenario, tramos, a.cierre_desde, a.fin)
    for k in range(a.replicas):
        shutil.copyfile(os.path.join(ev, f"routes_{a.perfil}_s{k:02d}.rou.xml"),
                        os.path.join(ev, f"routes_{a.perfil}_cierre_s{k:02d}.rou.xml"))
    shutil.copyfile(plan, os.path.join(a.scenario, f"webster_plan_{a.perfil}_cierre.json"))
    informe["cierre"] = {"adicional": os.path.relpath(add), "desde_s": a.cierre_desde, "tramos": tramos,
                         "largo_total_m": round(sum(t["largo_m"] for t in tramos)),
                         "variable": f'TSC_SUMO_EXTRA="-a {add}"'}
    print(f"Cierre: {len(tramos)} tramos, {informe['cierre']['largo_total_m']} m -> {add}")
    if a.solo_cierre:
        ruta = os.path.join(a.scenario, f"robustez_{a.perfil}.json")
        previo = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else {}
        previo["cierre"] = informe["cierre"]
        json.dump(previo, open(ruta, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("OK (solo cierre)")
        return

    # Alza súbita
    tmp = tempfile.mkdtemp(prefix="alza_")
    subprocess.run([sys.executable, os.path.join(AQUI, "build_demand_area.py"), "--scenario", a.scenario,
                    "--escala", str(a.escala * a.alza), "--speed-factor", str(a.speed_factor),
                    "--profiles", a.perfil, "--train-replicas", str(a.replicas), "--carpeta", tmp,
                    "--seed", "77"], check=True)  # réplicas «train» (semillas 1000+k): otras que las de evaluación
    informe["alza"] = {"factor": a.alza, "desde_s": a.alza_desde, "replicas": []}
    for k in range(a.replicas):
        base = os.path.join(ev, f"routes_{a.perfil}_s{k:02d}.rou.xml")
        extra = os.path.join(tmp, "train", f"routes_{a.perfil}_t{k:02d}.rou.xml")
        salida = os.path.join(ev, f"routes_{a.perfil}_alza_s{k:02d}.rou.xml")
        n_base, n_extra = juntar(base, extra, a.alza_desde, salida)
        informe["alza"]["replicas"].append({"archivo": os.path.basename(salida), "base": n_base, "extra": n_extra})
        print(f"Alza s{k:02d}: {n_base} + {n_extra} vehículos")
    shutil.copyfile(plan, os.path.join(a.scenario, f"webster_plan_{a.perfil}_alza.json"))
    shutil.rmtree(tmp, ignore_errors=True)

    with open(os.path.join(a.scenario, f"robustez_{a.perfil}.json"), "w", encoding="utf-8") as f:
        json.dump(informe, f, indent=1, ensure_ascii=False)
    print("OK")


if __name__ == "__main__":
    main()
