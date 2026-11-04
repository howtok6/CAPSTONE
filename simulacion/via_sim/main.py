"""API HTTP del servicio de simulación (FastAPI).

Es un servicio interno: solo lo consulta el backend Go, nunca la app.

Ejecutar desde simulacion/:
    python run.py                 # tiempo real, puerto 8000
    python run.py --velocidad 5

Variables de entorno (las fija run.py): TSC_RAIZ, TSC_ESCENARIO, TSC_VELOCIDAD,
TSC_CALENTAMIENTO.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .simulacion import RAIZ, SimulacionEnVivo


class NuevoViaje(BaseModel):
    ruta: int = Field(0, ge=0, description="Índice del destino (ver GET /destinos)")


def _simulacion_desde_entorno() -> SimulacionEnVivo:
    return SimulacionEnVivo(
        os.environ.get("TSC_ESCENARIO", str(RAIZ / "scenarios" / "eje_comunal")),
        velocidad=float(os.environ.get("TSC_VELOCIDAD", "1")),
        calentamiento=int(os.environ.get("TSC_CALENTAMIENTO", "300")),
    )


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    sim = _simulacion_desde_entorno()
    app.state.sim = sim.iniciar()
    yield
    sim.detener()


app = FastAPI(title="Vía · Servicio de simulación", version="0.2.0", lifespan=ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/estado")
def estado():
    return app.state.sim.estado()


@app.get("/destinos")
def destinos():
    return app.state.sim.destinos()


@app.post("/viajes", status_code=201)
def crear_viaje(cuerpo: NuevoViaje):
    try:
        return app.state.sim.crear_viaje(cuerpo.ruta)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/viajes/{viaje_id}")
def ver_viaje(viaje_id: str):
    foto = app.state.sim.viaje(viaje_id)
    if foto is None:
        raise HTTPException(404, "viaje no encontrado")
    return foto


@app.delete("/viajes/{viaje_id}", status_code=204)
def finalizar_viaje(viaje_id: str):
    if not app.state.sim.finalizar_viaje(viaje_id):
        raise HTTPException(404, "viaje no encontrado")
    return Response(status_code=204)


# --- Proveedor de tráfico ---------------------------------------------------
@app.get("/semaforos")
def semaforos():
    """Semáforos de la red: ubicación y accesos con su rumbo (estático)."""
    return app.state.sim.semaforos()


@app.get("/semaforos/estado")
def estado_semaforos(ids: str | None = Query(None, description="ids separados por coma; vacío = todos")):
    """Color y cuenta regresiva de cada acceso, en el instante actual."""
    lista = [i for i in (ids or "").split(",") if i]
    return app.state.sim.estado_semaforos(lista or None)


@app.get("/red/calles")
def calles():
    """Calles de la red con su geometría y velocidad libre (estático)."""
    return app.state.sim.calles()


@app.get("/trafico")
def trafico():
    """Velocidad media, vehículos y nivel de servicio por calle (cada 5 s simulados)."""
    return app.state.sim.trafico()
