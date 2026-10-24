"""Entorno de aprendizaje por refuerzo multi-agente.

Se construye sobre `sumo-rl`, que ya expone la simulación como entorno
PettingZoo (un agente por intersección). Aquí se fija la especificación del
Dec-POMDP de la tesis —observación, acción, recompensa, restricciones duras—
en un solo lugar, para que entrenamiento y evaluación no puedan divergir.

Decisiones de diseño que conviene poder defender:

* **Verde mínimo y máximo son restricciones del entorno, no penalizaciones
  aprendidas.** Un semáforo que aprende a saltarse el verde mínimo no es
  desplegable, por bueno que sea su retorno.
* **La recompensa por defecto es la variación de la espera acumulada.** Es la
  de sumo-rl y la más usada, lo que hace comparables los resultados con la
  literatura. Las variantes (presión, penalización por conmutación) se
  seleccionan por nombre para poder correr el ablation.
"""
from __future__ import annotations

import os
import sys

if "SUMO_HOME" not in os.environ:
    import sumo
    os.environ["SUMO_HOME"] = os.path.dirname(sumo.__file__)
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import json  # noqa: E402

import sumo_rl  # noqa: E402
from gymnasium.utils import EzPickle  # noqa: E402
from pettingzoo.utils import agent_selector, wrappers  # noqa: E402
from pettingzoo.utils.conversions import parallel_wrapper_fn  # noqa: E402
from sumo_rl.environment.env import SumoEnvironment, SumoEnvironmentPZ  # noqa: E402

from tsc.observations import WazeCongestionObservation  # noqa: E402


# --------------------------------------------------------------------------
# Control de un subconjunto de semáforos
#
# sumo-rl controla TODOS los semáforos de la red. En el eje comunal solo deben
# aprender los del eje (docs/07, decisión 2); los de las transversales siguen
# su programa de tiempo fijo como demanda de contexto. Estas dos subclases
# filtran la lista sin modificar la librería instalada.
# --------------------------------------------------------------------------

class SubsetSumoEnvironment(SumoEnvironment):
    """SumoEnvironment que controla solo los semáforos de `controlled_ts`."""

    def __init__(self, *args, controlled_ts=None, **kwargs):
        super().__init__(*args, **kwargs)
        if controlled_ts:
            pedidos = set(controlled_ts)
            faltan = pedidos - set(self.ts_ids)
            if faltan:
                raise ValueError(f"semáforos que no existen en la red: {sorted(faltan)[:5]}")
            # reset() reconstruye traffic_signals a partir de self.ts_ids
            self.ts_ids = [t for t in self.ts_ids if t in pedidos]
            self.traffic_signals = {t: self.traffic_signals[t] for t in self.ts_ids}
            self.observations = {t: None for t in self.ts_ids}
            self.rewards = {t: None for t in self.ts_ids}


class SubsetSumoEnvironmentPZ(SumoEnvironmentPZ):
    """Versión PettingZoo: mismo cuerpo que la de sumo-rl, con el entorno filtrado."""

    def __init__(self, **kwargs):
        EzPickle.__init__(self, **kwargs)
        controlled = kwargs.pop("controlled_ts", None)
        self._kwargs = kwargs
        self.seed()
        self.env = SubsetSumoEnvironment(controlled_ts=controlled, **kwargs)
        self.agents = self.env.ts_ids
        self.possible_agents = self.env.ts_ids
        self._agent_selector = agent_selector(self.agents)
        self.agent_selection = self._agent_selector.reset()
        self.action_spaces = {a: self.env.action_spaces(a) for a in self.agents}
        self.observation_spaces = {a: self.env.observation_spaces(a) for a in self.agents}
        self.rewards = {a: 0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}


def _subset_aec_env(**kwargs):
    env = SubsetSumoEnvironmentPZ(**kwargs)
    env = wrappers.AssertOutOfBoundsWrapper(env)
    return wrappers.OrderEnforcingWrapper(env)


subset_parallel_env = parallel_wrapper_fn(_subset_aec_env)


def controlled_tls(scenario: str, control: str = "auto") -> list | None:
    """Lista de semáforos que controla el agente.

    control = "todos" → None (todos los de la red, comportamiento de sumo-rl)
    control = "eje"   → la lista `eje` de <escenario>/tls_eje.json (scripts/list_axis_tls.py)
    control = "auto"  → "eje" si existe tls_eje.json, si no "todos"
    """
    path = os.path.join(scenario, "tls_eje.json")
    if control == "todos" or (control == "auto" and not os.path.exists(path)):
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(f"falta {path}: corre scripts/list_axis_tls.py")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["eje"]


def pressure_reward(ts) -> float:
    """Recompensa basada en la presión de la intersección (estilo PressLight)."""
    return -abs(ts.get_pressure())


def queue_reward(ts) -> float:
    return -float(sum(ts.get_lanes_queue()))


REWARDS = {
    "wait": "diff-waiting-time",   # por defecto en sumo-rl
    "queue": queue_reward,
    "pressure": pressure_reward,
    "speed": "average-speed",
}


def make_parallel_env(
    net_file: str,
    route_file: str,
    *,
    reward: str = "wait",
    num_seconds: int = 3600,
    delta_time: int = 5,
    yellow_time: int = 3,
    min_green: int = 10,
    max_green: int = 60,
    seed: int = 0,
    out_csv: str | None = None,
    gui: bool = False,
    use_waze_obs: bool = False,
    tls_ids: list | None = None,
):
    """Entorno PettingZoo paralelo: un agente por intersección.

    `tls_ids` limita los agentes a esos semáforos; los demás conservan su
    programa de tiempo fijo. None = todos (comportamiento original).
    """
    if reward not in REWARDS:
        raise ValueError(f"reward debe ser uno de {sorted(REWARDS)}")
        
    env_kwargs = {
        "net_file": net_file,
        "route_file": route_file,
        "out_csv_name": out_csv,
        "use_gui": gui,
        "num_seconds": num_seconds,
        "delta_time": delta_time,
        "yellow_time": yellow_time,
        "min_green": min_green,
        "max_green": max_green,
        "reward_fn": REWARDS[reward],
        "sumo_seed": seed,
        "sumo_warnings": False,
        "add_system_info": True,
    }
    
    if use_waze_obs:
        env_kwargs["observation_class"] = WazeCongestionObservation

    if tls_ids:
        return subset_parallel_env(controlled_ts=list(tls_ids), **env_kwargs)
    return sumo_rl.parallel_env(**env_kwargs)


def make_sb3_vec_env(num_vec_envs: int = 1, num_cpus: int = 1, **kwargs):
    """Adapta el entorno PettingZoo a un VecEnv de Stable-Baselines3.

    Se usa *parameter sharing*: una sola red que actúa en todas las
    intersecciones, tratando a cada agente como una muestra más del lote.
    Es la variante IPPO más barata de entrenar y el punto de partida natural
    antes de pasar a un crítico centralizado (MAPPO).
    """
    import supersuit as ss
    from stable_baselines3.common.vec_env import VecMonitor

    env = make_parallel_env(**kwargs)
    # sumo-rl no define `render_mode` en su envoltorio PettingZoo y SuperSuit
    # lo exige. Se fija aquí en lugar de parchear la dependencia.
    if not hasattr(env.unwrapped, "render_mode"):
        env.unwrapped.render_mode = None
    env = ss.pad_observations_v0(env)      # intersecciones con distinto nº de fases
    env = ss.pad_action_space_v0(env)
    env = ss.pettingzoo_env_to_vec_env_v1(env)
    env = ss.concat_vec_envs_v1(
        env, num_vec_envs, num_cpus=num_cpus, base_class="stable_baselines3"
    )
    return VecMonitor(env)
