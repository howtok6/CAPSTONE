#!/usr/bin/env python3
"""Semáforos que controlan los agentes en un escenario por comunas -> tls_eje.json.

El arnés (run_baselines, build_webster, train_rl, eval_rl) lee la lista `eje` de
<escenario>/tls_eje.json para saber qué semáforos son adaptativos; el resto sigue
su programa de tiempo fijo. En el escenario del área se controlan los semáforos
de la red que tienen código UOCT (tls_uoct.json, de emparejar_uoct.py), al menos
dos fases verdes y no más de --max-fases (la observación por fase de
tsc/observations.py tiene MAX_FASES = 4 columnas por bloque). El nombre `eje` se
conserva para no tocar el arnés.

    python scripts/listar_tls_area.py --scenario scenarios/las_condes_providencia
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)
except ImportError:
    import sumo
    os.environ.setdefault("SUMO_HOME", sumo.SUMO_HOME)
import sumolib  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--max-fases", type=int, default=4)
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net = sumolib.net.readNet(os.path.join(a.scenario, "net.net.xml"), withPrograms=True)
    uoct = json.load(open(os.path.join(a.scenario, "tls_uoct.json"), encoding="utf-8"))
    controlados, una_fase, muchas, sin_uoct = [], [], [], 0
    for t in net.getTrafficLights():
        verdes = max(sum(1 for ph in p.getPhases() if ("G" in ph.state or "g" in ph.state) and "y" not in ph.state)
                     for p in t.getPrograms().values())
        if t.getID() not in uoct:
            sin_uoct += 1
        elif verdes < 2:
            una_fase.append(t.getID())
        elif verdes > a.max_fases:
            muchas.append(t.getID())
        else:
            controlados.append(t.getID())
    out = {"eje": sorted(controlados),
           "_meta": {"criterio": f"semáforo con código UOCT y entre 2 y {a.max_fases} fases verdes",
                     "semaforos_red": len(net.getTrafficLights()), "controlados": len(controlados),
                     "uoct_con_una_fase": sorted(una_fase),
                     "uoct_con_mas_fases": sorted(muchas), "sin_codigo_uoct": sin_uoct}}
    json.dump(out, open(os.path.join(a.scenario, "tls_eje.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"Controlados: {len(controlados)} · UOCT con una sola fase verde: {len(una_fase)} · "
          f"con más de {a.max_fases}: {len(muchas)} · "
          f"sin código UOCT (tiempo fijo): {sin_uoct} · total {len(net.getTrafficLights())}")


if __name__ == "__main__":
    main()
