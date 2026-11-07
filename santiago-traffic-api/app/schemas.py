import math
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class BoundingBox(BaseModel):
    min_lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    min_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    max_lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    max_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_extent(self) -> Self:
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError("Las coordenadas mínimas deben ser menores que las máximas")
        # Aproximación esférica conservadora del límite de 10.000 km² de TomTom.
        area_km2 = (
            6378.137**2
            * math.radians(self.max_lon - self.min_lon)
            * (math.sin(math.radians(self.max_lat)) - math.sin(math.radians(self.min_lat)))
        )
        if area_km2 > 10_000:
            raise ValueError("El área solicitada supera 10.000 km²")
        return self

    def to_query(self) -> str:
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


class SegmentCoordinates(BaseModel):
    coordinate: list[Point] = Field(min_length=2)


class TomTomFlowData(BaseModel):
    currentSpeed: float = Field(ge=0, allow_inf_nan=False)
    freeFlowSpeed: float = Field(ge=0, allow_inf_nan=False)
    currentTravelTime: int = Field(ge=0)
    freeFlowTravelTime: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    roadClosure: bool
    coordinates: SegmentCoordinates


class FlowResponse(BaseModel):
    source: Literal["tomtom"] = "tomtom"
    fetched_at: datetime
    requested_point: Point
    current_speed_kmh: float = Field(description="Velocidad actual estimada del tramo, en km/h")
    free_flow_speed_kmh: float = Field(
        description="Velocidad de referencia con flujo libre, en km/h; no es el límite legal"
    )
    current_travel_time_s: int = Field(description="Tiempo actual del tramo, en segundos")
    free_flow_travel_time_s: int = Field(
        description="Tiempo de referencia del tramo con flujo libre, en segundos"
    )
    delay_s: int = Field(description="Tiempo adicional frente a la referencia, en segundos")
    confidence: float = Field(description="Indicador de calidad de TomTom entre 0 y 1")
    road_closed: bool = Field(description="Indica si el tramo está cerrado al tránsito")
    coordinates: list[Point] = Field(description="Geometría del tramo; no contiene velocidades")


class TomTomIncidentsData(BaseModel):
    incidents: list[dict[str, Any]]


class IncidentsResponse(BaseModel):
    source: Literal["tomtom"] = "tomtom"
    fetched_at: datetime
    bbox: BoundingBox
    incidents: list[dict[str, Any]]


class TomTomRouteSummary(BaseModel):
    lengthInMeters: int = Field(ge=0)
    travelTimeInSeconds: int = Field(ge=0)
    trafficDelayInSeconds: int = Field(ge=0)
    trafficLengthInMeters: int | None = Field(default=None, ge=0)
    departureTime: datetime | None = None
    arrivalTime: datetime | None = None


class TomTomRouteLeg(BaseModel):
    points: list[Point] = Field(min_length=1)


class TomTomRouteData(BaseModel):
    summary: TomTomRouteSummary
    legs: list[TomTomRouteLeg] = Field(min_length=1)


class TomTomRoutesData(BaseModel):
    routes: list[TomTomRouteData] = Field(min_length=1)


class RouteResponse(BaseModel):
    source: Literal["tomtom"] = "tomtom"
    fetched_at: datetime
    origin: Point
    destination: Point
    traffic: Literal["live"] = "live"
    distance_m: int
    travel_time_s: int
    traffic_delay_s: int
    traffic_length_m: int | None
    departure_time: datetime | None
    arrival_time: datetime | None
    coordinates: list[Point]
