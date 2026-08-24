"""Pruebas rápidas del pipeline.

No prueban la calidad de los algoritmos —eso lo hace el experimento— sino que
la mecánica no esté rota: que las fases se lean bien, que el verde mínimo se
respete y que Max-Pressure supere a tiempo fijo, que es la comprobación de
sanidad más informativa que existe en este dominio.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsc.controllers import FixedTimeController, MaxPressureController  # noqa: E402
from tsc.controllers.webster import webster_plan  # noqa: E402
from tsc.runner import run_episode  # noqa: E402

SCEN = os.path.join(os.path.dirname(__file__), "..", "scenarios", "grid4x4")
NET = os.path.join(SCEN, "net.net.xml")
ROU = os.path.join(SCEN, "routes.rou.xml")

pytestmark = pytest.mark.skipif(
    not os.path.exists(NET),
    reason="ejecuta primero: make grid",
)


def test_webster_cycle_grows_with_demand():
    low = webster_plan({0: 300.0, 1: 300.0})
    high = webster_plan({0: 1200.0, 1: 1200.0})
    assert high["cycle"] > low["cycle"]
    assert high["Y"] > low["Y"]


def test_webster_splits_favour_the_busier_phase():
    plan = webster_plan({0: 1000.0, 1: 300.0})
    assert plan["greens"][0] > plan["greens"][1]


def test_fixed_time_runs_and_reports_metrics():
    r = run_episode(FixedTimeController(), NET, ROU, seed=0, end=900)
    assert r["vehicles_finished"] > 0
    assert r["time_loss_mean"] > 0
    assert r["queue_mean"] >= 0


def test_maxpressure_beats_fixed_time():
    """Si esto falla, revisa `switch_penalty`: si es grande respecto de la
    escala de la presión, el controlador se congela en una sola fase."""
    fixed = run_episode(FixedTimeController(), NET, ROU, seed=0, end=1800)
    mp = run_episode(MaxPressureController(), NET, ROU, seed=0, end=1800)
    assert mp["time_loss_mean"] < fixed["time_loss_mean"]


def test_min_green_is_respected():
    from tsc.sumo_env import SumoSimulation

    ctrl = MaxPressureController(min_green=15)
    sim = SumoSimulation(NET, ROU, end=600, seed=0)
    with sim:
        ctrl.setup(sim)
        last_phase = {t: sim.tls[t].current_phase() for t in sim.tls}
        held = {t: 0 for t in sim.tls}
        t = 0
        while sim.running() and t < 400:
            sim.step(ctrl.decision_interval)
            t += ctrl.decision_interval
            ctrl.act(sim)
            for tid, tl in sim.tls.items():
                cur = tl.current_phase()
                is_green = tl.phases[cur].is_green
                if cur == last_phase[tid]:
                    held[tid] += ctrl.decision_interval
                else:
                    if is_green and tl.phases[last_phase[tid]].is_green:
                        # dos verdes consecutivos sin ámbar: no debería ocurrir
                        assert held[tid] >= ctrl.min_green, (
                            f"{tid} cambió de verde tras {held[tid]}s"
                        )
                    held[tid] = 0
                    last_phase[tid] = cur
