"""Pruebas de la API de simulación en vivo (app móvil «Vía»).

1. La cuenta regresiva se calcula bien sobre un programa sintético.
2. Con Webster cargado en SUMO, la predicción coincide con el cambio real.
3. La API responde de punta a punta sobre la red del eje (simulación sin pausa).
"""
import os
import sys
import time

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, RAIZ)

from api.simulacion import acortar, categoria, segundos_visibles, tiempo_hasta_cambio  # noqa: E402

GRID = os.path.join(RAIZ, "scenarios", "grid4x4")
EJE = os.path.join(RAIZ, "scenarios", "eje_comunal")


def test_cuenta_regresiva_en_programa_sintetico():
    # enlace 0: verde 30 s, amarillo 3 s, rojo 27 s
    fases = [("Gr", 30), ("yr", 3), ("rG", 24), ("ry", 3)]
    assert tiempo_hasta_cambio(fases, 0, 12, 0) == (12, "amarillo")
    assert tiempo_hasta_cambio(fases, 1, 2, 0) == (2, "rojo")
    # en rojo: quedan 5 s de la fase 2 y luego 3 s de amarillo transversal
    assert tiempo_hasta_cambio(fases, 2, 5, 0) == (8, "verde")
    # enlace que nunca cambia
    assert tiempo_hasta_cambio([("G", 30), ("G", 10)], 0, 4, 0) == (None, "verde")
    assert categoria("g") == "verde" and categoria("s") == "rojo"
    assert segundos_visibles(12.4) == 13 and segundos_visibles(None) is None
    assert acortar("Avenida Libertador Bernardo O&apos;Higgins") == "Alameda"
    assert acortar("Avenida Portugal") == "Av. Portugal"


@pytest.mark.skipif(not os.path.exists(os.path.join(GRID, "webster_plan.json")), reason="falta grid4x4")
def test_prediccion_coincide_con_el_cambio_real():
    from api.simulacion import SimulacionEnVivo
    from tsc.controllers import WebsterController
    from tsc.sumo_env import SumoSimulation

    sim = SumoSimulation(os.path.join(GRID, "net.net.xml"), os.path.join(GRID, "routes.rou.xml"), end=600)
    with sim:
        WebsterController(os.path.join(GRID, "webster_plan.json")).setup(sim)
        programas = SimulacionEnVivo._leer_programas(sim)
        sim.step(37)
        revisados = 0
        for tid in list(sim.tls)[:4]:
            c = sim.conn.trafficlight
            restante = c.getNextSwitch(tid) - sim.time
            segundos, siguiente = tiempo_hasta_cambio(programas[tid], c.getPhase(tid), restante, 0)
            if segundos is None:
                continue
            t0, color0 = sim.time, categoria(c.getRedYellowGreenState(tid)[0])
            while categoria(c.getRedYellowGreenState(tid)[0]) == color0 and sim.time < t0 + 300:
                sim.step()
            assert sim.time - t0 == pytest.approx(segundos_visibles(segundos), abs=1)
            assert categoria(c.getRedYellowGreenState(tid)[0]) == siguiente
            revisados += 1
        assert revisados >= 2


@pytest.mark.skipif(not os.path.exists(os.path.join(EJE, "webster_plan.json")), reason="falta eje_comunal")
def test_api_de_punta_a_punta(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("TSC_ESCENARIO", EJE)
    monkeypatch.setenv("TSC_VELOCIDAD", "20")
    monkeypatch.setenv("TSC_CALENTAMIENTO", "120")
    from api.main import app

    with TestClient(app) as cliente:
        assert cliente.get("/estado").json()["lista"] is True

        destinos = cliente.get("/destinos").json()
        assert [d["id"] for d in destinos] == ["bustamante", "matucana"]
        assert all(d["distancia_km"] > 1 for d in destinos)

        r = cliente.post("/viajes", json={"ruta": 0})
        assert r.status_code == 201
        viaje_id = r.json()["id"]

        semaforo, limite = None, time.monotonic() + 60
        while time.monotonic() < limite:
            foto = cliente.get(f"/viajes/{viaje_id}").json()
            semaforo = foto.get("proximo_semaforo")
            if foto["estado"] == "en_ruta" and semaforo:
                break
            time.sleep(0.2)
        assert semaforo, f"sin próximo semáforo: {foto}"
        assert semaforo["color"] in ("verde", "amarillo", "rojo")
        assert semaforo["segundos_para_cambio"] is None or semaforo["segundos_para_cambio"] >= 0
        assert semaforo["distancia_m"] >= 0 and semaforo["nombre"]
        assert foto["distancia_restante_m"] <= foto["distancia_total_m"]

        assert cliente.post("/viajes", json={"ruta": 9}).status_code == 422
        assert cliente.delete(f"/viajes/{viaje_id}").status_code == 204
        assert cliente.get(f"/viajes/{viaje_id}").json()["estado"] == "finalizado"
        assert cliente.get("/viajes/nada").status_code == 404
