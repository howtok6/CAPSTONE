#!/usr/bin/env python3
"""Entrena un agente MARL con parameter sharing (IPPO) sobre el escenario.

Punto de partida deliberadamente simple: una sola red compartida por todas las
intersecciones, entrenada con PPO tratando cada agente como una muestra más
del lote. Es la configuración IPPO más barata y el escalón previo a MAPPO con
crítico centralizado.

    python scripts/train_rl.py --scenario scenarios/grid4x4 --steps 200000

Cómo aprende de sus errores: tras cada lote de experiencia, PPO calcula la
*ventaja* de cada acción (retorno obtenido menos el que el crítico esperaba,
estimada con GAE). Las acciones que salieron peor de lo esperado pierden
probabilidad y las que salieron mejor la ganan; el crítico, a su vez, corrige su
estimación con el error de valor. El recorte (clip) impide que una corrección
sea tan grande que desarme lo aprendido.

Optimizador (--optimizer):
  adam     (por defecto) momento + paso adaptativo por parámetro. Es el del
           artículo de PPO y el que SB3 usa por defecto; funciona bien con las
           varias pasadas de minilotes sobre el mismo lote que hace PPO.
  rmsprop  paso adaptativo sin momento; el de DQN (Mnih 2015) y A2C. Se deja
           para el ablation: con recompensas ruidosas a veces es más estable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tsc.rl_env import controlled_tls, make_sb3_vec_env  # noqa: E402

# Hiperparámetros de cada optimizador. eps=1e-5 es el que usa SB3 para Adam en
# PPO y para RMSprop en A2C (evita divisiones casi por cero al inicio).
OPTIMIZADORES = {
    "adam": ("Adam", {"eps": 1e-5}),
    "rmsprop": ("RMSprop", {"alpha": 0.99, "eps": 1e-5, "weight_decay": 0.0}),
}


def commit_actual() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconocido"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", default=None, help="Nombre del perfil de demanda (valle, punta_manana, punta_tarde, sobresaturado)")
    ap.add_argument("--routes", default=None, help="Ruta directa al archivo de rutas .rou.xml")
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--reward", default="wait", choices=["wait", "queue", "pressure", "speed"])
    ap.add_argument("--seconds", type=int, default=3600, help="duración del episodio (s sim)")
    ap.add_argument("--delta-time", type=int, default=5)
    ap.add_argument("--min-green", type=int, default=10)
    ap.add_argument("--max-green", type=int, default=60)
    ap.add_argument("--n-envs", type=int, default=2, help="simulaciones SUMO en paralelo")
    ap.add_argument("--n-cpus", type=int, default=1,
                    help="procesos worker. Súbelo con cuidado: con >1 los "
                         "entornos corren en subprocesos y el arranque se "
                         "vuelve frágil (en Windows, además, cada worker "
                         "reimporta el módulo porque no hay fork)")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--optimizer", default="adam", choices=sorted(OPTIMIZADORES),
                    help="optimizador de la red (ver docstring)")
    ap.add_argument("--lr-schedule", default="linear", choices=["constant", "linear"],
                    help="linear: la tasa baja a 0 al final; afina sin desarmar lo aprendido")
    ap.add_argument("--control", default="auto", choices=["auto", "eje", "todos"],
                    help="semáforos que controla el agente (auto: los de tls_eje.json si existe)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="auto", help="auto|cpu|cuda")
    ap.add_argument("--out", default=None)
    ap.add_argument("--use-waze-obs", action="store_true", help="Añade datos simulados de Waze a la observación de la red")
    args = ap.parse_args()

    from stable_baselines3 import PPO
    from stable_baselines3.common.utils import set_random_seed

    set_random_seed(args.seed)

    try:
        import tensorboard  # noqa: F401
        tb_log = os.path.join("results", "tb")
    except ImportError:
        tb_log = None

    net = os.path.join(args.scenario, "net.net.xml")
    if args.routes:
        rou = args.routes
    elif args.profile:
        rou = os.path.join(args.scenario, "demand", f"routes_{args.profile}.rou.xml")
        if not os.path.exists(rou):
            rou = os.path.join(args.scenario, f"routes_{args.profile}.rou.xml")
    else:
        rou = os.path.join(args.scenario, "routes.rou.xml")

    if not os.path.exists(rou):
        sys.exit(f"Error: No se encontró el archivo de rutas {rou}")

    tag_profile = f"_{args.profile}" if args.profile else ""
    tag = f"ppo_{args.reward}_{args.optimizer}{tag_profile}"
    out = args.out or os.path.join("models", os.path.basename(args.scenario), tag)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    tls_ids = controlled_tls(args.scenario, args.control)
    print(f"Semáforos controlados: {'todos' if tls_ids is None else len(tls_ids)} · "
          f"optimizador {args.optimizer} · lr {args.lr} ({args.lr_schedule})")
    env = make_sb3_vec_env(
        num_vec_envs=args.n_envs,
        num_cpus=args.n_cpus,
        net_file=net,
        route_file=rou,
        reward=args.reward,
        num_seconds=args.seconds,
        delta_time=args.delta_time,
        min_green=args.min_green,
        max_green=args.max_green,
        seed=args.seed,
        use_waze_obs=args.use_waze_obs,
        tls_ids=tls_ids,
    )

    import torch as th

    opt_name, opt_kwargs = OPTIMIZADORES[args.optimizer]
    lr = args.lr if args.lr_schedule == "constant" else (lambda progreso: args.lr * progreso)
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=lr,
        policy_kwargs={"optimizer_class": getattr(th.optim, opt_name),
                       "optimizer_kwargs": opt_kwargs},
        max_grad_norm=0.5,  # recorta gradientes: un episodio malo no desarma la red
        n_steps=256,
        batch_size=256,
        n_epochs=10,
        gamma=0.95,        # el control de semáforos tiene horizonte corto
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,     # sin esto, colapsa a una sola fase muy rápido
        verbose=1,
        device=args.device,
        tensorboard_log=tb_log,
    )
    t0 = dt.datetime.now()
    model.learn(total_timesteps=args.steps, progress_bar=False, tb_log_name=os.path.basename(out))
    model.save(out)
    env.close()
    # Metadatos de la corrida: lo que hace falta para reproducirla y compararla
    meta = {k: v for k, v in vars(args).items()}
    meta.update({"modelo": out + ".zip", "rutas": rou, "commit_git": commit_actual(),
                 "inicio": t0.isoformat(timespec="seconds"),
                 "duracion_s": round((dt.datetime.now() - t0).total_seconds(), 1),
                 "semaforos_controlados": None if tls_ids is None else len(tls_ids),
                 "optimizador_kwargs": opt_kwargs})
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print(f"\nOK  modelo -> {out}.zip")
    print(f"    Evalúa con:  python scripts/eval_rl.py --scenario {args.scenario} --model {out}.zip "
          f"--control {args.control}")


if __name__ == "__main__":
    main()
