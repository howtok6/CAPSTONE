"""Una captura por ejecución. No inicia sondeos ni guarda archivos automáticamente."""

import argparse
import asyncio
import json
import logging

import httpx

from app.config import Settings
from app.study import STUDY_FILES, StudySnapshot, collect_snapshot, snapshot_csv
from app.tomtom import TomTomError, TomTomService


async def capture(
    *, include_incidents: bool, include_routes: bool, study_id: str = "las-condes"
) -> StudySnapshot:
    settings = Settings()
    async with httpx.AsyncClient(
        base_url="https://api.tomtom.com", timeout=settings.tomtom_timeout_seconds
    ) as client:
        return await collect_snapshot(
            TomTomService(client, settings),
            study_id=study_id,
            include_incidents=include_incidents,
            include_routes=include_routes,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=list(STUDY_FILES), default="las-condes")
    parser.add_argument("--format", choices=["summary", "json", "csv"], default="summary")
    parser.add_argument("--include-routes", action="store_true")
    parser.add_argument("--without-incidents", action="store_true")
    args = parser.parse_args()
    if args.format == "csv" and args.include_routes:
        parser.error("CSV solo exporta flujo; utiliza --format json para rutas e incidentes.")
    # Flow y Routing reciben la clave en la URL. No imprimir logs de solicitudes.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        snapshot = asyncio.run(
            capture(
                study_id=args.study,
                include_incidents=not args.without_incidents and args.format != "csv",
                include_routes=args.include_routes,
            )
        )
    except TomTomError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message}, ensure_ascii=False))
        return 1
    if args.format == "json":
        print(snapshot.model_dump_json(indent=2))
    elif args.format == "csv":
        print(snapshot_csv(snapshot), end="")
    else:
        print(
            json.dumps(
                {
                    "study_id": snapshot.study_id,
                    "commune": snapshot.commune,
                    "status": snapshot.status,
                    "local_started_at": snapshot.local_started_at.isoformat(),
                    "requests": snapshot.provider_requests_attempted,
                    "flows": [
                        {
                            "id": item.point.id,
                            "name": item.point.name,
                            "speed_kmh": item.flow.current_speed_kmh,
                            "free_flow_kmh": item.flow.free_flow_speed_kmh,
                            "delay_s": item.flow.delay_s,
                            "confidence": item.flow.confidence,
                            "road_closed": item.flow.road_closed,
                        }
                        for item in snapshot.flows
                    ],
                    "incident_count": (
                        len(snapshot.incidents.incidents)
                        if snapshot.incidents is not None
                        else None
                    ),
                    "routes": [
                        {
                            "id": item.id,
                            "distance_m": item.route.distance_m,
                            "travel_time_s": item.route.travel_time_s,
                            "traffic_delay_s": item.route.traffic_delay_s,
                        }
                        for item in snapshot.routes
                    ],
                    "errors": [error.model_dump() for error in snapshot.errors],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0 if snapshot.status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
