"""Junta las comparaciones SUMO vs TomTom de logs/validacion en una tabla agregada para el repositorio.

    python scripts/resumen_validacion.py [--captura flujo_20261118_1857]

Escribe results/validacion/resumen_<captura>.{json,md}. Solo métricas agregadas: las velocidades
por punto de TomTom quedan fuera del repositorio (condiciones de uso).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--captura", default="flujo_20261118_1857")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    filas = []
    for f in sorted(glob.glob(os.path.join(RAIZ, "logs", "validacion", f"tomtom_{a.captura}_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        m = d["metricas"]
        filas.append({"corrida": os.path.basename(f)[len(f"tomtom_{a.captura}_"):-5], "rutas": d["rutas"],
                      "speed_factor": d.get("speed_factor"), "sumo_extra": d["sumo_extra"], "ventana_s": d["ventana_s"],
                      "arcos": d["con_muestra"], "velocidad": m["global"], "indice": m["global_indice"],
                      "por_estrato": {k: m[k] for k in ("troncal", "secundaria", "terciaria")},
                      "libre_tomtom_vs_limite_red": m["libre_vs_limite"],
                      "atasco_tomtom_pct": m["atasco_tomtom_pct"], "atasco_sim_pct": m["atasco_sim_pct"],
                      "segundos_computo": d["segundos_computo"], "captura_meta": d["captura_meta"]})
    if not filas:
        sys.exit("No hay comparaciones para esa captura.")
    os.makedirs(os.path.join(RAIZ, "results", "validacion"), exist_ok=True)
    base = os.path.join(RAIZ, "results", "validacion", f"resumen_{a.captura}")
    json.dump(filas, open(base + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    meta = filas[0]["captura_meta"]
    lineas = [f"# SUMO vs TomTom · captura {meta['hora_local']} ({meta['franja']}, {meta['dia_semana']})", "",
              "| Corrida | v TomTom / sim | Sesgo | MAE | r | Índice TomTom / sim | ρ índice | % atascado TomTom / sim | s |",
              "|---|---|---:|---:|---:|---|---:|---|---:|"]
    for r in filas:
        v, i = r["velocidad"], r["indice"]
        lineas.append(f"| {r['corrida']} | {v['media_tomtom']:.1f} / {v['media_sim']:.1f} | {v['sesgo']:+.1f} | {v['mae']:.1f} "
                      f"| {v['pearson']} | {i['media_tomtom']:.2f} / {i['media_sim']:.2f} | {i['spearman']} "
                      f"| {r['atasco_tomtom_pct']} / {r['atasco_sim_pct']} | {r['segundos_computo']} |")
    open(base + ".md", "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    print("\n".join(lineas))
    print(f"OK -> {base}.json")


if __name__ == "__main__":
    main()
