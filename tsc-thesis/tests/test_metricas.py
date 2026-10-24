"""Pruebas de las métricas corregidas el 24-oct-2026.

1. `phase_switches` debía contar cambios de fase y siempre daba 0.
2. La demora media solo consideraba viajes terminados; `delay_all_mean`
   incluye a los que siguen en la red o esperan entrar.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsc.controllers import FixedTimeController, MaxPressureController  # noqa: E402
from tsc.metrics import combine_delay, planned_departures  # noqa: E402
from tsc.runner import run_episode  # noqa: E402

SCEN = os.path.join(os.path.dirname(__file__), "..", "scenarios", "grid4x4")
NET = os.path.join(SCEN, "net.net.xml")
ROU = os.path.join(SCEN, "routes.rou.xml")

pytestmark = pytest.mark.skipif(not os.path.exists(NET), reason="ejecuta primero: make grid")


@pytest.mark.parametrize("ctrl", [FixedTimeController, MaxPressureController])
def test_phase_switches_se_cuentan(ctrl):
    r = run_episode(ctrl(), NET, ROU, seed=0, end=600, warmup=100)
    assert r["phase_switches"] > 0


def test_delay_all_incluye_no_terminados():
    r = run_episode(FixedTimeController(), NET, ROU, seed=0, end=600, warmup=100)
    assert not any(k.startswith("_") for k in r), "quedaron claves auxiliares en el resultado"
    # al cortar a los 600 s quedan vehículos en la red: deben contarse
    assert r["vehicles_running_end"] > 0
    assert r["vehicles_considered"] == (r["vehicles_finished"] + r["vehicles_running_end"]
                                        + r["vehicles_pending_end"])
    assert r["delay_all_mean"] > 0


def test_combine_delay_promedia_terminados_y_no_terminados():
    r = {"vehicles_finished": 2, "_finished_delay_sum": 20.0,
         "_unfinished_n": 2, "_unfinished_delay_sum": 100.0}
    combine_delay(r)
    assert r["vehicles_considered"] == 4
    assert r["delay_all_mean"] == 30.0
    assert not any(k.startswith("_") for k in r)


def test_planned_departures_lee_el_archivo_de_rutas():
    d = planned_departures(ROU)
    assert d and all(v >= 0 for v in d.values())
