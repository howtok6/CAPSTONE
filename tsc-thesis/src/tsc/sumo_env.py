"""Thin, controller-agnostic wrapper around a SUMO simulation.

Every controller in this project sees the network through this class, so that
the comparison between classical and learned controllers is apples-to-apples:
same network, same demand, same measurement points, same clock.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

if "SUMO_HOME" not in os.environ:
    try:
        import sumo  # noqa: F401  (pip package `eclipse-sumo`)
        os.environ["SUMO_HOME"] = os.path.dirname(sumo.__file__)
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "SUMO_HOME no está definido y el paquete `eclipse-sumo` no está instalado."
        ) from exc

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

try:
    import libsumo as _traci  # ~8x más rápido que TraCI, sin GUI
    LIBSUMO = True
except ImportError:  # pragma: no cover
    import traci as _traci
    LIBSUMO = False


@dataclass
class Phase:
    """Una fase semafórica, pre-analizada para que los controladores no
    tengan que volver a interpretar el estado de SUMO en cada paso."""

    index: int
    state: str
    duration: float
    min_dur: float
    max_dur: float
    is_green: bool
    incoming_lanes: tuple = field(default_factory=tuple)
    outgoing_lanes: tuple = field(default_factory=tuple)
    movements: tuple = field(default_factory=tuple)  # pares (in_lane, out_lane)


class TrafficLight:
    """Vista estática + dinámica de una intersección semaforizada."""

    def __init__(self, tls_id: str, conn):
        self.id = tls_id
        self.conn = conn
        logic = conn.trafficlight.getAllProgramLogics(tls_id)[0]
        self.program_id = logic.programID
        self.links = conn.trafficlight.getControlledLinks(tls_id)

        self.phases = []
        for i, p in enumerate(logic.phases):
            state = p.state
            is_green = ("y" not in state.lower()) and ("g" in state.lower())
            inc, out, movs = set(), set(), []
            if is_green:
                for li, signal in enumerate(state):
                    if signal in "gG" and li < len(self.links) and self.links[li]:
                        in_lane, out_lane, _ = self.links[li][0]
                        inc.add(in_lane)
                        out.add(out_lane)
                        movs.append((in_lane, out_lane))
            self.phases.append(
                Phase(
                    index=i,
                    state=state,
                    duration=p.duration,
                    min_dur=getattr(p, "minDur", p.duration),
                    max_dur=getattr(p, "maxDur", p.duration),
                    is_green=is_green,
                    incoming_lanes=tuple(sorted(inc)),
                    outgoing_lanes=tuple(sorted(out)),
                    movements=tuple(movs),
                )
            )
        self.green_phases = [p for p in self.phases if p.is_green]
        self.green_indices = [p.index for p in self.green_phases]
        self.incoming_lanes = sorted({lk[0][0] for lk in self.links if lk})
        self.outgoing_lanes = sorted({lk[0][1] for lk in self.links if lk})
        self.lane_length = {ln: conn.lane.getLength(ln) for ln in self.incoming_lanes}
        for ln in self.outgoing_lanes:
            self.lane_length.setdefault(ln, conn.lane.getLength(ln))

    # --- estado dinámico ------------------------------------------------
    def queue(self, lane: str) -> int:
        return self.conn.lane.getLastStepHaltingNumber(lane)

    def vehicles(self, lane: str) -> int:
        return self.conn.lane.getLastStepVehicleNumber(lane)

    def density(self, lane: str) -> float:
        n = self.conn.lane.getLastStepVehicleNumber(lane)
        cap = max(1.0, self.lane_length.get(lane, 100.0) / 7.5)
        return min(1.0, n / cap)

    def total_queue(self) -> int:
        return sum(self.queue(ln) for ln in self.incoming_lanes)

    def waiting_time(self) -> float:
        return sum(
            self.conn.lane.getWaitingTime(ln) for ln in self.incoming_lanes
        )

    def current_phase(self) -> int:
        return self.conn.trafficlight.getPhase(self.id)

    def set_phase(self, index: int) -> None:
        self.conn.trafficlight.setPhase(self.id, index)

    def set_phase_duration(self, seconds: float) -> None:
        self.conn.trafficlight.setPhaseDuration(self.id, seconds)

    def yellow_between(self, from_idx: int, to_idx: int):
        """Índice de la fase de transición (ámbar/rojo) entre dos fases verdes."""
        n = len(self.phases)
        step = (from_idx + 1) % n
        while step != to_idx:
            if not self.phases[step].is_green:
                return step
            step = (step + 1) % n
        return None


class SumoSimulation:
    """Dueño del proceso SUMO; expone lo que los controladores necesitan."""

    def __init__(
        self,
        net_file: str,
        route_file: str,
        *,
        begin: int = 0,
        end: int = 3600,
        step_length: float = 1.0,
        seed: int = 0,
        gui: bool = False,
        tripinfo: str | None = None,
        verbose: bool = False,
        extra_args: list | None = None,
    ):
        self.net_file = net_file
        self.route_file = route_file
        self.begin = begin
        self.end = end
        self.step_length = step_length
        self.seed = seed
        self.gui = gui
        self.tripinfo = tripinfo
        self.verbose = verbose
        self.extra_args = extra_args or []
        self.conn = None
        self.tls: dict = {}

    def start(self):
        binary = "sumo-gui" if self.gui else "sumo"
        cmd = [
            binary,
            "-n", self.net_file,
            "-r", self.route_file,
            "--begin", str(self.begin),
            "--end", str(self.end),
            "--step-length", str(self.step_length),
            "--seed", str(self.seed),
            "--time-to-teleport", "-1",   # nunca teletransportar: el bloqueo debe verse
            "--waiting-time-memory", "10000",
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--duration-log.statistics", str(self.verbose).lower(),
            "--verbose", str(self.verbose).lower(),
        ] + self.extra_args
        if self.tripinfo:
            cmd += ["--tripinfo-output", self.tripinfo]

        if self.gui or not LIBSUMO:
            import traci as t
            t.start(cmd)
            self.conn = t
        else:
            _traci.start(cmd)
            self.conn = _traci

        self.tls = {
            tid: TrafficLight(tid, self.conn)
            for tid in self.conn.trafficlight.getIDList()
        }
        return self

    def step(self, n: int = 1):
        for _ in range(n):
            self.conn.simulationStep()

    @property
    def time(self) -> float:
        return self.conn.simulation.getTime()

    def running(self) -> bool:
        return (
            self.time < self.end
            and self.conn.simulation.getMinExpectedNumber() > 0
        )

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
