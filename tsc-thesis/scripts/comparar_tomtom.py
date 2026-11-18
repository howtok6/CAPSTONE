"""Compara velocidades simuladas (SUMO, edgeData) con una captura TomTom en los mismos arcos.

Uso:
    python scripts/comparar_tomtom.py --scenario scenarios/las_condes_providencia \
        --captura data/tomtom/las_condes_providencia/flujo_20261118_1857.json \
        --rutas scenarios/las_condes_providencia/demand/eval/routes_eod_punta_tarde_s00.rou.xml

* Simula la hora con los planes de la red (tiempo fijo) y mide en [--desde, --fin] la velocidad media
  de cada arco muestreado (edgeData, ponderada por tiempo: incluye a los detenidos en cola, igual que
  la velocidad de segmento de TomTom).
* Compara: velocidad actual (TomTom) vs simulada, índice de congestión (v/v_libre) y velocidad a flujo
  libre de TomTom vs límite del arco en la red (calibración de velocidades máximas).
* Métricas por estrato y global: media, sesgo, MAE, RMSE, correlación de Pearson y de Spearman,
  % de arcos con índice simulado < 0,25 (atasco) frente a TomTom. Arcos sin vehículos en la ventana
  quedan como «sin_muestra» y no entran en las métricas.
* Salida: logs/validacion/tomtom_<captura>_<perfil>.json y figura .png de dispersión.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import sumolib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLORES = {"troncal": "#2a78d6", "secundaria": "#eb6834", "terciaria": "#1baf7a"}


def rangos(v: list[float]) -> list[float]:
    orden = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and v[orden[j + 1]] == v[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            r[orden[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if not sa or not sb:
        return None
    return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb), 3)


def metricas(obs: list[float], sim: list[float]) -> dict:
    n = len(obs)
    if not n:
        return {"n": 0}
    err = [s - o for o, s in zip(obs, sim)]
    return {"n": n, "media_tomtom": round(sum(obs) / n, 2), "media_sim": round(sum(sim) / n, 2),
            "sesgo": round(sum(err) / n, 2), "mae": round(sum(map(abs, err)) / n, 2),
            "rmse": round(math.sqrt(sum(e * e for e in err) / n), 2),
            "pearson": pearson(obs, sim), "spearman": pearson(rangos(obs), rangos(sim))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--captura", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--net", default=None)
    ap.add_argument("--desde", type=int, default=900, help="inicio de la ventana medida (s), tras el calentamiento")
    ap.add_argument("--fin", type=int, default=3600)
    ap.add_argument("--teleport", type=int, default=-1, help="--time-to-teleport de SUMO (-1 = como el arnés)")
    ap.add_argument("--sumo-extra", default="")
    ap.add_argument("--speed-factor", type=float, default=None,
                    help="media del speedFactor del tipo por defecto (SUMO usa 1,0); prueba de velocidad deseada")
    ap.add_argument("--etiqueta", default="")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cap = json.load(open(a.captura, encoding="utf-8"))
    puntos = [p for p in cap["puntos"] if "error" not in p and p.get("v_libre_kmh")]
    net_file = a.net or os.path.join(a.scenario, "net.net.xml")
    net = sumolib.net.readNet(net_file)

    tmp = tempfile.mkdtemp()
    add = os.path.join(tmp, "edgedata.add.xml")
    salida = os.path.join(tmp, "edgedata.xml")
    with open(add, "w", encoding="utf-8") as f:
        f.write("<additional>\n")
        if a.speed_factor:
            f.write(f'  <vType id="DEFAULT_VEHTYPE" speedFactor="normc({a.speed_factor},0.1,0.2,2)"/>\n')
        f.write(f'  <edgeData id="v" file="{salida}" begin="{a.desde}" end="{a.fin}" excludeEmpty="true"/>\n'
                "</additional>\n")
    t0 = time.perf_counter()
    p = subprocess.run([sumolib.checkBinary("sumo"), "-n", net_file, "-r", a.rutas, "-a", add,
                        "--begin", "0", "--end", str(a.fin), "--time-to-teleport", str(a.teleport),
                        "--no-step-log", "true", "--no-warnings", "true", "--duration-log.statistics", "true",
                        *a.sumo_extra.split()], capture_output=True, text=True)
    seg = time.perf_counter() - t0
    if p.returncode:
        sys.exit(p.stderr[-2000:])
    vel = {}
    for e in ET.parse(salida).getroot().iter("edge"):
        if "speed" in e.attrib:
            vel[e.get("id")] = (float(e.get("speed")) * 3.6, float(e.get("sampledSeconds", 0)))

    filas = []
    for q in puntos:
        e = net.getEdge(q["edge"]) if net.hasEdge(q["edge"]) else None
        lim = e.getSpeed() * 3.6 * (a.speed_factor or 1.0) if e else None  # velocidad deseada media
        fila = {k: q[k] for k in ("id", "edge", "calle", "estrato", "lat", "lon")}
        fila |= {"v_tomtom": q["v_actual_kmh"], "v_libre_tomtom": q["v_libre_kmh"], "limite_red": round(lim, 1) if lim else None,
                 "ic_tomtom": round(q["v_actual_kmh"] / q["v_libre_kmh"], 3), "confianza": q.get("confianza")}
        if q["edge"] in vel:
            v, ss = vel[q["edge"]]
            fila |= {"v_sim": round(v, 1), "segundos_muestra": round(ss), "ic_sim": round(v / lim, 3) if lim else None}
        else:
            fila["sin_muestra"] = True
        filas.append(fila)

    con = [f for f in filas if "v_sim" in f]
    res = {"global": metricas([f["v_tomtom"] for f in con], [f["v_sim"] for f in con])}
    ic = [f for f in con if f.get("ic_sim") is not None]
    res["global_indice"] = metricas([f["ic_tomtom"] for f in ic], [f["ic_sim"] for f in ic])
    res["libre_vs_limite"] = metricas([f["v_libre_tomtom"] for f in filas if f["limite_red"]],
                                      [f["limite_red"] for f in filas if f["limite_red"]])
    for est in COLORES:
        sub = [f for f in con if f["estrato"] == est]
        res[est] = metricas([f["v_tomtom"] for f in sub], [f["v_sim"] for f in sub])
    res["atasco_sim_pct"] = round(100 * sum(f["ic_sim"] < 0.25 for f in ic) / len(ic), 1) if ic else None
    res["atasco_tomtom_pct"] = round(100 * sum(f["ic_tomtom"] < 0.25 for f in ic) / len(ic), 1) if ic else None

    nombre = os.path.basename(a.captura).replace(".json", "")
    perfil = os.path.basename(a.rutas).replace("routes_", "").replace(".rou.xml", "")
    base = os.path.join(RAIZ, "logs", "validacion", f"tomtom_{nombre}_{perfil}{'_' + a.etiqueta if a.etiqueta else ''}")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    out = {"captura": a.captura, "captura_meta": cap["_meta"], "rutas": a.rutas, "red": net_file,
           "ventana_s": [a.desde, a.fin], "teleport": a.teleport, "sumo_extra": a.sumo_extra, "speed_factor": a.speed_factor,
           "segundos_computo": round(seg), "puntos": len(puntos), "con_muestra": len(con),
           "sin_muestra": len(filas) - len(con), "metricas": res, "arcos": filas}
    json.dump(out, open(base + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ejes = plt.subplots(1, 2, figsize=(11, 4.8))
        for ax, (cx, cy, titulo, tope) in zip(ejes, (("v_tomtom", "v_sim", "Velocidad (km/h)", 70),
                                                     ("ic_tomtom", "ic_sim", "Índice v / v libre", 1.3))):
            ax.plot([0, tope], [0, tope], color="#9a9a9a", lw=1, zorder=1)
            for est, col in COLORES.items():
                sub = [f for f in con if f["estrato"] == est and f.get(cy) is not None]
                ax.scatter([f[cx] for f in sub], [f[cy] for f in sub], s=34, color=col, label=est,
                           edgecolor="white", linewidth=1, zorder=2)
            ax.set_xlim(0, tope); ax.set_ylim(0, tope)
            ax.set_xlabel(f"TomTom — {titulo}"); ax.set_ylabel(f"SUMO — {titulo}")
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            ax.grid(color="#e6e6e6", lw=0.6)
        ejes[0].legend(frameon=False, loc="upper left")
        m = cap["_meta"]
        fig.suptitle(f"SUMO vs TomTom · {perfil} · captura {m['hora_local']} ({m['franja']}) · n={len(con)}", fontsize=11)
        fig.tight_layout()
        fig.savefig(base + ".png", dpi=150)
    except ImportError:
        pass
    print(json.dumps({k: v for k, v in out.items() if k not in ("arcos", "captura_meta")}, ensure_ascii=False))
    print(f"OK -> {base}.json")


if __name__ == "__main__":
    main()
