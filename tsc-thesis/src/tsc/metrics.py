"""Métricas de evaluación.

Se distingue deliberadamente entre dos fuentes:

* **tripinfo** (post-simulación): la fuente de verdad para las métricas
  primarias por vehículo. Sólo incluye viajes *terminados*, lo que sesga
  a favor de controladores que dejan vehículos atrapados en la red; por eso
  también se reporta `vehicles_not_finished`.
* **muestreo por paso** (durante la simulación): colas y tiempos de espera
  instantáneos, que sí capturan lo que ocurre con los vehículos atrapados.

Reportar sólo la primera es el error más común en la literatura aplicada.
"""
from __future__ import annotations

import statistics
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class StepSampler:
    """Acumula estado de la red durante la simulación."""

    queue_series: list = field(default_factory=list)
    waiting_series: list = field(default_factory=list)
    running_series: list = field(default_factory=list)
    switches: int = 0
    _last_green: dict = field(default_factory=dict)

    def track_phases(self, sim) -> None:
        """Cuenta cambios de fase verde observando la red, no al controlador.

        Así la cifra es comparable entre controladores: el de tiempo fijo deja
        que SUMO ejecute su programa y aun así sus conmutaciones se cuentan.
        Se llama en cada intervalo de decisión; un verde más corto que ese
        intervalo podría no verse, pero todos los controladores respetan un
        verde mínimo mayor.
        """
        for tid, tl in sim.tls.items():
            if not tl.green_indices:
                continue
            p = tl.current_phase()
            if p not in tl.green_indices:
                continue
            last = self._last_green.get(tid)
            if last is not None and p != last:
                self.switches += 1
            self._last_green[tid] = p

    def end_state(self, sim, planned_depart: dict) -> dict:
        """Demora de los vehículos que no terminaron su viaje al cerrar.

        tripinfo solo trae viajes terminados. Un controlador que satura la red
        deja vehículos dentro o esperando entrar, y su demora desaparece de la
        media. Aquí se recupera: para los que circulan, timeLoss + retardo de
        salida; para los que esperan entrar, el tiempo desde su salida prevista.
        """
        return end_state_from_conn(sim.conn, sim.time, planned_depart)  # `time` es propiedad

    def sample(self, sim) -> None:
        q = sum(tl.total_queue() for tl in sim.tls.values())
        w = sum(tl.waiting_time() for tl in sim.tls.values())
        self.queue_series.append(q)
        self.waiting_series.append(w)
        self.running_series.append(sim.conn.vehicle.getIDCount())

    def summary(self) -> dict:
        if not self.queue_series:
            return {}
        return {
            "queue_mean": statistics.fmean(self.queue_series),
            "queue_max": max(self.queue_series),
            "waiting_mean_network": statistics.fmean(self.waiting_series),
            "vehicles_in_network_mean": statistics.fmean(self.running_series),
            "phase_switches": self.switches,
        }


def parse_tripinfo(path: str) -> dict:
    """Métricas por vehículo desde el archivo tripinfo de SUMO."""
    root = ET.parse(path).getroot()
    dur, wait, loss, depart_delay, stops = [], [], [], [], []
    for trip in root.iter("tripinfo"):
        dur.append(float(trip.get("duration")))
        wait.append(float(trip.get("waitingTime")))
        loss.append(float(trip.get("timeLoss")))
        depart_delay.append(float(trip.get("departDelay")))
        stops.append(float(trip.get("waitingCount", 0)))

    if not dur:
        return {"vehicles_finished": 0}

    def pct(xs, p):
        xs = sorted(xs)
        k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
        return xs[k]

    return {
        "vehicles_finished": len(dur),
        "travel_time_mean": statistics.fmean(dur),
        "travel_time_p95": pct(dur, 95),
        "waiting_time_mean": statistics.fmean(wait),
        "waiting_time_p95": pct(wait, 95),   # equidad: ¿a quién se sacrifica?
        "time_loss_mean": statistics.fmean(loss),
        "depart_delay_mean": statistics.fmean(depart_delay),
        "stops_mean": statistics.fmean(stops),
        "_finished_delay_sum": sum(loss) + sum(depart_delay),
    }


def end_state_from_conn(conn, now: float, planned_depart: dict) -> dict:
    """Vehículos dentro de la red o esperando entrar al cerrar, y su demora.

    Funciona con cualquier conexión TraCI/libsumo, así que lo usan tanto el
    runner de los controladores clásicos como la evaluación del agente.
    """
    running = list(conn.vehicle.getIDList())
    try:
        pending = list(conn.simulation.getPendingVehicles())
    except Exception:  # noqa: BLE001 — versiones sin getPendingVehicles
        pending = []
    delay_sum = 0.0
    for v in running:
        delay_sum += conn.vehicle.getTimeLoss(v) + max(0.0, conn.vehicle.getDepartDelay(v))
    for v in pending:
        delay_sum += max(0.0, now - planned_depart.get(v, now))
    return {
        "vehicles_running_end": len(running),
        "vehicles_pending_end": len(pending),
        "_unfinished_delay_sum": delay_sum,
        "_unfinished_n": len(running) + len(pending),
    }


class GreenSwitchCounter:
    """Cuenta cambios de fase verde leyendo el estado de los semáforos.

    Versión para entornos que no exponen `sim.tls` (la evaluación del agente
    sobre sumo-rl). Una fase cuenta como verde si tiene algún 'G'/'g' y ningún
    'y'; misma definición que `green_indices` en el runner. Compara la cadena
    de estado y no el índice de fase, porque sumo-rl fija el estado con
    `setRedYellowGreenState` y el índice de fase no cambia.
    """

    def __init__(self) -> None:
        self.switches = 0
        self._last: dict = {}

    def update(self, conn, tls_ids) -> None:
        for tid in tls_ids:
            state = conn.trafficlight.getRedYellowGreenState(tid)
            low = state.lower()
            if "y" in low or "g" not in low:
                continue
            last = self._last.get(tid)
            if last is not None and state != last:
                self.switches += 1
            self._last[tid] = state


def planned_departures(route_file: str) -> dict:
    """Hora de salida prevista de cada vehículo o viaje del archivo de rutas."""
    out = {}
    for _, el in ET.iterparse(route_file):
        if el.tag in ("vehicle", "trip") and el.get("id") is not None:
            try:
                out[el.get("id")] = float(el.get("depart", "0"))
            except ValueError:  # 'triggered', 'now', etc.
                pass
        el.clear()
    return out


def combine_delay(result: dict) -> None:
    """Agrega `delay_all_mean`: demora media de TODOS los vehículos cargados.

    Suma timeLoss + retardo de salida de los viajes terminados y la demora de
    los que siguen dentro o esperando entrar (ver StepSampler.end_state). Es la
    métrica que no premia a un controlador por dejar la saturación fuera de la
    red. Las claves auxiliares (con «_») se eliminan.
    """
    n_fin = result.get("vehicles_finished", 0)
    n_unf = result.pop("_unfinished_n", 0)
    total = result.pop("_finished_delay_sum", 0.0) + result.pop("_unfinished_delay_sum", 0.0)
    n = n_fin + n_unf
    result["vehicles_considered"] = n
    result["delay_all_mean"] = total / n if n else float("nan")


PRIMARY_METRICS = (
    "delay_all_mean",       # demora media incluyendo vehículos no terminados
    "time_loss_mean",       # demora media de viajes terminados (comparable con informes previos)
    "travel_time_mean",
    "waiting_time_mean",
    "queue_mean",
    "throughput",
)
