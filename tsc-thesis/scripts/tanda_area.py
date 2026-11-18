#!/usr/bin/env python3
"""Tanda del escenario Las Condes + Providencia: Webster, líneas base, IPPO, evaluación y resumen.

    python scripts/tanda_area.py                      # receta del 18-nov
    python scripts/tanda_area.py --pasos 3000000 --nucleos 4

Versión de `tanda_eod.py` para el área. Diferencias, todas por costo de simulación
(una hora de punta mañana tarda ~37 min en el PC con los planes de OSM):

  * Perfiles con réplicas: valle y punta tarde (`--replicas`, 3 por defecto).
    Punta mañana va como diagnóstico con una sola corrida (`--replicas-pm`).
    Sobresaturado queda fuera de esta tanda.
  * Dos entrenamientos IPPO (obs por fase, recompensa de espera) sobre el conjunto
    mixto de valle y punta tarde, semillas 0 y 1, en paralelo desde el inicio.
  * Una cadena por perfil: Webster (calibrado con el voraz) -> líneas base (tiempo
    fijo, Webster, voraz, Max-Pressure) -> evaluación de cada modelo -> comparación.
  * Al final, `resumen_area.py` arma la tabla y los gráficos.

Agentes y controladores adaptativos actúan sobre los semáforos de tls_eje.json
(scripts/listar_tls_area.py: con código UOCT y 2 a 4 fases verdes). El resto sigue
su programa. Logs en logs/tanda_area/<paso>.log y avance en logs/tanda_area/estado.json.
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
LOGS = os.path.join(RAIZ, "logs", "tanda_area")
BAJA = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
MIXTO = ["eod_valle", "eod_punta_tarde"]

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
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    ap.add_argument("--pasos", type=int, default=3_000_000)
    ap.add_argument("--replicas", type=int, default=3, help="réplicas de evaluación en valle y punta tarde")
    ap.add_argument("--replicas-pm", type=int, default=1, help="corridas en punta mañana (diagnóstico)")
    ap.add_argument("--semillas", default="0,1", help="semillas de entrenamiento IPPO")
    ap.add_argument("--nucleos", type=int, default=4)
    ap.add_argument("--mixto-por-perfil", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # sin suspensión

    # Conjunto mixto: réplicas de entrenamiento de valle y punta tarde, intercaladas
    train = os.path.join(RAIZ, args.scenario, "demand", "train")
    for viejo in glob.glob(os.path.join(train, "routes_eod_mixto_t*.rou.xml")):
        os.remove(viejo)
    k = 0
    for j in range(args.mixto_por_perfil):
        for p in MIXTO:
            shutil.copyfile(os.path.join(train, f"routes_{p}_t{j:02d}.rou.xml"),
                            os.path.join(train, f"routes_eod_mixto_t{k:02d}.rou.xml"))
            k += 1

    esc = os.path.basename(args.scenario)
    modelos = {f"ippo_mixto_s{s}": ("eod_mixto", int(s)) for s in args.semillas.split(",")}
    perfiles = {"eod_valle": args.replicas, "eod_punta_tarde": args.replicas, "eod_punta_manana": args.replicas_pm}
    nucleos = threading.Semaphore(args.nucleos)
    hilos_entrenamiento = {}
    for nombre, (perfil, semilla) in modelos.items():
        orden = ["scripts/train_rl.py", "--scenario", args.scenario, "--profile", perfil, "--obs", "fase",
                 "--seed", str(semilla), "--steps", str(args.pasos), "--checkpoint-every", "500000"]
        h = threading.Thread(target=correr, args=(f"entrena_{nombre}", orden, nucleos))
        h.start()
        hilos_entrenamiento[nombre] = h

    def cadena(perfil: str, n: int) -> None:
        correr(f"webster_{perfil}", ["scripts/build_webster.py", "--scenario", args.scenario,
                                     "--profile", perfil], nucleos)
        correr(f"baselines_{perfil}", ["scripts/run_baselines.py", "--scenario", args.scenario,
                                       "--profile", perfil, "--seeds", str(n)], nucleos)
        for nombre, (entrenado_en, semilla) in modelos.items():
            hilos_entrenamiento[nombre].join()
            modelo = os.path.join("models", esc, f"ppo_fase_wait_adam_{entrenado_en}_s{semilla}.zip")
            if not os.path.exists(os.path.join(RAIZ, modelo)):
                anotar(f"evalua_{nombre}_{perfil}", "omitido: no hay modelo")
                continue
            correr(f"evalua_{nombre}_{perfil}", ["scripts/eval_rl.py", "--scenario", args.scenario,
                                                 "--profile", perfil, "--model", modelo,
                                                 "--seeds", str(n), "--name", nombre], nucleos)
        correr(f"compara_{perfil}", ["scripts/compare.py", "--results",
                                     os.path.join("results", f"{esc}_{perfil}_baselines.json")], nucleos)

    cadenas = [threading.Thread(target=cadena, args=(p, n)) for p, n in perfiles.items()]
    for h in cadenas:
        h.start()
    for h in list(hilos_entrenamiento.values()) + cadenas:
        h.join()
    correr("resumen", ["scripts/resumen_area.py", "--scenario", args.scenario])
    anotar("TANDA", "terminada")


if __name__ == "__main__":
    main()
