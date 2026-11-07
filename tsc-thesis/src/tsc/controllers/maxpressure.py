"""Controlador Max-Pressure (Varaiya, 2013).

En cada instante de decisión, cada intersección elige de forma independiente
la fase que maximiza la *presión*: la diferencia entre la demanda acumulada
aguas arriba de los movimientos habilitados y la ocupación aguas abajo.

    presión(fase) = Σ_movimientos [ x(pista_entrada) - x(pista_salida) ]

Es descentralizado (sólo información local y de las pistas de salida
inmediatas) y tiene una garantía teórica de estabilidad: maximiza la región
de demandas para las que las colas permanecen acotadas. Por eso es la línea
base más exigente, y no un simple punto de comparación.

Dos parámetros, ajustados en el eje comunal solo con demandas de entrenamiento
(scripts/ajustar_baselines.py, punta tarde, 5-nov-2026):
  * `medida`: conteo de vehículos, como en la formulación original. Normalizar
    por capacidad rindió peor: en pistas cortas un solo vehículo satura la medida.
  * `switch_penalty` (histéresis): 0. El verde mínimo ya limita la conmutación y
    cualquier penalización mayor rindió peor.

ATENCIÓN al calibrar `switch_penalty`: debe estar en la misma escala que la
medida de ocupación, y depende de la red. Si es demasiado alta, el controlador
se queda en una fase hasta agotar el verde máximo: si Max-Pressure rinde mal,
este es el primer parámetro que hay que revisar.
"""
from __future__ import annotations

from .base import PhaseSwitchingController


class MaxPressureController(PhaseSwitchingController):
    name = "maxpressure"

    def __init__(
        self,
        min_green: int = 10,
        max_green: int = 60,
        yellow_time: int = 3,
        medida: str = "vehiculos",
        switch_penalty: float = 0.0,
    ):
        if medida not in ("densidad", "vehiculos", "cola"):
            raise ValueError(f"medida desconocida: {medida}")
        self.min_green = min_green
        self.max_green = max_green
        self.yellow_time = yellow_time
        self.medida = medida
        self.switch_penalty = switch_penalty

    def _occupancy(self, tl, lane: str) -> float:
        if self.medida == "densidad":
            return tl.density(lane)
        if self.medida == "cola":
            return float(tl.queue(lane))
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
