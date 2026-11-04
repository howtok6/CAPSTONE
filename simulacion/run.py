#!/usr/bin/env python3
"""Levanta el servicio de simulación (entorno de pruebas del backend).

Uso (desde simulacion/):
    python run.py [--velocidad 1] [--puerto 8000]

Lo consume el backend Go (VIA_SIMULACION_URL), no la app.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

AQUI = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, AQUI)
TSC = os.environ.get("TSC_RAIZ", os.path.join(AQUI, "..", "tsc-thesis"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", default=os.path.join(TSC, "scenarios", "eje_comunal"))
    ap.add_argument("--velocidad", type=float, default=1.0, help="1 = tiempo real; 0 = sin pausa")
    ap.add_argument("--calentamiento", type=int, default=300, help="segundos simulados antes de abrir")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para exponerlo en la red (p. ej. en Docker)")
    ap.add_argument("--puerto", type=int, default=8000)
    args = ap.parse_args()

    os.environ["TSC_RAIZ"] = os.path.abspath(TSC)
    os.environ["TSC_ESCENARIO"] = args.escenario
    os.environ["TSC_VELOCIDAD"] = str(args.velocidad)
    os.environ["TSC_CALENTAMIENTO"] = str(args.calentamiento)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    import uvicorn

    uvicorn.run("via_sim.main:app", host=args.host, port=args.puerto, log_level="info")


if __name__ == "__main__":
    main()
