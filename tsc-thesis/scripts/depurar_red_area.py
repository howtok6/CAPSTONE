#!/usr/bin/env python3
"""Depuración reproducible de la red de un escenario por comunas (Las Condes + Providencia).

En el eje la red se arregló a mano en netedit; con ~600 semáforos eso no es viable.
Este script aplica correcciones automáticas y verificables, siempre sobre la red
tal como sale de `build_comunas.py` (se guarda una vez como `net_osm.net.xml`), de
modo que se puede correr las veces que haga falta y da siempre el mismo resultado:

  1. Une semáforos separados por menos de --tls-join-dist m (netconvert --tls.join).
     build_comunas usa 20 m; entre 20 y 25 m quedaban 11 pares de semáforos de un
     mismo cruce con bandejón (Bilbao, Riesco, Estoril…) controlados por separado,
     y la cola de uno bloqueaba al otro.
  1b. Tope de velocidad urbana: netconvert deja a 100/80 km/h las avenidas sin
     `maxspeed` en OSM; pasan a 50 km/h (ver limitar_velocidades). Visto con TomTom.
  2. Da dos fases a los semáforos con un solo verde y virajes permisivos (`g`):
     pasante y viraje protegido, con amarillo de 3 s (misma regla que fix_tls.py en
     el eje). Los de un solo verde sin `g` son cruces peatonales y quedan igual.
  3. Aplica `correcciones_area.json`, si existe: correcciones puntuales por cruce
     detectadas con `puntos_bloqueo.py` (ver el archivo).
  4. Vuelve a emparejar con la UOCT, rehace tls_eje.json y resumen_red.json.

    python scripts/depurar_red_area.py --scenario scenarios/las_condes_providencia

Después hay que regenerar los planes de Webster (cambian los semáforos) y conviene
correr puntos_bloqueo.py para comparar con la red anterior.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)
except ImportError:
    import sumo
    os.environ.setdefault("SUMO_HOME", sumo.SUMO_HOME)
import sumolib  # noqa: E402
from fix_tls import programas_corregidos  # noqa: E402


def netconvert(*args: str) -> None:
    subprocess.run([sumolib.checkBinary("netconvert"), *args, "--no-warnings", "true"], check=True,
                   stdout=subprocess.DEVNULL)


def contar(net_file: str) -> dict:
    net = sumolib.net.readNet(net_file, withPrograms=True)
    tid_de = {}
    for t in net.getTrafficLights():
        for c in t.getConnections():
            tid_de[c[0].getEdge().getToNode().getID()] = t.getID()
    una = 0
    for t in net.getTrafficLights():
        verdes = max(sum(1 for ph in p.getPhases() if ("G" in ph.state or "g" in ph.state) and "y" not in ph.state)
                     for p in t.getPrograms().values())
        una += verdes < 2
    cortos = [e for e in net.getEdges() if e.getLength() < 25
              and e.getFromNode().getType() == "traffic_light" and e.getToNode().getType() == "traffic_light"]
    entre = sum(1 for e in cortos if tid_de.get(e.getFromNode().getID()) != tid_de.get(e.getToNode().getID()))
    return {"semaforos": len(net.getTrafficLights()), "una_fase_verde": una,
            "arcos_cortos_entre_semaforos": len(cortos), "de_ellos_entre_semaforos_distintos": entre}


AUTOPISTA = ("highway.motorway", "highway.motorway_link")


def limitar_velocidades(net_file: str, limite_kmh: float, carpeta: str) -> dict:
    """Corrige la velocidad máxima que netconvert asigna por tipo cuando OSM no trae `maxspeed`.

    El mapa de tipos de netconvert deja primarias y secundarias a 100 km/h y terciarias a 80 km/h
    (unos 72 km de avenidas urbanas en Las Condes + Providencia: Bilbao, Manquehue, Pedro de
    Valdivia, Providencia…). La Ley 21.103 (2018) fija 50 km/h en zona urbana salvo señalización,
    y TomTom mide ~33 km/h a flujo libre en esas vías. Regla: toda vía que no sea autopista con
    ≥ 79 km/h pasa a --limite-urbano; las de 60–70 km/h vienen de `maxspeed` en OSM y se respetan.
    En autopistas se acota a 100 km/h (hay un tramo de Kennedy a 142 km/h).
    """
    net = sumolib.net.readNet(net_file)
    arcos = ET.Element("edges")
    km = {"urbanas": 0.0, "autopista": 0.0}
    for e in net.getEdges():
        if e.getFunction() == "internal":
            continue
        v = e.getSpeed() * 3.6
        if e.getType() in AUTOPISTA:
            nuevo, clase = (100.0, "autopista") if v > 100.5 else (None, None)
        else:
            nuevo, clase = (limite_kmh, "urbanas") if v >= 79 else (None, None)
        if nuevo:
            ET.SubElement(arcos, "edge", id=e.getID(), speed=f"{nuevo / 3.6:.2f}")
            km[clase] += e.getLength() / 1000
    if len(arcos):
        f = os.path.join(carpeta, "_velocidades.edg.xml")
        ET.ElementTree(arcos).write(f, encoding="utf-8")
        netconvert("-s", net_file, "--edge-files", f, "-o", net_file)
        os.remove(f)
    return {"arcos": len(arcos), "km_urbanas": round(km["urbanas"], 1), "km_autopista": round(km["autopista"], 1),
            "limite_urbano_kmh": limite_kmh}


def aplicar_correcciones(net: str, ruta: str, carpeta: str) -> list:
    """correcciones_area.json: lista de {"tipo": ..., ...} con un "motivo" cada una.

    tipos:
      quitar_semaforo   {"nodo": id}            el cruce queda con prioridad (sin semáforo)
      prioridad         {"nodo": id}            cruce sin semáforo con prioridad en vez de
                                                «derecha primero» (right_before_left)
      pistas            {"arco": id, "pistas": n}  corrige el número de pistas de un arco
    """
    cambios = json.load(open(ruta, encoding="utf-8"))
    nodos = ET.Element("nodes")
    arcos = ET.Element("edges")
    for c in cambios:
        if c["tipo"] in ("quitar_semaforo", "prioridad"):
            ET.SubElement(nodos, "node", id=c["nodo"], type="priority")
        elif c["tipo"] == "pistas":
            ET.SubElement(arcos, "edge", id=c["arco"], numLanes=str(c["pistas"]))
        else:
            raise SystemExit(f"tipo de corrección desconocido: {c['tipo']}")
    args = ["-s", net, "-o", net]
    if len(nodos):
        f = os.path.join(carpeta, "_correcciones.nod.xml")
        ET.ElementTree(nodos).write(f, encoding="utf-8")
        args += ["--node-files", f]
    if len(arcos):
        f = os.path.join(carpeta, "_correcciones.edg.xml")
        ET.ElementTree(arcos).write(f, encoding="utf-8")
        args += ["--edge-files", f]
    if len(args) > 4:
        netconvert(*args)
    for f in ("_correcciones.nod.xml", "_correcciones.edg.xml"):
        if os.path.exists(os.path.join(carpeta, f)):
            os.remove(os.path.join(carpeta, f))
    return cambios


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--tls-join-dist", type=float, default=25.0)
    ap.add_argument("--limite-urbano", type=float, default=50.0,
                    help="km/h para vías no autopista que OSM deja con la velocidad por defecto (80/100 km/h)")
    ap.add_argument("--uoct", default="data/uoct/semaforos_uoct_rm_2023.geojson")
    ap.add_argument("--etiquetas-uoct", default="LAS CONDES,PROVIDENCIA,VITACURA/LAS CONDES")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net = os.path.join(a.scenario, "net.net.xml")
    original = os.path.join(a.scenario, "net_osm.net.xml")
    if not os.path.exists(original):
        shutil.copyfile(net, original)
        print(f"Red sin depurar guardada en {original}")
    informe = {"antes": contar(original)}

    print(f"1. Unir semáforos a menos de {a.tls_join_dist:g} m…", flush=True)
    netconvert("-s", original, "-o", net, "--tls.join", "true", "--tls.join-dist", str(a.tls_join_dist))
    informe["tras_unir"] = contar(net)

    print(f"1b. Velocidades: tope urbano de {a.limite_urbano:g} km/h donde OSM no trae maxspeed…", flush=True)
    informe["velocidades"] = limitar_velocidades(net, a.limite_urbano, a.scenario)

    print("2. Dos fases para los semáforos de un solo verde con virajes permisivos…", flush=True)
    nuevos = programas_corregidos(net)
    if nuevos:
        add = ET.Element("additional")
        add.extend(nuevos)
        ET.indent(add)
        destino = os.path.join(a.scenario, "tls_fixes.add.xml")
        ET.ElementTree(add).write(destino, encoding="utf-8", xml_declaration=True)
        netconvert("-s", net, "--tllogic-files", destino, "-o", net)
    informe["fases_corregidas"] = [e.get("id") for e in nuevos]

    ruta = os.path.join(a.scenario, "correcciones_area.json")
    if os.path.exists(ruta):
        print("3. Correcciones puntuales (correcciones_area.json)…", flush=True)
        informe["correcciones"] = aplicar_correcciones(net, ruta, a.scenario)
    informe["despues"] = contar(net)

    print("4. Emparejar con la UOCT y rehacer tls_eje.json…", flush=True)
    comunas = os.path.join(a.scenario, "comunas.geojson")
    subprocess.run([sys.executable, os.path.join(AQUI, "emparejar_uoct.py"), "--net", net, "--uoct", a.uoct,
                    "--area", comunas, "--comunas", a.etiquetas_uoct, "--out", a.scenario], check=True)
    subprocess.run([sys.executable, os.path.join(AQUI, "listar_tls_area.py"), "--scenario", a.scenario], check=True)
    from build_comunas import resumen
    informe["resumen_red"] = resumen(net, a.scenario)
    json.dump(informe, open(os.path.join(a.scenario, "depuracion.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    for k in ("antes", "tras_unir", "despues"):
        print(f"  {k:10s} {informe[k]}")
    print(f"  fases corregidas: {len(informe['fases_corregidas'])}")
    print("OK. Regenera los planes de Webster: build_webster.py --scenario … --profile …")


if __name__ == "__main__":
    main()
