#!/usr/bin/env python3
"""Análisis estadístico de las corridas.

Reporta media, desviación, intervalo de confianza al 95 %, mejora porcentual
respecto de la línea base y el test de Wilcoxon pareado. El valor p va siempre
acompañado del tamaño de efecto: una diferencia significativa de 0,3 s no le
sirve a nadie.

    python scripts/compare.py --results results/grid4x4_baselines.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from scipy import stats
    HAVE_SCIPY = True
except ImportError:  # pragma: no cover
    HAVE_SCIPY = False

METRICS = [
    ("delay_all_mean", "Demora media incl. no terminados (s)", True),
    ("time_loss_mean", "Demora media (s)", True),
    ("travel_time_mean", "Tiempo de viaje (s)", True),
    ("waiting_time_mean", "Espera media (s)", True),
    ("waiting_time_p95", "Espera p95 (s)", True),
    ("queue_mean", "Cola media (veh)", True),
    ("throughput", "Throughput (veh/h)", False),
    ("vehicles_pending_end", "Sin poder entrar al cierre (veh)", True),
]


def ci95(xs):
    if len(xs) < 2:
        return 0.0
    return 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--baseline", default="fixed")
    args = ap.parse_args()

    rows = json.load(open(args.results))
    by_ctrl = defaultdict(list)
    for r in rows:
        by_ctrl[r["controller"]].append(r)
    for name in by_ctrl:
        by_ctrl[name].sort(key=lambda r: r["seed"])

    base = args.baseline if args.baseline in by_ctrl else next(iter(by_ctrl))
    others = [c for c in by_ctrl if c != base]

    for key, label, lower_is_better in METRICS:
        if key not in by_ctrl[base][0]:
            continue
        print(f"\n=== {label} ===")
        base_vals = [r[key] for r in by_ctrl[base]]
        print(
            f"  {base:12s} (base)  {statistics.fmean(base_vals):9.2f} "
            f"± {ci95(base_vals):5.2f}   n={len(base_vals)}"
        )
        for ctrl in others:
            vals = [r[key] for r in by_ctrl[ctrl]]
            mean = statistics.fmean(vals)
            base_mean = statistics.fmean(base_vals)
            delta = (mean - base_mean) / base_mean * 100 if base_mean else 0.0
            better = (delta < 0) if lower_is_better else (delta > 0)
            mark = "mejor " if better else "peor  "
            line = (
                f"  {ctrl:12s}         {mean:9.2f} ± {ci95(vals):5.2f}   "
                f"{delta:+6.1f}%  {mark}"
            )
            if HAVE_SCIPY and len(vals) == len(base_vals) and len(vals) >= 6:
                try:
                    _, p = stats.wilcoxon(vals, base_vals)
                    line += f"  p={p:.4f}"
                except ValueError:
                    line += "  p=n/a"
            print(line)

    if not HAVE_SCIPY:
        print("\n[aviso] scipy no está instalado: no se reportan valores p.")


if __name__ == "__main__":
    main()
