import json
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.study import (
    LIMITATIONS,
    StudySnapshot,
    collect_snapshot,
    list_studies,
    load_study,
    snapshot_csv,
)

router = APIRouter(prefix="/api/studies", tags=["Pilotos por comuna"])


@router.get("", summary="Comunas disponibles, sin consultar TomTom")
async def get_studies():
    return {
        "scope": "Provincia de Santiago",
        "commune_count": len(list_studies()),
        "point_count": sum(len(config.points) for config in list_studies()),
        "studies": [
            {
                "id": config.id,
                "commune": config.commune,
                "name": config.name,
                "point_count": len(config.points),
                "table_url": f"/{config.id}",
                "config_url": f"/api/studies/{config.id}",
            }
            for config in list_studies()
        ],
    }


@router.get(
    "/{study_id}", summary="Configuración: ubicaciones y fuentes, sin mediciones de velocidad"
)
async def get_study(study_id: str):
    config = load_study(study_id)
    return {
        **config.model_dump(mode="json"),
        "requests_per_capture": {
            "flow_only": len(config.points),
            "flow_and_incidents": len(config.points) + 1,
            "flow_incidents_and_routes": len(config.points) + 1 + len(config.route_pairs),
        },
        "limitations": LIMITATIONS,
    }


@router.get(
    "/{study_id}/points.geojson", summary="Cruces de referencia para un mapa (sin consultar TomTom)"
)
async def get_points(study_id: str):
    config = load_study(study_id)
    return Response(
        content=json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": point.id,
                        "geometry": {
                            "type": "Point",
                            "coordinates": [point.longitude, point.latitude],
                        },
                        "properties": {
                            "uoct_id": point.id,
                            "name": point.name,
                            "corridor": point.corridor,
                            "commune": config.commune,
                            "inventory_revision": config.inventory_revision.isoformat(),
                            "source": config.inventory_source,
                            "source_page": point.source_page,
                            "source_commune": point.source_commune,
                            "current_signal_state_verified": False,
                        },
                    }
                    for point in config.points
                ],
            },
            ensure_ascii=False,
        ),
        media_type="application/geo+json",
    )


@router.get(
    "/{study_id}/snapshot",
    response_model=StudySnapshot,
    summary="Mediciones: velocidad actual, tiempos de referencia y demora",
    description=(
        "Las mediciones aparecen en flows → flow. Los objetos point y coordinates "
        "solo contienen ubicaciones. Para leer los valores en una tabla, abre /comunas. "
        "Esta integración no entrega aceleración."
    ),
)
async def get_snapshot(
    study_id: str,
    request: Request,
    response: Response,
    include_incidents: Annotated[
        bool, Query(description="Agrega una consulta de incidentes")
    ] = True,
    include_routes: Annotated[bool, Query(description="Agrega dos consultas de rutas")] = False,
) -> StudySnapshot:
    response.headers["Cache-Control"] = "no-store"
    snapshot = await collect_snapshot(
        request.app.state.tomtom,
        study_id=study_id,
        include_incidents=include_incidents,
        include_routes=include_routes,
    )
    if snapshot.status == "failed":
        response.status_code = 502
    return snapshot


@router.get(
    "/{study_id}/snapshot.csv",
    response_class=Response,
    summary="Descarga de velocidades y demoras actuales en CSV (6 consultas)",
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
async def get_snapshot_csv(study_id: str, request: Request) -> Response:
    snapshot = await collect_snapshot(
        request.app.state.tomtom,
        study_id=study_id,
        include_incidents=False,
        include_routes=False,
    )
    return Response(
        content=snapshot_csv(snapshot),
        status_code=502 if snapshot.status == "failed" else 200,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{snapshot.study_id.replace("-", "_")}_flujo_actual.csv"'
            ),
            "Cache-Control": "no-store",
            "X-Capture-Status": snapshot.status,
        },
    )
