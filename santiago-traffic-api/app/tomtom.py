from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas import (
    BoundingBox,
    FlowResponse,
    IncidentsResponse,
    Point,
    RouteResponse,
    TomTomFlowData,
    TomTomIncidentsData,
    TomTomRoutesData,
)


class TomTomError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class TomTomService:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def _get_response(
        self,
        path: str,
        params: dict[str, str],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if not self.settings.tomtom_configured:
            raise TomTomError(
                503,
                "TOMTOM_NOT_CONFIGURED",
                "Completa TOMTOM_API_KEY en el archivo .env y reinicia el servidor.",
            )
        try:
            response = await self.client.get(path, params=params, headers=headers)
        except httpx.TimeoutException:
            raise TomTomError(
                504, "TOMTOM_TIMEOUT", "TomTom tardó demasiado en responder."
            ) from None
        except httpx.RequestError:
            raise TomTomError(
                502, "TOMTOM_UNREACHABLE", "No fue posible conectar con TomTom."
            ) from None

        if response.status_code in (401, 403):
            raise TomTomError(
                502, "TOMTOM_ACCESS_DENIED", "Revisa la API key y sus permisos en TomTom."
            )
        if response.status_code == 429:
            raise TomTomError(
                503, "TOMTOM_RATE_LIMITED", "Se alcanzó un límite de consultas de TomTom."
            )
        if not response.is_success:
            raise TomTomError(502, "TOMTOM_UPSTREAM_ERROR", "TomTom rechazó la consulta.")
        return response

    async def _get_json(
        self,
        path: str,
        params: dict[str, str],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._get_response(path, params=params, headers=headers)
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Se esperaba un objeto JSON")
            return data
        except ValueError:
            raise self._invalid_response() from None

    @staticmethod
    def _invalid_response() -> TomTomError:
        return TomTomError(
            502, "TOMTOM_INVALID_RESPONSE", "TomTom devolvió una respuesta inesperada."
        )

    async def flow_tile(self, zoom: int, x: int, y: int) -> bytes:
        response = await self._get_response(
            f"/maps/orbis/traffic/flow/vector/tile/{zoom}/{x}/{y}",
            params={"apiVersion": "2"},
            headers={
                "TomTom-Api-Key": self.settings.tomtom_api_key.get_secret_value(),
                "Accept": "application/vnd.mapbox-vector-tile",
            },
        )
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
        if content_type != "application/vnd.mapbox-vector-tile":
            raise self._invalid_response()
        return response.content

    async def flow(self, point: Point, zoom: int) -> FlowResponse:
        payload = await self._get_json(
            f"/traffic/services/4/flowSegmentData/absolute/{zoom}/json",
            params={
                "key": self.settings.tomtom_api_key.get_secret_value(),
                "point": f"{point.latitude},{point.longitude}",
                "unit": "kmph",
            },
        )
        try:
            flow = TomTomFlowData.model_validate(payload["flowSegmentData"])
        except (KeyError, ValidationError):
            raise self._invalid_response() from None
        return FlowResponse(
            fetched_at=datetime.now(UTC),
            requested_point=point,
            current_speed_kmh=flow.currentSpeed,
            free_flow_speed_kmh=flow.freeFlowSpeed,
            current_travel_time_s=flow.currentTravelTime,
            free_flow_travel_time_s=flow.freeFlowTravelTime,
            delay_s=max(0, flow.currentTravelTime - flow.freeFlowTravelTime),
            confidence=flow.confidence,
            road_closed=flow.roadClosure,
            coordinates=flow.coordinates.coordinate,
        )

    async def incidents(self, bbox: BoundingBox) -> IncidentsResponse:
        payload = await self._get_json(
            "/maps/orbis/traffic/incidents/details",
            params={"apiVersion": "2", "bbox": bbox.to_query(), "timeValidity": "present"},
            headers={
                "TomTom-Api-Key": self.settings.tomtom_api_key.get_secret_value(),
                "Attributes": "incidents",
            },
        )
        try:
            data = TomTomIncidentsData.model_validate(payload)
        except ValidationError:
            raise self._invalid_response() from None
        return IncidentsResponse(fetched_at=datetime.now(UTC), bbox=bbox, incidents=data.incidents)

    async def route(self, origin: Point, destination: Point) -> RouteResponse:
        locations = (
            f"{origin.latitude},{origin.longitude}:{destination.latitude},{destination.longitude}"
        )
        payload = await self._get_json(
            f"/maps/orbis/routing/calculateRoute/{locations}/json",
            params={
                "apiVersion": "2",
                "key": self.settings.tomtom_api_key.get_secret_value(),
                "traffic": "live",
                "departAt": "now",
                "travelMode": "car",
                "routeType": "fast",
                "routeRepresentation": "polyline",
                "maxAlternatives": "0",
            },
        )
        try:
            data = TomTomRoutesData.model_validate(payload)
        except ValidationError:
            raise self._invalid_response() from None
        route = data.routes[0]
        return RouteResponse(
            fetched_at=datetime.now(UTC),
            origin=origin,
            destination=destination,
            distance_m=route.summary.lengthInMeters,
            travel_time_s=route.summary.travelTimeInSeconds,
            traffic_delay_s=route.summary.trafficDelayInSeconds,
            traffic_length_m=route.summary.trafficLengthInMeters,
            departure_time=route.summary.departureTime,
            arrival_time=route.summary.arrivalTime,
            coordinates=[point for leg in route.legs for point in leg.points],
        )
