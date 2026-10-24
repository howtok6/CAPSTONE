"""Pruebas de la configuración del agente (24-oct-2026).

1. El entorno controla solo los semáforos pedidos; los demás siguen su programa.
2. El optimizador elegido (Adam o RMSprop) es el que efectivamente usa la red.
"""
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SCEN = os.path.join(os.path.dirname(__file__), "..", "scenarios", "grid4x4")
NET = os.path.join(SCEN, "net.net.xml")
ROU = os.path.join(SCEN, "routes.rou.xml")

pytestmark = pytest.mark.skipif(not os.path.exists(NET), reason="ejecuta primero: make grid")


def _todos_los_tls():
    import sumolib
    return sorted(tl.getID() for tl in sumolib.net.readNet(NET).getTrafficLights())


def test_entorno_controla_solo_el_subconjunto():
    from tsc.rl_env import make_parallel_env

    todos = _todos_los_tls()
    pedidos = todos[:3]
    env = make_parallel_env(NET, ROU, num_seconds=120, tls_ids=pedidos)
    obs, _ = env.reset()
    assert set(env.agents) == set(pedidos)
    assert set(obs) == set(pedidos)
    inner = env.unwrapped.env
    libre = todos[-1]
    fases = set()
    while env.agents:
        acciones = {a: env.action_space(a).sample() for a in env.agents}
        obs, _, term, trunc, _ = env.step(acciones)
        fases.add(inner.sumo.trafficlight.getPhase(libre))
        if all(term.values()) or all(trunc.values()):
            break
    env.close()
    # el semáforo no controlado siguió su programa de tiempo fijo (cambió de fase)
    assert len(fases) > 1


def test_semaforo_inexistente_falla_claro():
    from tsc.rl_env import make_parallel_env

    with pytest.raises(ValueError):
        make_parallel_env(NET, ROU, num_seconds=60, tls_ids=["no_existe"])


@pytest.mark.parametrize("nombre,clase", [("adam", "Adam"), ("rmsprop", "RMSprop")])
def test_optimizador_llega_a_la_red(nombre, clase):
    import torch as th
    from stable_baselines3 import PPO

    from tsc.rl_env import make_sb3_vec_env

    spec = importlib.util.spec_from_file_location(
        "train_rl", os.path.join(os.path.dirname(__file__), "..", "scripts", "train_rl.py"))
    train_rl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(train_rl)
    opt_name, opt_kwargs = train_rl.OPTIMIZADORES[nombre]

    env = make_sb3_vec_env(num_vec_envs=1, num_cpus=1, net_file=NET, route_file=ROU,
                           num_seconds=60, tls_ids=_todos_los_tls()[:2])
    model = PPO("MlpPolicy", env, n_steps=16, batch_size=16,
                policy_kwargs={"optimizer_class": getattr(th.optim, opt_name),
                               "optimizer_kwargs": opt_kwargs})
    assert type(model.policy.optimizer).__name__ == clase
    model.learn(total_timesteps=32)  # una actualización completa sin errores
    env.close()
