#!/usr/bin/env python3
"""Graba un video de la simulación con el controlador que elijas.

Usa sumo-gui de verdad (no un dibujo aparte), así que lo que ves en el video
es exactamente lo que verías en pantalla. En un servidor sin monitor se apoya
en Xvfb; en tu WSL2 con WSLg funciona igual, o puedes abrir la GUI directo:

    sumo-gui -c scenarios/apoquindo/apoquindo.sumocfg

Ejemplos:

    python scripts/record_run.py --scenario scenarios/apoquindo \\
        --controller maxpressure --begin 600 --seconds 240

    # comparación lado a lado
    python scripts/record_run.py --scenario scenarios/apoquindo \\
        --controller fixed --out results/video/fixed
    python scripts/record_run.py --scenario scenarios/apoquindo \\
        --controller maxpressure --out results/video/maxpressure

`--begin` salta los primeros segundos: al arrancar la red está vacía y no se
ve nada interesante hasta que la demanda carga.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsc.controllers import (  # noqa: E402
    FixedTimeController,
    GreedyQueueController,
    MaxPressureController,
    WebsterController,
)
from tsc.sumo_env import SumoSimulation  # noqa: E402

CONTROLLERS = {
    "fixed": lambda scen: FixedTimeController(),
    "greedy": lambda scen: GreedyQueueController(),
    "maxpressure": lambda scen: MaxPressureController(),
    "webster": lambda scen: WebsterController(
        os.path.join(scen, "webster_plan.json")
    ),
}


def have_display() -> bool:
    return bool(os.environ.get("DISPLAY"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--controller", default="maxpressure", choices=sorted(CONTROLLERS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--begin", type=int, default=600,
                    help="segundos simulados a saltar antes de grabar")
    ap.add_argument("--seconds", type=int, default=240,
                    help="segundos simulados a grabar")
    ap.add_argument("--every", type=int, default=1,
                    help="capturar un cuadro cada N segundos simulados")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--zoom", type=float, default=None,
                    help="anula el zoom de gui-settings.xml")
    ap.add_argument("--center", default=None, help="x,y del centro de la vista")
    ap.add_argument("--out", default=None)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    net = os.path.join(args.scenario, "net.net.xml")
    rou = os.path.join(args.scenario, "routes.rou.xml")
    gui_settings = os.path.join(args.scenario, "gui-settings.xml")

    out = args.out or os.path.join(
        "results", "video", f"{os.path.basename(args.scenario)}_{args.controller}"
    )
    frames = out + "_frames"
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames, exist_ok=True)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    # `--quit-on-end` es obligatorio: sin él, sumo-gui se queda abierto al
    # terminar y `traci.close()` nunca retorna (el script parece colgado).
    extra = [
        "--window-size", f"{args.width},{args.height}",
        "--start", "true", "--quit-on-end", "true",
    ]
    if os.path.exists(gui_settings):
        extra += ["--gui-settings-file", gui_settings]

    sim = SumoSimulation(
        net_file=net, route_file=rou,
        end=args.begin + args.seconds, seed=args.seed,
        gui=True, extra_args=extra,
    )

    controller = CONTROLLERS[args.controller](args.scenario)

    with sim:
        controller.setup(sim)
        gui = sim.conn.gui
        if args.zoom or args.center:
            x, y = (
                [float(v) for v in args.center.split(",")]
                if args.center else gui.getOffset("View #0")
            )
            gui.setOffset("View #0", x, y)
            if args.zoom:
                gui.setZoom("View #0", args.zoom)

        # Se avanza de a un segundo simulado para que el video sea fluido; el
        # controlador decide cada `decision_interval`, igual que en los
        # experimentos, de modo que lo grabado es la ejecución real y no una
        # versión ralentizada para la cámara.
        interval = max(1, int(getattr(controller, "decision_interval", 5)))
        t, frame, since_decision = 0, 0, 0
        end_t = args.begin + args.seconds
        while sim.running() and t < end_t:
            sim.step(1)
            t += 1
            since_decision += 1
            if since_decision >= interval:
                controller.act(sim)
                since_decision = 0
            if t >= args.begin and (t - args.begin) % args.every == 0:
                gui.screenshot("View #0", os.path.join(frames, f"f{frame:05d}.png"))
                frame += 1
                if frame % 25 == 0:
                    print(f"  {frame} cuadros…", flush=True)
        controller.teardown(sim)

    n = len([f for f in os.listdir(frames) if f.endswith(".png")])
    if n == 0:
        raise SystemExit("No se capturó ningún cuadro. ¿Está corriendo sumo-gui?")
    print(f"  {n} cuadros capturados")

    mp4 = out + ".mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps),
         "-i", os.path.join(frames, "f%05d.png"),
         "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", mp4],
        check=True,
    )
    if not args.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)
    print(f"OK  {mp4}")


if __name__ == "__main__":
    main()
