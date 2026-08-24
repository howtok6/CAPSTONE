"""Interfaz común a todos los controladores.

El runner llama a `act(sim)` cada `decision_interval` segundos simulados.
Los controladores de tiempo fijo simplemente no hacen nada y dejan que SUMO
ejecute el programa cargado; los adaptativos conmutan fases explícitamente.
"""
from __future__ import annotations


class Controller:
    name = "base"
    #: cada cuántos segundos simulados se le pide una decisión
    decision_interval: int = 5

    def setup(self, sim) -> None:
        """Se llama una vez tras iniciar la simulación."""

    def act(self, sim) -> None:
        """Se llama cada `decision_interval` segundos simulados."""

    def teardown(self, sim) -> None:
        """Se llama antes de cerrar la simulación."""


class PhaseSwitchingController(Controller):
    """Base para controladores que eligen la próxima fase verde.

    Se encarga de la mecánica común y no negociable: verde mínimo, verde
    máximo e inserción de la fase ámbar/rojo al conmutar. Las subclases sólo
    implementan `choose_phase`, que es donde vive la política.
    """

    min_green = 10
    max_green = 60
    yellow_time = 3

    def setup(self, sim) -> None:
        self._since_change = {tid: 0.0 for tid in sim.tls}
        self._target = {}
        self._in_yellow = {tid: False for tid in sim.tls}
        self._yellow_left = {tid: 0.0 for tid in sim.tls}
        for tid, tl in sim.tls.items():
            if tl.green_indices:
                tl.set_phase(tl.green_indices[0])
                tl.set_phase_duration(10_000)

    def choose_phase(self, tl) -> int:
        raise NotImplementedError

    def act(self, sim) -> None:
        dt = self.decision_interval
        for tid, tl in sim.tls.items():
            if not tl.green_indices:
                continue

            if self._in_yellow[tid]:
                self._yellow_left[tid] -= dt
                if self._yellow_left[tid] <= 0:
                    tl.set_phase(self._target[tid])
                    tl.set_phase_duration(10_000)
                    self._in_yellow[tid] = False
                    self._since_change[tid] = 0.0
                continue

            self._since_change[tid] += dt
            if self._since_change[tid] < self.min_green:
                continue

            current = tl.current_phase()
            desired = self.choose_phase(tl)
            forced = self._since_change[tid] >= self.max_green
            if desired == current and not forced:
                continue
            if desired == current and forced:
                # verde máximo agotado: pasar a la siguiente fase verde
                pos = tl.green_indices.index(current)
                desired = tl.green_indices[(pos + 1) % len(tl.green_indices)]
                if desired == current:
                    continue

            yellow = tl.yellow_between(current, desired)
            if yellow is None:
                tl.set_phase(desired)
                tl.set_phase_duration(10_000)
                self._since_change[tid] = 0.0
            else:
                tl.set_phase(yellow)
                tl.set_phase_duration(10_000)
                self._target[tid] = desired
                self._in_yellow[tid] = True
                self._yellow_left[tid] = self.yellow_time
