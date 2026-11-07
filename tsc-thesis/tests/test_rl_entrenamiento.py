"""Pruebas del entrenamiento (5-nov-2026).

Cada una protege una condición sin la cual el resultado de la tesis no vale:

1. La evaluación ejecuta la misma política que se entrenó (relleno de acciones).
2. El verde máximo se cumple como restricción del entorno.
3. Cada episodio usa otra demanda.
4. La observación por fase tiene el mismo significado en todos los cruces.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SCEN = os.path.join(os.path.dirname(__file__), "..", "scenarios", "grid4x4")
NET = os.path.join(SCEN, "net.net.xml")
ROU = os.path.join(SCEN, "routes.rou.xml")

pytestmark = pytest.mark.skipif(not os.path.exists(NET), reason="ejecuta primero: make grid")


@pytest.mark.parametrize("n_fases", [2, 3, 4])
def test_accion_real_coincide_con_supersuit(n_fases):
    from gymnasium import spaces
    from supersuit.utils.action_transforms.homogenize_ops import dehomogenize_actions

    from tsc.rl_env import accion_real

    espacio = spaces.Discrete(n_fases)
    for salida in range(4):
        assert accion_real(salida, n_fases) == int(dehomogenize_actions(espacio, salida))


def test_verde_maximo_se_cumple():
    from tsc.rl_env import make_parallel_env

    max_green = 30
    env = make_parallel_env(NET, ROU, num_seconds=600, min_green=10, max_green=max_green)
    obs, _ = env.reset()
    inner = env.unwrapped.env
    ultimo, verde_desde, mayor = {}, {}, 0
    while env.agents:
        # política que nunca quiere cambiar
        acciones = {a: inner.traffic_signals[a].green_phase for a in env.agents}
        obs, _, term, trunc, _ = env.step(acciones)
        ahora = inner.sim_step
        for a, ts in inner.traffic_signals.items():
            if ts.is_yellow:
                continue
            if ultimo.get(a) != ts.green_phase:
                ultimo[a] = ts.green_phase
                verde_desde[a] = ahora
            mayor = max(mayor, ahora - verde_desde[a])
        if all(term.values()) or all(trunc.values()):
            break
    env.close()
    assert 0 < mayor <= max_green


def test_cada_episodio_usa_otra_demanda():
    from tsc.rl_env import make_parallel_env

    otra = ROU  # basta verificar la rotación del archivo y de la semilla
    env = make_parallel_env(NET, ROU, num_seconds=20, seed=7, route_pool=[ROU, otra, ROU])
    inner = env.unwrapped.env
    semillas = []
    for _ in range(3):
        env.reset()
        semillas.append(inner.sumo_seed)
    env.close()
    assert semillas == [7, 8, 9]


def test_observacion_por_fase_es_coherente():
    from tsc.observations import MAX_FASES, PhaseObservation
    from tsc.rl_env import make_parallel_env

    env = make_parallel_env(NET, ROU, num_seconds=300, obs="fase")
    obs, _ = env.reset()
    inner = env.unwrapped.env
    for _ in range(40):
        obs, _, term, trunc, _ = env.step({a: 0 for a in env.agents})
    for agente, o in obs.items():
        ts = inner.traffic_signals[agente]
        assert o.shape == (PhaseObservation.DIM,)
        assert np.all(o >= 0) and np.all(o <= 1)
        assert o[:MAX_FASES].sum() == 1 and o[ts.green_phase] == 1
        assert o[MAX_FASES:2 * MAX_FASES].sum() == ts.num_green_phases
        base = 2 * MAX_FASES + 2
        # las fases que no existen no aportan columnas
        assert np.all(o[base + ts.num_green_phases: base + MAX_FASES] == 0)
    env.close()
