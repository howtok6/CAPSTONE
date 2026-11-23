"""MAPPO: el actor decide solo con lo local y el crítico ve el bloque global."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

th = pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")
from gymnasium import spaces  # noqa: E402

try:
    from tsc.mappo import DIM_GLOBAL, DIM_LOCAL, MaskedActorCriticPolicy  # noqa: E402
except ImportError as e:  # sumo-rl exige SUMO_HOME al importarse
    pytest.skip(f"tsc.mappo no importable: {e}", allow_module_level=True)


def _politica():
    obs = spaces.Box(0.0, 1.0, shape=(DIM_LOCAL + DIM_GLOBAL,), dtype=np.float32)
    return MaskedActorCriticPolicy(obs, spaces.Discrete(4), lr_schedule=lambda _: 3e-4)


def test_actor_ignora_bloque_global():
    p = _politica()
    rng = np.random.default_rng(0)
    a = rng.random((5, DIM_LOCAL + DIM_GLOBAL), dtype=np.float32)
    b = a.copy()
    b[:, DIM_LOCAL:] = rng.random((5, DIM_GLOBAL), dtype=np.float32)
    with th.no_grad():
        pa = p.get_distribution(th.as_tensor(a)).distribution.probs
        pb = p.get_distribution(th.as_tensor(b)).distribution.probs
        va = p.predict_values(th.as_tensor(a))
        vb = p.predict_values(th.as_tensor(b))
    assert th.allclose(pa, pb)
    assert not th.allclose(va, vb)


def test_evaluate_actions_usa_mascara():
    p = _politica()
    obs = th.rand(3, DIM_LOCAL + DIM_GLOBAL)
    otra = obs.clone()
    otra[:, DIM_LOCAL:] = th.rand(3, DIM_GLOBAL)
    acciones = th.tensor([0, 1, 2])
    with th.no_grad():
        _, lp1, _ = p.evaluate_actions(obs, acciones)
        _, lp2, _ = p.evaluate_actions(otra, acciones)
    assert th.allclose(lp1, lp2)
