#!/usr/bin/env python3
"""H3: IPPO vs MAPPO (crítico centralizado) controlando solo los semáforos de Providencia.

    python scripts/tanda_mappo_prov.py                         # 3 semillas por algoritmo, 3M pasos
    python scripts/tanda_mappo_prov.py --semillas 0 --pasos 300000   # prueba corta

Opción A del cierre: MAPPO acotado a Providencia (206 semáforos, tls_providencia.json); el resto
del área sigue su programa fijo. Para que la comparación cambie una sola cosa, IPPO se reentrena
con el mismo alcance: ambos usan la misma red de política, los mismos hiperparámetros, la misma
demanda mixta y las mismas semillas; solo cambia lo que ve el crítico (tsc.mappo).

  1. Entrena IPPO (obs fase) y MAPPO (obs fase_global) por semilla, --nucleos a la vez.
  2. Evalúa cada modelo en valle y punta tarde con --replicas réplicas, cada uno a
     results/mappo_prov/<perfil>_<algo>_s<k>.json, y junta todo en
     results/las_condes_providencia_<perfil>_providencia.json.

Logs en logs/tanda_v2/mappo_<paso>.log y avance en logs/tanda_v2/mappo_estado.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(RAIZ, "logs", "tanda_v2")
BAJA = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
PERFILES = ["eod_valle", "eod_punta_tarde"]
estado, candado = {}, threading.Lock()


def anotar(paso: str, valor: str) -> None:
    with candado:
        estado[paso] = f"{valor} {dt.datetime.now().strftime('%d-%m %H:%M:%S')}"
        with open(os.path.join(LOGS, "mappo_estado.json"), "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=1, ensure_ascii=False)


def correr(paso: str, orden: list, nucleos: threading.Semaphore) -> int:
    with nucleos:
        anotar(paso, "en curso desde")
        with open(os.path.join(LOGS, f"mappo_{paso}.log"), "w", encoding="utf-8") as log:
            codigo = subprocess.run([sys.executable, "-u"] + orden, cwd=RAIZ, stdout=log,
                                    stderr=subprocess.STDOUT, creationflags=BAJA).returncode
    anotar(paso, "listo" if codigo == 0 else f"FALLÓ (código {codigo})")
    return codigo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    ap.add_argument("--pasos", type=int, default=3_000_000)
    ap.add_argument("--semillas", default="0,1,2")
    ap.add_argument("--algos", default="ippo,mappo")
    ap.add_argument("--replicas", type=int, default=10)
    ap.add_argument("--nucleos", type=int, default=6)
    ap.add_argument("--control", default="providencia")
    args = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(os.path.join(RAIZ, "results", "mappo_prov"), exist_ok=True)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # sin suspensión

    esc = os.path.basename(args.scenario)
    nucleos = threading.Semaphore(args.nucleos)
    semillas = [int(s) for s in args.semillas.split(",")]
    algos = args.algos.split(",")
    modelos, hilos = {}, {}
    for algo in algos:
        obs = "fase_global" if algo == "mappo" else "fase"
        pref = "mappo" if algo == "mappo" else "ppo"
        for s in semillas:
            nombre = f"{algo}_{args.control}_s{s}"
            modelos[nombre] = os.path.join("models", esc, f"{pref}_{obs}_wait_adam_eod_mixto_{args.control}_s{s}.zip")
            orden = ["scripts/train_rl.py", "--scenario", args.scenario, "--profile", "eod_mixto",
                     "--algo", algo, "--obs", obs, "--control", args.control, "--seed", str(s),
                     "--steps", str(args.pasos), "--checkpoint-every", "500000"]
            hilos[nombre] = threading.Thread(target=correr, args=(f"entrena_{nombre}", orden, nucleos))
            hilos[nombre].start()

    def evaluar(nombre: str, perfil: str) -> None:
        hilos[nombre].join()
        if not os.path.exists(os.path.join(RAIZ, modelos[nombre])):
            anotar(f"evalua_{nombre}_{perfil}", "omitido: no hay modelo")
            return
        correr(f"evalua_{nombre}_{perfil}", ["scripts/eval_rl.py", "--scenario", args.scenario, "--profile", perfil,
                                            "--model", modelos[nombre], "--seeds", str(args.replicas),
                                            "--name", nombre, "--merge-into",
                                            os.path.join("results", "mappo_prov", f"{perfil}_{nombre}.json")], nucleos)

    evals = [threading.Thread(target=evaluar, args=(n, p)) for n in modelos for p in PERFILES]
    for h in evals:
        h.start()
    for h in list(hilos.values()) + evals:
        h.join()

    for perfil in PERFILES:
        filas = []
        for f in sorted(glob.glob(os.path.join(RAIZ, "results", "mappo_prov", f"{perfil}_*.json"))):
            filas += json.load(open(f))
        destino = os.path.join(RAIZ, "results", f"{esc}_{perfil}_{args.control}.json")
        json.dump(filas, open(destino, "w"), indent=2)
        anotar(f"junta_{perfil}", f"{len(filas)} filas")
    anotar("TANDA", "terminada")


if __name__ == "__main__":
    main()
