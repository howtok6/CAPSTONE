"""MAPPO con crítico centralizado (CTDE) sobre el mismo esquema de parámetros compartidos que IPPO.

Entrenamiento centralizado, ejecución descentralizada:

* `GlobalPhaseObservation` = la observación por fase de IPPO (22 columnas, `PhaseObservation`)
  seguida de un bloque global de 11 columnas que solo usa el crítico: densidad y cola medias de
  los 4 semáforos controlados más cercanos (8) y, sobre todos los controlados, densidad media,
  cola media y fracción de cruces con cola (3).
* `MaskedActorCriticPolicy`: PPO con extractores separados para actor y crítico. El del actor
  pone en cero el bloque global, así que la política decide solo con su observación local (se
  puede desplegar cruce a cruce, igual que IPPO); el crítico ve todo el vector, que es lo que
  distingue a MAPPO (Yu et al., 2022) de IPPO.

Con eso la comparación IPPO vs MAPPO cambia una sola cosa: lo que ve el crítico.
"""
from __future__ import annotations

import math

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3.common.policies import ActorCriticPolicy

from tsc.observations import PhaseObservation

VECINOS = 4
DIM_LOCAL = PhaseObservation.DIM
DIM_GLOBAL = 2 * VECINOS + 3


class _Cache:
    """Estado por entorno y por instante: cada semáforo no recalcula lo de los demás."""

    def __init__(self):
        self.t = None
        self.stats: dict[str, tuple[float, float]] = {}
        self.vecinos: dict[str, list[str]] = {}
        self.globales = None


_CACHES: dict[int, _Cache] = {}


def _cache(env) -> _Cache:
    c = _CACHES.get(id(env))
    if c is None:
        c = _CACHES[id(env)] = _Cache()
    return c


def _posicion(ts) -> tuple[float, float]:
    puntos = [ts.sumo.lane.getShape(p)[-1] for p in ts.lanes]
    return (sum(x for x, _ in puntos) / len(puntos), sum(y for _, y in puntos) / len(puntos))


class GlobalPhaseObservation(PhaseObservation):
    DIM = DIM_LOCAL + DIM_GLOBAL

    def _stats(self, c: _Cache, tid: str) -> tuple[float, float]:
        if tid not in c.stats:
            ts = self.ts.env.traffic_signals[tid]
            d, q = ts.get_lanes_density(), ts.get_lanes_queue()
            c.stats[tid] = (sum(d) / max(1, len(d)), sum(q) / max(1, len(q)))
        return c.stats[tid]

    def __call__(self):
        # PhaseObservation reserva self.DIM columnas (aquí 33) y llena las primeras 22
        local = super().__call__()[:DIM_LOCAL]
        env = self.ts.env
        c = _cache(env)
        t = self.ts.sumo.simulation.getTime()
        if c.t != t:
            c.t, c.stats, c.globales = t, {}, None
        if not c.vecinos:
            pos = {tid: _posicion(ts) for tid, ts in env.traffic_signals.items()}
            for tid, (x, y) in pos.items():
                otros = sorted((math.hypot(x - ox, y - oy), o) for o, (ox, oy) in pos.items() if o != tid)
                c.vecinos[tid] = [o for _, o in otros[:VECINOS]]
        if c.globales is None:
            todos = [self._stats(c, tid) for tid in env.traffic_signals]
            n = max(1, len(todos))
            c.globales = [sum(d for d, _ in todos) / n, sum(q for _, q in todos) / n,
                          sum(1 for _, q in todos if q > 0.05) / n]
        g = np.zeros(DIM_GLOBAL, dtype=np.float32)
        for k, v in enumerate(c.vecinos.get(self.ts.id, [])):
            g[2 * k], g[2 * k + 1] = self._stats(c, v)
        g[2 * VECINOS:] = c.globales
        return np.concatenate([local, np.clip(g, 0.0, 1.0)])

    def observation_space(self):
        return spaces.Box(low=0.0, high=1.0, shape=(self.DIM,), dtype=np.float32)


class _MascaraActor(th.nn.Module):
    """Extractor del actor: aplana y anula las columnas globales (ejecución descentralizada)."""

    def __init__(self, dim_total: int, dim_local: int):
        super().__init__()
        mascara = th.zeros(dim_total)
        mascara[:dim_local] = 1.0
        self.register_buffer("mascara", mascara)
        self.features_dim = dim_total

    def forward(self, obs: th.Tensor) -> th.Tensor:
        return th.flatten(obs, start_dim=1) * self.mascara


class MaskedActorCriticPolicy(ActorCriticPolicy):
    """ActorCriticPolicy de SB3 con actor local y crítico centralizado."""

    def __init__(self, *args, dim_local: int = DIM_LOCAL, **kwargs):
        kwargs["share_features_extractor"] = False
        super().__init__(*args, **kwargs)
        total = int(np.prod(self.observation_space.shape))
        # Sin parámetros propios: reemplazarlo después de crear el optimizador no cambia nada
        self.pi_features_extractor = _MascaraActor(total, dim_local)
