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

# libsumo corre SUMO dentro del proceso: varias veces más rápido que TraCI, pero
# admite una sola simulación por proceso. Debe fijarse antes de importar sumo-rl.
if __name__ == "__main__" and "--traci" not in sys.argv:
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tsc.demand import rutas_entrenamiento  # noqa: E402
from tsc.rl_env import OBSERVACIONES, controlled_tls, make_sb3_vec_env  # noqa: E402

# Hiperparámetros de cada optimizador. eps=1e-5 es el que usa SB3 para Adam en
# PPO y para RMSprop en A2C (evita divisiones casi por cero al inicio).
OPTIMIZADORES = {
    "adam": ("Adam", {"eps": 1e-5}),
    "rmsprop": ("RMSprop", {"alpha": 0.99, "eps": 1e-5, "weight_decay": 0.0}),
}


def commit_actual() -> str:
    """Commit del código; con «+cambios» si se entrenó con cambios sin confirmar."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
        sucio = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit + ("+cambios" if sucio else "")
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
    ap.add_argument("--n-envs", type=int, default=1,
                    help="simulaciones SUMO en paralelo (con libsumo, una por worker)")
    ap.add_argument("--traci", action="store_true",
                    help="usa TraCI en vez de libsumo (más lento; permite varias simulaciones por proceso)")
    ap.add_argument("--obs", default="estandar", choices=sorted(OBSERVACIONES),
                    help="estandar: por pista (sumo-rl); fase: por fase, igual en todos los cruces")
    ap.add_argument("--checkpoint-every", type=int, default=250_000,
                    help="guarda la política cada tantas muestras (0 = no guarda)")
    ap.add_argument("--resume", default=None, help="continúa desde este .zip hasta --steps")
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
    ap.add_argument("--device", default="cpu",
                    help="cpu|cuda. Una MLP pequeña no gana con GPU: cada minilote paga la copia a la tarjeta")
    ap.add_argument("--out", default=None)
    ap.add_argument("--use-waze-obs", action="store_true", help="Añade datos simulados de Waze a la observación de la red")
    args = ap.parse_args()

    if not args.traci and args.n_envs > args.n_cpus:
        sys.exit("libsumo admite una simulación por proceso: usa --n-cpus >= --n-envs o --traci")

    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.utils import set_random_seed

    set_random_seed(args.seed)

    net = os.path.join(args.scenario, "net.net.xml")
    # Varias demandas de entrenamiento si el perfil las tiene: un episodio distinto
    # cada vez. Con --routes explícito se entrena sobre ese único archivo.
    pool = [] if args.routes else rutas_entrenamiento(args.scenario, args.profile)
    if args.routes:
        rou = args.routes
    elif pool:
        rou = pool[0]
    elif args.profile:
        rou = os.path.join(args.scenario, "demand", f"routes_{args.profile}.rou.xml")
        if not os.path.exists(rou):
            rou = os.path.join(args.scenario, f"routes_{args.profile}.rou.xml")
    else:
        rou = os.path.join(args.scenario, "routes.rou.xml")

    if not os.path.exists(rou):
        sys.exit(f"Error: No se encontró el archivo de rutas {rou}")

    tag_profile = f"_{args.profile}" if args.profile else ""
    tag = f"ppo_{args.obs}_{args.reward}_{args.optimizer}{tag_profile}_s{args.seed}"
    out = args.out or os.path.join("models", os.path.basename(args.scenario), tag)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    tls_ids = controlled_tls(args.scenario, args.control)
    print(f"Semáforos controlados: {'todos' if tls_ids is None else len(tls_ids)} · "
          f"optimizador {args.optimizer} · lr {args.lr} ({args.lr_schedule}) · obs {args.obs} · "
          f"demandas {len(pool) or 1} · {'TraCI' if args.traci else 'libsumo'}", flush=True)
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
        obs=args.obs,
        route_pool=pool or None,
    )

    import torch as th

    # Varias corridas conviven en 4 núcleos: PyTorch multihilo solo las estorba
    th.set_num_threads(1)

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
    )
    if args.resume:
        model.set_parameters(args.resume, device=args.device)
        previo = PPO.load(args.resume, device=args.device)
        model.num_timesteps = previo.num_timesteps
        del previo
        print(f"Continúa desde {args.resume} ({model.num_timesteps} muestras)", flush=True)
    # progress.csv: la curva de aprendizaje queda en disco aunque la corrida se corte
    model.set_logger(configure(out + "_log", ["stdout", "csv"]))
    guardado = None
    if args.checkpoint_every:
        guardado = CheckpointCallback(save_freq=max(1, args.checkpoint_every // env.num_envs),
                                      save_path=out + "_ckpt", name_prefix="paso")
    t0 = dt.datetime.now()
    # Metadatos de la corrida: lo que hace falta para reproducirla y compararla. Se
    # escriben al partir para que eval_rl pueda evaluar checkpoints durante la corrida.
    meta = {k: v for k, v in vars(args).items()}
    meta.update({"modelo": out + ".zip", "rutas": rou, "commit_git": commit_actual(),
                 "inicio": t0.isoformat(timespec="seconds"),
                 "semaforos_controlados": None if tls_ids is None else len(tls_ids),
                 "demandas_entrenamiento": pool or [rou],
                 "optimizador_kwargs": opt_kwargs})
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    if sys.platform == "win32":
        # El equipo no entra en suspensión mientras dure el proceso; se libera solo al terminar
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    # Al continuar, learn suma las muestras ya hechas: el total sigue siendo --steps
    # y la tasa de aprendizaje retoma donde iba.
    model.learn(total_timesteps=args.steps - model.num_timesteps, progress_bar=False,
                reset_num_timesteps=not args.resume, callback=guardado)
    model.save(out)
    env.close()
    meta.update({"duracion_s": round((dt.datetime.now() - t0).total_seconds(), 1),
                 "muestras": model.num_timesteps})
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print(f"\nOK  modelo -> {out}.zip")
    tag_eval = f"--profile {args.profile} " if args.profile else ""
    print(f"    Evalúa con:  python scripts/eval_rl.py --scenario {args.scenario} {tag_eval}"
          f"--model {out}.zip --control {args.control}")


if __name__ == "__main__":
    main()
