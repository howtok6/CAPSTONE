#!/usr/bin/env python3
"""Subconjunto de los semáforos controlados (tls_eje.json) que están en una comuna.

    python scripts/listar_tls_comuna.py --scenario scenarios/las_condes_providencia --comuna PROVIDENCIA

Escribe <escenario>/tls_<comuna>.json con la misma forma que tls_eje.json ({"eje": [...], "_meta"}),
de modo que train_rl.py / eval_rl.py --control providencia controlen solo esos. La comuna de
cada semáforo es la de sus cruces UOCT (tls_uoct.json + uoct_match.json); si un semáforo agrupa
cruces de dos comunas, se asigna a la mayoritaria.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--comuna", default="PROVIDENCIA")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    leer = lambda n: json.load(open(os.path.join(a.scenario, n), encoding="utf-8"))  # noqa: E731
    eje = leer("tls_eje.json")["eje"]
    tls_uoct = leer("tls_uoct.json")
    comuna_de = {c["codigo"]: c.get("comuna_geo") or c["comuna"] for c in leer("uoct_match.json")}
    elegidos, por_comuna = [], Counter()
    for t in eje:
        votos = Counter(comuna_de.get(cod, "?") for cod in tls_uoct.get(t, []))
        comuna = votos.most_common(1)[0][0] if votos else "?"
        por_comuna[comuna] += 1
        if comuna.upper() == a.comuna.upper():
            elegidos.append(t)
    nombre = a.comuna.lower().replace(" ", "_")
    salida = os.path.join(a.scenario, f"tls_{nombre}.json")
    json.dump({"eje": elegidos, "_meta": {"criterio": f"semáforos de tls_eje.json con cruces UOCT en {a.comuna}",
                                          "controlados": len(elegidos), "por_comuna": dict(por_comuna)}},
              open(salida, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(elegidos)} de {len(eje)} semáforos controlados en {a.comuna} -> {salida}  {dict(por_comuna)}")


if __name__ == "__main__":
    main()
