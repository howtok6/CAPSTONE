#!/usr/bin/env python3
"""Video con varios controladores lado a lado, sobre la misma demanda.

Cada controlador corre sobre la misma demanda de evaluación, la misma semilla y
la misma ventana de tiempo. Los cuadros se dibujan directamente desde la
simulación (posición, rumbo y velocidad de cada vehículo y color de cada
semáforo), sin sumo-gui: así no depende de que una ventana esté en primer plano
y corre con libsumo, varias veces más rápido. Vehículos rojos = detenidos.

El agente corre sobre sumo-rl, igual que en la evaluación; los clásicos sobre
tsc.runner. Lo dibujado es la ejecución real, cuadro a cuadro.

    python scripts/video_comparativo.py --scenario scenarios/eje_comunal \
        --profile punta_tarde --controllers fixed,ppo \
        --model models/eje_comunal/ppo_fase_wait_adam_punta_tarde_s1.zip \
        --begin 1500 --seconds 600 --center 10900,5110 --ancho-m 900 --out results/video/pt_apoquindo
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if __name__ == "__main__":
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import cv2  # noqa: E402
import numpy as np  # noqa: E402

# sumo-rl antes que tsc.sumo_env (ver medir_colas_eje.py)
from tsc.rl_env import accion_real, controlled_tls  # noqa: E402, I001
from tsc.demand import ruta_evaluacion  # noqa: E402

NOMBRES = {"fixed": "Tiempo fijo", "webster": "Webster", "maxpressure": "Max-Pressure",
           "greedy": "Voraz por cola", "ppo": "IPPO (aprendido)"}
# colores BGR
FONDO, PISTA, INTERNA = (246, 247, 245), (196, 199, 196), (214, 216, 213)
TEXTO, TEXTO2 = (35, 35, 35), (90, 90, 90)
SEMAFORO = {"r": (40, 40, 205), "y": (0, 170, 235), "g": (60, 160, 40)}
ACENTO = {"fixed": (52, 104, 235), "webster": (0, 161, 237), "maxpressure": (122, 175, 27),
          "greedy": (164, 123, 232), "ppo": (214, 120, 42)}


def color_velocidad(v: float):
    """Rojo detenido → naranjo → amarillo → verde a velocidad de circulación."""
    paradas = [(0.0, (40, 45, 205)), (4.0, (45, 160, 238)), (8.0, (80, 215, 235)), (13.0, (95, 165, 60))]
    if v <= 0.1:
        return paradas[0][1]
    for (v0, c0), (v1, c1) in zip(paradas, paradas[1:]):
        if v <= v1:
            f = (v - v0) / (v1 - v0)
            return tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
    return paradas[-1][1]


class Lienzo:
    """Mapa base de la vista y transformación de coordenadas de la red a píxeles."""

    def __init__(self, net_file, centro, ancho_m, ancho_px, alto_px):
        import sumolib

        self.W, self.H = ancho_px, alto_px
        self.s = ancho_px / ancho_m
        alto_m = alto_px / self.s
        self.x0, self.y0 = centro[0] - ancho_m / 2, centro[1] - alto_m / 2
        self.x1, self.y1 = self.x0 + ancho_m, self.y0 + alto_m
        red = sumolib.net.readNet(net_file, withInternal=True)
        self.base = np.full((alto_px, ancho_px, 3), FONDO, np.uint8)
        self.forma = {}
        for e in red.getEdges(withInternal=True):
            interna = e.getFunction() == "internal"
            for ln in e.getLanes():
                pts = ln.getShape()
                self.forma[ln.getID()] = pts
                if not self._cerca(pts):
                    continue
                grosor = max(1, int(round(ln.getWidth() * self.s * 0.92)))
                cv2.polylines(self.base, [self.px(pts)], False, INTERNA if interna else PISTA, grosor,
                              cv2.LINE_AA)
        # barra de escala de 100 m
        x, y = 24, alto_px - 22
        metros = 100 if ancho_m < 3000 else 1000
        cv2.line(self.base, (x, y), (x + int(metros * self.s), y), TEXTO2, 2, cv2.LINE_AA)
        cv2.putText(self.base, f"{metros} m" if metros < 1000 else "1 km", (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXTO2, 1, cv2.LINE_AA)
        # leyenda
        lx, ly = ancho_px - 330, alto_px - 22
        for i, (etq, col) in enumerate((("detenido", color_velocidad(0)), ("lento", color_velocidad(6)),
                                        ("circula", color_velocidad(14)))):
            cx = lx + i * 100
            cv2.rectangle(self.base, (cx, ly - 6), (cx + 14, ly + 2), col, -1)
            cv2.putText(self.base, etq, (cx + 20, ly + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.48, TEXTO2, 1,
                        cv2.LINE_AA)

    def _cerca(self, pts, margen=30):
        return any(self.x0 - margen <= x <= self.x1 + margen and self.y0 - margen <= y <= self.y1 + margen
                   for x, y in pts)

    def px(self, pts):
        return np.array([[(x - self.x0) * self.s, self.H - (y - self.y0) * self.s] for x, y in pts],
                        np.int32).reshape(-1, 1, 2)

    def dentro(self, x, y, margen=10):
        return self.x0 - margen <= x <= self.x1 + margen and self.y0 - margen <= y <= self.y1 + margen


class Camara:
    """Dibuja un cuadro cada `every` segundos y guarda las métricas de ese instante."""

    def __init__(self, conn, lienzo, carpeta, begin, every):
        self.c, self.L, self.carpeta, self.begin, self.every = conn, lienzo, carpeta, begin, every
        self.n, self.metricas, self.llegados = 0, [], 0
        # semáforos visibles y el punto donde se dibuja cada enlace (final de su pista de entrada)
        self.luces = []
        for tl in conn.trafficlight.getIDList():
            puntos = []
            for i, enlaces in enumerate(conn.trafficlight.getControlledLinks(tl)):
                if not enlaces:
                    continue
                pts = lienzo.forma.get(enlaces[0][0])
                if pts and lienzo.dentro(*pts[-1]):
                    puntos.append((i, pts[-1]))
            if puntos:
                self.luces.append((tl, puntos))

    def paso(self) -> None:
        c = self.c
        self.llegados += c.simulation.getArrivedNumber()
        t = int(c.simulation.getTime())
        if t < self.begin or (t - self.begin) % self.every:
            return
        L = self.L
        img = L.base.copy()
        ids = c.vehicle.getIDList()
        detenidos = 0
        largo, ancho = 5.0 * L.s, max(2.0, 2.0 * L.s)
        for v in ids:
            vel = c.vehicle.getSpeed(v)
            detenidos += vel < 0.1
            x, y = c.vehicle.getPosition(v)
            if not L.dentro(x, y):
                continue
            if L.s < 1.0:
                # vista general: a esta escala un auto mide menos de un píxel; se dibuja como punto
                p = (int((x - L.x0) * L.s), int(L.H - (y - L.y0) * L.s))
                cv2.circle(img, p, 2, color_velocidad(vel), -1, cv2.LINE_AA)
                continue
            ang = c.vehicle.getAngle(v)  # grados, 0 = norte, sentido horario
            # la posición de SUMO es el frente del vehículo; se centra medio largo atrás
            rad = math.radians(ang)
            cx = (x - L.x0) * L.s - math.sin(rad) * largo / 2
            cy = L.H - (y - L.y0) * L.s + math.cos(rad) * largo / 2
            caja = cv2.boxPoints(((cx, cy), (ancho, largo), ang))
            cv2.fillPoly(img, [caja.astype(np.int32)], color_velocidad(vel), cv2.LINE_AA)
        for tl, puntos in (self.luces if L.s >= 1.0 else []):
            estado = c.trafficlight.getRedYellowGreenState(tl)
            for i, (x, y) in puntos:
                letra = estado[i].lower() if i < len(estado) else "r"
                p = L.px([(x, y)])[0][0]
                cv2.circle(img, (int(p[0]), int(p[1])), max(3, int(1.3 * L.s)),
                           SEMAFORO.get(letra, SEMAFORO["r"]), -1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(self.carpeta, f"f{self.n:05d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 93])
        self.metricas.append({"t": t, "detenidos": int(detenidos), "en_red": len(ids), "llegados": self.llegados})
        self.n += 1


def grabar_clasico(nombre, a, net, rou, eje, carpeta, lienzo):
    from run_baselines import build_controllers
    from tsc.controllers.base import PhaseSwitchingController
    from tsc.sumo_env import SumoSimulation

    ctrl = build_controllers(a.scenario, [nombre], a.profile)[0]()
    if isinstance(ctrl, PhaseSwitchingController):
        ctrl.tls_ids = eje
    sim = SumoSimulation(net_file=net, route_file=rou, end=a.begin + a.seconds + 1, seed=a.replica)
    with sim:
        ctrl.setup(sim)
        cam = Camara(sim.conn, lienzo, carpeta, a.begin, a.every)
        intervalo = max(1, int(getattr(ctrl, "decision_interval", 5)))
        while sim.running() and sim.time < a.begin + a.seconds:
            for _ in range(intervalo):
                sim.step(1)
                cam.paso()
            ctrl.act(sim)
    return cam


def grabar_ppo(a, net, rou, eje, carpeta, lienzo):
    from eval_rl import leer_metadatos
    from stable_baselines3 import PPO

    from tsc.rl_env import make_parallel_env

    model = PPO.load(a.model, device="cpu")
    meta = leer_metadatos(a.model)
    env = make_parallel_env(net_file=net, route_file=rou, num_seconds=a.begin + a.seconds + 5,
                            seed=a.replica, tls_ids=eje, obs=meta.get("obs", "estandar"),
                            delta_time=meta.get("delta_time", 5), min_green=meta.get("min_green", 10),
                            max_green=meta.get("max_green", 60))
    obs, _ = env.reset()
    inner = env.unwrapped.env
    cam = Camara(inner.sumo, lienzo, carpeta, a.begin, a.every)
    original = inner._sumo_step

    def paso():
        original()
        cam.paso()

    inner._sumo_step = paso
    dim = model.observation_space.shape[0]
    while env.agents and inner.sim_step < a.begin + a.seconds:
        agentes = list(obs)
        lote = np.zeros((len(agentes), dim), dtype=np.float32)
        for i, ag in enumerate(agentes):
            lote[i, : len(obs[ag])] = obs[ag]
        salidas, _ = model.predict(lote, deterministic=True)
        obs, _, term, trunc, _ = env.step({ag: accion_real(salidas[i], env.action_space(ag).n)
                                           for i, ag in enumerate(agentes)})
        if all(term.values()) or all(trunc.values()):
            break
    env.close()
    return cam


def rotulo(img, nombre, m):
    alto = 58
    barra = np.full((alto, img.shape[1], 3), 255, np.uint8)
    cv2.rectangle(barra, (0, 0), (9, alto), ACENTO[nombre], -1)
    angosto = img.shape[1] < 1200  # en la grilla de 2 × 2 el rótulo se achica para no montarse
    cv2.putText(barra, NOMBRES[nombre], (24, 38), cv2.FONT_HERSHEY_DUPLEX, 0.8 if angosto else 0.95, TEXTO, 2,
                cv2.LINE_AA)
    h, s = divmod(m["t"], 3600)
    sep = "   " if angosto else "    "
    texto = (f"{h}:{s // 60:02d}:{s % 60:02d}{sep}detenidos en la red: {m['detenidos']:4d}{sep}"
             f"viajes terminados: {m['llegados']:5d}")
    escala = 0.5 if angosto else 0.62
    (tw, _), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 1 if angosto else 2)
    cv2.putText(barra, texto, (img.shape[1] - tw - 16, 37), cv2.FONT_HERSHEY_SIMPLEX, escala, TEXTO2,
                1 if angosto else 2, cv2.LINE_AA)
    cv2.line(barra, (0, alto - 1), (img.shape[1], alto - 1), (225, 225, 225), 1)
    return np.vstack([barra, img])


def componer(camaras, out, fps):
    n = min(c.n for _, c in camaras)
    escritor = None
    for k in range(n):
        partes = [rotulo(cv2.imread(os.path.join(cam.carpeta, f"f{k:05d}.jpg")), nombre, cam.metricas[k])
                  for nombre, cam in camaras]
        ancho, alto = partes[0].shape[1], partes[0].shape[0]
        if len(partes) == 4:
            cuadro = np.vstack([np.hstack(partes[:2]), np.hstack(partes[2:])])
        else:
            cuadro = np.vstack(partes) if ancho / alto > 1.3 else np.hstack(partes)
        cuadro = cuadro[: cuadro.shape[0] // 2 * 2, : cuadro.shape[1] // 2 * 2]
        if escritor is None:
            # H.264 si OpenCV lo trae (se reproduce en cualquier lado); si no, MPEG-4
            for codec in ("avc1", "mp4v"):
                escritor = cv2.VideoWriter(out + ".mp4", cv2.VideoWriter_fourcc(*codec), fps,
                                           (cuadro.shape[1], cuadro.shape[0]))
                if escritor.isOpened():
                    print(f"  códec {codec}", flush=True)
                    break
        escritor.write(cuadro)
        if k == n // 2:
            cv2.imwrite(out + "_muestra.png", cuadro)
    escritor.release()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--controllers", default="fixed,ppo")
    ap.add_argument("--model", default=None)
    ap.add_argument("--replica", type=int, default=0)
    ap.add_argument("--begin", type=int, default=1500)
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--every", type=int, default=2, help="segundos simulados entre cuadros")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--ancho-m", type=float, default=900, help="metros de calle visibles a lo ancho")
    ap.add_argument("--center", required=True, help="x,y de la red")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    net = os.path.join(a.scenario, "net.net.xml")
    rou = ruta_evaluacion(a.scenario, a.profile, a.replica, None)
    eje = controlled_tls(a.scenario, "eje")
    centro = tuple(float(v) for v in a.center.split(","))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    lienzo = Lienzo(net, centro, a.ancho_m, a.width, a.height)

    camaras = []
    for nombre in a.controllers.split(","):
        carpeta = f"{a.out}_{nombre}_cuadros"
        shutil.rmtree(carpeta, ignore_errors=True)
        os.makedirs(carpeta)
        print(f"Grabando {nombre} …", flush=True)
        if nombre == "ppo":
            cam = grabar_ppo(a, net, rou, eje, carpeta, lienzo)
        else:
            cam = grabar_clasico(nombre, a, net, rou, eje, carpeta, lienzo)
        print(f"  {cam.n} cuadros", flush=True)
        camaras.append((nombre, cam))

    n = componer(camaras, a.out, a.fps)
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump({"rutas": rou, "vista": {"centro": centro, "ancho_m": a.ancho_m}, "argumentos": vars(a),
                   "metricas": {n_: c.metricas for n_, c in camaras}}, f, ensure_ascii=False)
    for _, cam in camaras:
        shutil.rmtree(cam.carpeta, ignore_errors=True)
    print(f"OK  {a.out}.mp4 ({n} cuadros)")


if __name__ == "__main__":
    main()
