#!/usr/bin/env python3
"""Elige la mejor configuración de Max-Pressure del ajuste y la deja donde run_baselines.py la lee.

    python scripts/elegir_maxpressure.py --scenario scenarios/las_condes_providencia --perfil eod_punta_tarde \
        [--tambien eod_punta_tarde_cierre,eod_punta_tarde_alza]

Lee results/ajuste_<esc>_<perfil>.json (ajustar_baselines.py --solo maxpressure, demandas de
entrenamiento), elige la configuración con menor demora media (delay_all) y escribe
<escenario>/maxpressure_<perfil>.json con {"medida", "switch_penalty", ...}. Con --tambien copia
la misma configuración a otros perfiles (las perturbaciones de robustez usan la del perfil base).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--perfil", required=True)
    ap.add_argument("--tambien", default="")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    esc = os.path.basename(os.path.normpath(a.scenario))
    filas = [f for f in json.load(open(os.path.join("results", f"ajuste_{esc}_{a.perfil}.json"), encoding="utf-8"))
             if f["tipo"] == "maxpressure"]
    por_config: dict[str, list] = {}
    for f in filas:
        por_config.setdefault(f["config"], []).append(f["delay_all_mean"])
    ranking = sorted((statistics.fmean(v), c, len(v)) for c, v in por_config.items())
    demora, config, n = ranking[0]
    medida, pen = config.split("|")
    salida = {"medida": medida, "switch_penalty": float(pen), "delay_all_ajuste": round(demora, 1),
              "replicas_ajuste": n, "fuente": f"results/ajuste_{esc}_{a.perfil}.json",
              "ranking": [{"config": c, "delay_all": round(d, 1)} for d, c, _ in ranking[:5]]}
    for p in [a.perfil] + [x for x in a.tambien.split(",") if x]:
        ruta = os.path.join(a.scenario, f"maxpressure_{p}.json")
        json.dump(salida, open(ruta, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"{p}: {medida} / penalización {pen} (delay_all {demora:.1f} s en el ajuste) -> {ruta}")


if __name__ == "__main__":
    main()
