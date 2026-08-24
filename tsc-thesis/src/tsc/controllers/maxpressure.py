"""Controlador Max-Pressure (Varaiya, 2013).

En cada instante de decisión, cada intersección elige de forma independiente
la fase que maximiza la *presión*: la diferencia entre la demanda acumulada
aguas arriba de los movimientos habilitados y la ocupación aguas abajo.

    presión(fase) = Σ_movimientos [ x(pista_entrada) - x(pista_salida) ]

Es descentralizado (sólo información local y de las pistas de salida
inmediatas) y tiene una garantía teórica de estabilidad: maximiza la región
de demandas para las que las colas permanecen acotadas. Por eso es la línea
base más exigente, y no un simple punto de comparación.

Dos ajustes prácticos respecto de la formulación teórica:
  * normalización por capacidad de la pista, para no penalizar pistas cortas;
  * histéresis (`switch_penalty`), porque la formulación original no castiga
    la conmutación frecuente y en la práctica genera oscilación de fases.

ATENCIÓN al calibrar `switch_penalty`: debe estar en la misma escala que la
medida de ocupación. Con `normalize=True` las presiones son del orden de
0,1–0,5, de modo que una penalización de 0,5 congela el controlador en una
sola fase hasta agotar el verde máximo — y el resultado es *peor* que tiempo
fijo. Este error es fácil de cometer y difícil de diagnosticar: si Max-Pressure
no supera a tiempo fijo, lo primero que hay que revisar es este parámetro.
"""
from __future__ import annotations

from .base import PhaseSwitchingController


class MaxPressureController(PhaseSwitchingController):
    name = "maxpressure"
    decision_interval = 5

    def __init__(
        self,
        min_green: int = 10,
        max_green: int = 60,
        yellow_time: int = 3,
        normalize: bool = True,
        switch_penalty: float = 0.05,
    ):
        self.min_green = min_green
        self.max_green = max_green
        self.yellow_time = yellow_time
        self.normalize = normalize
        self.switch_penalty = switch_penalty

    def _occupancy(self, tl, lane: str) -> float:
        if self.normalize:
            return tl.density(lane)
        return float(tl.vehicles(lane))

    def pressure(self, tl, phase) -> float:
        total = 0.0
        for in_lane, out_lane in phase.movements:
            total += self._occupancy(tl, in_lane) - self._occupancy(tl, out_lane)
        return total

    def choose_phase(self, tl) -> int:
        current = tl.current_phase()
        best_idx, best_val = current, float("-inf")
        for phase in tl.green_phases:
            val = self.pressure(tl, phase)
            if phase.index == current:
                val += self.switch_penalty  # histéresis: favorece mantener
            if val > best_val:
                best_val, best_idx = val, phase.index
        return best_idx
