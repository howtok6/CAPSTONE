#!/usr/bin/env python3
"""Demanda de un área completa (Las Condes + Providencia) desde la EOD 2012 (SECTRA).

Versión por área de `build_demand_eod.py`: allá cada viaje se proyecta sobre un
eje; acá se usa la posición real de origen y destino dentro de la red.

    python scripts/build_demand_area.py --scenario scenarios/las_condes_providencia --solo-calibrar --probar
    python scripts/build_demand_area.py --scenario scenarios/las_condes_providencia \
        --train-replicas 10 --eval-replicas 10

Perfiles (mismos nombres que la demanda del eje, para reutilizar el arnés):
    eod_valle 10:00-12:00 · eod_punta_manana 07:00-09:00 · eod_punta_tarde 17:30-19:30
    (estas dos llevadas a su hora más cargada) · eod_sobresaturado = 130 % de la punta más cargada

Cada viaje en auto de la encuesta (auto chofer y taxi = 1 vehículo, colectivo = 1/3,
buses fuera) se clasifica según sus extremos respecto del área de la red:
    interno  origen y destino dentro
    sale     origen dentro, destino fuera
    entra    origen fuera, destino dentro
    paso     ambos fuera y la recta origen-destino atraviesa el área al menos --paso-min m
Los demás viajes no tocan el área y se descartan.

Extremo dentro del área: arco cercano al punto de la encuesta (radio 400 m, peso
pistas x largo x exp(-d/150 m)), sin autopistas ni sus ramales.
Extremo fuera: arco del borde (entrada o salida de la red) cercano al punto donde
la recta origen-destino cruza el límite del área (peso pistas x exp(-d/700 m)).
Así los viajes que vienen de lejos entran por Kennedy, Costanera o los ejes
principales según hacia dónde van.

Nivel: factor de expansión de la EOD, crecimiento del parque 1,49 (EMS 2024 / EOD
2012) y factor de hora punta, igual que en el eje. Con eso la punta mañana suma
~267 000 veh/h que tocan el área; asignados a la ruta más corta, Apoquindo y
Providencia quedan ~4 veces sobre el censo. `--escala` 0,25 (por defecto) los deja
en el rango del censo (17-nov). Cada entrada del borde tiene
un tope de capacidad (pistas x 1800 veh/h x verde); lo que excede se recorta y se informa.
Solo se usan arcos de la componente fuertemente conexa principal: así casi todos
los viajes encuentran ruta.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiPoint, Point, shape
from shapely.prepared import prep

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import tsc.sumo_env  # noqa: F401,E402 (fija SUMO_HOME)
import sumolib  # noqa: E402
from build_demand_eod import VENTANAS, factor_hora_punta, leer_eod  # noqa: E402

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIN_EXTREMOS = {"highway.motorway", "highway.motorway_link", "highway.trunk_link"}
R_INTERNO, SIGMA_INTERNO = 400.0, 150.0
R_BORDE, SIGMA_BORDE = 2500.0, 700.0
CLASES = ["interno", "sale", "entra", "paso"]
# Secciones de control (lon, lat, palabras del nombre de la calle)
SECCIONES = {
    "Providencia / M. Montt": (-70.6195, -33.4294, ("Providencia", "Nueva Providencia", "Septiembre")),
    "Providencia / P. de Valdivia": (-70.6140, -33.4254, ("Providencia", "Nueva Providencia", "Septiembre")),
    "Apoquindo / Alcántara": (-70.5895, -33.4155, ("Apoquindo",)),
    "Apoquindo / Manquehue": (-70.5690, -33.4095, ("Apoquindo",)),
    "Kennedy / Alonso de Córdova": (-70.5735, -33.3990, ("Kennedy",)),
    "Costanera Norte / Lyon": (-70.6080, -33.4170, ("Costanera",)),
}


# --------------------------------------------------------------------------- red
class Red:
    def __init__(self, net_file: str, area_geojson: str, verde: float):
        net = sumolib.net.readNet(net_file, withPrograms=False)
        self.net = net
        aristas = [e for e in net.getEdges() if e.allows("passenger")]
        idx = {e.getID(): i for i, e in enumerate(aristas)}
        fil, col = [], []
        for e in aristas:
            for o in e.getOutgoing():
                if o.getID() in idx:
                    fil.append(idx[e.getID()])
                    col.append(idx[o.getID()])
        g = csr_matrix((np.ones(len(fil)), (fil, col)), shape=(len(aristas), len(aristas)))
        _, lab = connected_components(g, directed=True, connection="strong")
        scc = lab == np.bincount(lab).argmax()
        self.n_scc, self.n_aristas = int(scc.sum()), len(aristas)

        def en_scc(lst):
            return any(scc[idx[o.getID()]] for o in lst if o.getID() in idx)

        internos, entradas, salidas = [], [], []
        for i, e in enumerate(aristas):
            ins = [x for x in e.getIncoming() if x.getID() in idx]
            outs = [x for x in e.getOutgoing() if x.getID() in idx]
            fx, fy = e.getFromNode().getCoord()
            tx, ty = e.getToNode().getCoord()
            if not ins and en_scc(outs):
                tope = e.getLaneNumber() * 1800.0 * (verde if e.getToNode().getType() == "traffic_light" else 0.9)
                entradas.append((e.getID(), fx, fy, e.getLaneNumber(), tope))
            if not outs and en_scc(ins):
                salidas.append((e.getID(), tx, ty, e.getLaneNumber()))
            if scc[i] and e.getType() not in SIN_EXTREMOS and e.getLength() >= 10:
                internos.append((e.getID(), (fx + tx) / 2, (fy + ty) / 2, e.getLaneNumber() * min(e.getLength(), 200.0)))
        self.int_ids = np.array([x[0] for x in internos])
        self.int_xy = np.array([(x[1], x[2]) for x in internos])
        self.int_w = np.array([x[3] for x in internos])
        self.ent_ids = np.array([x[0] for x in entradas])
        self.ent_xy = np.array([(x[1], x[2]) for x in entradas])
        self.ent_w = np.array([x[3] for x in entradas], float)
        self.tope = {x[0]: x[4] for x in entradas}
        self.sal_ids = np.array([x[0] for x in salidas])
        self.sal_xy = np.array([(x[1], x[2]) for x in salidas])
        self.sal_w = np.array([x[3] for x in salidas], float)
        self.t_int, self.t_ent, self.t_sal = cKDTree(self.int_xy), cKDTree(self.ent_xy), cKDTree(self.sal_xy)
        geo = shape(json.load(open(area_geojson, encoding="utf-8"))["geometry"])
        self.area = shapely.transform(geo, lambda c: np.array([net.convertLonLat2XY(x, y) for x, y in c]))
        self.area_p = prep(self.area)

    def elegir(self, tipo: str, xy: np.ndarray, rng) -> np.ndarray:
        """Arco para cada punto: 'int' cerca del punto, 'ent'/'sal' del borde cerca del cruce."""
        ids, pts, w, arbol, r, sig = {
            "int": (self.int_ids, self.int_xy, self.int_w, self.t_int, R_INTERNO, SIGMA_INTERNO),
            "ent": (self.ent_ids, self.ent_xy, self.ent_w, self.t_ent, R_BORDE, SIGMA_BORDE),
            "sal": (self.sal_ids, self.sal_xy, self.sal_w, self.t_sal, R_BORDE, SIGMA_BORDE),
        }[tipo]
        out = np.empty(len(xy), dtype=object)
        # se agrupa por celdas de 50 m: los puntos de una celda comparten candidatos
        celda = np.floor(xy / 50.0).astype(np.int64)
        grupos = pd.DataFrame({"a": celda[:, 0], "b": celda[:, 1]}).groupby(["a", "b"]).indices
        for (a, b), k in grupos.items():
            c = np.array([(a + 0.5) * 50.0, (b + 0.5) * 50.0])
            cand = arbol.query_ball_point(c, r)
            if not cand:
                cand = list(np.atleast_1d(arbol.query(c, k=min(5, len(ids)))[1]))
            cand = np.array(cand)
            d = np.hypot(*(pts[cand] - c).T)
            p = w[cand] * np.exp(-d / sig)
            out[k] = ids[cand[rng.choice(len(cand), size=len(k), p=p / p.sum())]]
        return out


def cruces(red: Red, v: pd.DataFrame, paso_min: float) -> pd.DataFrame:
    """Clase de cada viaje y puntos donde la recta origen-destino entra y sale del área."""
    oi = np.array([red.area_p.contains(Point(x, y)) for x, y in zip(v.xo, v.yo)])
    di = np.array([red.area_p.contains(Point(x, y)) for x, y in zip(v.xd, v.yd)])
    v = v.assign(o_in=oi, d_in=di)
    bx_o, by_o, bx_d, by_d = (np.full(len(v), np.nan) for _ in range(4))
    clase = np.where(oi & di, "interno", np.where(oi, "sale", np.where(di, "entra", "")))
    borde = red.area.exterior
    for k in np.nonzero(~(oi & di))[0]:
        o, d = (v.xo.iat[k], v.yo.iat[k]), (v.xd.iat[k], v.yd.iat[k])
        seg = LineString([o, d])
        if not seg.intersects(red.area):
            continue
        inter = seg.intersection(borde)
        pts = [p for p in (inter.geoms if hasattr(inter, "geoms") else [inter]) if p.geom_type == "Point"]
        if not pts:
            continue
        pts = MultiPoint(pts)
        po = min(pts.geoms, key=lambda p: p.distance(Point(o)))  # entrada: el cruce más cercano al origen
        pd_ = min(pts.geoms, key=lambda p: p.distance(Point(d)))  # salida: el más cercano al destino
        if not oi[k] and not di[k]:
            if seg.intersection(red.area).length < paso_min:
                continue
            clase[k] = "paso"
        bx_o[k], by_o[k], bx_d[k], by_d[k] = po.x, po.y, pd_.x, pd_.y
    v = v.assign(clase=clase, bx_o=bx_o, by_o=by_o, bx_d=bx_d, by_d=by_d)
    falta = (np.isin(clase, ["entra", "paso"]) & np.isnan(bx_o)) | (np.isin(clase, ["sale", "paso"]) & np.isnan(bx_d))
    return v[(v.clase != "") & ~falta].reset_index(drop=True)


# --------------------------------------------------------------------------- realización
def realizar(c: pd.DataFrame, escala: float, red: Red, rng, fin: int):
    n = rng.poisson(c.veh.to_numpy() * escala * fin / 3600.0)
    i = np.repeat(np.arange(len(c)), n)
    cl = c.clase.to_numpy()[i]
    o_int = np.isin(cl, ["interno", "sale"])
    d_int = np.isin(cl, ["interno", "entra"])
    desde = np.empty(len(i), dtype=object)
    hasta = np.empty(len(i), dtype=object)
    xy_o = np.where(o_int[:, None], c[["xo", "yo"]].to_numpy()[i], c[["bx_o", "by_o"]].to_numpy()[i])
    xy_d = np.where(d_int[:, None], c[["xd", "yd"]].to_numpy()[i], c[["bx_d", "by_d"]].to_numpy()[i])
    desde[o_int] = red.elegir("int", xy_o[o_int], rng)
    desde[~o_int] = red.elegir("ent", xy_o[~o_int], rng)
    hasta[d_int] = red.elegir("int", xy_d[d_int], rng)
    hasta[~d_int] = red.elegir("sal", xy_d[~d_int], rng)
    v = pd.DataFrame({"salida": rng.uniform(0, fin, len(i)), "desde": desde, "hasta": hasta, "clase": cl})
    v = v[v.desde != v.hasta]
    # tope de capacidad por entrada del borde
    v = v.sample(frac=1.0, random_state=int(rng.integers(1 << 31)))
    orden = v.groupby("desde").cumcount()
    tope = v.desde.map(lambda e: red.tope.get(e, np.inf) * fin / 3600.0)
    recortados = int((orden >= tope).sum())
    v = v[orden < tope].sort_values("salida").reset_index(drop=True)
    return v, recortados


def rutear(viajes: pd.DataFrame, net_file: str, salida: str, semilla: int, speed_factor: float | None = None) -> int:
    trips = salida.replace(".rou.xml", ".trips.xml")
    with open(trips, "w", encoding="utf-8") as f:
        f.write("<routes>\n")
        tipo = ""
        if speed_factor:
            # velocidad deseada media = speed_factor × límite (validación TomTom 18-nov: 0,7)
            f.write(f'    <vType id="auto" speedFactor="normc({speed_factor},0.1,0.2,2)"/>\n')
            tipo = ' type="auto"'
        for k, (t, a, b) in enumerate(zip(viajes.salida, viajes.desde, viajes.hasta)):
            f.write(f'    <trip id="{k}"{tipo} depart="{t:.2f}" from="{a}" to="{b}" departLane="best" departSpeed="max"/>\n')
        f.write("</routes>\n")
    subprocess.run([sumolib.checkBinary("duarouter"), "-n", net_file, "--route-files", trips, "-o", salida,
                    "--ignore-errors", "true", "--no-warnings", "true", "--no-step-log", "true",
                    "--remove-loops", "true", "--seed", str(semilla),
                    "--routing-algorithm", "astar", "--routing-threads", "4"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for sobra in (trips, salida.replace(".rou.xml", ".rou.alt.xml")):
        if os.path.exists(sobra):
            os.remove(sobra)
    with open(salida, encoding="utf-8") as f:
        return sum(1 for linea in f if "<vehicle " in linea)


def contar_rutas(rutas: str) -> dict:
    cuenta = {}
    with open(rutas, encoding="utf-8") as f:
        for linea in f:
            m = re.search(r'<route edges="([^"]+)"', linea)
            if m:
                for e in m.group(1).split():
                    cuenta[e] = cuenta.get(e, 0) + 1
    return cuenta


def flujos_secciones(red: Red, cuenta: dict, fin: int) -> dict:
    """Flujo por sentido en cada sección de control, veh/h, a partir de conteos por arco."""
    out = {}
    for nombre, (lon, lat, palabras) in SECCIONES.items():
        x, y = red.net.convertLonLat2XY(lon, lat)
        mejor = {}
        for e, _ in red.net.getNeighboringEdges(x, y, 80):
            if not any(p.lower() in e.getName().lower() for p in palabras):
                continue
            (fx, _), (tx, _) = e.getFromNode().getCoord(), e.getToNode().getCoord()
            sentido = "oriente" if tx > fx else "poniente"
            mejor[sentido] = max(mejor.get(sentido, 0), cuenta.get(e.getID(), 0))
        out[nombre] = {k: round(v * 3600.0 / fin) for k, v in sorted(mejor.items())}
    return out


def probar(red: Red, scenario: str, rutas: str, fin: int) -> dict:
    """Una hora con los planes fijos de la red (sin controlador): ¿circula la demanda y cuánto pasa por cada sección?"""
    datos = rutas.replace(".rou.xml", ".edgedata.xml")
    adicional = rutas.replace(".rou.xml", ".add.xml")
    with open(adicional, "w", encoding="utf-8") as f:
        f.write(f'<additional><edgeData id="ed" file="{os.path.basename(datos)}" begin="0" end="{fin}"/></additional>\n')
    p = subprocess.run([sumolib.checkBinary("sumo"), "-n", os.path.join(scenario, "net.net.xml"), "-r", rutas,
                        "-a", adicional, "--begin", "0", "--end", str(fin), "--no-step-log", "true",
                        "--no-warnings", "true", "--time-to-teleport", "300", "--duration-log.statistics", "true"],
                       capture_output=True, text=True)
    t = p.stdout + p.stderr
    r = {}
    for k, nombre in (("Inserted", "insertados"), ("Loaded", "cargados"), ("Running", "en_red_al_final"),
                      ("Waiting", "sin_entrar_al_final"), ("Teleports", "teletransportes"),
                      ("Duration", "viaje_s"), ("TimeLoss", "demora_s")):
        m = re.findall(rf"\b{k}: ([\d.]+)", t)
        if m:
            r[nombre] = float(m[-1])
    if os.path.exists(datos):
        with open(datos, encoding="utf-8") as f:
            cuenta = {m.group(1): int(float(m.group(2)))
                      for m in re.finditer(r'<edge id="([^"]+)"[^>]*? entered="([\d.]+)"', f.read())}
        r["flujo_simulado_secciones"] = flujos_secciones(red, cuenta, fin)
        os.remove(datos)
    os.remove(adicional)
    return r


# --------------------------------------------------------------------------- principal
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    ap.add_argument("--eod", default="data/eod2012")
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--crecimiento", type=float, default=1.49)
    ap.add_argument("--escala", type=float, default=0.25,
                    help="factor sobre la demanda EOD; 0,25 reproduce el censo en Apoquindo y Providencia "
                         "con asignación a ruta más corta (calibración del 17-nov)")
    ap.add_argument("--verde", type=float, default=0.5, help="verde efectivo en entradas semaforizadas (tope)")
    ap.add_argument("--paso-min", type=float, default=1000.0, help="m mínimos de recta dentro del área para «paso»")
    ap.add_argument("--sobresaturado", type=float, default=1.3)
    ap.add_argument("--train-replicas", type=int, default=0)
    ap.add_argument("--eval-replicas", type=int, default=0)
    ap.add_argument("--profiles", default=None)
    ap.add_argument("--solo-calibrar", action="store_true")
    ap.add_argument("--probar", action="store_true", help="simula una hora con planes fijos por perfil")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed-factor", type=float, default=None,
                    help="speedFactor medio de los autos (validación TomTom 18-nov: 0,7); sin él, el de SUMO (1,0)")
    ap.add_argument("--carpeta", default=None,
                    help="carpeta de salida (por defecto <escenario>/demand); p. ej. demand/calib_e018 para calibrar")
    args = ap.parse_args()

    net_file = os.path.join(args.scenario, "net.net.xml")
    red = Red(net_file, os.path.join(args.scenario, "area.geojson"), args.verde)
    print(f"Red: {red.n_scc}/{red.n_aristas} arcos en la componente principal · {len(red.int_ids)} arcos de "
          f"extremo interno · {len(red.ent_ids)} entradas · {len(red.sal_ids)} salidas", flush=True)
    v = leer_eod(args.eod, red.net)

    datos, fhp, resumen = {}, {}, {"crecimiento": args.crecimiento, "escala": args.escala, "speed_factor": args.speed_factor,
                                   "verde_tope": args.verde,
                                   "paso_min_m": args.paso_min, "perfiles": {}}
    for perfil, (h0, h1, punta) in VENTANAS.items():
        en = v[(v.hora >= h0) & (v.hora < h1)].copy()
        fhp[perfil] = factor_hora_punta(v, h0, h1) if punta else 1.0
        en["veh"] = en.veh / (h1 - h0) * fhp[perfil] * args.crecimiento
        c = cruces(red, en, args.paso_min)
        datos[perfil] = c
        por_clase = c.groupby("clase").veh.sum().reindex(CLASES, fill_value=0)
        resumen["perfiles"][perfil] = {"registros_eod": int(len(c)), "factor_hora_punta": round(fhp[perfil], 3),
                                       "veh_h_esperados": {k: round(x) for k, x in por_clase.items()}}
        print(f"{perfil}: {len(c):,} registros · fhp {fhp[perfil]:.2f} · "
              + " · ".join(f"{k} {x:,.0f}" for k, x in por_clase.items()) + f" = {por_clase.sum():,.0f} veh/h",
              flush=True)

    carpeta = args.carpeta or os.path.join(args.scenario, "demand")
    for sub in ("train", "eval"):
        os.makedirs(os.path.join(carpeta, sub), exist_ok=True)
    perfiles = list(VENTANAS) + ["eod_sobresaturado"]
    punta = max(("eod_punta_manana", "eod_punta_tarde"), key=lambda k: datos[k].veh.sum())
    resumen["sobresaturado_base"] = punta

    def generar(perfil, salida, semilla):
        base, factor = (punta, args.sobresaturado) if perfil == "eod_sobresaturado" else (perfil, 1.0)
        rng = np.random.default_rng([semilla, perfiles.index(perfil)])
        viajes, rec = realizar(datos[base], args.escala * factor, red, rng, args.end)
        return viajes, rec, rutear(viajes, net_file, salida, semilla, args.speed_factor)

    pedidos = [p for p in perfiles if not args.profiles or p in args.profiles.split(",")]
    if args.solo_calibrar:
        for perfil in pedidos:
            salida = os.path.join(carpeta, f"_prueba_{perfil}.rou.xml")
            viajes, rec, n = generar(perfil, salida, args.seed)
            d = resumen["perfiles"].setdefault(perfil, {})
            d["prueba"] = {"pedidos": int(len(viajes)), "ruteados": n, "recortados_por_tope": rec,
                           "por_clase": viajes.clase.value_counts().to_dict(),
                           "flujo_asignado_secciones": flujos_secciones(red, contar_rutas(salida), args.end)}
            print(f"\n{perfil}: {len(viajes):,} viajes · {n:,} con ruta · {rec:,} recortados por tope", flush=True)
            for s, f in d["prueba"]["flujo_asignado_secciones"].items():
                print(f"   {s:30s} {f}")
            if args.probar:
                d["prueba"]["tiempo_fijo"] = probar(red, args.scenario, salida, args.end)
                print("   tiempo fijo:", d["prueba"]["tiempo_fijo"], flush=True)
            os.remove(salida)
        with open(os.path.join(carpeta, "eod_area_calibracion.json"), "w", encoding="utf-8") as f:
            json.dump(resumen, f, indent=1, ensure_ascii=False)
        return

    trabajos = []
    for perfil in pedidos:
        trabajos.append((perfil, os.path.join(carpeta, f"routes_{perfil}.rou.xml"), args.seed))
        trabajos += [(perfil, os.path.join(carpeta, "train", f"routes_{perfil}_t{k:02d}.rou.xml"), 1000 + k)
                     for k in range(args.train_replicas)]
        trabajos += [(perfil, os.path.join(carpeta, "eval", f"routes_{perfil}_s{k:02d}.rou.xml"), 2000 + k)
                     for k in range(args.eval_replicas)]
    for i, (perfil, salida, semilla) in enumerate(trabajos, 1):
        viajes, rec, n = generar(perfil, salida, semilla)
        resumen["perfiles"].setdefault(perfil, {}).setdefault("realizaciones", []).append(
            {"archivo": os.path.basename(salida), "pedidos": int(len(viajes)), "ruteados": n, "recortados_por_tope": rec})
        print(f"  [{i}/{len(trabajos)}] {salida}: {n:,} vehículos ({len(viajes) - n} sin ruta, {rec} recortados)",
              flush=True)
    with open(os.path.join(carpeta, "eod_area_calibracion.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=1, ensure_ascii=False)
    print(f"\nOK: {len(trabajos)} archivos de demanda en {carpeta}")


if __name__ == "__main__":
    main()
