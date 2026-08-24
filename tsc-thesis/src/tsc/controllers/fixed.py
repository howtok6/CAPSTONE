"""Control de tiempo fijo: piso de comparación.

No interviene la simulación. SUMO ejecuta el programa semafórico definido en
la red, que es el que produce `netconvert` o el que el analista definió a mano.
"""
from .base import Controller


class FixedTimeController(Controller):
    name = "fixed"
    decision_interval = 10

    def act(self, sim) -> None:  # pragma: no cover - deliberadamente vacío
        return
