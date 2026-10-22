#!/usr/bin/env python3
"""Diagnóstico de una red importada desde OpenStreetMap.

Antes de comparar controladores hay que saber si la red es apta. Este script
responde eso con números en vez de con impresiones, y entrega una lista
priorizada de qué arreglar en `netedit`.

    python scripts/diagnose_net.py --scenario scenarios/providencia

Qué revisa y por qué importa:

  * **Semáforos con menos de dos fases verdes.** No son controlables: no hay
    nada que conmutar. Si están en el corredor, hay que darles fases a mano.
  * **Fases verdes sin movimientos asociados.** Síntoma de que `netconvert`
    adivinó mal la estructura de fases.
  * **Arcos muy cortos entre semáforos.** Con menos de ~25 m la cola de una
    intersección bloquea la anterior y la red entra en bloqueo permanente.
    Es la causa número uno de resultados absurdos en redes de OSM.
  * **Teletransportes en simulación.** SUMO teletransporta vehículos atascados;
    con `--time-to-teleport -1` no lo hace, y entonces el bloqueo se ve. Si hay
    muchos, la red o la demanda están mal.
  * **Vehículos no insertados.** Si la demanda no cabe, estás midiendo la
    capacidad de los accesos y no el desempeño del control.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tsc.sumo_env  # noqa: F401  (fija SUMO_HOME)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SHORT_EDGE_M = 25.0


def is_green(state: str) -> bool:
    return "y" not in state.lower() and "g" in state.lower()


def analyse_net(net_file: str) -> dict:
    root = ET.parse(net_file).getroot()

    tls_junctions = {j.get("id"): j for j in root.iter("junction")
                     if j.get("type") == "traffic_light"}
    logics = {t.get("id"): t for t in root.iter("tlLogic")}

    one_phase, empty_green, phase_counts = [], [], Counter()
    for tid, logic in logics.items():
        greens = [p.get("state") for p in logic.iter("phase") if is_green(p.get("state"))]
        phase_counts[len(greens)] += 1
        if len(greens) < 2:
            one_phase.append(tid)
        for st in greens:
            if "G" not in st and "g" not in st:
                empty_green.append(tid)

    junction_tls = {}
    for c in root.iter("connection"):
        via = c.get("via", "")
        tl = c.get("tl")
        if via.startswith(":") and tl:
            jid = via[1:].rsplit("_", 2)[0]
            if jid in tls_junctions:
                junction_tls.setdefault(jid, set()).add(tl)

    edges, short_between_tls = {}, []
    for e in root.iter("edge"):
        if e.get("function") == "internal":
            continue
        lanes = list(e.iter("lane"))
        if not lanes:
            continue
        length = max(float(ln.get("length", 0)) for ln in lanes)
        edges[e.get("id")] = {
            "length": length,
            "from": e.get("from"),
            "to": e.get("to"),
            "lanes": len(lanes),
            "name": e.get("name", ""),
        }
        if (length < SHORT_EDGE_M
                and e.get("from") in tls_junctions
                and e.get("to") in tls_junctions):
            f_tls = junction_tls.get(e.get("from"), set())
            t_tls = junction_tls.get(e.get("to"), set())
            # Si ambos extremos están coordinados bajo el mismo programa de semáforo
            # (joined TLS), no hay riesgo de desincronización ni bloqueo.
            if not (f_tls and t_tls and (f_tls & t_tls)):
                short_between_tls.append((e.get("id"), round(length, 1)))

    return {
        "tls_total": len(tls_junctions),
        "tls_uncontrollable": one_phase,
        "tls_empty_green": sorted(set(empty_green)),
        "phase_histogram": dict(sorted(phase_counts.items())),
        "edges_total": len(edges),
        "short_edges_between_tls": sorted(short_between_tls, key=lambda x: x[1]),
        "edges": edges,
    }


def run_health_check(net_file: str, route_file: str, end: int = 1200) -> dict:
    """Simula con las advertencias encendidas y cuenta patologías."""
    log = os.path.join(os.path.dirname(net_file), "_health.log")
    cmd = [
        "sumo", "-n", net_file, "-r", route_file,
        "--end", str(end), "--no-step-log", "true",
        "--time-to-teleport", "-1",
        "--duration-log.statistics", "true",
        "--log", log, "--message-log", log,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = (proc.stdout or "") + (proc.stderr or "")
    if os.path.exists(log):
        text += open(log, errors="ignore").read()

    out = {
        "teleports": text.count("teleporting"),
        "collisions": text.count("collision"),
        "jams": text.count("waiting too long"),
        "insertion_problems": text.count("could not be inserted"),
        "ok": proc.returncode == 0,
    }
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("Inserted:"):
            out["inserted"] = s
        elif s.startswith("Running:"):
            out["still_running"] = s
        elif s.startswith("TimeLoss:"):
            out["time_loss"] = s
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--net", default=None)
    ap.add_argument("--routes", default=None)
    ap.add_argument("--end", type=int, default=1200)
    ap.add_argument("--skip-sim", action="store_true")
    args = ap.parse_args()

    net = args.net or os.path.join(args.scenario, "net.net.xml")
    rou = args.routes or os.path.join(args.scenario, "routes.rou.xml")

    a = analyse_net(net)
    print(f"\n### Estructura — {net}")
    print(f"  arcos                          {a['edges_total']}")
    print(f"  intersecciones semaforizadas   {a['tls_total']}")
    print(f"  fases verdes por semáforo      {a['phase_histogram']}")

    problems = []
    if a["tls_uncontrollable"]:
        problems.append(
            (f"{len(a['tls_uncontrollable'])} semáforos con < 2 fases verdes "
             f"(no controlables)", a["tls_uncontrollable"][:8])
        )
    if a["tls_empty_green"]:
        problems.append(
            (f"{len(a['tls_empty_green'])} semáforos con fases verdes vacías",
             a["tls_empty_green"][:8])
        )
    if a["short_edges_between_tls"]:
        problems.append(
            (f"{len(a['short_edges_between_tls'])} arcos < {SHORT_EDGE_M:.0f} m entre "
             f"dos semáforos (riesgo de bloqueo)",
             a["short_edges_between_tls"][:8])
        )

    if problems:
        print("\n### Problemas estructurales")
        for i, (title, sample) in enumerate(problems, 1):
            print(f"  {i}. {title}")
            print(f"     ejemplos: {sample}")
    else:
        print("\n### Problemas estructurales: ninguno detectado")

    if not args.skip_sim and os.path.exists(rou):
        h = run_health_check(net, rou, args.end)
        print(f"\n### Salud en simulación ({args.end} s)")
        for k in ("inserted", "still_running", "time_loss"):
            if k in h:
                print(f"  {h[k]}")
        print(f"  teletransportes    {h['teleports']}")
        print(f"  colisiones         {h['collisions']}")
        print(f"  atascos reportados {h['jams']}")
        print(f"  no insertados      {h['insertion_problems']}")
        verdict = (
            "APTA para comparar controladores"
            if h["teleports"] == 0 and h["collisions"] == 0 and not problems
            else "NO APTA todavía — arreglar lo anterior en netedit"
        )
        print(f"\n  -> {verdict}")


if __name__ == "__main__":
    main()
