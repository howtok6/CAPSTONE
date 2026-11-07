"""Obtención acotada de datos actuales por comuna."""

import csv
import io
from datetime import UTC, date, datetime
from functools import lru_cache
from importlib.resources import files
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from app.communes import COMMUNES
from app.schemas import BoundingBox, FlowResponse, IncidentsResponse, Point, RouteResponse
from app.tomtom import TomTomError, TomTomService

LIMITATIONS = [
    "Muestra de puntos seleccionados; no es un histórico ni representa toda la comuna.",
    "Cada punto consulta el tramo más cercano. La vía y el sentido deben validarse en el mapa.",
    "Una consulta en el centro del cruce no mide todos sus accesos ni aísla demora semafórica.",
    "Las llamadas se realizan secuencialmente: la captura no es una instantánea simultánea.",
    "Tramos devueltos por puntos distintos pueden coincidir; no sumar sus demoras.",
    "La velocidad de flujo libre no es el límite legal de velocidad.",
    "Faltan aforos, giros, colas, fases, ciclos, verdes, entreverdes y desfases para semáforos.",
    "La ventana de incidentes es un rectángulo piloto, no el polígono comunal.",
    "Retener y reutilizar un histórico requiere verificar las condiciones del producto contratado.",
]

STUDY_FILES = {slug: f"{slug.replace('-', '_')}.json" for slug in COMMUNES}


class UnknownStudyError(ValueError):
    pass


class StudyPoint(Point):
    id: str
    name: str
    corridor: str
    source_page: int = Field(ge=1)
    source_commune: str | None = None
    source_latitude_raw: str | None = None
    source_longitude_raw: str | None = None


class RoutePair(BaseModel):
    id: str
    origin_id: str
    destination_id: str


class StudyConfig(BaseModel):
    id: str
    commune: str
    name: str
    timezone: str
    scope: str
    inventory_source: str
    inventory_revision: date
    inventory_note: str
    bbox: BoundingBox
    points: list[StudyPoint] = Field(min_length=1, max_length=12)
    route_pairs: list[RoutePair] = Field(max_length=4)

    @model_validator(mode="after")
    def validate_points_and_routes(self) -> Self:
        ids = {point.id for point in self.points}
        if len(ids) != len(self.points):
            raise ValueError("Los puntos deben tener identificadores únicos")
        for point in self.points:
            if not (
                self.bbox.min_lon <= point.longitude <= self.bbox.max_lon
                and self.bbox.min_lat <= point.latitude <= self.bbox.max_lat
            ):
                raise ValueError("Los puntos deben estar dentro de la ventana piloto")
        if len({route.id for route in self.route_pairs}) != len(self.route_pairs):
            raise ValueError("Las rutas deben tener identificadores únicos")
        for route in self.route_pairs:
            if route.origin_id not in ids or route.destination_id not in ids:
                raise ValueError("Cada ruta debe referenciar puntos existentes")
        ZoneInfo(self.timezone)
        return self


@lru_cache(maxsize=len(STUDY_FILES))
def load_study(study_id: str = "las-condes") -> StudyConfig:
    if study_id not in STUDY_FILES:
        raise UnknownStudyError("La comuna solicitada no está disponible en este piloto.")
    path = files("app").joinpath(f"data/{STUDY_FILES[study_id]}")
    config = StudyConfig.model_validate_json(path.read_text(encoding="utf-8"))
    if config.id != study_id:
        raise ValueError("El identificador de la configuración no coincide con la comuna")
    if config.commune != COMMUNES[study_id]:
        raise ValueError("El nombre de la comuna no coincide con el catálogo")
    return config


def list_studies() -> list[StudyConfig]:
    return [load_study(study_id) for study_id in STUDY_FILES]


class CollectionError(BaseModel):
    target: str
    code: str
    message: str


class FlowObservation(BaseModel):
    point: StudyPoint
    flow: FlowResponse
    speed_ratio: float | None
    travel_time_ratio: float | None
    approach_validated: Literal[False] = False


class RouteObservation(BaseModel):
    id: str
    route: RouteResponse


class StudySnapshot(BaseModel):
    study_id: str
    commune: str
    status: Literal["complete", "partial", "failed"]
    started_at: datetime
    finished_at: datetime
    local_started_at: datetime
    timezone: str
    provider_requests_attempted: int
    flows: list[FlowObservation]
    incidents: IncidentsResponse | None
    routes: list[RouteObservation]
    errors: list[CollectionError]
    limitations: list[str]


def _record_error(errors: list[CollectionError], target: str, exc: TomTomError) -> None:
    # No insistir con las demás consultas si la clave o la cuota fueron rechazadas.
    if exc.code in {"TOMTOM_NOT_CONFIGURED", "TOMTOM_ACCESS_DENIED", "TOMTOM_RATE_LIMITED"}:
        raise exc
    errors.append(CollectionError(target=target, code=exc.code, message=exc.message))


async def collect_snapshot(
    service: TomTomService,
    *,
    study_id: str = "las-condes",
    include_incidents: bool = True,
    include_routes: bool = False,
) -> StudySnapshot:
    config = load_study(study_id)
    started_at = datetime.now(UTC)
    flows = []
    routes = []
    errors = []
    incidents = None
    attempted = 0
    for point in config.points:
        attempted += 1
        try:
            flow = await service.flow(
                Point(latitude=point.latitude, longitude=point.longitude), zoom=17
            )
            flows.append(
                FlowObservation(
                    point=point,
                    flow=flow,
                    speed_ratio=(
                        flow.current_speed_kmh / flow.free_flow_speed_kmh
                        if flow.free_flow_speed_kmh > 0
                        else None
                    ),
                    travel_time_ratio=(
                        flow.current_travel_time_s / flow.free_flow_travel_time_s
                        if flow.free_flow_travel_time_s > 0
                        else None
                    ),
                )
            )
        except TomTomError as exc:
            _record_error(errors, point.id, exc)

    if include_incidents:
        attempted += 1
        try:
            incidents = await service.incidents(config.bbox)
        except TomTomError as exc:
            _record_error(errors, "incidents", exc)

    if include_routes:
        points_by_id = {point.id: point for point in config.points}
        for pair in config.route_pairs:
            attempted += 1
            try:
                origin = points_by_id[pair.origin_id]
                destination = points_by_id[pair.destination_id]
                route = await service.route(
                    Point(latitude=origin.latitude, longitude=origin.longitude),
                    Point(latitude=destination.latitude, longitude=destination.longitude),
                )
                routes.append(RouteObservation(id=pair.id, route=route))
            except TomTomError as exc:
                _record_error(errors, pair.id, exc)

    has_data = bool(flows or routes or incidents is not None)
    return StudySnapshot(
        study_id=config.id,
        commune=config.commune,
        status="complete" if not errors else "partial" if has_data else "failed",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        local_started_at=started_at.astimezone(ZoneInfo(config.timezone)),
        timezone=config.timezone,
        provider_requests_attempted=attempted,
        flows=flows,
        incidents=incidents,
        routes=routes,
        errors=errors,
        limitations=LIMITATIONS,
    )


def snapshot_csv(snapshot: StudySnapshot) -> str:
    """Una fila por punto configurado, incluidos los que no entregaron datos."""
    config = load_study(snapshot.study_id)
    observations = {observation.point.id: observation for observation in snapshot.flows}
    errors = {error.target: error for error in snapshot.errors}
    buffer = io.StringIO(newline="")
    fields = [
        "capture_started_at_utc",
        "capture_started_at_local",
        "fetched_at_utc",
        "study_id",
        "commune",
        "uoct_id",
        "name",
        "corridor",
        "latitude",
        "longitude",
        "status",
        "current_speed_kmh",
        "free_flow_speed_kmh",
        "current_travel_time_s",
        "free_flow_travel_time_s",
        "delay_s",
        "confidence",
        "road_closed",
        "speed_ratio",
        "travel_time_ratio",
        "approach_validated",
        "error_code",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for point in config.points:
        observation = observations.get(point.id)
        row = {
            "capture_started_at_utc": snapshot.started_at.isoformat(),
            "capture_started_at_local": snapshot.local_started_at.isoformat(),
            "study_id": config.id,
            "commune": config.commune,
            "uoct_id": point.id,
            "name": point.name,
            "corridor": point.corridor,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "status": "ok" if observation else "error",
            "approach_validated": False,
        }
        if observation:
            flow = observation.flow
            row.update(
                fetched_at_utc=flow.fetched_at.isoformat(),
                current_speed_kmh=flow.current_speed_kmh,
                free_flow_speed_kmh=flow.free_flow_speed_kmh,
                current_travel_time_s=flow.current_travel_time_s,
                free_flow_travel_time_s=flow.free_flow_travel_time_s,
                delay_s=flow.delay_s,
                confidence=flow.confidence,
                road_closed=flow.road_closed,
                speed_ratio=observation.speed_ratio,
                travel_time_ratio=observation.travel_time_ratio,
            )
        else:
            row["error_code"] = errors[point.id].code if point.id in errors else "NO_OBSERVATION"
        writer.writerow(row)
    return buffer.getvalue()
