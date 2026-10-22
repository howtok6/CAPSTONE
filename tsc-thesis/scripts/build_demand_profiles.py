#!/usr/bin/env python3
"""Generación y calibración formal de los 4 perfiles de demanda para la red real.

Perfiles implementados:
  1. valle: baja demanda (período ~2.0 s, ~1800 veh/h), flujo libre y equilibrado.
  2. punta_manana: alta demanda direccional Poniente -> Oriente (período ~0.85 s, ~4200 veh/h).
  3. punta_tarde: alta demanda direccional Oriente -> Poniente (período ~0.72 s, ~5000 veh/h),
     calibrada para reflejar la congestión severa registrada por Waze (11-13 km/h).
  4. sobresaturado: demanda al 130 % de la punta tarde (período ~0.55 s, ~6500 veh/h) para
     estresar la red y evaluar robustez de los algoritmos ante colapso por colas.

Uso:
    python scripts/build_demand_profiles.py --scenario scenarios/alameda_providencia --end 3600
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tsc.sumo_env  # noqa: F401 (fija SUMO_HOME)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOOLS = os.path.join(os.environ["SUMO_HOME"], "tools")


def extract_network_geometry(net_file: str):
    """Extrae las coordenadas de las calles para identificar Poniente y Oriente."""
    root = ET.parse(net_file).getroot()
    edges = {}
    all_x = []

    for e in root.iter("edge"):
        if e.get("function") == "internal":
            continue
        lanes = list(e.iter("lane"))
        if not lanes:
            continue
        # Comprobar si admite vehículos de pasajeros
        disallow = lanes[0].get("disallow", "")
        allow = lanes[0].get("allow", "")
        if "passenger" in disallow and "passenger" not in allow:
            continue

        shape = lanes[0].get("shape", "")
        coords = [tuple(map(float, pt.split(","))) for pt in shape.split()]
        xs = [pt[0] for pt in coords]
        min_x, max_x = min(xs), max(xs)
        all_x.extend(xs)

        edges[e.get("id")] = {
            "name": e.get("name", ""),
            "min_x": min_x,
            "max_x": max_x,
            "mid_x": (min_x + max_x) / 2.0,
            "from": e.get("from"),
            "to": e.get("to"),
        }

    net_min_x = min(all_x) if all_x else 0.0
    net_max_x = max(all_x) if all_x else 1000.0
    mid_xs = sorted(ed["mid_x"] for ed in edges.values())
    if mid_xs:
        poniente_threshold = mid_xs[int(len(mid_xs) * 0.30)]
        oriente_threshold = mid_xs[int(len(mid_xs) * 0.70)]
    else:
        poniente_threshold = 0.0
        oriente_threshold = 1000.0

    poniente_edges = [eid for eid, ed in edges.items() if ed["mid_x"] <= poniente_threshold]
    oriente_edges = [eid for eid, ed in edges.items() if ed["mid_x"] >= oriente_threshold]
    centro_edges = [eid for eid, ed in edges.items() if poniente_threshold < ed["mid_x"] < oriente_threshold]

    return {
        "edges": edges,
        "net_min_x": net_min_x,
        "net_max_x": net_max_x,
        "poniente_edges": poniente_edges,
        "oriente_edges": oriente_edges,
        "centro_edges": centro_edges,
    }


def write_weight_file(path: str, weights: dict[str, float], interval_id: str = "weights"):
    """Escribe un archivo de pesos XML en formato edgedata de SUMO."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    total = sum(weights.values())
    with open(path, "w", encoding="utf-8") as f:
        f.write("<edgedata>\n")
        f.write(f'    <interval id="{interval_id}" begin="0" end="86400" totalWeight="{total:.2f}">\n')
        for eid, w in weights.items():
            f.write(f'        <edge id="{eid}" value="{w:.2f}"/>\n')
        f.write("    </interval>\n")
        f.write("</edgedata>\n")


def generate_profile(
    scenario_dir: str,
    net_file: str,
    profile_name: str,
    period: float,
    geom: dict,
    end: int = 3600,
    seed: int = 42,
    direction: str = "balanced",  # "balanced", "west_to_east", "east_to_west"
):
    """Genera trips y routes para un perfil determinado."""
    demand_dir = os.path.join(scenario_dir, "demand")
    os.makedirs(demand_dir, exist_ok=True)

    trips_file = os.path.join(demand_dir, f"trips_{profile_name}.trips.xml")
    routes_file = os.path.join(demand_dir, f"routes_{profile_name}.rou.xml")
    weights_prefix = os.path.join(demand_dir, f"_weights_{profile_name}")

    all_edges = geom["edges"]
    src_weights = {}
    dst_weights = {}

    for eid in all_edges:
        if direction == "balanced":
            src_weights[eid] = 10.0
            dst_weights[eid] = 10.0
        elif direction == "west_to_east":
            # Punta Mañana: orígenes principalmente en Poniente, destinos en Oriente
            if eid in geom["poniente_edges"]:
                src_weights[eid] = 80.0
                dst_weights[eid] = 5.0
            elif eid in geom["oriente_edges"]:
                src_weights[eid] = 5.0
                dst_weights[eid] = 80.0
            else:
                src_weights[eid] = 15.0
                dst_weights[eid] = 15.0
        elif direction == "east_to_west":
            # Punta Tarde / Sobresaturado: orígenes en Oriente, destinos en Poniente
            if eid in geom["oriente_edges"]:
                src_weights[eid] = 80.0
                dst_weights[eid] = 5.0
            elif eid in geom["poniente_edges"]:
                src_weights[eid] = 5.0
                dst_weights[eid] = 80.0
            else:
                src_weights[eid] = 15.0
                dst_weights[eid] = 15.0

    write_weight_file(weights_prefix + ".src.xml", src_weights)
    write_weight_file(weights_prefix + ".dst.xml", dst_weights)

    fringe_factor = "10" if direction == "balanced" else "25"

    cmd = [
        sys.executable, os.path.join(TOOLS, "randomTrips.py"),
        "-n", net_file,
        "-o", trips_file,
        "-r", routes_file,
        "--begin", "0",
        "--end", str(end),
        "--period", str(period),
        "--seed", str(seed),
        "--fringe-factor", fringe_factor,
        "--weights-prefix", weights_prefix,
        "--validate",
        "--remove-loops",
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Limpiar temporales de pesos
    for suffix in [".src.xml", ".dst.xml"]:
        wpath = weights_prefix + suffix
        if os.path.exists(wpath):
            try:
                os.remove(wpath)
            except OSError:
                pass

    return routes_file


def evaluate_health(net_file: str, route_file: str, end: int = 1200):
    """Ejecuta una corrida corta de prueba de salud para evaluar teletransportes y demora."""
    cmd = [
        "sumo", "-n", net_file, "-r", route_file,
        "--end", str(end),
        "--no-step-log", "true",
        "--time-to-teleport", "-1",
        "--duration-log.statistics", "true",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    text = (proc.stdout or "") + (proc.stderr or "")

    inserted = 0
    running = 0
    time_loss = 0.0
    speed = 0.0

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Inserted:"):
            # Inserted: 1234 (Loaded: 1240)
            parts = line.split()
            inserted = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        elif line.startswith("Running:"):
            parts = line.split()
            running = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        elif line.startswith("TimeLoss:"):
            try:
                time_loss = float(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif line.startswith("Speed:"):
            try:
                # Speed en m/s -> convertir a km/h
                speed = float(line.split()[1]) * 3.6
            except (IndexError, ValueError):
                pass

    teleports = text.count("teleporting")
    collisions = text.count("collision")

    return {
        "inserted": inserted,
        "running": running,
        "finished": max(0, inserted - running),
        "time_loss": time_loss,
        "speed_kmh": speed,
        "teleports": teleports,
        "collisions": collisions,
    }


def main():
    ap = argparse.ArgumentParser(description="Genera los 4 perfiles de demanda para SUMO.")
    ap.add_argument("--scenario", default="scenarios/alameda_providencia", help="Ruta al escenario SUMO")
    ap.add_argument("--net", default=None, help="Archivo net.net.xml (opcional)")
    ap.add_argument("--end", type=int, default=3600, help="Duración del episodio en segundos")
    ap.add_argument("--seed", type=int, default=42, help="Semilla aleatoria")
    ap.add_argument("--check-end", type=int, default=1200, help="Segundos de prueba de salud")
    args = ap.parse_args()

    net = args.net or os.path.join(args.scenario, "net.net.xml")
    if not os.path.exists(net):
        sys.exit(f"Error: no existe la red {net}")

    print(f"Analizando geometría del corredor en {net}...")
    geom = extract_network_geometry(net)
    print(f"  Calles identificadas: {len(geom['edges'])}")
    print(f"  Calles sector Poniente: {len(geom['poniente_edges'])}")
    print(f"  Calles sector Oriente:  {len(geom['oriente_edges'])}")

    profiles = [
        {
            "name": "valle",
            "desc": "Valle (Baja demanda, flujo libre)",
            "period": 2.0,
            "direction": "balanced",
        },
        {
            "name": "punta_manana",
            "desc": "Punta Mañana (Direccional Poniente -> Oriente)",
            "period": 0.85,
            "direction": "west_to_east",
        },
        {
            "name": "punta_tarde",
            "desc": "Punta Tarde (Direccional Oriente -> Poniente)",
            "period": 0.72,
            "direction": "east_to_west",
        },
        {
            "name": "sobresaturado",
            "desc": "Sobresaturado (130 % Punta Tarde)",
            "period": 0.55,
            "direction": "east_to_west",
        },
    ]

    print("\nGenerando y validando los 4 perfiles de demanda...")
    results = []

    for p in profiles:
        print(f"\n---> Construyendo perfil: {p['name']} ({p['desc']})...")
        rou_file = generate_profile(
            scenario_dir=args.scenario,
            net_file=net,
            profile_name=p["name"],
            period=p["period"],
            geom=geom,
            end=args.end,
            seed=args.seed,
            direction=p["direction"],
        )
        print(f"     Archivo generado: {rou_file}")
        print(f"     Validando salud en simulación ({args.check_end} s)...")
        health = evaluate_health(net, rou_file, end=args.check_end)
        results.append((p, rou_file, health))

    print("\n" + "=" * 95)
    print(f"{'Perfil':<16} | {'Período':<8} | {'Insertados':<10} | {'Velocidad':<11} | {'TimeLoss':<10} | {'Teleports':<9} | {'Estado'}")
    print("=" * 95)

    for p, rou_file, h in results:
        status = "APTA / LIMPIA" if h["teleports"] == 0 and h["collisions"] == 0 else "CON ADVERTENCIAS"
        vel_str = f"{h['speed_kmh']:.1f} km/h"
        tl_str = f"{h['time_loss']:.1f} s"
        print(f"{p['name']:<16} | {p['period']:<8.2f} | {h['inserted']:<10d} | {vel_str:<11} | {tl_str:<10} | {h['teleports']:<9d} | {status}")

    print("=" * 95)
    print("\nOK: Todos los perfiles quedaron disponibles en:", os.path.join(args.scenario, "demand"))


if __name__ == "__main__":
    main()
