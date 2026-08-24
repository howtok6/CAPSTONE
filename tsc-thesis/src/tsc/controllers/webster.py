"""Plan de tiempo fijo optimizado con el método de Webster (1958).

Dos etapas:
  1. Una corrida de calibración mide el flujo de llegada por fase (veh/h).
  2. Con esos flujos se calcula la duración de ciclo que minimiza la demora
     y el reparto de verdes proporcional a los grados de saturación.

Fórmula de Webster para el ciclo óptimo:      C = (1.5 * L + 5) / (1 - Y)
donde L es el tiempo perdido total por ciclo e Y la suma de los flujos
críticos normalizados por el flujo de saturación.

Es la línea base *justa*: representa lo que un ingeniero de tránsito haría
con los mismos datos, y no el plan por defecto sin optimizar.
"""
from __future__ import annotations

import json

from .base import Controller

SATURATION_FLOW = 1800.0  # veh/h por pista de aproximación (valor típico)


def webster_plan(
    phase_flows: dict,
    *,
    lost_time_per_phase: float = 4.0,
    min_green: float = 8.0,
    max_cycle: float = 150.0,
    min_cycle: float = 40.0,
    saturation_flow: float = SATURATION_FLOW,
) -> dict:
    """Devuelve {índice_de_fase: verde_en_segundos} según Webster."""
    ratios = {
        idx: min(0.95, flow / saturation_flow) for idx, flow in phase_flows.items()
    }
    Y = sum(ratios.values())
    n_phases = max(1, len(ratios))
    L = lost_time_per_phase * n_phases

    if Y >= 0.95:  # sobresaturado: Webster no está definido, se usa el ciclo máximo
        cycle = max_cycle
    else:
        cycle = (1.5 * L + 5.0) / (1.0 - Y)
        cycle = float(min(max_cycle, max(min_cycle, cycle)))

    effective_green = cycle - L
    if Y <= 0:
        share = {idx: 1.0 / n_phases for idx in ratios}
    else:
        share = {idx: r / Y for idx, r in ratios.items()}

    greens = {idx: max(min_green, effective_green * s) for idx, s in share.items()}
    return {"cycle": cycle, "greens": greens, "Y": Y, "lost_time": L}


class WebsterController(Controller):
    """Aplica un plan de Webster precalculado (archivo JSON) a la red."""

    name = "webster"
    decision_interval = 1

    def __init__(self, plan_file: str):
        with open(plan_file) as fh:
            self.plans = json.load(fh)

    def setup(self, sim) -> None:
        for tid, tl in sim.tls.items():
            plan = self.plans.get(tid)
            if plan is None:
                continue
            greens = {int(k): v for k, v in plan["greens"].items()}
            self._apply(sim, tl, greens)

    def _apply(self, sim, tl, greens: dict) -> None:
        """Reescribe las duraciones del programa, conservando las fases ámbar."""
        logic = sim.conn.trafficlight.getAllProgramLogics(tl.id)[0]
        for i, phase in enumerate(logic.phases):
            if i in greens:
                phase.duration = greens[i]
                phase.minDur = greens[i]
                phase.maxDur = greens[i]
        sim.conn.trafficlight.setProgramLogic(tl.id, logic)
        sim.conn.trafficlight.setPhase(tl.id, 0)

    def act(self, sim) -> None:
        return
