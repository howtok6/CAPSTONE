#!/usr/bin/env python3
"""Tabla resumen de la tanda EOD: demora media por controlador y perfil, con IC 95 %.

    python scripts/resumen_tanda_eod.py

Lee results/eje_comunal_eod_<perfil>_baselines.json. La métrica es la demora media por vehículo
incluyendo a los que no terminaron (`delay_all_mean`), la misma del informe comparativo.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PERFILES = ["eod_valle", "eod_punta_tarde", "eod_punta_manana", "eod_sobresaturado"]
CLASICOS = ["fixed", "webster", "greedy", "maxpressure"]
T95 = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 7: 2.45, 8: 2.36, 9: 2.31, 10: 2.26}


def ic95(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    return T95.get(n, 1.96) * statistics.stdev(xs) / math.sqrt(n)


def main() -> None:
    metrica = sys.argv[1] if len(sys.argv) > 1 else "delay_all_mean"
    for perfil in PERFILES:
        ruta = os.path.join("results", f"eje_comunal_{perfil}_baselines.json")
        if not os.path.exists(ruta):
            print(f"\n## {perfil}: sin resultados")
            continue
        filas = json.load(open(ruta))
        por = {}
        for r in filas:
            if metrica in r and r[metrica] is not None:
                por.setdefault(r["controller"], []).append(r[metrica])
        medias = {c: statistics.fmean(v) for c, v in por.items()}
        clasicos = {c: m for c, m in medias.items() if c in CLASICOS}
        mejor = min(clasicos, key=clasicos.get) if clasicos else None
        print(f"\n## {perfil}  ({metrica}; mejor clásico: {mejor})")
        print("| Controlador | n | Media (s) | IC 95 % | vs. mejor clásico | Terminan | Sin entrar al final |")
        print("|---|---|---|---|---|---|---|")
        for c in sorted(medias, key=medias.get):
            xs = por[c]
            rel = f"{100 * (medias[c] / medias[mejor] - 1):+.1f} %" if mejor and c != mejor else "—"
            fin = statistics.fmean(r.get("vehicles_finished", 0) for r in filas if r["controller"] == c)
            pend = statistics.fmean(r.get("vehicles_pending_end", 0) for r in filas if r["controller"] == c)
            print(f"| {c} | {len(xs)} | {medias[c]:.1f} | ±{ic95(xs):.1f} | {rel} | {fin:,.0f} | {pend:,.0f} |")


if __name__ == "__main__":
    main()
