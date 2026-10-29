#!/usr/bin/env python3
"""Calcula el plan de Webster para un escenario y lo guarda como JSON.

    python scripts/build_webster.py --scenario scenarios/grid4x4
    python scripts/build_webster.py --scenario scenarios/eje_comunal --profile punta_tarde

Tres pasos:
  1. Corrida de calibración con tiempo fijo: flujo por fase de cada semáforo.
  2. Webster por semáforo: ciclo óptimo y reparto de verdes.
  3. Si el escenario tiene `tls_eje.json` (eje comunal), coordinación del eje:
     - ciclo común por avenida (Alameda, Providencia, Apoquindo): el mayor del
       grupo, para que el cruce más cargado no se sature;
     - desfases para una onda verde en el sentido de la punta: hacia el centro
       (poniente) en punta mañana, hacia el oriente en punta tarde y
       sobresaturado; sin onda en valle.
     Los semáforos de transversales quedan con su Webster aislado.

Decisión registrada en docs/decisiones/08 (tiempos estimados, anclados después en la
medición de terreno). Con `--profile` mide con las rutas del perfil y guarda
`webster_plan_<perfil>.json`, que es el que usa run_baselines con ese perfil.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tsc.controllers.webster import coordinate_cycles, progression_offsets, webster_plan  # noqa: E402
from tsc.runner import measure_phase_flows  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Sentido de la onda verde según el perfil (punta mañana: hacia el centro)
SENTIDO_POR_PERFIL = {"punta_manana": "poniente", "punta_tarde": "oriente",
                      "sobresaturado": "oriente", "valle": "ninguno"}


def avenida(nombre: str) -> str | None:
    if "Higgins" in nombre and "Libertador" in nombre:
        return "Alameda"
    if nombre == "Avenida Providencia":
        return "Providencia"
    if nombre == "Avenida Apoquindo":
        return "Apoquindo"
    return None


def geometria_eje(net_file: str, tls_eje: list) -> tuple[dict, dict]:
    """Avenida de cada semáforo del eje y su posición (m) a lo largo de ella.

    La avenida es la que aporta más conexiones controladas (Baquedano toca dos).
    La posición se mide encadenando las distancias entre semáforos ordenados de
    poniente a oriente (coordenada x de la red, en metros).
    """
    root = ET.parse(net_file).getroot()
    edges = {e.get("id"): e for e in root.iter("edge") if e.get("function") != "internal"}
    nodes = {j.get("id"): (float(j.get("x")), float(j.get("y"))) for j in root.iter("junction")}
    por_tls = defaultdict(Counter)
    coords = defaultdict(list)
    for c in root.iter("connection"):
        tl, fr = c.get("tl"), c.get("from")
        if tl in tls_eje and fr in edges:
            av = avenida(edges[fr].get("name", ""))
            if av:
                por_tls[tl][av] += 1
            to = nodes.get(edges[fr].get("to"))
            if to:
                coords[tl].append(to)
    grupo = {t: c.most_common(1)[0][0] for t, c in por_tls.items()}
    centro = {t: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
              for t, v in coords.items() if v}
    posicion = {}
    for g in set(grupo.values()):
        miembros = sorted((t for t in grupo if grupo[t] == g and t in centro),
                          key=lambda t: centro[t][0])
        acumulado = 0.0
        for i, t in enumerate(miembros):
            if i:
                (x0, y0), (x1, y1) = centro[miembros[i - 1]], centro[t]
                acumulado += math.hypot(x1 - x0, y1 - y0)
            posicion[t] = acumulado
    return grupo, posicion


def commit_actual() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconocido"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", default=None, help="valle, punta_manana, punta_tarde, sobresaturado")
    ap.add_argument("--net", default=None)
    ap.add_argument("--routes", default=None)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--coordinate", default="auto", choices=["auto", "avenida", "ninguna"],
                    help="ciclo común por avenida del eje (auto: si existe tls_eje.json)")
    ap.add_argument("--offsets", default="auto", choices=["auto", "oriente", "poniente", "ninguno"],
                    help="sentido de la onda verde (auto: según el perfil)")
    ap.add_argument("--speed-kmh", type=float, default=40.0,
                    help="velocidad de progresión de la onda verde")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    net = args.net or os.path.join(args.scenario, "net.net.xml")
    if args.routes:
        rou = args.routes
    elif args.profile:
        rou = os.path.join(args.scenario, "demand", f"routes_{args.profile}.rou.xml")
    else:
        rou = os.path.join(args.scenario, "routes.rou.xml")
    if not os.path.exists(rou):
        sys.exit(f"Error: no existe el archivo de rutas {rou}")
    sufijo = f"_{args.profile}" if args.profile else ""
    out = args.out or os.path.join(args.scenario, f"webster_plan{sufijo}.json")

    print(f"Corrida de calibración (tiempo fijo, {args.end} s) con {rou} …")
    flows = measure_phase_flows(net, rou, seed=args.seed, end=args.end)

    plans = {}
    for tls_id, phase_flows in flows.items():
        pf = {int(k): v for k, v in phase_flows.items()}
        plan = webster_plan(pf)
        plans[tls_id] = {
            "cycle": round(plan["cycle"], 1),
            "Y": round(plan["Y"], 3),
            "greens": {str(k): round(v, 1) for k, v in plan["greens"].items()},
            "measured_flows": {str(k): round(v, 1) for k, v in pf.items()},
        }

    tls_json = os.path.join(args.scenario, "tls_eje.json")
    coordinar = args.coordinate == "avenida" or (args.coordinate == "auto" and os.path.exists(tls_json))
    sentido = args.offsets
    if sentido == "auto":
        sentido = SENTIDO_POR_PERFIL.get(args.profile or "", "ninguno")
    resumen_grupos = {}
    if coordinar:
        with open(tls_json, encoding="utf-8") as f:
            eje = json.load(f)["eje"]
        grupo, posicion = geometria_eje(net, eje)
        coordinate_cycles(plans, grupo)
        for g in sorted(set(grupo.values())):
            miembros = {t: posicion[t] for t in grupo if grupo[t] == g and t in plans and t in posicion}
            if not miembros:
                continue
            ciclo = plans[next(iter(miembros))]["cycle"]
            offs = progression_offsets(miembros, ciclo, args.speed_kmh / 3.6, sentido)
            for t, o in offs.items():
                plans[t]["offset"] = o
                plans[t]["position_m"] = round(miembros[t], 1)
            resumen_grupos[g] = {"semaforos": len(miembros), "ciclo": ciclo,
                                 "largo_m": round(max(miembros.values()), 0)}

    plans["_meta"] = {
        "rutas": rou, "perfil": args.profile, "coordinacion": "avenida" if coordinar else "ninguna",
        "onda_verde": sentido, "velocidad_kmh": args.speed_kmh, "semilla": args.seed,
        "duracion_calibracion_s": args.end, "commit_git": commit_actual(),
        "fecha": dt.datetime.now().isoformat(timespec="seconds"), "grupos": resumen_grupos,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(plans, fh, indent=2, ensure_ascii=False)

    cycles = [p["cycle"] for k, p in plans.items() if not k.startswith("_")]
    print(f"OK  {len(cycles)} semáforos -> {out}")
    print(f"    ciclo: min={min(cycles):.0f}s  medio={sum(cycles) / len(cycles):.0f}s  max={max(cycles):.0f}s")
    for g, r in resumen_grupos.items():
        print(f"    {g:12s} {r['semaforos']:3d} semáforos, ciclo común {r['ciclo']:.0f} s, "
              f"{r['largo_m'] / 1000:.1f} km, onda verde: {sentido}")


if __name__ == "__main__":
    main()
