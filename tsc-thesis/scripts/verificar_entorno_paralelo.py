#!/usr/bin/env python3
"""Comprueba que el entorno paralelo nativo da lo mismo que la cadena AEC de sumo-rl, y cuánto más rápido.

    python scripts/verificar_entorno_paralelo.py --scenario scenarios/las_condes_providencia \
        --model models/las_condes_providencia/ppo_fase_wait_adam_eod_mixto_s0.zip --profile eod_valle

Corre eval_rl.py dos veces con el mismo modelo, réplica y semilla: con TSC_ENV_AEC=1 (cadena
AEC → paralela original) y sin ella (`SubsetSumoParallelEnv`). Las métricas deben coincidir
exactamente. Resultado del 23-nov (487 semáforos, valle, 900 s): 18 de 18 métricas iguales;
71 s contra 128 s de reloj (incluye ~15 s de arranque). En entrenamiento, una iteración de PPO
con 206 semáforos dejó los parámetros idénticos (diferencia máxima 0,0).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time


def correr(a, aec: bool) -> tuple[dict, float]:
    salida = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    os.unlink(salida)
    env = dict(os.environ, TSC_ENV_AEC="1" if aec else "")
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "scripts/eval_rl.py", "--scenario", a.scenario, "--profile", a.profile,
                    "--model", a.model, "--seeds", "1", "--seconds", str(a.seconds), "--name", "verif",
                    "--merge-into", salida], env=env, check=True, capture_output=True)
    seg = time.perf_counter() - t0
    fila = json.load(open(salida))[0]
    os.unlink(salida)
    return fila, seg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--profile", default="eod_valle")
    ap.add_argument("--seconds", type=int, default=900)
    a = ap.parse_args()
    nuevo, t_nuevo = correr(a, aec=False)
    viejo, t_viejo = correr(a, aec=True)
    distintas = {k: (viejo[k], nuevo.get(k)) for k in viejo if k != "controller" and viejo[k] != nuevo.get(k)}
    print(f"métricas distintas: {len(distintas)} {distintas if distintas else ''}")
    print(f"tiempo: AEC {t_viejo:.0f} s · paralelo nativo {t_nuevo:.0f} s (×{t_viejo / t_nuevo:.2f})")
    sys.exit(1 if distintas else 0)


if __name__ == "__main__":
    main()
