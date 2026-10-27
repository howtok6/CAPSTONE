"""Pruebas de la coordinación del plan Webster (27-oct-2026)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsc.controllers.webster import (  # noqa: E402
    WebsterController,
    coordinate_cycles,
    progression_offsets,
)

SCEN = os.path.join(os.path.dirname(__file__), "..", "scenarios", "grid4x4")
NET = os.path.join(SCEN, "net.net.xml")
ROU = os.path.join(SCEN, "routes.rou.xml")
PLAN = os.path.join(SCEN, "webster_plan.json")


def test_ciclo_comun_es_el_mayor_del_grupo():
    plans = {"a": {"cycle": 60.0}, "b": {"cycle": 90.0}, "c": {"cycle": 75.0}, "x": {"cycle": 50.0}}
    coordinate_cycles(plans, {"a": "Prov", "b": "Prov", "c": "Apoq"})
    assert plans["a"]["cycle"] == plans["b"]["cycle"] == 90.0
    assert plans["a"]["cycle_webster"] == 60.0
    assert plans["c"]["cycle"] == 75.0          # grupo propio
    assert plans["x"]["cycle"] == 50.0          # fuera del eje: no se toca
    assert "group" not in plans["x"]


def test_desfases_de_onda_verde():
    pos = {"a": 0.0, "b": 400.0, "c": 800.0}
    assert progression_offsets(pos, 90, 10.0, "oriente") == {"a": 0.0, "b": 40.0, "c": 80.0}
    assert progression_offsets(pos, 90, 10.0, "poniente") == {"a": 80.0, "b": 40.0, "c": 0.0}
    assert progression_offsets(pos, 60, 10.0, "oriente")["c"] == 20.0   # módulo el ciclo
    assert set(progression_offsets(pos, 90, 10.0, "ninguno").values()) == {0.0}


@pytest.mark.skipif(not os.path.exists(PLAN), reason="ejecuta primero build_webster sobre grid4x4")
def test_ciclo_real_igual_al_objetivo(tmp_path):
    from tsc.runner import run_episode

    with open(PLAN) as f:
        plans = json.load(f)
    for k, p in plans.items():
        if not k.startswith("_"):
            p["cycle"], p["offset"] = 90.0, 25.0
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plans))
    ctrl = WebsterController(str(plan_file))
    run_episode(ctrl, NET, ROU, seed=0, end=120, warmup=0)
    assert ctrl.real_cycles, "el controlador no aplicó ningún plan"
    for tid, real in ctrl.real_cycles.items():
        assert abs(real - 90.0) < 0.01, f"{tid}: ciclo real {real} s"
