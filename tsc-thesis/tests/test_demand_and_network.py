"""Pruebas automatizadas de la red real calibrada (Alameda-Providencia) y sus perfiles de demanda."""
from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsc.controllers.fixed import FixedTimeController
from tsc.controllers.maxpressure import MaxPressureController
from tsc.runner import run_episode


SCENARIO = "scenarios/alameda_providencia"
NET_FILE = os.path.join(SCENARIO, "net.net.xml")
DEMAND_DIR = os.path.join(SCENARIO, "demand")


def test_alameda_providencia_net_exists():
    assert os.path.exists(NET_FILE), f"No se encontró el archivo de red {NET_FILE}"


@pytest.mark.parametrize("profile", ["valle", "punta_manana", "punta_tarde", "sobresaturado"])
def test_demand_profiles_exist(profile: str):
    rou = os.path.join(DEMAND_DIR, f"routes_{profile}.rou.xml")
    assert os.path.exists(rou), f"No existe el archivo de rutas para el perfil {profile}"
    assert os.path.getsize(rou) > 100_000, f"El archivo {rou} parece incompleto o vacío"


def test_fixed_controller_runs_on_valle_profile():
    rou = os.path.join(DEMAND_DIR, "routes_valle.rou.xml")
    res = run_episode(FixedTimeController(), NET_FILE, rou, end=60, warmup=10, seed=42)
    assert res["controller"] == "fixed"
    assert "queue_mean" in res
    assert "throughput" in res
    assert "vehicles_finished" in res


def test_maxpressure_controller_runs_on_punta_tarde():
    rou = os.path.join(DEMAND_DIR, "routes_punta_tarde.rou.xml")
    res = run_episode(MaxPressureController(), NET_FILE, rou, end=60, warmup=10, seed=42)
    assert res["controller"] == "maxpressure"
    assert "queue_mean" in res
    assert "throughput" in res
    assert "vehicles_finished" in res
