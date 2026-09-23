"""Ejecuta un controlador sobre un escenario y devuelve sus métricas.

Todos los controladores pasan exactamente por aquí, de modo que el protocolo
de medición (calentamiento, muestreo, cierre) sea idéntico y las diferencias
observadas sean atribuibles al controlador y no al arnés de evaluación.
"""
from __future__ import annotations

import os
import tempfile

from .metrics import StepSampler, parse_tripinfo
from .sumo_env import SumoSimulation


def run_episode(
    controller,
    net_file: str,
    route_file: str,
    *,
    seed: int = 0,
    end: int = 3600,
    warmup: int = 300,
    sample_every: int = 10,
    gui: bool = False,
    verbose: bool = False,
    tripinfo_path: str | None = None,
    keep_tripinfo: bool = False,
    waze_rerouting_threshold: float = -1.0,
    waze_reroute_pct: float = 0.2,
    use_gnn_router: bool = False,
) -> dict:
    tmp = None
    if tripinfo_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tripinfo_path = tmp.name
        tmp.close()

    sim = SumoSimulation(
        net_file=net_file,
        route_file=route_file,
        end=end,
        seed=seed,
        gui=gui,
        verbose=verbose,
        tripinfo=tripinfo_path,
    )
    sampler = StepSampler()

    with sim:
        controller.setup(sim)
        
        # Inicializar GNN Router si fue solicitado
        gnn = None
        if use_gnn_router:
            from .gnn_router import GNNRouter
            gnn = GNNRouter(net_file)
            
        interval = max(1, int(getattr(controller, "decision_interval", 5)))
        t = 0
        while sim.running():
            sim.step(interval)
            t += interval
            controller.act(sim)
            
            # --- Integración GNN ---
            if gnn is not None and t >= warmup and t % 10 == 0:
                gnn.act(sim) # Actualiza pesos de ruta en tiempo real
            # -----------------------
            
            # --- Integración Waze: Desvío Dinámico (Rerouting) ---
            if waze_rerouting_threshold > 0 and t >= warmup:
                # Proxy de índice Waze: suma del tiempo de espera de toda la red
                total_wait = sum(tl.waiting_time() for tl in sim.tls.values())
                
                if total_wait > waze_rerouting_threshold:
                    import random
                    # Desviar a un % de los vehículos que acaban de partir (nuevos conductores abriendo Waze)
                    departed = sim.conn.simulation.getDepartedIDList()
                    for veh in departed:
                        if random.random() < waze_reroute_pct:
                            try:
                                # Fuerza al vehículo a recalcular la ruta óptima dada la congestión actual
                                sim.conn.vehicle.rerouteTraveltime(veh)
                            except Exception:
                                pass # Algunos vehículos ya no pueden ser enrutados
            # ------------------------------------------------------
            
            if t >= warmup and t % sample_every < interval:
                sampler.sample(sim)
        controller.teardown(sim)

    result = {"controller": controller.name, "seed": seed}
    result.update(sampler.summary())
    result.update(parse_tripinfo(tripinfo_path))
    # Throughput: vehículos que completaron su viaje por hora simulada.
    # Se deriva de tripinfo, la misma fuente que usan las métricas por
    # vehículo, para que la definición sea idéntica en todos los
    # controladores (incluido el agente aprendido).
    result["throughput"] = result.get("vehicles_finished", 0) / max(1e-9, end / 3600.0)

    if tmp is not None and not keep_tripinfo:
        os.unlink(tripinfo_path)
    return result


def measure_phase_flows(
    net_file: str,
    route_file: str,
    *,
    seed: int = 0,
    end: int = 3600,
    warmup: int = 300,
    sample_every: int = 2,
) -> dict:
    """Corrida de calibración: flujo de llegada por fase, en veh/h.

    Alimenta el método de Webster. El flujo por pista se mide contando
    vehículos *distintos* observados sobre la pista de aproximación, no
    promediando ocupación: la ocupación es densidad, no flujo, y confundirlas
    produce ciclos de Webster sistemáticamente subestimados.

    El intervalo de muestreo debe ser menor que el tiempo de recorrido de la
    pista más corta, o se pierden vehículos. Con pistas de 100 m a 50 km/h eso
    son ~7 s; por eso el valor por defecto es 2 s.
    """
    from .controllers.fixed import FixedTimeController

    sim = SumoSimulation(net_file=net_file, route_file=route_file, end=end, seed=seed)
    flows: dict = {}

    with sim:
        FixedTimeController().setup(sim)
        seen = {
            tid: {ln: set() for ln in tl.incoming_lanes}
            for tid, tl in sim.tls.items()
        }
        t = 0
        while sim.running():
            sim.step(sample_every)
            t += sample_every
            if t < warmup:
                continue
            for tid, tl in sim.tls.items():
                for ln in tl.incoming_lanes:
                    seen[tid][ln].update(sim.conn.lane.getLastStepVehicleIDs(ln))

        hours = max(1e-9, (t - warmup) / 3600.0)
        for tid, tl in sim.tls.items():
            per_lane = {ln: len(v) / hours for ln, v in seen[tid].items()}
            flows[tid] = {
                # el movimiento crítico define la fase, dividido por el número
                # de pistas que comparten ese movimiento (flujo por pista)
                str(p.index): max(
                    [per_lane.get(ln, 0.0) for ln in p.incoming_lanes] or [0.0]
                )
                for p in tl.green_phases
            }
    return flows
