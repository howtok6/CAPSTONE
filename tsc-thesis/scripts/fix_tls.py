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


PRIORIDAD_DIR = {"s": 0, "r": 1, "R": 1, "l": 2, "L": 2, "t": 3}


def enlaces(root: ET.Element) -> dict[str, dict[int, tuple[str, str]]]:
    """tl -> {linkIndex: (pista de destino, dirección)} según las conexiones de la red."""
    out: dict[str, dict[int, tuple[str, str]]] = {}
    for c in root.iter("connection"):
        if c.get("tl") is not None and c.get("linkIndex") is not None:
            out.setdefault(c.get("tl"), {})[int(c.get("linkIndex"))] = (
                f"{c.get('to')}_{c.get('toLane')}", c.get("dir", "s"))
    return out


def sin_verdes_dobles(state: str, links: dict[int, tuple[str, str]]) -> str:
    """Si dos o más enlaces con `G` llegan a la misma pista, deja `G` solo al de mayor prioridad
    (pasante, luego derecha, luego izquierda) y los demás en `g`, que ceden el paso.

    El viraje protegido pone en `G` todos los antiguos permisivos; cuando dos de ellos
    desembocan en la misma pista SUMO avisa «Unsafe green phase … targeted by 2 'G'-links»
    (pasaba en 2 semáforos de Las Condes + Providencia).
    """
    s = list(state)
    por_destino: dict[str, list[int]] = {}
    for i, c in enumerate(s):
        if c == "G" and i in links:
            por_destino.setdefault(links[i][0], []).append(i)
    for idx in por_destino.values():
        if len(idx) > 1:
            idx.sort(key=lambda i: (PRIORIDAD_DIR.get(links[i][1], 9), i))
            for i in idx[1:]:
                s[i] = "g"
    return "".join(s)


def programas_corregidos(net_file: str) -> list[ET.Element]:
    root = ET.parse(net_file).getroot()
    por_tl = enlaces(root)
    nuevos = []
    for logic in root.iter("tlLogic"):
        verdes = [p.get("state") for p in logic.iter("phase") if es_verde(p.get("state"))]
        if len(verdes) != 1 or "g" not in verdes[0]:
            continue
        base = verdes[0]
        links = por_tl.get(logic.get("id"), {})
        pasante = sin_verdes_dobles("".join("r" if c == "g" else c for c in base), links)
        viraje = sin_verdes_dobles("".join("G" if c == "g" else "r" for c in base), links)
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
