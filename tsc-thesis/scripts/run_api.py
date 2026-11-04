#!/usr/bin/env python3
"""Levanta la API de simulación en vivo para la app móvil «Vía».

Uso (desde tsc-thesis/):
    python scripts/run_api.py [--velocidad 1] [--puerto 8000]

Para probar en un celular Android conectado por USB:
    adb reverse tcp:8000 tcp:8000
y la app usa http://127.0.0.1:8000. Por Wi-Fi, la app debe apuntar a la IP del PC.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", default=os.path.join(RAIZ, "scenarios", "eje_comunal"))
    ap.add_argument("--velocidad", type=float, default=1.0, help="1 = tiempo real; 0 = sin pausa")
    ap.add_argument("--calentamiento", type=int, default=300, help="segundos simulados antes de abrir")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--puerto", type=int, default=8000)
    args = ap.parse_args()

    os.environ["TSC_ESCENARIO"] = args.escenario
    os.environ["TSC_VELOCIDAD"] = str(args.velocidad)
    os.environ["TSC_CALENTAMIENTO"] = str(args.calentamiento)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    import uvicorn

    uvicorn.run("api.main:app", host=args.host, port=args.puerto, log_level="info")


if __name__ == "__main__":
    main()
