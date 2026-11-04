"""Simulación en vivo que consulta la app móvil.

Mantiene una simulación SUMO de un escenario corriendo a velocidad real (o
acelerada), con los semáforos manejados por el plan Webster coordinado. Cada
viaje que abre la app agrega a la simulación un vehículo propio; con él, SUMO
entrega directamente lo que la app muestra: el próximo semáforo de la ruta, su
distancia, su color y cuántos segundos faltan para que cambie.

Todo el acceso a SUMO ocurre en un único hilo (libsumo no admite llamadas
concurrentes). Los manejadores HTTP leen instantáneas protegidas por un candado
y envían órdenes al hilo de simulación por una cola.

Este módulo solo importa `tsc`; no modifica el arnés de la tesis.
"""
from __future__ import annotations

import html
import itertools
import logging
import os
import sys
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from tsc.controllers import WebsterController  # noqa: E402
from tsc.sumo_env import SumoSimulation  # noqa: E402

import sumolib  # noqa: E402  (disponible tras importar tsc.sumo_env)

log = logging.getLogger("via.simulacion")

# Recorridos del prototipo. Coordenadas WGS84 (lon, lat); los cruces de destino
# son los de la muestra de terreno (data/terreno/cruces_muestra.csv).
ORIGEN = ("Alameda frente a Plaza de Armas", -70.6505, -33.4433)
# Solo destinos alcanzables desde el origen: en eje_comunal (3-nov-2026) no hay
# ruta desde la Alameda hacia el oriente de Bustamante (ver README de la API).
DESTINOS = [
    ("bustamante", "Av. General Bustamante", -70.63313, -33.43696),  # C03, al oriente
    ("matucana", "Matucana", -70.67882, -33.45068),  # C11, al poniente
]

NOMBRES_CORTOS = {
    "Avenida Libertador Bernardo O'Higgins": "Alameda",
    "Avenida ": "Av. ",
}


def categoria(senal: str) -> str:
    """Color que ve el conductor para un carácter de estado de SUMO."""
    if senal in "Gg":
        return "verde"
    if senal in "yYu":
        return "amarillo"
    if senal in "rRs":
        return "rojo"
    return "apagado"


def tiempo_hasta_cambio(fases: list, fase_actual: int, restante: float, indice: int):
    """Segundos hasta que cambia el color de un enlace, y el color siguiente.

    `fases` es la lista de (estado, duración) del programa vigente; `restante`,
    lo que le queda a la fase actual. Recorre el programa hacia adelante hasta
    que el color del enlace `indice` cambia. Si en un ciclo completo no cambia,
    devuelve (None, color_actual).
    """
    actual = categoria(fases[fase_actual][0][indice])
    total = max(0.0, restante)
    n = len(fases)
    for k in range(1, n + 1):
        estado, duracion = fases[(fase_actual + k) % n]
        color = categoria(estado[indice])
        if color != actual:
            return total, color
        total += duracion
    return None, actual


def segundos_visibles(segundos: float | None) -> int | None:
    """Pasa del tiempo del programa a lo que se ve en la simulación.

    Con pasos de 1 s, SUMO aplica cada cambio de fase en un segundo entero y el
    nuevo color aparece en el estado del paso siguiente. Medido sobre la red del
    eje con el plan Webster (170 cambios, 3-nov-2026): sin esta
    corrección el cambio llega 0,6 a 1,7 s tarde; con ella, 150 de 170
    predicciones son exactas y el resto se desvía 1 s.
    """
    if segundos is None:
        return None
    return int(round(segundos)) + 1


def acortar(nombre: str) -> str:
    # Algunos nombres de OSM llegan con entidades XML sin decodificar (O&apos;Higgins).
    nombre = html.unescape(nombre)
    for largo, corto in NOMBRES_CORTOS.items():
        nombre = nombre.replace(largo, corto)
    return nombre


@dataclass
class Viaje:
    id: str
    vehiculo: str
    destino: int
    largo_m: float
    estado: str = "esperando"  # esperando | en_ruta | llego | finalizado | reiniciado
    instantanea: dict = field(default_factory=dict)


class SimulacionEnVivo:
    """Dueña del hilo de simulación."""

    def __init__(
        self,
        escenario: str | os.PathLike = RAIZ / "scenarios" / "eje_comunal",
        *,
        velocidad: float = 1.0,
        calentamiento: int = 300,
        fin: int = 3600,
        semilla: int = 0,
        plan: str | os.PathLike | None = None,
    ):
        self.escenario = Path(escenario)
        self.net_file = str(self.escenario / "net.net.xml")
        self.route_file = str(self.escenario / "routes.rou.xml")
        self.plan = str(plan or self.escenario / "webster_plan.json")
        self.velocidad = velocidad  # 1 = tiempo real; 0 = lo más rápido posible
        self.calentamiento = calentamiento
        self.fin = fin
        self.semilla = semilla

        self._candado = threading.Lock()
        self._ordenes: Queue = Queue()
        self._detener = threading.Event()
        self._lista = threading.Event()
        self._hilo: threading.Thread | None = None
        self._ids = itertools.count(1)
        self._viajes: dict[str, Viaje] = {}
        self._estado: dict = {"lista": False}
        self._error: BaseException | None = None

        self._red = None
        self._nombres: dict[str, list] = {}
        self._rutas: list[dict] = []
        self._programas: dict[str, list] = {}

    # ------------------------------------------------------------------ API
    def iniciar(self, esperar: float = 180.0) -> "SimulacionEnVivo":
        self._hilo = threading.Thread(target=self._bucle, name="sumo", daemon=True)
        self._hilo.start()
        if not self._lista.wait(esperar):
            raise TimeoutError("la simulación no terminó de arrancar")
        if self._error:
            raise RuntimeError("la simulación no pudo arrancar") from self._error
        return self

    def detener(self) -> None:
        self._detener.set()
        if self._hilo:
            self._hilo.join(timeout=30)

    def estado(self) -> dict:
        with self._candado:
            return dict(self._estado)

    def destinos(self) -> list[dict]:
        return [
            {
                "ruta": i,
                "id": DESTINOS[i][0],
                "nombre": DESTINOS[i][1],
                "origen": ORIGEN[0],
                "distancia_km": round(r["largo_m"] / 1000, 1),
            }
            for i, r in enumerate(self._rutas)
        ]

    def crear_viaje(self, ruta: int, esperar: float = 10.0) -> dict:
        if not 0 <= ruta < len(DESTINOS):
            raise ValueError(f"ruta debe estar entre 0 y {len(DESTINOS) - 1}")
        futuro: Future = Future()
        self._ordenes.put(("crear", ruta, futuro))
        return futuro.result(timeout=esperar)

    def viaje(self, viaje_id: str) -> dict | None:
        with self._candado:
            v = self._viajes.get(viaje_id)
            return dict(v.instantanea) if v else None

    def finalizar_viaje(self, viaje_id: str, esperar: float = 10.0) -> bool:
        futuro: Future = Future()
        self._ordenes.put(("finalizar", viaje_id, futuro))
        return futuro.result(timeout=esperar)

    # --------------------------------------------------------------- hilo
    def _bucle(self) -> None:
        try:
            self._red = sumolib.net.readNet(self.net_file, withPrograms=False)
            semilla = self.semilla
            while not self._detener.is_set():
                self._correr_episodio(semilla)
                semilla += 1
        except BaseException as exc:  # noqa: BLE001
            log.exception("la simulación se detuvo por un error")
            self._error = exc
            self._lista.set()

    def _correr_episodio(self, semilla: int) -> None:
        sim = SumoSimulation(self.net_file, self.route_file, end=self.fin, seed=semilla)
        with sim:
            controlador = WebsterController(self.plan)
            controlador.setup(sim)
            self._programas = self._leer_programas(sim)
            if not self._rutas:
                self._rutas = self._calcular_rutas(sim)
                self._nombres = self._nombrar_semaforos(sim)
            log.info("calentando %s s simulados (semilla %s)", self.calentamiento, semilla)
            sim.step(self.calentamiento)
            self._lista.set()

            reloj0, t0 = time.monotonic(), sim.time
            while not self._detener.is_set() and sim.time < self.fin:
                self._atender_ordenes(sim)
                sim.step()
                self._actualizar(sim)
                if self.velocidad > 0:
                    objetivo = reloj0 + (sim.time - t0) / self.velocidad
                    pausa = objetivo - time.monotonic()
                    if pausa > 0:
                        time.sleep(pausa)

            with self._candado:
                for v in self._viajes.values():
                    if v.estado in ("esperando", "en_ruta"):
                        v.estado = "reiniciado"
                        v.instantanea["estado"] = "reiniciado"
        self._atender_ordenes(None)

    @staticmethod
    def _leer_programas(sim) -> dict:
        programas = {}
        for tid in sim.tls:
            vigente = sim.conn.trafficlight.getProgram(tid)
            for logica in sim.conn.trafficlight.getAllProgramLogics(tid):
                if logica.programID == vigente:
                    programas[tid] = [(f.state, f.duration) for f in logica.phases]
        return programas

    def _calcular_rutas(self, sim) -> list[dict]:
        """Ruta más rápida desde el origen a cada destino, a flujo libre."""

        def candidatos(lon, lat):
            x, y = self._red.convertLonLat2XY(lon, lat)
            cerca = self._red.getNeighboringEdges(x, y, 150)
            cerca = [(e, d) for e, d in cerca if e.allows("passenger") and e.getFunction() != "internal"]
            return [e.getID() for e, _ in sorted(cerca, key=lambda par: par[1])[:6]]

        origenes = candidatos(ORIGEN[1], ORIGEN[2])
        if not origenes:
            raise RuntimeError(f"el origen «{ORIGEN[0]}» queda fuera de la red")
        rutas = []
        for clave, nombre, lon, lat in DESTINOS:
            mejor = None
            for o in origenes:
                for d in candidatos(lon, lat):
                    r = sim.conn.simulation.findRoute(o, d)
                    if r.edges and (mejor is None or r.travelTime < mejor.travelTime):
                        mejor = r
            if mejor is None:
                raise RuntimeError(f"no hay ruta hacia «{nombre}»")
            rutas.append({"edges": list(mejor.edges), "largo_m": mejor.length})
            log.info("ruta a %s: %.1f km, %d arcos", nombre, mejor.length / 1000, len(mejor.edges))
        return rutas

    def _nombrar_semaforos(self, sim) -> dict:
        nombres = {}
        for tid in sim.tls:
            calles = set()
            for enlace in sim.conn.trafficlight.getControlledLinks(tid):
                for entrada, _salida, _via in enlace:
                    arco = sim.conn.lane.getEdgeID(entrada)
                    if self._red.hasEdge(arco):
                        nombre = self._red.getEdge(arco).getName()
                        if nombre:
                            calles.add(acortar(nombre))
            nombres[tid] = sorted(calles)
        return nombres

    def _atender_ordenes(self, sim) -> None:
        while True:
            try:
                orden, arg, futuro = self._ordenes.get_nowait()
            except Empty:
                return
            try:
                if sim is None:
                    raise RuntimeError("la simulación se está reiniciando; intenta de nuevo")
                if orden == "crear":
                    futuro.set_result(self._crear(sim, arg))
                elif orden == "finalizar":
                    futuro.set_result(self._finalizar(sim, arg))
            except Exception as exc:  # noqa: BLE001
                futuro.set_exception(exc)

    def _crear(self, sim, ruta: int) -> dict:
        n = next(self._ids)
        viaje_id, vehiculo = f"v{n}", f"app_{n}"
        ruta_sumo = f"ruta_app_{n}"
        sim.conn.route.add(ruta_sumo, self._rutas[ruta]["edges"])
        sim.conn.vehicle.add(vehiculo, ruta_sumo, typeID="DEFAULT_VEHTYPE", depart="now")
        sim.conn.vehicle.setColor(vehiculo, (245, 203, 69, 255))
        v = Viaje(viaje_id, vehiculo, ruta, self._rutas[ruta]["largo_m"])
        v.instantanea = self._base(v, sim)
        with self._candado:
            self._viajes[viaje_id] = v
        return dict(v.instantanea)

    def _finalizar(self, sim, viaje_id: str) -> bool:
        with self._candado:
            v = self._viajes.get(viaje_id)
        if v is None:
            return False
        if v.estado in ("esperando", "en_ruta"):
            try:
                sim.conn.vehicle.remove(v.vehiculo)
            except Exception:  # noqa: BLE001  (ya salió de la red)
                pass
        with self._candado:
            v.estado = "finalizado"
            v.instantanea["estado"] = "finalizado"
        return True

    def _base(self, v: Viaje, sim) -> dict:
        return {
            "id": v.id,
            "estado": v.estado,
            "ruta": v.destino,
            "destino": DESTINOS[v.destino][1],
            "tiempo_sim": sim.time,
            "distancia_total_m": round(v.largo_m),
        }

    def _actualizar(self, sim) -> None:
        c = sim.conn
        salieron = set(c.simulation.getDepartedIDList())
        llegaron = set(c.simulation.getArrivedIDList())
        with self._candado:
            viajes = [v for v in self._viajes.values() if v.estado in ("esperando", "en_ruta")]
        for v in viajes:
            if v.vehiculo in llegaron:
                v.estado = "llego"
            elif v.vehiculo in salieron:
                v.estado = "en_ruta"
            foto = self._base(v, sim)
            if v.estado == "en_ruta":
                foto.update(self._medir(sim, v))
            with self._candado:
                v.instantanea = foto
        with self._candado:
            self._estado = {
                "lista": True,
                "escenario": self.escenario.name,
                "controlador": "webster",
                "tiempo_sim": sim.time,
                "vehiculos": c.vehicle.getIDCount(),
                "velocidad": self.velocidad,
                "viajes_activos": len(viajes),
            }

    def _medir(self, sim, v: Viaje) -> dict:
        c = sim.conn
        x, y = c.vehicle.getPosition(v.vehiculo)
        lon, lat = c.simulation.convertGeo(x, y)
        foto = {
            "posicion": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "velocidad_kmh": round(c.vehicle.getSpeed(v.vehiculo) * 3.6, 1),
            "distancia_restante_m": round(max(0.0, v.largo_m - c.vehicle.getDistance(v.vehiculo))),
            "proximo_semaforo": None,
        }
        siguientes = c.vehicle.getNextTLS(v.vehiculo)
        if siguientes:
            tid, indice, distancia, senal = siguientes[0]
            fases = self._programas.get(tid)
            segundos, siguiente = (None, None)
            if fases:
                restante = c.trafficlight.getNextSwitch(tid) - sim.time
                segundos, siguiente = tiempo_hasta_cambio(
                    fases, c.trafficlight.getPhase(tid), restante, indice
                )
            calles = self._nombres.get(tid, [])
            foto["proximo_semaforo"] = {
                "id": tid,
                "nombre": " × ".join(calles) or tid,
                "calles": calles,
                "distancia_m": round(distancia),
                "color": categoria(senal),
                "segundos_para_cambio": segundos_visibles(segundos),
                "siguiente_color": siguiente,
                # Con un plan fijo (Webster) el cambio es exacto; con un
                # controlador adaptativo solo se conocería un mínimo.
                "exacto": True,
                "margen_s": 1,
            }
        return foto
