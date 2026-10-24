#!/usr/bin/env python3
"""Separa los semáforos de una red entre los del eje y los de transversales.

Un semáforo es «del eje» si alguno de los arcos que controla pertenece a la
Alameda, Av. Providencia o Av. Apoquindo. Escribe <escenario>/tls_eje.json con
las dos listas: la del eje es la que controla el agente (decisión pendiente de
validar, docs/07); las transversales quedan en tiempo fijo.

Ojo: netconvert guarda el nombre de la Alameda como «O&apos;Higgins» (apóstrofo
escapado dos veces); el patrón lo tolera.

Uso:
    python scripts/list_axis_tls.py --scenario scenarios/eje_comunal
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter

EJE = re.compile(r"^Avenida (Libertador Bernardo O.*Higgins|Providencia|Apoquindo)$")


def clasificar(net_file: str) -> dict:
    root = ET.parse(net_file).getroot()
    names = {e.get("id"): e.get("name", "") for e in root.iter("edge")
             if e.get("function") != "internal"}
    streets: dict = {}
    for c in root.iter("connection"):
        if c.get("tl") and c.get("from") in names:
            streets.setdefault(c.get("tl"), set()).add(names[c.get("from")])
    eje = sorted(t for t, s in streets.items() if any(EJE.match(n) for n in s))
    por_avenida = Counter()
    for t in eje:
        for n in streets[t]:
            if EJE.match(n):
                por_avenida["Alameda" if "Higgins" in n else n.replace("Avenida ", "")] += 1
    return {"eje": eje, "transversales": sorted(t for t in streets if t not in eje),
            "por_avenida": dict(por_avenida)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    args = ap.parse_args()
    r = clasificar(os.path.join(args.scenario, "net.net.xml"))
    with open(os.path.join(args.scenario, "tls_eje.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=1)
    print(f"{len(r['eje']) + len(r['transversales'])} programas de semáforo: "
          f"{len(r['eje'])} sobre el eje {r['por_avenida']}, {len(r['transversales'])} en transversales")


if __name__ == "__main__":
    main()
