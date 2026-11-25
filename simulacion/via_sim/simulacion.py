"""Simulación en vivo: el entorno de pruebas que provee datos de tráfico.

Mantiene una simulación SUMO de un escenario corriendo a velocidad real (o
acelerada), con los semáforos manejados por el plan Webster coordinado, y la
expone como un *proveedor de tráfico* que consulta el backend:

- semáforos: ubicación, accesos con su rumbo y, en cada instante, el color y
  los segundos que faltan para el cambio en cada acceso;
- tráfico: velocidad media y vehículos por calle;
- viajes simulados: un vehículo propio dentro de SUMO, para demos sin moverse.

En producción, este servicio se reemplaza por una fuente real (p. ej. UOCT)
que cumpla el mismo contrato.

Todo el acceso a SUMO ocurre en un único hilo (libsumo no admite llamadas
concurrentes). Los manejadores HTTP leen instantáneas protegidas por un candado
y envían órdenes al hilo de simulación por una cola.

Este módulo solo importa `tsc`; no modifica el arnés de la tesis.
"""
from __future__ import annotations

import html
import itertools
import json
import logging
import math
import os
import sys
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

# Raíz del código de la tesis (tsc-thesis/), de donde se importan el arnés y los escenarios.
RAIZ = Path(os.environ.get("TSC_RAIZ", Path(__file__).resolve().parents[2] / "tsc-thesis"))
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

# Recorridos por escenario (nombre de la carpeta). El del área parte en Providencia y
# termina en cruces del inventario UOCT de ambas comunas (uoct_match.json).
RECORRIDOS = {
    "eje_comunal": (ORIGEN, DESTINOS),
    "las_condes_providencia": (
        ("Av. Providencia con Manuel Montt", -70.620355, -33.428811),  # J001121
        [
            ("apoquindo_tomas_moro", "Av. Apoquindo con Tomás Moro", -70.551794, -33.408396),  # J060141
            ("padre_hurtado_las_condes", "Padre Hurtado con Av. Las Condes", -70.545483, -33.394198),  # J057251
            ("tobalaba_bilbao", "Tobalaba con Bilbao", -70.584766, -33.431779),  # J005431
        ],
    ),
}
# Perfil de demanda del escenario del área cuando no se indica otro: la punta tarde es el
# perfil validado con TomTom (la punta mañana también usa sus resultados, 24-nov-2026).
PERFIL_POR_DEFECTO = "eod_punta_tarde"

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


def rumbo(x0: float, y0: float, x1: float, y1: float) -> float:
    """Rumbo en grados (0 = norte, 90 = este) del vector de (x0, y0) a (x1, y1).

    Las coordenadas de la red SUMO son UTM con el norte hacia arriba.
    """
    return round(math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360, 1)


def nivel_de_servicio(velocidad: float, libre: float, vehiculos: int) -> str:
    """Clasifica una calle según su velocidad media respecto de la libre."""
    if vehiculos == 0 or libre <= 0:
        return "libre"
    razon = velocidad / libre
    if razon >= 0.7:
        return "fluido"
    if razon >= 0.4:
        return "moderado"
    return "congestionado"


# Preferencia al elegir el enlace que representa un acceso: seguir derecho primero.
PRIORIDAD_DIRECCION = {"s": 0, "r": 1, "R": 1, "l": 2, "L": 2, "t": 3}

CADA_TRAFICO_S = 5  # cada cuántos segundos simulados se recalcula el tráfico

# Viajes con origen y destino libres (recorridos A → B elegidos en la app).
RADIO_CALLE_M = 150  # un punto debe tener una calle para autos a esta distancia
DISTANCIA_MINIMA_M = 200  # origen y destino más cerca que esto no forman un recorrido
CANDIDATOS_POR_PUNTO = 4  # arcos cercanos que se prueban en cada extremo


def dentro_de_poligono(lon: float, lat: float, anillo: list) -> bool:
    """Prueba del rayo: si el punto (lon, lat) queda dentro del anillo [[lon, lat], ...]."""
    dentro = False
    n = len(anillo)
    for i in range(n):
        x0, y0 = anillo[i][0], anillo[i][1]
        x1, y1 = anillo[(i + 1) % n][0], anillo[(i + 1) % n][1]
        if (y0 > lat) != (y1 > lat):
            x = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
            if lon < x:
                dentro = not dentro
    return dentro


def leer_comunas(escenario: Path) -> list[tuple[str, list]]:
    """Polígonos de las comunas del escenario (comunas.geojson), si los trae.

    Devuelve [(nombre, anillo_exterior)]. Sin el archivo, la lista queda vacía y
    solo se exige que el punto esté cerca de una calle de la red.
    """
    archivo = escenario / "comunas.geojson"
    if not archivo.exists():
        return []
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    comunas = []
    for f in datos.get("features", []):
        g = f.get("geometry") or {}
        nombre = (f.get("properties") or {}).get("comuna", "")
        poligonos = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", [])
        for poligono in poligonos:
            if poligono:
                comunas.append((nombre, poligono[0]))
    return comunas


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
    destino: int | None  # índice del recorrido de demostración; None en un viaje libre
    largo_m: float
    nombre_destino: str = ""
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
        perfil: str | None = None,
    ):
        self.escenario = Path(escenario)
        self.net_file = str(self.escenario / "net.net.xml")
        # eje_comunal trae routes.rou.xml y webster_plan.json; el área, un archivo por perfil
        # de demanda (demand/routes_<perfil>.rou.xml y webster_plan_<perfil>.json).
        self.perfil = perfil
        rutas = self.escenario / "routes.rou.xml"
        if perfil or not rutas.exists():
            self.perfil = perfil or PERFIL_POR_DEFECTO
            rutas = self.escenario / "demand" / f"routes_{self.perfil}.rou.xml"
        self.route_file = str(rutas)
        if plan is None:
            plan = self._plan_de(self.perfil)
        self.plan = str(plan)
        self.origen, self.destinos_def = RECORRIDOS.get(self.escenario.name, (ORIGEN, DESTINOS))
        self.comunas = leer_comunas(self.escenario)
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
        # Ajustes en vivo: la velocidad se aplica en el paso siguiente; un cambio de
        # perfil termina el episodio y el siguiente arranca con la nueva demanda.
        self._reanclar = False
        self._reiniciar = threading.Event()
        self._reiniciando = False

        self._red = None
        self._nombres: dict[str, list] = {}
        self._rutas: list[dict] = []
        self._programas: dict[str, list] = {}

        # Datos estáticos de la red (se calculan una vez) y dinámicos (cada paso)
        self._semaforos: list[dict] = []
        self._accesos: dict[str, list] = {}  # tid -> [(arco, enlace)]
        self._calles: list[dict] = []
        self._ids_calles: list[str] = []
        self._estado_semaforos: dict = {}
        self._trafico: dict = {"tiempo_sim": None, "calles": []}

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

    # ---------------------------------------------------------- ajustes
    def _plan_de(self, perfil: str | None) -> Path:
        plan = self.escenario / "webster_plan.json"
        if perfil and (self.escenario / f"webster_plan_{perfil}.json").exists():
            plan = self.escenario / f"webster_plan_{perfil}.json"
        return plan

    def perfiles_disponibles(self) -> list[str]:
        """Perfiles de demanda con archivo de rutas en demand/ (vacío en el eje)."""
        if (self.escenario / "routes.rou.xml").exists() and not self.perfil:
            return []
        carpeta = self.escenario / "demand"
        return sorted(
            f.name[len("routes_"):-len(".rou.xml")]
            for f in carpeta.glob("routes_*.rou.xml")
        ) if carpeta.exists() else []

    def ajustes(self) -> dict:
        """Velocidad y perfil de demanda vigentes, y si la simulación está lista
        (false mientras se reinicia por un cambio de perfil)."""
        with self._candado:
            lista = bool(self._estado.get("lista")) and not self._reiniciando
        return {
            "velocidad": self.velocidad,
            "perfil": self.perfil,
            "perfiles": self.perfiles_disponibles(),
            "lista": lista,
        }

    def cambiar_ajustes(self, velocidad: float | None = None, perfil: str | None = None) -> dict:
        """Cambia la velocidad (al instante) y el perfil de demanda.

        Cambiar el perfil reinicia la simulación con su demanda y su plan Webster:
        tarda unos segundos y los viajes en curso quedan «reiniciado». Elegir el
        perfil vigente no reinicia nada.
        """
        if velocidad is not None:
            if not 0 <= velocidad <= 50:
                raise ValueError("velocidad debe estar entre 0 y 50")
            self.velocidad = float(velocidad)
            self._reanclar = True
        if perfil is not None and perfil != self.perfil:
            disponibles = self.perfiles_disponibles()
            if perfil not in disponibles:
                raise ValueError(f"perfil desconocido: {perfil} (disponibles: {', '.join(disponibles) or 'ninguno'})")
            self.route_file = str(self.escenario / "demand" / f"routes_{perfil}.rou.xml")
            self.plan = str(self._plan_de(perfil))
            self.perfil = perfil
            with self._candado:
                self._reiniciando = True
                self._estado["lista"] = False
            self._reiniciar.set()
            log.info("cambio de perfil a %s: se reinicia la simulación", perfil)
        return self.ajustes()

    def destinos(self) -> list[dict]:
        """Recorridos de demostración, con el trazado que sigue el vehículo
        ([lat, lon]) y los semáforos por los que pasa, en orden."""
        por_id = {s["id"]: s for s in self._semaforos}
        return [
            {
                "ruta": i,
                "id": self.destinos_def[i][0],
                "nombre": self.destinos_def[i][1],
                "origen": self.origen[0],
                "distancia_km": round(r["largo_m"] / 1000, 1),
                "trazado": r.get("trazado", []),
                "semaforos": [
                    {
                        "id": tid,
                        "nombre": por_id[tid]["nombre"],
                        "lat": por_id[tid]["lat"],
                        "lon": por_id[tid]["lon"],
                        "distancia_desde_inicio_m": distancia,
                    }
                    for tid, distancia in r.get("semaforos", [])
                    if tid in por_id
                ],
            }
            for i, r in enumerate(self._rutas)
        ]

    def crear_viaje(self, ruta: int, esperar: float = 10.0) -> dict:
        if not 0 <= ruta < len(self.destinos_def):
            raise ValueError(f"ruta debe estar entre 0 y {len(self.destinos_def) - 1}")
        futuro: Future = Future()
        self._ordenes.put(("crear", ruta, futuro))
        return futuro.result(timeout=esperar)

    def crear_viaje_libre(
        self,
        origen: tuple[float, float],
        destino: tuple[float, float],
        nombre_destino: str = "",
        esperar: float = 20.0,
    ) -> dict:
        """Viaje simulado entre dos puntos cualesquiera del área, dados como (lat, lon).

        Devuelve lo mismo que `crear_viaje` más `recorrido`: el trazado que sigue el
        vehículo, los semáforos que cruza y su largo. Lanza ValueError si un punto
        queda fuera de las comunas o lejos de una calle, o si no hay ruta.
        """
        for nombre, (lat, lon) in (("origen", origen), ("destino", destino)):
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"el {nombre} tiene coordenadas inválidas")
            if self.comunas and not any(dentro_de_poligono(lon, lat, a) for _, a in self.comunas):
                comunas = " y ".join(sorted({n.title() for n, _ in self.comunas}))
                raise ValueError(f"el {nombre} queda fuera del área simulada ({comunas})")
        futuro: Future = Future()
        self._ordenes.put(("crear_libre", (origen, destino, nombre_destino), futuro))
        return futuro.result(timeout=esperar)

    def viaje(self, viaje_id: str) -> dict | None:
        with self._candado:
            v = self._viajes.get(viaje_id)
            return dict(v.instantanea) if v else None

    def finalizar_viaje(self, viaje_id: str, esperar: float = 10.0) -> bool:
        futuro: Future = Future()
        self._ordenes.put(("finalizar", viaje_id, futuro))
        return futuro.result(timeout=esperar)

    def semaforos(self) -> list[dict]:
        return self._semaforos

    def estado_semaforos(self, ids: list[str] | None = None) -> dict:
        with self._candado:
            todos = self._estado_semaforos
            tiempo = self._estado.get("tiempo_sim")
        elegidos = todos if not ids else {t: todos[t] for t in ids if t in todos}
        return {"tiempo_sim": tiempo, "semaforos": elegidos}

    def calles(self) -> list[dict]:
        return self._calles

    def trafico(self) -> dict:
        with self._candado:
            return dict(self._trafico)

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
        self._reiniciar.clear()
        sim = SumoSimulation(self.net_file, self.route_file, end=self.fin, seed=semilla)
        with sim:
            controlador = WebsterController(self.plan)
            controlador.setup(sim)
            self._programas = self._leer_programas(sim)
            if not self._rutas:
                self._rutas = self._calcular_rutas(sim)
                self._nombres = self._nombrar_semaforos(sim)
                self._describir_red(sim)
            log.info("calentando %s s simulados (semilla %s)", self.calentamiento, semilla)
            sim.step(self.calentamiento)
            self._trafico = {"tiempo_sim": None, "calles": []}
            self._actualizar(sim)
            with self._candado:
                # Si mientras calentaba llegó otro cambio de perfil, sigue reiniciándose.
                self._reiniciando = self._reiniciar.is_set()
            self._lista.set()

            reloj0, t0 = time.monotonic(), sim.time
            while not self._detener.is_set() and sim.time < self.fin:
                if self._reiniciar.is_set():
                    break
                self._atender_ordenes(sim)
                sim.step()
                self._actualizar(sim)
                if self._reanclar:
                    # Nueva velocidad: el ritmo se mide desde ahora.
                    reloj0, t0 = time.monotonic(), sim.time
                    self._reanclar = False
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

    def _candidatos(self, lon: float, lat: float, cuantos: int = 6) -> list[str]:
        """Arcos para autos más cercanos a un punto, a menos de RADIO_CALLE_M."""
        x, y = self._red.convertLonLat2XY(lon, lat)
        cerca = self._red.getNeighboringEdges(x, y, RADIO_CALLE_M)
        cerca = [(e, d) for e, d in cerca if e.allows("passenger") and e.getFunction() != "internal"]
        return [e.getID() for e, _ in sorted(cerca, key=lambda par: par[1])[:cuantos]]

    def _calcular_rutas(self, sim) -> list[dict]:
        """Ruta más rápida desde el origen a cada destino, a flujo libre."""
        candidatos = self._candidatos
        origenes = candidatos(self.origen[1], self.origen[2])
        if not origenes:
            raise RuntimeError(f"el origen «{self.origen[0]}» queda fuera de la red")
        rutas = []
        for clave, nombre, lon, lat in self.destinos_def:
            mejor = None
            for o in origenes:
                for d in candidatos(lon, lat):
                    r = sim.conn.simulation.findRoute(o, d)
                    if r.edges and (mejor is None or r.travelTime < mejor.travelTime):
                        mejor = r
            if mejor is None:
                raise RuntimeError(f"no hay ruta hacia «{nombre}»")
            trazado, semaforos = self._geometria_ruta(sim, list(mejor.edges))
            rutas.append({
                "edges": list(mejor.edges),
                "largo_m": mejor.length,
                "trazado": trazado,
                "semaforos": semaforos,
            })
            log.info("ruta a %s: %.1f km, %d arcos", nombre, mejor.length / 1000, len(mejor.edges))
        return rutas

    def _geometria_ruta(self, sim, arcos: list[str]) -> tuple[list, list]:
        """Trazado [lat, lon] de una ruta de SUMO y los semáforos que cruza.

        El trazado une la forma de cada arco. Un semáforo cuenta si controla la
        conexión entre un arco de la ruta y el siguiente, que es exactamente el
        que verá el vehículo; su distancia es lo recorrido hasta la línea de
        detención.
        """
        red = self._red
        geo = sim.conn.simulation.convertGeo
        trazado: list[list[float]] = []
        semaforos: list[tuple[str, int]] = []
        recorrido = 0.0
        for i, arco_id in enumerate(arcos):
            arco = red.getEdge(arco_id)
            for x, y in arco.getShape():
                lon, lat = geo(x, y)
                punto = [round(lat, 6), round(lon, 6)]
                if not trazado or trazado[-1] != punto:
                    trazado.append(punto)
            recorrido += arco.getLength()
            if i + 1 == len(arcos):
                break
            for conexion in arco.getConnections(red.getEdge(arcos[i + 1])):
                tid = conexion.getTLSID()
                if tid and tid in sim.tls and all(t != tid for t, _ in semaforos):
                    semaforos.append((tid, round(recorrido)))
                    break
        return trazado, semaforos

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

    def _describir_red(self, sim) -> None:
        """Ubicación y accesos de cada semáforo, y geometría de las calles."""
        red = self._red
        geo = sim.conn.simulation.convertGeo
        # Una pasada por todas las conexiones: semáforo -> arco de entrada -> enlaces
        conexiones: dict[str, dict[str, list]] = {}
        nodos_de: dict[str, set] = {}
        for arco in red.getEdges():
            for carril in arco.getLanes():
                for c in carril.getOutgoing():
                    tid = c.getTLSID()
                    if tid and tid in sim.tls:
                        conexiones.setdefault(tid, {}).setdefault(arco.getID(), []).append(
                            (PRIORIDAD_DIRECCION.get(c.getDirection(), 9), c.getTLLinkIndex())
                        )
                        nodos_de.setdefault(tid, set()).add(arco.getToNode())
        semaforos = []
        for tid in sorted(conexiones):
            por_arco, nodos = conexiones[tid], nodos_de[tid]
            accesos, enlaces = [], []
            for arco_id, opciones in sorted(por_arco.items()):
                arco = red.getEdge(arco_id)
                forma = arco.getShape()
                (x0, y0), (x1, y1) = forma[-2], forma[-1]
                enlace = min(opciones)[1]
                accesos.append({
                    "id": arco_id,
                    "calle": acortar(arco.getName() or ""),
                    "rumbo": rumbo(x0, y0, x1, y1),
                })
                enlaces.append((arco_id, enlace))
            x = sum(n.getCoord()[0] for n in nodos) / len(nodos)
            y = sum(n.getCoord()[1] for n in nodos) / len(nodos)
            lon, lat = geo(x, y)
            calles = self._nombres.get(tid, [])
            semaforos.append({
                "id": tid,
                "nombre": " × ".join(calles) or tid,
                "calles": calles,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "accesos": accesos,
            })
            self._accesos[tid] = enlaces
        self._semaforos = semaforos

        calles = []
        for arco in red.getEdges():
            if arco.getFunction() == "internal" or not arco.allows("passenger"):
                continue
            forma = [geo(x, y) for x, y in arco.getShape()]
            calles.append({
                "id": arco.getID(),
                "nombre": acortar(arco.getName() or ""),
                "velocidad_libre_kmh": round(arco.getSpeed() * 3.6, 1),
                "forma": [[round(la, 6), round(lo, 6)] for lo, la in forma],
            })
        self._calles = calles
        self._ids_calles = [c["id"] for c in calles]
        log.info("red descrita: %d semáforos, %d calles", len(semaforos), len(calles))

    def _medir_semaforos(self, sim) -> dict:
        c = sim.conn.trafficlight
        estado = {}
        for tid, enlaces in self._accesos.items():
            senales = c.getRedYellowGreenState(tid)
            fases = self._programas.get(tid)
            fase, restante = c.getPhase(tid), c.getNextSwitch(tid) - sim.time
            accesos = {}
            for arco, enlace in enlaces:
                segundos, siguiente = (None, None)
                if fases:
                    segundos, siguiente = tiempo_hasta_cambio(fases, fase, restante, enlace)
                accesos[arco] = {
                    "color": categoria(senales[enlace]),
                    "segundos_para_cambio": segundos_visibles(segundos),
                    "siguiente_color": siguiente,
                    "exacto": True,
                }
            estado[tid] = accesos
        return estado

    def _medir_trafico(self, sim) -> dict:
        arcos = sim.conn.edge
        libres = {c["id"]: c["velocidad_libre_kmh"] for c in self._calles}
        calles = []
        for arco in self._ids_calles:
            n = arcos.getLastStepVehicleNumber(arco)
            v = arcos.getLastStepMeanSpeed(arco) * 3.6 if n else libres[arco]
            calles.append({
                "id": arco,
                "velocidad_kmh": round(v, 1),
                "vehiculos": n,
                "nivel": nivel_de_servicio(v, libres[arco], n),
            })
        return {"tiempo_sim": sim.time, "calles": calles}

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
                elif orden == "crear_libre":
                    futuro.set_result(self._crear_libre(sim, *arg))
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
        v = Viaje(viaje_id, vehiculo, ruta, self._rutas[ruta]["largo_m"], self.destinos_def[ruta][1])
        v.instantanea = self._base(v, sim)
        with self._candado:
            self._viajes[viaje_id] = v
        return dict(v.instantanea)

    def _crear_libre(self, sim, origen, destino, nombre_destino: str) -> dict:
        """Calcula la ruta más rápida entre dos puntos y pone un vehículo en ella."""
        (lat0, lon0), (lat1, lon1) = origen, destino
        x0, y0 = self._red.convertLonLat2XY(lon0, lat0)
        x1, y1 = self._red.convertLonLat2XY(lon1, lat1)
        if math.hypot(x1 - x0, y1 - y0) < DISTANCIA_MINIMA_M:
            raise ValueError(f"el origen y el destino están a menos de {DISTANCIA_MINIMA_M} m")
        desde = self._candidatos(lon0, lat0, CANDIDATOS_POR_PUNTO)
        if not desde:
            raise ValueError(f"el origen no tiene una calle de la red a menos de {RADIO_CALLE_M} m")
        hasta = self._candidatos(lon1, lat1, CANDIDATOS_POR_PUNTO)
        if not hasta:
            raise ValueError(f"el destino no tiene una calle de la red a menos de {RADIO_CALLE_M} m")
        mejor = None
        for o in desde:
            for d in hasta:
                if o == d:
                    continue
                r = sim.conn.simulation.findRoute(o, d)
                if r.edges and (mejor is None or r.travelTime < mejor.travelTime):
                    mejor = r
        if mejor is None:
            raise ValueError("no hay ruta en auto entre esos puntos dentro de la red simulada")
        arcos = list(mejor.edges)
        trazado, semaforos = self._geometria_ruta(sim, arcos)
        nombre = nombre_destino.strip() or self._nombre_de_arco(arcos[-1]) or "Destino elegido"

        n = next(self._ids)
        viaje_id, vehiculo = f"v{n}", f"app_{n}"
        ruta_sumo = f"ruta_app_{n}"
        sim.conn.route.add(ruta_sumo, arcos)
        sim.conn.vehicle.add(vehiculo, ruta_sumo, typeID="DEFAULT_VEHTYPE", depart="now")
        sim.conn.vehicle.setColor(vehiculo, (245, 203, 69, 255))
        v = Viaje(viaje_id, vehiculo, None, mejor.length, nombre)
        v.instantanea = self._base(v, sim)
        with self._candado:
            self._viajes[viaje_id] = v
        log.info("viaje libre %s hacia %s: %.1f km, %d semáforos", viaje_id, nombre, mejor.length / 1000, len(semaforos))

        por_id = {s["id"]: s for s in self._semaforos}
        foto = dict(v.instantanea)
        foto["recorrido"] = {
            "distancia_km": round(mejor.length / 1000, 1),
            "trazado": trazado,
            "semaforos": [
                {
                    "id": tid,
                    "nombre": por_id[tid]["nombre"],
                    "lat": por_id[tid]["lat"],
                    "lon": por_id[tid]["lon"],
                    "distancia_desde_inicio_m": distancia,
                }
                for tid, distancia in semaforos
                if tid in por_id
            ],
        }
        return foto

    def _nombre_de_arco(self, arco_id: str) -> str:
        if not self._red.hasEdge(arco_id):
            return ""
        return acortar(self._red.getEdge(arco_id).getName() or "")

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
            "destino": v.nombre_destino,
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
        semaforos = self._medir_semaforos(sim)
        trafico = None
        if int(sim.time) % CADA_TRAFICO_S == 0 or self._trafico["tiempo_sim"] is None:
            trafico = self._medir_trafico(sim)
        with self._candado:
            self._estado_semaforos = semaforos
            if trafico is not None:
                self._trafico = trafico
            self._estado = {
                "lista": not self._reiniciando,
                "escenario": self.escenario.name,
            "perfil": self.perfil,
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
