#!/usr/bin/env python3
"""Genera el escenario sintético de grilla (control de sanidad del pipeline).

Una grilla 4x4 con demanda controlable es el escenario estándar de la
literatura: sirve para verificar que los controladores funcionan antes de
enfrentarlos a una red real, donde los errores de geometría se confunden con
los errores de algoritmo.

    python scripts/build_grid.py --size 4 --out scenarios/grid4x4
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tsc.sumo_env import os as _  # noqa: F401  (fija SUMO_HOME)

TOOLS = os.path.join(os.environ["SUMO_HOME"], "tools")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=4, help="intersecciones por lado")
    ap.add_argument("--length", type=int, default=200, help="largo de arco (m)")
    ap.add_argument("--lanes", type=int, default=2)
    ap.add_argument("--out", default="scenarios/grid4x4")
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--period", type=float, default=1.2,
                    help="segundos entre vehículos generados (menor = más demanda)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    net = os.path.join(args.out, "net.net.xml")
    routes = os.path.join(args.out, "routes.rou.xml")

    subprocess.run(
        [
            "netgenerate", "--grid",
            "--grid.number", str(args.size),
            "--grid.length", str(args.length),
            "--default.lanenumber", str(args.lanes),
            "--default.speed", "13.89",
            "--tls.guess", "true",
            "--tls.default-type", "static",
            "--tls.green.time", "31",
            "--tls.yellow.time", "3",
            "--no-turnarounds", "true",
            "-o", net,
        ],
        check=True,
    )

    subprocess.run(
        [
            sys.executable, os.path.join(TOOLS, "randomTrips.py"),
            "-n", net,
            "-o", os.path.join(args.out, "trips.trips.xml"),
            "-r", routes,
            "--begin", "0", "--end", str(args.end),
            "--period", str(args.period),
            "--seed", str(args.seed),
            "--fringe-factor", "10",   # la mayoría de los viajes entra/sale por el borde
            "--validate",
        ],
        check=True,
    )
    print(f"OK  net={net}\n    routes={routes}")


if __name__ == "__main__":
    main()
