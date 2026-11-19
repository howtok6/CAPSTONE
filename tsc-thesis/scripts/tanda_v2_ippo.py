#!/usr/bin/env python3
"""Tanda v2, parte IPPO: reentrena y evalúa sobre la red depurada y la demanda validada con TomTom.

    python scripts/tanda_v2_ippo.py                       # 3 semillas, 3M pasos, 10 réplicas
    python scripts/tanda_v2_ippo.py --semillas 0 --pasos 500000   # prueba corta

Supone que ya corrieron tanda_v2_pt.ps1 y tanda_v2_valle.ps1 (demanda 0,18 + speedFactor 0,7,
Webster y líneas base de valle y punta tarde). A diferencia de tanda_area.py no rehace Webster
ni líneas base:

  1. Arma el conjunto mixto (réplicas train de valle y punta tarde, intercaladas).
  2. Mueve los modelos de la red original a models/<esc>/_red_original/.
  3. Entrena IPPO (obs por fase, recompensa de espera) con cada semilla, en paralelo.
  4. Evalúa cada modelo en valle y punta tarde con --replicas réplicas (eval_rl.py agrega las
     filas al JSON de líneas base de cada perfil) y corre compare.py por perfil.

Logs en logs/tanda_v2/ippo_<paso>.log y avance en logs/tanda_v2/ippo_estado.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import shutil
import subprocess
import sys
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(RAIZ, "logs", "tanda_v2")
BAJA = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
MIXTO = ["eod_valle", "eod_punta_tarde"]
estado, candado = {}, threading.Lock()


def anotar(paso: str, valor: str) -> None:
    with candado:
        estado[paso] = f"{valor} {dt.datetime.now().strftime('%d-%m %H:%M:%S')}"
        with open(os.path.join(LOGS, "ippo_estado.json"), "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=1, ensure_ascii=False)


def correr(paso: str, orden: list, nucleos: threading.Semaphore) -> int:
    with nucleos:
        anotar(paso, "en curso desde")
        with open(os.path.join(LOGS, f"ippo_{paso}.log"), "w", encoding="utf-8") as log:
            codigo = subprocess.run([sys.executable, "-u"] + orden, cwd=RAIZ, stdout=log,
                                    stderr=subprocess.STDOUT, creationflags=BAJA).returncode
    anotar(paso, "listo" if codigo == 0 else f"FALLÓ (código {codigo})")
    return codigo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    ap.add_argument("--pasos", type=int, default=3_000_000)
    ap.add_argument("--semillas", default="0,1,2")
    ap.add_argument("--replicas", type=int, default=10)
    ap.add_argument("--nucleos", type=int, default=4)
    ap.add_argument("--mixto-por-perfil", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # sin suspensión

    train = os.path.join(RAIZ, args.scenario, "demand", "train")
    for viejo in glob.glob(os.path.join(train, "routes_eod_mixto_t*.rou.xml")):
        os.remove(viejo)
    k = 0
    for j in range(args.mixto_por_perfil):
        for p in MIXTO:
            shutil.copyfile(os.path.join(train, f"routes_{p}_t{j:02d}.rou.xml"),
                            os.path.join(train, f"routes_eod_mixto_t{k:02d}.rou.xml"))
            k += 1
    anotar("mixto", f"{k} réplicas")

    esc = os.path.basename(args.scenario)
    carpeta = os.path.join(RAIZ, "models", esc)
    viejos = os.path.join(carpeta, "_red_original")
    os.makedirs(viejos, exist_ok=True)
    for f in glob.glob(os.path.join(carpeta, "ppo_fase_wait_adam_eod_mixto_s*")):
        destino = os.path.join(viejos, os.path.basename(f))
        if not os.path.exists(destino):
            shutil.move(f, destino)

    nucleos = threading.Semaphore(args.nucleos)
    semillas = [int(s) for s in args.semillas.split(",")]
    hilos = {}
    for s in semillas:
        orden = ["scripts/train_rl.py", "--scenario", args.scenario, "--profile", "eod_mixto", "--obs", "fase",
                 "--seed", str(s), "--steps", str(args.pasos), "--checkpoint-every", "500000"]
        hilos[s] = threading.Thread(target=correr, args=(f"entrena_s{s}", orden, nucleos))
        hilos[s].start()

    def evaluar(perfil: str) -> None:
        for s in semillas:
            hilos[s].join()
            modelo = os.path.join("models", esc, f"ppo_fase_wait_adam_eod_mixto_s{s}.zip")
            if not os.path.exists(os.path.join(RAIZ, modelo)):
                anotar(f"evalua_s{s}_{perfil}", "omitido: no hay modelo")
                continue
            correr(f"evalua_s{s}_{perfil}", ["scripts/eval_rl.py", "--scenario", args.scenario, "--profile", perfil,
                                            "--model", modelo, "--seeds", str(args.replicas),
                                            "--name", f"ippo_mixto_s{s}"], nucleos)
        correr(f"compara_{perfil}", ["scripts/compare.py", "--results",
                                     os.path.join("results", f"{esc}_{perfil}_baselines.json")], nucleos)

    cadenas = [threading.Thread(target=evaluar, args=(p,)) for p in MIXTO]
    for h in cadenas:
        h.start()
    for h in list(hilos.values()) + cadenas:
        h.join()
    anotar("TANDA", "terminada")


if __name__ == "__main__":
    main()
