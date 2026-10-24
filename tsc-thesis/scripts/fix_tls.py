#!/usr/bin/env python3
"""Corrige semáforos con una sola fase verde y virajes permisivos.

`netconvert` deja algunos cruces con un único verde donde los virajes son
permisivos (`g`): todos los movimientos comparten la fase y no hay nada que
controlar. Es el caso de Providencia × Condell, corregido a mano el 14-oct en la
red anterior. Este script aplica la misma corrección de forma reproducible:

    fase 1: pasante  — los `g` pasan a rojo, el resto queda en verde
    fase 2: viraje protegido — solo los antiguos `g` en verde

con amarillos de 3 s entre ambas. Los tiempos son iniciales: Webster los
recalcula después. Los cruces peatonales (un verde, una sola calle, sin `g`)
no se tocan: quedan en tiempo fijo y fuera del control del agente.

Uso:
    python scripts/fix_tls.py --scenario scenarios/eje_comunal
Escribe <escenario>/tls_fixes.add.xml y reescribe net.net.xml con netconvert.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import xml.etree.ElementTree as ET

AMARILLO, PASANTE, VIRAJE = 3, 45, 15


def es_verde(state: str) -> bool:
    s = state.lower()
    return "y" not in s and "g" in s


def amarillo_entre(desde: str, hacia: str) -> str:
    """Amarillo para los enlaces que estaban en verde y pasan a rojo."""
    return "".join("y" if a in "Gg" and b == "r" else a for a, b in zip(desde, hacia))


def programas_corregidos(net_file: str) -> list[ET.Element]:
    root = ET.parse(net_file).getroot()
    nuevos = []
    for logic in root.iter("tlLogic"):
        verdes = [p.get("state") for p in logic.iter("phase") if es_verde(p.get("state"))]
        if len(verdes) != 1 or "g" not in verdes[0]:
            continue
        base = verdes[0]
        pasante = "".join("r" if c == "g" else c for c in base)
        viraje = "".join("G" if c == "g" else "r" for c in base)
        fases = [(PASANTE, pasante), (AMARILLO, amarillo_entre(pasante, viraje)),
                 (VIRAJE, viraje), (AMARILLO, amarillo_entre(viraje, pasante))]
        el = ET.Element("tlLogic", id=logic.get("id"), type="static",
                        programID=logic.get("programID", "0"), offset="0")
        for dur, st in fases:
            ET.SubElement(el, "phase", duration=str(dur), state=st)
        nuevos.append(el)
    return nuevos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    args = ap.parse_args()
    net = os.path.join(args.scenario, "net.net.xml")
    nuevos = programas_corregidos(net)
    if not nuevos:
        print("Ningún semáforo que corregir.")
        return
    add = ET.Element("additional")
    add.extend(nuevos)
    ET.indent(add)
    destino = os.path.join(args.scenario, "tls_fixes.add.xml")
    ET.ElementTree(add).write(destino, encoding="utf-8", xml_declaration=True)
    subprocess.run(["netconvert", "--sumo-net-file", net, "--tllogic-files", destino,
                    "-o", net, "--output.street-names", "true"], check=True)
    print(f"Corregidos {len(nuevos)} semáforos: {[e.get('id') for e in nuevos]} -> {destino}")


if __name__ == "__main__":
    main()
