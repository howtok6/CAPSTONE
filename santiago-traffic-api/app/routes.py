from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from app.schemas import BoundingBox, FlowResponse, IncidentsResponse, Point, RouteResponse

router = APIRouter(prefix="/api/traffic", tags=["Tránsito"])


@router.get(
    "/flow/tiles/{zoom}/{x}/{y}",
    response_class=Response,
    summary="Tesela vectorial de flujo (Orbis v2)",
    description=(
        "Devuelve datos binarios MVT/PBF para un mapa. "
        "zoom, x e y identifican una tesela; no son latitud y longitud. "
        "No devuelve JSON ni una imagen."
    ),
    responses={
        200: {
            "description": "Tesela vectorial de flujo de TomTom",
            "content": {
                "application/vnd.mapbox-vector-tile": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def get_flow_tile(
    request: Request,
    zoom: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0, le=2**22 - 1)],
    y: Annotated[int, Path(ge=0, le=2**22 - 1)],
) -> Response:
    if x >= 2**zoom or y >= 2**zoom:
        raise HTTPException(422, "x e y deben estar entre 0 y 2^zoom - 1.")
    content = await request.app.state.tomtom.flow_tile(zoom, x, y)
    return Response(content=content, media_type="application/vnd.mapbox-vector-tile")


@router.get(
    "/route",
    response_model=RouteResponse,
    summary="Ruta en automóvil con tránsito actual (Orbis v2)",
    description=(
        "Calcula un recorrido entre origen y destino, saliendo ahora. "
        "Incluye distancia, tiempo estimado con tránsito, demora y coordenadas de la ruta."
    ),
)
async def get_route(
    request: Request,
    origin_lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    origin_lon: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    destination_lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    destination_lon: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
) -> RouteResponse:
    return await request.app.state.tomtom.route(
        Point(latitude=origin_lat, longitude=origin_lon),
        Point(latitude=destination_lat, longitude=destination_lon),
    )


@router.get("/flow", response_model=FlowResponse, summary="Flujo cerca de una coordenada")
async def get_flow(
    request: Request,
    lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    lon: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    zoom: Annotated[int, Query(ge=0, le=22)] = 15,
) -> FlowResponse:
    return await request.app.state.tomtom.flow(Point(latitude=lat, longitude=lon), zoom)


@router.get("/incidents", response_model=IncidentsResponse, summary="Incidentes dentro de una zona")
async def get_incidents(
    request: Request,
    bbox: Annotated[
        str,
        Query(
            max_length=100,
            description="minLon,minLat,maxLon,maxLat. Área máxima: 10.000 km².",
            examples=["-70.70,-33.47,-70.63,-33.42"],
        ),
    ],
) -> IncidentsResponse:
    try:
        parts = [float(part.strip()) for part in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Se requieren cuatro coordenadas")
        bounds = BoundingBox.model_validate(
            dict(zip(("min_lon", "min_lat", "max_lon", "max_lat"), parts, strict=True))
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "bbox debe tener minLon,minLat,maxLon,maxLat con coordenadas válidas, "
                "mínimos menores que máximos y área máxima de 10.000 km²."
            ),
        ) from None
    return await request.app.state.tomtom.incidents(bounds)
