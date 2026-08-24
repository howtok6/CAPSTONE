"""Controlador voraz por longitud de cola.

No forma parte del conjunto de líneas base del anteproyecto, pero es útil
como control de sanidad: cualquier cosa que no supere a este controlador
trivial tiene un problema de implementación, no de algoritmo.
"""
from __future__ import annotations

from .base import PhaseSwitchingController


class GreedyQueueController(PhaseSwitchingController):
    name = "greedy"
    decision_interval = 5

    def choose_phase(self, tl) -> int:
        best_idx, best_val = tl.current_phase(), float("-inf")
        for phase in tl.green_phases:
            val = sum(tl.queue(ln) for ln in phase.incoming_lanes)
            if phase.index == tl.current_phase():
                val += 0.5
            if val > best_val:
                best_val, best_idx = val, phase.index
        return best_idx
