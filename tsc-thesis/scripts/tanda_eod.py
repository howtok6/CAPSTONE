#!/usr/bin/env python3
"""Tanda completa sobre la demanda EOD: entrenamientos, líneas base, evaluación y comparación.

    python scripts/tanda_eod.py --pasos 2000000 --replicas 10

Reparte el trabajo en los núcleos disponibles sin que dos procesos escriban el mismo archivo:

  * Entrenamientos (uno por núcleo, en paralelo desde el inicio):
      ppo_fase · eod_punta_tarde · semillas 0 y 1   (misma receta que la tanda sintética)
      ppo_fase · eod_mixto · semilla 0              (los cuatro perfiles rotando por episodio)
  * Una cadena por perfil, cada paso en serie: plan de Webster -> líneas base -> evaluación de
    cada modelo (espera a que termine su entrenamiento) -> comparación estadística.

Cada paso deja su salida en logs/tanda_eod/<paso>.log y el avance en logs/tanda_eod/estado.json.
Los resultados quedan en results/eje_comunal_<perfil>_baselines.json, igual que antes.
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
PERFILES = ["eod_punta_tarde", "eod_punta_manana", "eod_valle", "eod_sobresaturado"]
LOGS = os.path.join(RAIZ, "logs", "tanda_eod")
BAJA = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)

estado, candado = {}, threading.Lock()


def anotar(paso: str, valor: str) -> None:
    with candado:
        estado[paso] = f"{valor} {dt.datetime.now().strftime('%d-%m %H:%M:%S')}"
        with open(os.path.join(LOGS, "estado.json"), "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=1, ensure_ascii=False)


def correr(paso: str, orden: list, nucleos: threading.Semaphore | None = None) -> int:
    if nucleos:
        nucleos.acquire()
    anotar(paso, "en curso desde")
    try:
        with open(os.path.join(LOGS, paso + ".log"), "w", encoding="utf-8") as log:
            codigo = subprocess.run([sys.executable, "-u"] + orden, cwd=RAIZ, stdout=log,
                                    stderr=subprocess.STDOUT, creationflags=BAJA).returncode
    finally:
        if nucleos:
            nucleos.release()
    anotar(paso, "listo" if codigo == 0 else f"FALLÓ (código {codigo})")
    return codigo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="scenarios/eje_comunal")
    ap.add_argument("--pasos", type=int, default=2_000_000)
    ap.add_argument("--replicas", type=int, default=10)
    ap.add_argument("--nucleos", type=int, default=4)
    ap.add_argument("--mixto-por-perfil", type=int, default=3,
                    help="réplicas de entrenamiento de cada perfil que entran al conjunto mixto")
    args = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # sin suspensión

    # Conjunto mixto: réplicas de entrenamiento de los cuatro perfiles, intercaladas
    train = os.path.join(RAIZ, args.scenario, "demand", "train")
    for viejo in glob.glob(os.path.join(train, "routes_eod_mixto_t*.rou.xml")):
        os.remove(viejo)
    k = 0
    for j in range(args.mixto_por_perfil):
        for p in PERFILES:
            shutil.copyfile(os.path.join(train, f"routes_{p}_t{j:02d}.rou.xml"),
                            os.path.join(train, f"routes_eod_mixto_t{k:02d}.rou.xml"))
            k += 1

    modelos = {  # nombre en los resultados: (perfil de entrenamiento, semilla)
        "ippo_pt_s0": ("eod_punta_tarde", 0),
        "ippo_pt_s1": ("eod_punta_tarde", 1),
        "ippo_mixto_s0": ("eod_mixto", 0),
    }
    esc = os.path.basename(args.scenario)
    nucleos = threading.Semaphore(args.nucleos)
    hilos_entrenamiento = {}
    for nombre, (perfil, semilla) in modelos.items():
        orden = ["scripts/train_rl.py", "--scenario", args.scenario, "--profile", perfil, "--obs", "fase",
                 "--seed", str(semilla), "--steps", str(args.pasos)]
        h = threading.Thread(target=correr, args=(f"entrena_{nombre}", orden, nucleos))
        h.start()
        hilos_entrenamiento[nombre] = h

    def cadena(perfil: str) -> None:
        correr(f"webster_{perfil}", ["scripts/build_webster.py", "--scenario", args.scenario,
                                     "--profile", perfil], nucleos)
        correr(f"baselines_{perfil}", ["scripts/run_baselines.py", "--scenario", args.scenario,
                                       "--profile", perfil, "--seeds", str(args.replicas)], nucleos)
        for nombre, (entrenado_en, semilla) in modelos.items():
            hilos_entrenamiento[nombre].join()
            modelo = os.path.join("models", esc, f"ppo_fase_wait_adam_{entrenado_en}_s{semilla}.zip")
            if not os.path.exists(os.path.join(RAIZ, modelo)):
                anotar(f"evalua_{nombre}_{perfil}", "omitido: no hay modelo")
                continue
            correr(f"evalua_{nombre}_{perfil}", ["scripts/eval_rl.py", "--scenario", args.scenario,
                                                 "--profile", perfil, "--model", modelo,
                                                 "--seeds", str(args.replicas), "--name", nombre], nucleos)
        correr(f"compara_{perfil}", ["scripts/compare.py", "--results",
                                     os.path.join("results", f"{esc}_{perfil}_baselines.json")], nucleos)

    cadenas = [threading.Thread(target=cadena, args=(p,)) for p in PERFILES]
    for h in cadenas:
        h.start()
    for h in list(hilos_entrenamiento.values()) + cadenas:
        h.join()
    anotar("TANDA", "terminada")


if __name__ == "__main__":
    main()
