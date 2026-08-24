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
    }


PRIMARY_METRICS = (
    "time_loss_mean",       # demora media por vehículo — métrica primaria
    "travel_time_mean",
    "waiting_time_mean",
    "queue_mean",
    "throughput",
)
