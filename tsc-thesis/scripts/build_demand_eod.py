#!/usr/bin/env python3
"""Demanda del eje comunal derivada de la Encuesta Origen Destino 2012 (SECTRA).

Reemplaza la demanda aleatoria de `build_demand_profiles.py` por una que hereda
de la EOD la *estructura* de los viajes en auto (dónde empiezan y terminan
respecto del eje, en qué sentido y a qué hora) y toma el *nivel* del censo
vehicular del proyecto (flujo máximo de punta mañana en Alameda-Providencia).

    python scripts/build_demand_eod.py --scenario scenarios/eje_comunal --solo-calibrar
    python scripts/build_demand_eod.py --scenario scenarios/eje_comunal \
        --train-replicas 10 --eval-replicas 10

Perfiles (mismos nombres de archivo que usa el resto del arnés, con prefijo
`eod_` para no pisar los sintéticos):

    eod_valle          10:00-12:00 de la EOD, llevado a una hora
    eod_punta_manana   07:00-09:00, llevado a la hora más cargada
    eod_punta_tarde    17:30-19:30, llevado a la hora más cargada
    eod_sobresaturado  130 % de la punta más cargada

Cómo se convierte un viaje de la encuesta en un viaje de la red (franja de
150 m a cada lado del eje, de Matucana a Los Dominicos):

  1. Cada extremo se proyecta sobre el eje: posición s (m desde Matucana) y
     distancia lateral d (norte positivo). Queda como interno (dentro de la
     franja), lateral norte o sur, o más allá de un extremo (poniente/oriente).
  2. Componente «eje»: el viaje recorre el eje entre las posiciones de sus
     extremos. Ocurre siempre si ambos extremos son internos; si no, con
     probabilidad exp(-d/lambda), donde d suma la distancia de los extremos
     externos a la franja (o al extremo del eje, si quedan más allá de él).
  3. Componente «local»: un viaje con un solo extremo interno que no recorre
     el eje entra o sale por una transversal cercana a ese extremo.
  4. Componente «cruce»: un viaje sin extremos internos, con origen y destino
     a lados opuestos, cruza por una transversal cercana al punto donde la
     recta origen-destino corta el eje, con probabilidad
     exp(-(d_o + d_d)/lambda_cruce): los cruces largos usan autopistas.
  5. El destino se elige solo entre los arcos alcanzables desde el origen.

Parámetros y cómo se fijaron (quedan en `demand/eod_calibracion.json`):

  * `lambda` se resuelve para que el flujo máximo de punta mañana entre Santa
    Rosa y Manuel Montt (ambos sentidos) sea el del censo vehicular del
    proyecto: 4 600 veh/h. Resultado: 445 m.
  * Crecimiento del parque 1,49 (viajes en auto EMS 2024 / EOD 2012): no se ajusta.
  * `beta` = 0,05 multiplica los componentes local y cruce. No sale de datos:
    es el nivel con que la red modelada atiende la punta tarde dejando menos
    de 5 % de vehículos sin entrar (controlador voraz). Con más, la red se
    bloquea; el tráfico de las transversales queda subrepresentado y es una
    limitación declarada.
  * `escala` = 1: el nivel del censo se usa sin retoque.

Vehículos: auto chofer = 1 por viaje; taxi = 1; colectivo = 1/3. Buses fuera.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tsc.sumo_env  # noqa: F401,E402 (fija SUMO_HOME)
import sumolib  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Hitos del eje (lon, lat): límites de las zonas del MVP
HITOS = [
    ("Ruta 5", -70.6603, -33.4463), ("Santa Rosa", -70.6447, -33.4428), ("Baquedano", -70.6345, -33.4372),
    ("M. Montt", -70.6195, -33.4294), ("P. de Valdivia", -70.6140, -33.4254), ("Tobalaba", -70.6015, -33.4182),
    ("Alcántara", -70.5895, -33.4155), ("Manquehue", -70.5680, -33.4092),
]
ZONAS = ["S0 Matucana–Ruta 5", "S1 Ruta 5–Santa Rosa", "S2 Santa Rosa–Baquedano", "P1 Baquedano–M. Montt",
         "P2 M. Montt–P. de Valdivia", "P3 P. de Valdivia–Tobalaba", "L1 Tobalaba–Alcántara",
         "L2 Alcántara–Manquehue", "L3 Manquehue–Los Dominicos"]

VENTANAS = {  # perfil: (inicio h, fin h, llevar a la hora más cargada)
    "eod_valle": (10.0, 12.0, False),
    "eod_punta_manana": (7.0, 9.0, True),
    "eod_punta_tarde": (17.5, 19.5, True),
}
R_FRANJA = 150.0      # m: semiancho de la franja modelada
SIGMA_ACCESO = 250.0  # m: dispersión al elegir la transversal de entrada o salida
MIN_TRAMO = 300.0     # m: recorrido mínimo para contar como viaje a lo largo del eje


# --------------------------------------------------------------------------- red
class Eje:
    """Polilínea del eje en coordenadas de la red y proyección de puntos sobre ella."""

    def __init__(self, net):
        pts = []
        for e in net.getEdges():
            n = e.getName()
            if ("Higgins" in n and "Libertador" in n) or n in ("Avenida Providencia", "Avenida Apoquindo"):
                pts.extend(e.getShape())
        pts = np.array(pts)
        bins = np.floor(pts[:, 0] / 150.0)
        self.P = np.array([pts[bins == b].mean(axis=0) for b in np.unique(bins)])
        seg = np.diff(self.P, axis=0)
        self.len = np.hypot(seg[:, 0], seg[:, 1])
        self.S = np.concatenate([[0.0], np.cumsum(self.len)])
        self.L = float(self.S[-1])

    def proyectar(self, x, y):
        """s (m, extrapolado fuera de los extremos) y d (m, norte positivo) de cada punto."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        mejor = np.full(len(x), np.inf)
        s, d = np.zeros(len(x)), np.zeros(len(x))
        m = len(self.P) - 1
        for i in range(m):
            a, ab, L = self.P[i], self.P[i + 1] - self.P[i], self.len[i]
            t = ((x - a[0]) * ab[0] + (y - a[1]) * ab[1]) / (L * L)
            tc = np.clip(t, 0, 1)
            if i == 0:
                tc = np.minimum(t, 1)
            if i == m - 1:
                tc = np.maximum(t, 0) if i else t
            px, py = a[0] + tc * ab[0], a[1] + tc * ab[1]
            dist = np.hypot(x - px, y - py)
            lado = (ab[0] * (y - a[1]) - ab[1] * (x - a[0])) / L
            k = dist < mejor
            mejor[k], s[k], d[k] = dist[k], self.S[i] + tc[k] * L, lado[k]
        return s, d


def leer_red(net_file: str):
    net = sumolib.net.readNet(net_file)
    eje = Eje(net)
    filas = []
    for e in net.getEdges():
        if not e.allows("passenger"):
            continue
        entra = not [i for i in e.getFromNode().getIncoming() if i.allows("passenger")]
        sale = not [o for o in e.getToNode().getOutgoing() if o.allows("passenger")]
        fx, fy = e.getFromNode().getCoord()
        tx, ty = e.getToNode().getCoord()
        filas.append({"id": e.getID(), "pistas": e.getLaneNumber(), "largo": e.getLength(),
                      "entra": entra, "sale": sale, "fx": fx, "fy": fy, "tx": tx, "ty": ty,
                      "nombre": e.getName()})
    ed = pd.DataFrame(filas)
    ed["s_f"], ed["d_f"] = eje.proyectar(ed.fx, ed.fy)
    ed["s_t"], ed["d_t"] = eje.proyectar(ed.tx, ed.ty)
    ed["s_m"] = (ed.s_f + ed.s_t) / 2
    hitos_s = [float(eje.proyectar([net.convertLonLat2XY(lon, lat)[0]], [net.convertLonLat2XY(lon, lat)[1]])[0][0])
               for _, lon, lat in HITOS]
    return net, eje, ed, hitos_s


# --------------------------------------------------------------------------- EOD
def leer_eod(carpeta: str, net) -> pd.DataFrame:
    v = pd.read_csv(os.path.join(carpeta, "viajes.csv"), sep=";", decimal=",", low_memory=False)
    per = pd.read_csv(os.path.join(carpeta, "personas.csv"), sep=";", decimal=",", low_memory=False,
                      usecols=["Persona", "Factor_LaboralNormal"])
    v = v.merge(per, on="Persona", how="left")
    v["w"] = pd.to_numeric(v["FactorLaboralNormal"], errors="coerce") * pd.to_numeric(
        v["Factor_LaboralNormal"], errors="coerce")
    v = v[v["w"].notna()].copy()
    medios = v["MediosUsados"].astype(str).str.split(";")
    veh = np.zeros(len(v))
    for i, ms in enumerate(medios):
        if "1" in ms:
            veh[i] = 1.0           # auto chofer
        elif "7" in ms:
            veh[i] = 1.0           # taxi
        elif "5" in ms:
            veh[i] = 1.0 / 3.0     # colectivo
    v["veh"] = v["w"].to_numpy() * veh
    v = v[v["veh"] > 0].copy()
    for c in ("OrigenCoordX", "OrigenCoordY", "DestinoCoordX", "DestinoCoordY"):
        v[c] = pd.to_numeric(v[c], errors="coerce")
    v = v.dropna(subset=["OrigenCoordX", "OrigenCoordY", "DestinoCoordX", "DestinoCoordY", "HoraIni", "HoraFin"])

    def horas(col):
        p = v[col].astype(str).str.split(":", expand=True)
        return pd.to_numeric(p[0], errors="coerce") + pd.to_numeric(p[1], errors="coerce") / 60.0

    hi, hf = horas("HoraIni"), horas("HoraFin")
    hf = np.where(hf < hi, hf + 24, hf)
    v["hora"] = ((hi + hf) / 2) % 24
    v = v.dropna(subset=["hora"])
    # EOD: UTM 19 sur. La red usa UTM 19 sin «+south»: norte = norte_sur - 10 000 000.
    ox, oy = net.getLocationOffset()
    v["xo"], v["yo"] = v.OrigenCoordX + ox, v.OrigenCoordY - 1e7 + oy
    v["xd"], v["yd"] = v.DestinoCoordX + ox, v.DestinoCoordY - 1e7 + oy
    return v[["veh", "hora", "xo", "yo", "xd", "yd"]].reset_index(drop=True)


def factor_hora_punta(v: pd.DataFrame, h0: float, h1: float) -> float:
    """Hora más cargada de la ventana respecto de su promedio horario (autos, toda la ciudad)."""
    en = v[(v.hora >= h0) & (v.hora < h1)]
    medio = en.veh.sum() / (h1 - h0)
    mejor = max(en[(en.hora >= a) & (en.hora < a + 1)].veh.sum() for a in np.arange(h0, h1 - 1 + 1e-9, 0.25))
    return float(mejor / medio)


def clasificar(v: pd.DataFrame, eje: Eje) -> pd.DataFrame:
    """Tipo de acceso de cada extremo: I interno, N/S lateral, W/E más allá de un extremo."""
    out = v.copy()
    for p, (x, y) in (("o", ("xo", "yo")), ("d", ("xd", "yd"))):
        s, d = eje.proyectar(v[x], v[y])
        fuera = np.where(s < 0, -s, np.where(s > eje.L, s - eje.L, 0.0))
        tipo = np.where(s < 0, "W", np.where(s > eje.L, "E", np.where(np.abs(d) <= R_FRANJA, "I",
                        np.where(d > 0, "N", "S"))))
        # Más allá de un extremo cuenta la distancia al extremo: los barrios vecinos entran por el eje,
        # los lejanos llegan por autopista y entran por una transversal cercana a su destino.
        dlat = np.where(fuera > 0, np.hypot(fuera, d), np.maximum(0, np.abs(d) - R_FRANJA))
        out[f"s_{p}"], out[f"d_{p}"] = s, d
        out[f"sc_{p}"], out[f"t_{p}"], out[f"lat_{p}"] = np.clip(s, 0, eje.L), tipo, dlat
    den = np.abs(out.d_o) + np.abs(out.d_d)
    out["s_x"] = out.s_o + (out.s_d - out.s_o) * np.abs(out.d_o) / np.where(den > 0, den, 1)
    out["opuestos"] = (np.sign(out.d_o) * np.sign(out.d_d)) < 0
    return out


def probabilidades(c: pd.DataFrame, lam: float, lam_x: float, L: float) -> pd.DataFrame:
    """Probabilidad de recorrer el eje (p_eje), de entrar junto al extremo interno (p_loc) y de cruzar (p_x)."""
    io, idd = c.t_o == "I", c.t_d == "I"
    tramo = np.abs(c.sc_d - c.sc_o) >= MIN_TRAMO
    p = pd.DataFrame(index=c.index)
    ambos = io & idd
    uno = io ^ idd
    lat_ext = np.where(io, c.lat_d, c.lat_o)
    q = np.exp(-lat_ext / lam)
    p["p_eje"] = np.where(ambos, 1.0, np.where(uno, np.where(tramo, q, 0.0),
                          np.where(tramo, np.exp(-(c.lat_o + c.lat_d) / lam), 0.0)))
    p["p_loc"] = np.where(uno, 1.0 - p.p_eje, 0.0)
    cruza = (~io) & (~idd) & c.opuestos & (c.s_x >= 0) & (c.s_x <= L)
    p["p_x"] = np.where(cruza, (1.0 - p.p_eje) * np.exp(-(np.abs(c.d_o) + np.abs(c.d_d)) / lam_x), 0.0)
    return p


def flujo_seccion(c, p, s_ref):
    """Vehículos esperados que recorren el eje por la sección s_ref: (hacia oriente, hacia poniente)."""
    a, b = c.sc_o.to_numpy(), c.sc_d.to_numpy()
    pasa = (np.minimum(a, b) < s_ref) & (np.maximum(a, b) > s_ref)
    e = c.veh.to_numpy() * p.p_eje.to_numpy() * pasa
    return float(e[b > a].sum()), float(e[b < a].sum())


# --------------------------------------------------------------------------- realización
PASO_S = 50.0  # m: resolución con que se tabulan las probabilidades de acceso


class Accesos:
    """Arcos por donde entra y sale cada tipo de extremo, con sus probabilidades tabuladas por posición."""

    def __init__(self, net, ed: pd.DataFrame, L: float, verde: float):
        self.L = L
        self.centros = np.arange(0.0, L + PASO_S, PASO_S)
        ent, sal = ed[ed.entra], ed[ed.sale]
        inter = ed[(ed.largo >= 15) & (ed.s_m > 0) & (ed.s_m < L)]
        # Alcance: a qué arcos se llega desde cada arco. El destino se elige entre los alcanzables,
        # así la demanda generada no depende de cuántos pares descarta el ruteo.
        ids = list(ed.id)
        self.fila = {e: k for k, e in enumerate(ids)}
        sig = {e: [o.getID() for o in net.getEdge(e).getOutgoing() if o.getID() in self.fila] for e in ids}
        alcance = np.zeros((len(ids), len(ids)), bool)
        for e in ids:
            visto, pila = set(), list(sig[e])
            while pila:
                x = pila.pop()
                if x not in visto:
                    visto.add(x)
                    pila.extend(sig[x])
            visto.discard(e)
            alcance[self.fila[e], [self.fila[x] for x in visto]] = True
        self.tablas = {}
        for lado, t in (("N", ent[ent.d_f > 0]), ("S", ent[ent.d_f <= 0])):
            self.tablas["o" + lado] = self._tabla(t, t.s_f, t.pistas, SIGMA_ACCESO)
        for lado, t in (("N", sal[sal.d_t > 0]), ("S", sal[sal.d_t <= 0])):
            self.tablas["d" + lado] = self._tabla(t, t.s_t, t.pistas, SIGMA_ACCESO)
        for lado, t, u in (("W", ent[ent.s_f < 250], sal[sal.s_t < 250]),
                           ("E", ent[ent.s_f > L - 250], sal[sal.s_t > L - 250])):
            self.tablas["o" + lado] = self._tabla(t, t.s_f, t.pistas, 1e9)
            self.tablas["d" + lado] = self._tabla(u, u.s_t, u.pistas, 1e9)
        io_, id_ = inter[~inter.sale], inter[~inter.entra]
        self.tablas["oI"] = self._tabla(io_, io_.s_m, io_.largo * io_.pistas, 150.0)
        self.tablas["dI"] = self._tabla(id_, id_.s_m, id_.largo * id_.pistas, 150.0)
        self.R = {k: alcance[:, [self.fila[e] for e in tb[0]]] for k, tb in self.tablas.items() if k[0] == "d"}
        self.laterales = set(ent[(ent.s_f >= 250) & (ent.s_f <= L - 250)].id)
        self.cap = {e: p * 1800.0 * verde for e, p in zip(ent.id, ent.pistas)}
        self.cap_lateral = float(sum(self.cap[e] for e in self.laterales))

    def _tabla(self, t, s, peso, sigma):
        w = peso.to_numpy(float)[None, :] * np.exp(-np.abs(s.to_numpy(float)[None, :] - self.centros[:, None]) / sigma)
        w = w / w.sum(axis=1, keepdims=True)
        return t.id.to_numpy(), w

    def elegir(self, extremo: str, tipos, s, rng):
        """Arco de cada viaje según el tipo de su extremo ('o' origen, 'd' destino) y su posición."""
        out = np.empty(len(s), dtype=object)
        casilla = np.clip(np.rint(s / PASO_S).astype(int), 0, len(self.centros) - 1)
        for tipo in ("I", "N", "S", "W", "E"):
            ids, w = self.tablas[extremo + tipo]
            m = np.nonzero(tipos == tipo)[0]
            for b in np.unique(casilla[m]):
                k = m[casilla[m] == b]
                out[k] = ids[rng.choice(len(ids), size=len(k), p=w[b])]
        return out

    def elegir_destino(self, desde, tipos, s, rng):
        """Como `elegir`, pero solo entre los arcos alcanzables desde el origen de cada viaje."""
        out = np.full(len(s), None, dtype=object)
        casilla = np.clip(np.rint(s / PASO_S).astype(int), 0, len(self.centros) - 1)
        grupos = pd.DataFrame({"o": desde, "t": tipos, "b": casilla}).groupby(["o", "t", "b"]).indices
        for (o, tp, b), k in grupos.items():
            ids, w = self.tablas["d" + tp]
            pr = w[b] * self.R["d" + tp][self.fila[o]]
            tot = pr.sum()
            if tot > 0:
                out[k] = ids[rng.choice(len(ids), size=len(k), p=pr / tot)]
        return out


def realizar(c, p, escala, beta, acc: Accesos, rng, fin: int):
    """Una realización de la demanda: tabla de viajes (salida, desde, hasta, clase) y entradas recortadas.

    `beta` reduce los componentes que entran por transversales (local y cruce).
    """
    pe, pl, px = p.p_eje.to_numpy(), p.p_loc.to_numpy() * beta, p.p_x.to_numpy() * beta
    n = rng.poisson(c.veh.to_numpy() * escala * (pe + pl + px))
    i = np.repeat(np.arange(len(c)), n)
    u = rng.random(len(i)) * (pe + pl + px)[i]
    clase = np.where(u < pe[i], 0, np.where(u < (pe + pl)[i], 1, 2))
    t_o, t_d = c.t_o.to_numpy()[i], c.t_d.to_numpy()[i]
    sc_o, sc_d, s_x = c.sc_o.to_numpy()[i], c.sc_d.to_numpy()[i], c.s_x.to_numpy()[i]
    lado_o = np.where(c.d_o.to_numpy()[i] > 0, "N", "S")
    lado_d = np.where(c.d_d.to_numpy()[i] > 0, "N", "S")
    ruido = rng.normal(0, 150, len(i))
    o_int = t_o == "I"
    # eje: de extremo a extremo · local: junto al extremo interno · cruce: por el punto de cruce
    tipo_o = np.where(clase == 0, t_o, np.where(clase == 1, np.where(o_int, "I", lado_o), lado_o))
    tipo_d = np.where(clase == 0, t_d, np.where(clase == 1, np.where(o_int, lado_d, "I"), lado_d))
    pos_o = np.where(clase == 0, sc_o, np.where(clase == 1, np.where(o_int, sc_o, sc_d + ruido), s_x))
    pos_d = np.where(clase == 0, sc_d, np.where(clase == 1, np.where(o_int, sc_o + ruido, sc_d), s_x))
    desde = acc.elegir("o", tipo_o, pos_o, rng)
    hasta = acc.elegir_destino(desde, tipo_d, pos_d, rng)
    v = pd.DataFrame({"salida": rng.uniform(0, fin, len(i)), "desde": desde, "hasta": hasta,
                      "clase": np.array(["eje", "local", "cruce"])[clase]})
    v = v[v.hasta.notna()]
    # Tope de capacidad por entrada: la encuesta no dice por qué calle se entra
    v = v.sample(frac=1.0, random_state=int(rng.integers(1 << 31)))
    orden = v.groupby("desde").cumcount()
    tope = v.desde.map(lambda e: acc.cap.get(e, np.inf) * fin / 3600.0)
    recortados = int((orden >= tope).sum())
    v = v[orden < tope].sort_values("salida").reset_index(drop=True)
    return v, recortados


def escribir_y_rutear(viajes: pd.DataFrame, net_file: str, salida: str, semilla: int) -> int:
    trips = salida.replace(".rou.xml", ".trips.xml")
    with open(trips, "w", encoding="utf-8") as f:
        f.write('<routes>\n')
        for k, (t, a, b) in enumerate(zip(viajes.salida, viajes.desde, viajes.hasta)):
            f.write(f'    <trip id="{k}" depart="{t:.2f}" from="{a}" to="{b}" departLane="best" departSpeed="max"/>\n')
        f.write('</routes>\n')
    subprocess.run(["duarouter", "-n", net_file, "--route-files", trips, "-o", salida,
                    "--ignore-errors", "true", "--no-warnings", "true", "--no-step-log", "true",
                    "--remove-loops", "true", "--seed", str(semilla)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for sobra in (trips, salida.replace(".rou.xml", ".rou.alt.xml")):
        if os.path.exists(sobra):
            os.remove(sobra)
    with open(salida, encoding="utf-8") as f:
        return sum(1 for linea in f if "<vehicle " in linea)


def probar(scenario: str, rutas: str, fin: int) -> dict:
    """Simulación de prueba con el controlador voraz en los semáforos del eje: ¿circula y a qué nivel?

    El índice de congestión (tiempo de viaje / tiempo a flujo libre) es comparable con el de la
    muestra de Waze del proyecto (2,3 a 4,5 en el eje en punta tarde).
    """
    from tsc.controllers import GreedyQueueController
    from tsc.runner import run_episode

    ctrl = GreedyQueueController()
    ruta_eje = os.path.join(scenario, "tls_eje.json")
    if os.path.exists(ruta_eje):
        with open(ruta_eje, encoding="utf-8") as f:
            ctrl.tls_ids = json.load(f)["eje"]
    r = run_episode(ctrl, os.path.join(scenario, "net.net.xml"), rutas, seed=0, end=fin, warmup=300)
    tv, perdida = r.get("travel_time_mean", float("nan")), r.get("time_loss_mean", float("nan"))
    return {"terminan": r.get("vehicles_finished"), "en_red_al_final": r.get("vehicles_running_end"),
            "sin_entrar_al_final": r.get("vehicles_pending_end"), "viaje_s": round(tv, 1),
            "demora_s": round(perdida, 1), "indice_congestion": round(tv / max(tv - perdida, 1e-9), 2),
            "cola_media": round(r.get("queue_mean", float("nan")), 1)}


# --------------------------------------------------------------------------- principal
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scenario", default="scenarios/eje_comunal")
    ap.add_argument("--eod", default="data/eod2012", help="carpeta con viajes.csv y personas.csv de la EOD 2012")
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--train-replicas", type=int, default=0)
    ap.add_argument("--eval-replicas", type=int, default=0)
    ap.add_argument("--profiles", default=None, help="perfiles separados por coma (por defecto, los cuatro)")
    ap.add_argument("--objetivo", type=float, default=4600.0,
                    help="veh/h, ambos sentidos, máximo de punta mañana entre Santa Rosa y M. Montt (censo)")
    ap.add_argument("--crecimiento", type=float, default=1.49, help="autos 2024 / autos 2012 (EMS 2024 / EOD 2012)")
    ap.add_argument("--lambda-m", type=float, default=None, help="fija lambda (m) en vez de resolverla")
    ap.add_argument("--lambda-cruce", type=float, default=2000.0, help="m: decaimiento de los cruces a nivel")
    ap.add_argument("--verde", type=float, default=0.40, help="verde efectivo de las transversales (tope de entrada)")
    ap.add_argument("--saturacion-lateral", type=float, default=0.5,
                    help="uso medio de la capacidad de las entradas laterales en el perfil más cargado")
    ap.add_argument("--beta", type=float, default=0.05,
                    help="factor de los componentes local y cruce (ver docstring); negativo: derivarlo de "
                         "--saturacion-lateral")
    ap.add_argument("--escala", type=float, default=1.0, help="factor final sobre toda la demanda (ajuste con simulación)")
    ap.add_argument("--sobresaturado", type=float, default=1.3)
    ap.add_argument("--solo-calibrar", action="store_true", help="informa la calibración sin generar réplicas")
    ap.add_argument("--probar", action="store_true", help="con --solo-calibrar: simula una realización por perfil")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    net_file = os.path.join(args.scenario, "net.net.xml")
    net, eje, ed, hitos_s = leer_red(net_file)
    print(f"Eje: {eje.L/1000:.2f} km · {int(ed.entra.sum())} entradas · {int(ed.sale.sum())} salidas", flush=True)
    limites = [0.0] + hitos_s + [eje.L]
    v = leer_eod(args.eod, net)
    print(f"EOD: {len(v):,} viajes en vehículo liviano en día laboral ({v.veh.sum():,.0f} vehículos-viaje)")

    datos, fhp = {}, {}
    for perfil, (h0, h1, punta) in VENTANAS.items():
        en = v[(v.hora >= h0) & (v.hora < h1)].copy()
        fhp[perfil] = factor_hora_punta(v, h0, h1) if punta else 1.0
        en["veh"] = en.veh / (h1 - h0) * fhp[perfil] * args.crecimiento
        c = clasificar(en, eje)
        util = (c.t_o == "I") | (c.t_d == "I") | (np.abs(c.sc_d - c.sc_o) >= MIN_TRAMO) | c.opuestos
        datos[perfil] = c[util].reset_index(drop=True)

    # lambda: bisección sobre el flujo máximo de punta mañana entre Santa Rosa y M. Montt
    cm = datos["eod_punta_manana"]
    secciones = np.linspace(hitos_s[1], hitos_s[3], 25)

    def maximo(lam):
        p = probabilidades(cm, lam, args.lambda_cruce, eje.L)
        return max(sum(flujo_seccion(cm, p, s)) for s in secciones)

    if args.lambda_m:
        lam = args.lambda_m
    else:
        lo, hi = 50.0, 20000.0
        if maximo(hi) < args.objetivo:
            lam = hi
        elif maximo(lo) > args.objetivo:
            lam = lo
        else:
            for _ in range(40):
                lam = (lo + hi) / 2
                lo, hi = (lam, hi) if maximo(lam) < args.objetivo else (lo, lam)
    print(f"lambda = {lam:.0f} m  ->  máximo Santa Rosa–M. Montt en punta mañana: {maximo(lam):,.0f} veh/h "
          f"(objetivo {args.objetivo:,.0f})")

    acc = Accesos(net, ed, eje.L, args.verde)
    probs = {perfil: probabilidades(c, lam, args.lambda_cruce, eje.L) for perfil, c in datos.items()}
    # beta: los componentes que entran por transversales se llevan a un uso medio dado de su capacidad
    lateral = {k: float((datos[k].veh * (probs[k].p_loc + probs[k].p_x)).sum()) for k in datos}
    beta = min(1.0, args.saturacion_lateral * acc.cap_lateral / max(lateral.values()))
    if args.beta >= 0:
        beta = args.beta
    print(f"Entradas laterales: capacidad {acc.cap_lateral:,.0f} veh/h; demanda EOD máxima {max(lateral.values()):,.0f} "
          f"-> beta = {beta:.3f}")

    resumen = {"lambda_m": round(lam, 1), "lambda_cruce_m": args.lambda_cruce, "crecimiento": args.crecimiento,
               "objetivo_veh_h": args.objetivo, "escala_final": args.escala, "verde_tope": args.verde,
               "saturacion_lateral": args.saturacion_lateral, "beta_lateral": round(beta, 4),
               "capacidad_lateral_veh_h": round(acc.cap_lateral),
               "factor_hora_punta": {k: round(x, 3) for k, x in fhp.items()}, "eje_km": round(eje.L / 1000, 2),
               "perfiles": {}}
    for perfil, c in datos.items():
        p = probs[perfil]
        e = c.veh.to_numpy() * args.escala
        comp = {"eje": float((e * p.p_eje).sum()), "local": float((e * p.p_loc).sum()) * beta,
                "cruce": float((e * p.p_x).sum()) * beta}
        zonas = {}
        for z, a, b in zip(ZONAS, limites[:-1], limites[1:]):
            este, oeste = flujo_seccion(c, p, (a + b) / 2)
            zonas[z] = {"hacia_oriente": round(este * args.escala), "hacia_poniente": round(oeste * args.escala)}
        resumen["perfiles"][perfil] = {"registros_eod": int(len(c)),
                                       "veh_h_esperados": {k: round(x) for k, x in comp.items()},
                                       "flujo_eje_por_zona": zonas}
        print(f"\n{perfil}: {len(c):,} registros · factor hora punta {fhp[perfil]:.2f} · "
              f"eje {comp['eje']:,.0f} + local {comp['local']:,.0f} + cruce {comp['cruce']:,.0f} "
              f"= {sum(comp.values()):,.0f} veh/h")
        for z, f in zonas.items():
            tot = f["hacia_oriente"] + f["hacia_poniente"]
            print(f"   {z:30s} -> oriente {f['hacia_oriente']:5d}   -> poniente {f['hacia_poniente']:5d}   "
                  f"total {tot:5d}   ({100*f['hacia_oriente']/max(tot,1):.0f} % al oriente)")

    carpeta = os.path.join(args.scenario, "demand")
    os.makedirs(os.path.join(carpeta, "train"), exist_ok=True)
    os.makedirs(os.path.join(carpeta, "eval"), exist_ok=True)
    perfiles = list(VENTANAS) + ["eod_sobresaturado"]
    punta = max(("eod_punta_manana", "eod_punta_tarde"),
                key=lambda k: sum(resumen["perfiles"][k]["veh_h_esperados"].values()))
    resumen["sobresaturado_base"] = punta

    def generar(perfil, salida, semilla):
        base, factor = (punta, args.sobresaturado) if perfil == "eod_sobresaturado" else (perfil, 1.0)
        rng = np.random.default_rng([semilla, perfiles.index(perfil)])
        viajes, rec = realizar(datos[base], probs[base], args.escala * factor, beta, acc, rng, args.end)
        n = escribir_y_rutear(viajes, net_file, salida, semilla)
        return viajes, rec, n

    if args.solo_calibrar:
        for perfil in (args.profiles.split(",") if args.profiles else perfiles):
            salida = os.path.join(carpeta, f"_prueba_{perfil}_{os.getpid()}.rou.xml")
            viajes, rec, n = generar(perfil, salida, args.seed)
            print(f"\n{perfil}: {len(viajes):,} viajes {viajes.clase.value_counts().to_dict()} · {n:,} con ruta · "
                  f"{rec:,} recortados por tope", flush=True)
            if args.probar:
                print("   voraz:", probar(args.scenario, salida, args.end), flush=True)
            os.remove(salida)
        return

    if args.profiles:
        perfiles_pedidos = [x for x in perfiles if x in args.profiles.split(",")]
    else:
        perfiles_pedidos = perfiles
    trabajos = []
    for perfil in perfiles_pedidos:
        trabajos.append((perfil, os.path.join(carpeta, f"routes_{perfil}.rou.xml"), args.seed))
        for k in range(args.train_replicas):
            trabajos.append((perfil, os.path.join(carpeta, "train", f"routes_{perfil}_t{k:02d}.rou.xml"), 1000 + k))
        for k in range(args.eval_replicas):
            trabajos.append((perfil, os.path.join(carpeta, "eval", f"routes_{perfil}_s{k:02d}.rou.xml"), 2000 + k))
    conteo = {}
    for i, (perfil, salida, semilla) in enumerate(trabajos, 1):
        viajes, rec, n = generar(perfil, salida, semilla)
        conteo.setdefault(perfil, []).append({"archivo": os.path.basename(salida), "pedidos": int(len(viajes)),
                                              "ruteados": n, "recortados_por_tope": rec})
        print(f"  [{i}/{len(trabajos)}] {salida}: {n:,} vehículos ({len(viajes) - n} sin ruta, {rec} recortados)",
              flush=True)
    for perfil, filas in conteo.items():
        resumen["perfiles"].setdefault(perfil, {})["realizaciones"] = filas
    ruta_cal = os.path.join(carpeta, "eod_calibracion.json")
    if os.path.exists(ruta_cal):  # conserva las realizaciones de perfiles generados en otra corrida
        with open(ruta_cal, encoding="utf-8") as f:
            previo = json.load(f)
        for perfil, d in previo.get("perfiles", {}).items():
            if "realizaciones" in d and "realizaciones" not in resumen["perfiles"].get(perfil, {}):
                resumen["perfiles"].setdefault(perfil, {})["realizaciones"] = d["realizaciones"]
    with open(ruta_cal, "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=1, ensure_ascii=False)
    print(f"\nOK: {len(trabajos)} archivos de demanda en {carpeta}")


if __name__ == "__main__":
    main()
