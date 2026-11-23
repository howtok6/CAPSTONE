#!/usr/bin/env python3
"""Velocidad media por calle, franja horaria y tipo de control, para las recomendaciones de la app.

El backend de «Vía» estima con esta tabla cuánto demora cada ruta propuesta según la hora
(`POST /v1/rutas`). Sale de la simulación del eje comunal con la demanda EOD:

    franja         perfil de demanda     ventana de la encuesta
    valle          eod_valle             10:00-12:00
    punta_manana   eod_punta_manana      07:00-09:00
    punta_tarde    eod_punta_tarde       17:30-19:30

y dos tipos de control: «actual» (plan de Webster, el mismo de la simulación en vivo) y
«adaptativo» (agente IPPO entrenado con los cuatro perfiles).

    python scripts/exportar_tiempos_app.py --armar --replicas 3

corre cada combinación sobre demandas de evaluación (un proceso por corrida: libsumo admite una
simulación por proceso), promedia y escribe ../backend/datos/tiempos_eje.json.

La velocidad de una calle es la media espacial: suma de velocidades de los vehículos presentes en
cada muestra sobre el número de vehículos. Con ella, largo / velocidad es el tiempo medio de
recorrido, colas incluidas. Son resultados de simulación, no mediciones en la calle.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if __name__ == "__main__":
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FRANJAS = [  # id, nombre, perfil de demanda
    ("valle", "Valle", "eod_valle"),
    ("punta_manana", "Punta mañana", "eod_punta_manana"),
    ("punta_tarde", "Punta tarde", "eod_punta_tarde"),
]
FUENTES = {
    "eje_comunal": "Simulación SUMO del eje Alameda-Providencia-Apoquindo con demanda EOD 2012 calibrada "
                   "(docs/datos/12-demanda-eod.md).",
    "las_condes_providencia": "Simulación SUMO de Las Condes + Providencia (594 semáforos, inventario UOCT) "
                              "con demanda EOD 2012 escala 0,18 y velocidad deseada validadas con TomTom "
                              "(docs/datos/14-depuracion-y-validacion-tomtom.md).",
}
CALENTAMIENTO = 300   # s: la red parte vacía
CADA = 10             # s entre muestras
MIN_MUESTRAS = 30     # vehículos-muestra para confiar en la velocidad de una calle
VEL_MINIMA = 3.0      # km/h: piso, para que una calle bloqueada no dé un tiempo infinito


class MuestreoArcos:
    """Misma interfaz que `medir_colas_eje.Muestreo`: acumula vehículos y velocidad por arco."""

    def __init__(self, conn, eje: list, cada: int):
        import numpy as np

        self.conn, self.cada = conn, cada
        self.arcos = [e for e in conn.edge.getIDList() if not e.startswith(":")]
        self.n = np.zeros(len(self.arcos))
        self.vn = np.zeros(len(self.arcos))

    def paso(self, t: float) -> None:
        if t < CALENTAMIENTO or int(t) % self.cada:
            return
        c = self.conn
        for i, e in enumerate(self.arcos):
            k = c.edge.getLastStepVehicleNumber(e)
            if k:
                self.n[i] += k
                self.vn[i] += k * c.edge.getLastStepMeanSpeed(e)


def una_corrida(args) -> None:
    import medir_colas_eje as base
    from tsc.demand import ruta_evaluacion
    from tsc.rl_env import controlled_tls

    base.Muestreo = MuestreoArcos
    net = os.path.join(args.scenario, "net.net.xml")
    rou = ruta_evaluacion(args.scenario, args.profile, args.seed,
                          os.path.join(args.scenario, "demand", f"routes_{args.profile}.rou.xml"))
    eje = controlled_tls(args.scenario, "auto")
    if args.controller == "ppo":
        m = base.correr_ppo(args.model, net, rou, eje, args.seed, args.end, CADA)
    else:
        m = base.correr_clasico(args.controller, args.scenario, args.profile, net, rou, eje, args.seed,
                                args.end, CADA)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"perfil": args.profile, "controlador": args.controller, "semilla": args.seed, "rutas": rou,
                   "arcos": m.arcos, "n": m.n.tolist(), "vn": m.vn.tolist()}, f)
    print(f"OK {args.out}")


def armar(args) -> None:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)
    import sumolib

    # Una carpeta por escenario: los nombres de archivo no llevan el escenario y, sin --rehacer,
    # se reutilizan las corridas que ya existen
    esc_nombre = os.path.basename(os.path.normpath(args.scenario))
    carpeta = os.path.join("results", "tiempos_app", esc_nombre)
    os.makedirs(carpeta, exist_ok=True)
    control = {"actual": ("webster", None), "adaptativo": ("ppo", args.model)}
    trabajos = []
    for _, _, perfil in FRANJAS:
        for esc, (ctrl, modelo) in control.items():
            for k in range(args.replicas):
                out = os.path.join(carpeta, f"{perfil}_{esc}_s{k:02d}.json")
                orden = [sys.executable, "-u", __file__, "--scenario", args.scenario, "--profile", perfil,
                         "--controller", ctrl, "--seed", str(k), "--end", str(args.end), "--out", out]
                if modelo:
                    orden += ["--model", modelo]
                trabajos.append((out, orden))

    def correr(tr):
        out, orden = tr
        if os.path.exists(out) and not args.rehacer:
            return out, 0
        r = subprocess.run(orden, capture_output=True, text=True, errors="replace")
        if r.returncode:
            print(f"FALLÓ {out}\n{(r.stdout or '')[-600:]}\n{(r.stderr or '')[-1200:]}", flush=True)
        return out, r.returncode

    with ThreadPoolExecutor(max_workers=args.trabajadores) as ex:
        for i, (out, codigo) in enumerate(ex.map(correr, trabajos), 1):
            print(f"  [{i}/{len(trabajos)}] {out} {'ok' if codigo == 0 else 'FALLÓ'}", flush=True)

    # Promedio entre réplicas: se suman vehículos-muestra y velocidades
    net = sumolib.net.readNet(os.path.join(args.scenario, "net.net.xml"))
    vel = {}  # arco -> franja -> escenario -> km/h
    cobertura = {}
    for franja, _, perfil in FRANJAS:
        for esc in control:
            n, vn = {}, {}
            for k in range(args.replicas):
                ruta = os.path.join(carpeta, f"{perfil}_{esc}_s{k:02d}.json")
                if not os.path.exists(ruta):
                    continue
                d = json.load(open(ruta, encoding="utf-8"))
                for e, a, b in zip(d["arcos"], d["n"], d["vn"]):
                    n[e] = n.get(e, 0.0) + a
                    vn[e] = vn.get(e, 0.0) + b
            con_dato = 0
            for e, total in n.items():
                if total >= MIN_MUESTRAS:
                    kmh = max(VEL_MINIMA, 3.6 * vn[e] / total)
                    vel.setdefault(e, {}).setdefault(franja, {})[esc] = round(kmh, 1)
                    con_dato += 1
            cobertura[f"{franja}/{esc}"] = con_dato

    calles = []
    for e in net.getEdges():
        if not e.allows("passenger"):
            continue
        forma = [[round(lat, 6), round(lon, 6)] for lon, lat in (net.convertXY2LonLat(x, y) for x, y in e.getShape())]
        calles.append({"id": e.getID(), "nombre": e.getName() or "", "largo_m": round(e.getLength(), 1),
                       "libre_kmh": round(e.getSpeed() * 3.6, 1), "forma": forma,
                       "vel": vel.get(e.getID(), {})})
    tabla = {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "escenario": os.path.basename(args.scenario),
        "fuente": (FUENTES.get(esc_nombre) or f"Simulación SUMO del escenario {esc_nombre}")
                  + " No son mediciones en la calle.",
        "replicas": args.replicas, "calentamiento_s": CALENTAMIENTO,
        "franjas": [{"id": f, "nombre": nombre, "perfil": perfil} for f, nombre, perfil in FRANJAS],
        "control": {"actual": "webster", "adaptativo": os.path.basename(args.model)},
        "calles_con_dato": cobertura,
        "calles": calles,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(tabla, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\nOK {args.salida}: {len(calles)} calles; con dato por franja/control: {cobertura}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="scenarios/eje_comunal")
    ap.add_argument("--armar", action="store_true", help="corre todas las combinaciones y escribe la tabla")
    ap.add_argument("--replicas", type=int, default=3)
    ap.add_argument("--trabajadores", type=int, default=4)
    ap.add_argument("--rehacer", action="store_true", help="repite corridas que ya tienen resultado")
    ap.add_argument("--model", default="models/eje_comunal/ppo_fase_wait_adam_eod_mixto_s0.zip")
    ap.add_argument("--salida", default=os.path.join("..", "backend", "datos", "tiempos_eje.json"))
    ap.add_argument("--profile")
    ap.add_argument("--controller", default="webster")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.armar:
        armar(args)
    else:
        una_corrida(args)


if __name__ == "__main__":
    main()
