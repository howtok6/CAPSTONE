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
from collections import defaultdict

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


def coordinate_cycles(plans: dict, groups: dict) -> dict:
    """Ciclo común por grupo (corredor coordinado).

    `groups` asigna cada semáforo a un grupo (p. ej. su avenida). Todos los del
    grupo toman el ciclo mayor del grupo: así el cruce más cargado no queda
    sobresaturado y los demás pueden coordinarse con él. Los verdes se
    reparten de nuevo en el controlador, en proporción a los de Webster.
    """
    by_group = defaultdict(list)
    for tid, g in groups.items():
        if tid in plans:
            by_group[g].append(tid)
    for g, tids in by_group.items():
        common = max(plans[t]["cycle"] for t in tids)
        for t in tids:
            plans[t]["cycle_webster"] = plans[t]["cycle"]
            plans[t]["cycle"] = common
            plans[t]["group"] = g
    return plans


def progression_offsets(positions: dict, cycle: float, speed_mps: float, direction: str) -> dict:
    """Desfases para una onda verde en un sentido.

    `positions` en metros a lo largo del eje, creciendo hacia el oriente. Un
    pelotón que sale con el verde del primer cruce llega al cruce i después de
    d_i / v segundos; ese es su desfase (módulo el ciclo). En una avenida de
    doble sentido la onda solo puede ser perfecta en uno: se elige el de la
    punta (hacia el centro en la mañana, hacia el oriente en la tarde).
    """
    if direction not in ("oriente", "poniente") or not positions:
        return {t: 0.0 for t in positions}
    origen = min(positions.values()) if direction == "oriente" else max(positions.values())
    return {t: round((abs(p - origen) / speed_mps) % cycle, 1) for t, p in positions.items()}


class WebsterController(Controller):
    """Aplica un plan de Webster precalculado (archivo JSON) a la red."""

    name = "webster"
    decision_interval = 1

    def __init__(self, plan_file: str):
        with open(plan_file) as fh:
            self.plans = json.load(fh)
        self.real_cycles: dict = {}

    def setup(self, sim) -> None:
        for tid, tl in sim.tls.items():
            plan = self.plans.get(tid)
            if plan is None:
                continue
            greens = {int(k): v for k, v in plan["greens"].items()}
            self._apply(sim, tl, greens, cycle=plan.get("cycle"), offset=plan.get("offset", 0.0))

    def _apply(self, sim, tl, greens: dict, cycle: float | None = None,
               offset: float = 0.0, min_green: float = 8.0) -> None:
        """Reescribe las duraciones del programa, conservando las fases ámbar.

        Si el plan trae `cycle`, los verdes se escalan para que el ciclo REAL
        (verdes + amarillos + rojos del programa) sea exactamente ese. Sin esto,
        dos semáforos con «el mismo ciclo» en el papel tendrían ciclos reales
        distintos y la coordinación se perdería en pocos minutos.
        Si trae `offset`, el programa arranca desfasado para formar la onda verde.
        """
        logic = sim.conn.trafficlight.getAllProgramLogics(tl.id)[0]
        if cycle:
            fijos = sum(p.duration for i, p in enumerate(logic.phases) if i not in greens)
            disponible = cycle - fijos
            total = sum(greens.values())
            if total > 0 and disponible > 0:
                greens = {i: max(min_green, g * disponible / total) for i, g in greens.items()}
        for i, phase in enumerate(logic.phases):
            if i in greens:
                phase.duration = greens[i]
                phase.minDur = greens[i]
                phase.maxDur = greens[i]
        sim.conn.trafficlight.setProgramLogic(tl.id, logic)

        # Desfase: posición dentro del ciclo en el instante actual
        dur = [p.duration for p in logic.phases]
        real = sum(dur)
        self.real_cycles[tl.id] = real
        pos = (sim.time - offset) % real if real > 0 else 0.0
        inicio = 0.0
        for k, d in enumerate(dur):
            if pos < inicio + d:
                sim.conn.trafficlight.setPhase(tl.id, k)
                sim.conn.trafficlight.setPhaseDuration(tl.id, inicio + d - pos)
                break
            inicio += d

    def act(self, sim) -> None:
        return
