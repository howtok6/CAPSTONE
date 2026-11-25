"""Pruebas del servicio de simulación (entorno de pruebas del backend).

1. La cuenta regresiva se calcula bien sobre un programa sintético.
2. Con Webster cargado en SUMO, la predicción coincide con el cambio real.
3. El servicio responde de punta a punta sobre la red del eje: viajes simulados
   y proveedor de tráfico (semáforos, estado por acceso, calles y tráfico).
4. En el área (Las Condes + Providencia) se simulan viajes libres entre dos
   puntos cualesquiera, y se rechazan los que quedan fuera del área.
"""
import os
import sys
import time

import pytest

AQUI = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, AQUI)

from via_sim.simulacion import (  # noqa: E402
    RAIZ,
    acortar,
    categoria,
    dentro_de_poligono,
    nivel_de_servicio,
    rumbo,
    segundos_visibles,
    tiempo_hasta_cambio,
)

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


def test_rumbo_y_nivel_de_servicio():
    assert rumbo(0, 0, 0, 10) == 0.0  # norte
    assert rumbo(0, 0, 10, 0) == 90.0  # este
    assert rumbo(0, 0, 0, -10) == 180.0
    assert rumbo(0, 0, -10, 0) == 270.0
    assert nivel_de_servicio(45, 50, 3) == "fluido"
    assert nivel_de_servicio(25, 50, 3) == "moderado"
    assert nivel_de_servicio(5, 50, 8) == "congestionado"
    assert nivel_de_servicio(0, 50, 0) == "libre"


def test_dentro_de_poligono():
    cuadrado = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert dentro_de_poligono(5, 5, cuadrado)
    assert not dentro_de_poligono(15, 5, cuadrado)
    assert not dentro_de_poligono(5, -1, cuadrado)


@pytest.mark.skipif(not os.path.exists(os.path.join(GRID, "webster_plan.json")), reason="falta grid4x4")
def test_prediccion_coincide_con_el_cambio_real():
    from via_sim.simulacion import SimulacionEnVivo
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
    from via_sim.main import app

    with TestClient(app) as cliente:
        assert cliente.get("/estado").json()["lista"] is True

        destinos = cliente.get("/destinos").json()
        assert [d["id"] for d in destinos] == ["bustamante", "matucana"]
        assert all(d["distancia_km"] > 1 for d in destinos)
        for d in destinos:
            # El trazado parte cerca del origen y llega cerca del destino.
            assert len(d["trazado"]) >= 2
            assert abs(d["trazado"][0][0] - (-33.4433)) < 0.003
            assert abs(d["trazado"][0][1] - (-70.6505)) < 0.003
            fin = {"bustamante": (-33.43696, -70.63313), "matucana": (-33.45068, -70.67882)}[d["id"]]
            assert abs(d["trazado"][-1][0] - fin[0]) < 0.003
            assert abs(d["trazado"][-1][1] - fin[1]) < 0.003
            # Semáforos en orden de paso, con nombre y ubicación.
            distancias = [s["distancia_desde_inicio_m"] for s in d["semaforos"]]
            assert distancias == sorted(distancias)
            assert all(s["nombre"] and s["lat"] < -33 for s in d["semaforos"])
        assert any(d["semaforos"] for d in destinos)

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

        # --- proveedor de tráfico
        semaforos = cliente.get("/semaforos").json()
        assert len(semaforos) >= 80
        s0 = semaforos[0]
        assert -33.6 < s0["lat"] < -33.3 and -70.8 < s0["lon"] < -70.4
        assert s0["accesos"] and all(0 <= a["rumbo"] < 360 for a in s0["accesos"])

        estado = cliente.get("/semaforos/estado", params={"ids": s0["id"]}).json()
        accesos = estado["semaforos"][s0["id"]]
        assert set(accesos) == {a["id"] for a in s0["accesos"]}
        for a in accesos.values():
            assert a["color"] in ("verde", "amarillo", "rojo", "apagado")
            assert a["segundos_para_cambio"] is None or a["segundos_para_cambio"] >= 0
        assert len(cliente.get("/semaforos/estado").json()["semaforos"]) == len(semaforos)

        calles = cliente.get("/red/calles").json()
        assert len(calles) > 500 and all(len(c["forma"]) >= 2 for c in calles[:50])
        trafico = cliente.get("/trafico").json()
        assert {c["id"] for c in trafico["calles"]} == {c["id"] for c in calles}
        assert {c["nivel"] for c in trafico["calles"]} <= {"libre", "fluido", "moderado", "congestionado"}


AREA = os.path.join(RAIZ, "scenarios", "las_condes_providencia")


@pytest.mark.skipif(not os.path.exists(os.path.join(AREA, "net.net.xml")), reason="falta las_condes_providencia")
def test_area_elige_demanda_plan_y_recorridos():
    """El área no trae routes.rou.xml: toma la demanda y el plan Webster del perfil
    (punta tarde por defecto) y sus propios recorridos de demostración."""
    from via_sim.simulacion import SimulacionEnVivo

    sim = SimulacionEnVivo(AREA)
    assert sim.perfil == "eod_punta_tarde"
    assert sim.route_file.endswith(os.path.join("demand", "routes_eod_punta_tarde.rou.xml"))
    assert sim.plan.endswith("webster_plan_eod_punta_tarde.json")
    assert os.path.exists(sim.route_file) and os.path.exists(sim.plan)
    assert len(sim.destinos_def) == 3 and sim.origen[0].startswith("Av. Providencia")
    valle = SimulacionEnVivo(AREA, perfil="eod_valle")
    assert valle.plan.endswith("webster_plan_eod_valle.json")


@pytest.mark.skipif(
    not os.path.exists(os.path.join(AREA, "demand", "routes_eod_punta_tarde.rou.xml")),
    reason="falta la demanda del área",
)
def test_viaje_libre_en_el_area(monkeypatch):
    """Un recorrido A → B elegido en la app: la simulación calcula la ruta, pone un
    vehículo en ella y entrega su trazado y semáforos; los puntos fuera del área o
    demasiado juntos se rechazan con un mensaje claro."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("TSC_ESCENARIO", AREA)
    monkeypatch.setenv("TSC_VELOCIDAD", "20")
    monkeypatch.setenv("TSC_CALENTAMIENTO", "60")
    from via_sim.main import app

    costanera = {"lat": -33.4176, "lon": -70.6065}
    escuela_militar = {"lat": -33.4140, "lon": -70.5847}
    with TestClient(app) as cliente:
        r = cliente.post("/viajes", json={
            "origen": costanera, "destino": escuela_militar, "nombre_destino": "Escuela Militar",
        })
        assert r.status_code == 201, r.text
        viaje = r.json()
        assert viaje["ruta"] is None and viaje["destino"] == "Escuela Militar"
        recorrido = viaje["recorrido"]
        assert 1 < recorrido["distancia_km"] < 6
        # El trazado parte cerca de A y llega cerca de B.
        assert abs(recorrido["trazado"][0][0] - costanera["lat"]) < 0.003
        assert abs(recorrido["trazado"][0][1] - costanera["lon"]) < 0.003
        assert abs(recorrido["trazado"][-1][0] - escuela_militar["lat"]) < 0.003
        assert abs(recorrido["trazado"][-1][1] - escuela_militar["lon"]) < 0.003
        distancias = [s["distancia_desde_inicio_m"] for s in recorrido["semaforos"]]
        assert distancias and distancias == sorted(distancias)

        # El vehículo avanza y ve sus semáforos, igual que en un recorrido de demostración.
        semaforo, limite = None, time.monotonic() + 60
        while time.monotonic() < limite:
            foto = cliente.get(f"/viajes/{viaje['id']}").json()
            semaforo = foto.get("proximo_semaforo")
            if foto["estado"] == "en_ruta" and semaforo:
                break
            time.sleep(0.2)
        assert semaforo, f"sin próximo semáforo: {foto}"
        assert semaforo["color"] in ("verde", "amarillo", "rojo")
        assert "recorrido" not in foto  # el trazado solo viaja al crear
        assert cliente.delete(f"/viajes/{viaje['id']}").status_code == 204

        # Sin nombre, el destino toma el de la calle de llegada.
        r = cliente.post("/viajes", json={"origen": escuela_militar, "destino": costanera})
        assert r.status_code == 201 and r.json()["destino"]
        cliente.delete(f"/viajes/{r.json()['id']}")

        plaza_de_armas = {"lat": -33.4378, "lon": -70.6504}
        r = cliente.post("/viajes", json={"origen": plaza_de_armas, "destino": escuela_militar})
        assert r.status_code == 422 and "fuera del área" in r.json()["detail"]
        r = cliente.post("/viajes", json={"origen": costanera, "destino": {"lat": -33.4177, "lon": -70.6066}})
        assert r.status_code == 422 and "menos de" in r.json()["detail"]
        r = cliente.post("/viajes", json={"origen": costanera})
        assert r.status_code == 422 and "origen y destino" in r.json()["detail"]
        # Los recorridos de demostración siguen igual.
        assert cliente.post("/viajes", json={"ruta": 0}).status_code == 201
