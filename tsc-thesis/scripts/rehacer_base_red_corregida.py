#!/usr/bin/env python3
"""Rehace sobre la red actual las corridas que se hicieron antes de corregir los verdes inseguros.

    python scripts/rehacer_base_red_corregida.py [--trabajos 7]

El 23-nov se corrigieron 2 semáforos (fix_tls.sin_verdes_dobles). Las líneas base fijo, Webster y
voraz de valle y punta tarde (19-nov) y la evaluación de IPPO s0 en valle (19-nov) corrieron con la
red anterior; Max-Pressure ajustado, IPPO s1/s2 y la robustez, con la nueva. En las réplicas 0-4 de
punta tarde la corrección movió la demora de −5,2 % (Webster) a +2,3 % (voraz), así que para comparar
sobre la misma red se repiten esas corridas (10 réplicas, repartidas en procesos). Las filas
anteriores quedan en los JSON con el sufijo «_red19nov».
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESC = "scenarios/las_condes_providencia"
NOMBRE = "las_condes_providencia"
SALIDA = os.path.join(RAIZ, "results", "red_corregida")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trabajos", type=int, default=7)
    ap.add_argument("--replicas", type=int, default=10)
    ap.add_argument("--por-proceso", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(SALIDA, exist_ok=True)
    trabajos = []
    for perfil in ("eod_valle", "eod_punta_tarde"):
        for ctrl in ("fixed", "webster", "greedy"):
            for ini in range(0, a.replicas, a.por_proceso):
                out = os.path.join(SALIDA, f"{perfil}_{ctrl}_{ini}.json")
                trabajos.append((out, ["scripts/run_baselines.py", "--scenario", ESC, "--profile", perfil,
                                       "--controllers", ctrl, "--seeds", str(a.por_proceso),
                                       "--semilla-inicial", str(ini), "--out", out]))
    out = os.path.join(SALIDA, "eod_valle_ippo_mixto_s0.json")
    trabajos.append((out, ["scripts/eval_rl.py", "--scenario", ESC, "--profile", "eod_valle", "--model",
                           f"models/{NOMBRE}/ppo_fase_wait_adam_eod_mixto_s0.zip", "--seeds", str(a.replicas),
                           "--name", "ippo_mixto_s0", "--merge-into", out]))

    def correr(tr):
        out, orden = tr
        if os.path.exists(out):
            return out, 0
        log = out.replace(".json", ".log")
        with open(log, "w", encoding="utf-8") as f:
            return out, subprocess.run([sys.executable, "-u"] + orden, cwd=RAIZ, stdout=f, stderr=subprocess.STDOUT).returncode

    with ThreadPoolExecutor(a.trabajos) as ex:
        for i, (out, cod) in enumerate(ex.map(correr, trabajos), 1):
            print(f"[{i}/{len(trabajos)}] {os.path.basename(out)} {'ok' if cod == 0 else f'FALLÓ {cod}'}", flush=True)

    for perfil in ("eod_valle", "eod_punta_tarde"):
        destino = os.path.join(RAIZ, "results", f"{NOMBRE}_{perfil}_baselines.json")
        filas = json.load(open(destino))
        nuevas = [r for f in sorted(glob.glob(os.path.join(SALIDA, f"{perfil}_*.json"))) for r in json.load(open(f))]
        rehechos = {r["controller"] for r in nuevas}
        for r in filas:
            if r["controller"] in rehechos:
                r["controller"] += "_red19nov"
        filas += nuevas
        json.dump(filas, open(destino, "w"), indent=2)
        print(perfil, len(nuevas), "filas nuevas;", sorted({r["controller"] for r in filas}), flush=True)


if __name__ == "__main__":
    main()
