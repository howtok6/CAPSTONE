import csv
import io

import httpx
import pytest
from fastapi.testclient import TestClient

from app.communes import COMMUNES
from app.config import Settings
from app.main import create_app
from app.study import UnknownStudyError, load_study

FAKE_KEY = "study-test-key-not-real"
BASE = "/api/studies/las-condes"
NEW_STUDIES = [slug for slug in COMMUNES if slug != "las-condes"]


def test_table_is_available_without_key_or_tomtom_requests():
    def no_upstream(request):
        pytest.fail("Abrir la tabla no debe consultar TomTom automáticamente")

    with study_client(no_upstream, key="") as client:
        response = client.get("/las-condes")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "Consultar velocidades y tiempos" in response.text
    assert FAKE_KEY not in response.text


def study_client(handler, *, key=FAKE_KEY):
    settings = Settings(_env_file=None, tomtom_api_key=key)
    return TestClient(create_app(settings, transport=httpx.MockTransport(handler)))


def flow_response(request, *, zero_reference=False):
    lat, lon = (float(part) for part in request.url.params["point"].split(","))
    return httpx.Response(
        200,
        json={
            "flowSegmentData": {
                "currentSpeed": 15,
                "freeFlowSpeed": 0 if zero_reference else 30,
                "currentTravelTime": 200,
                "freeFlowTravelTime": 0 if zero_reference else 100,
                "confidence": 0.9,
                "roadClosure": False,
                "coordinates": {
                    "coordinate": [
                        {"latitude": lat, "longitude": lon},
                        {"latitude": lat + 0.001, "longitude": lon},
                    ]
                },
            }
        },
    )


def successful_upstream(request):
    if "flowSegmentData" in request.url.path:
        return flow_response(request)
    if request.url.path.endswith("/incidents/details"):
        return httpx.Response(200, json={"incidents": []})
    if "calculateRoute" in request.url.path:
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "summary": {
                            "lengthInMeters": 5000,
                            "travelTimeInSeconds": 1000,
                            "trafficDelayInSeconds": 100,
                        },
                        "legs": [
                            {
                                "points": [
                                    {"latitude": -33.416258, "longitude": -70.594058},
                                    {"latitude": -33.408677, "longitude": -70.567186},
                                ]
                            }
                        ],
                    }
                ]
            },
        )
    pytest.fail(f"Ruta del proveedor inesperada: {request.url.path}")


def test_inventory_and_geojson_do_not_call_tomtom():
    def no_upstream(request):
        pytest.fail("Consultar el inventario no debe consumir cuota")

    with study_client(no_upstream, key="") as client:
        info = client.get(BASE)
        points = client.get(f"{BASE}/points.geojson")
    assert info.status_code == points.status_code == 200
    data = info.json()
    assert len(data["points"]) == 6
    assert data["inventory_revision"] == "2023-05-15"
    assert data["requests_per_capture"]["flow_incidents_and_routes"] == 9
    features = points.json()["features"]
    assert len(features) == 6
    assert points.headers["content-type"] == "application/geo+json"
    assert features[0]["geometry"]["coordinates"] == [-70.594058, -33.416258]
    assert features[0]["properties"]["current_signal_state_verified"] is False


def test_default_capture_returns_real_contract_and_limits_requests():
    requests = []

    def upstream(request):
        requests.append(request)
        return successful_upstream(request)

    with study_client(upstream) as client:
        response = client.get(f"{BASE}/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["provider_requests_attempted"] == len(requests) == 7
    assert len(data["flows"]) == 6
    assert data["incidents"]["incidents"] == []
    assert data["routes"] == []
    assert data["errors"] == []
    assert data["timezone"] == "America/Santiago"
    assert data["started_at"].endswith("Z")
    assert data["local_started_at"] != data["started_at"]
    assert data["flows"][0]["speed_ratio"] == 0.5
    assert data["flows"][0]["travel_time_ratio"] == 2
    assert data["flows"][0]["approach_validated"] is False
    assert response.headers["cache-control"] == "no-store"
    assert FAKE_KEY not in response.text


def test_optional_routes_use_both_directions_and_no_extra_calls():
    locations = []

    def upstream(request):
        if "calculateRoute" in request.url.path:
            locations.append(request.url.path.split("/")[-2])
        return successful_upstream(request)

    with study_client(upstream) as client:
        response = client.get(f"{BASE}/snapshot?include_routes=true")
    data = response.json()
    assert response.status_code == 200
    assert data["provider_requests_attempted"] == 9
    assert len(data["routes"]) == 2
    assert locations == [
        "-33.416258,-70.594058:-33.408677,-70.567186",
        "-33.408677,-70.567186:-33.416258,-70.594058",
    ]


def test_partial_capture_keeps_successes_and_reports_missing_point():
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        if calls == 2:
            return httpx.Response(503, text=f"Provider error including {FAKE_KEY}")
        return successful_upstream(request)

    with study_client(upstream) as client:
        response = client.get(f"{BASE}/snapshot?include_incidents=false")
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "partial"
    assert len(data["flows"]) == 5
    assert data["incidents"] is None
    assert data["errors"][0]["target"] == load_study().points[1].id
    assert data["errors"][0]["code"] == "TOMTOM_UPSTREAM_ERROR"
    assert FAKE_KEY not in response.text


def test_empty_capture_returns_failure_instead_of_zero_traffic():
    with study_client(lambda request: httpx.Response(503)) as client:
        response = client.get(f"{BASE}/snapshot?include_incidents=false")
    assert response.status_code == 502
    assert response.json()["status"] == "failed"
    assert response.json()["flows"] == []
    assert len(response.json()["errors"]) == 6


@pytest.mark.parametrize("upstream_status", [401, 403, 429])
def test_invalid_key_or_rate_limit_stops_further_requests(upstream_status):
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        return httpx.Response(upstream_status)

    with study_client(upstream) as client:
        response = client.get(f"{BASE}/snapshot?include_routes=true")
    assert response.status_code in (502, 503)
    assert calls == 1


def test_unconfigured_capture_does_not_call_provider():
    def no_upstream(request):
        pytest.fail("La captura sin clave no debe consultar el proveedor")

    with study_client(no_upstream, key="") as client:
        response = client.get(f"{BASE}/snapshot")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "TOMTOM_NOT_CONFIGURED"


def test_csv_preserves_missing_values_and_uses_only_six_flow_requests():
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        assert "flowSegmentData" in request.url.path
        if calls == 1:
            return httpx.Response(503)
        return flow_response(request, zero_reference=True)

    with study_client(upstream) as client:
        response = client.get(f"{BASE}/snapshot.csv")
    assert response.status_code == 200
    assert response.headers["x-capture-status"] == "partial"
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == calls == 6
    assert rows[0]["status"] == "error"
    assert rows[0]["current_speed_kmh"] == ""
    assert rows[0]["error_code"] == "TOMTOM_UPSTREAM_ERROR"
    assert rows[1]["status"] == "ok"
    assert rows[1]["free_flow_speed_kmh"] == "0.0"
    assert rows[1]["speed_ratio"] == ""
    assert rows[1]["travel_time_ratio"] == ""
    assert rows[1]["approach_validated"] == "False"
    assert FAKE_KEY not in response.text


def test_catalog_lists_all_communes_without_provider_requests():
    def no_upstream(request):
        pytest.fail("Listar comunas no debe consumir cuota")

    with study_client(no_upstream, key="") as client:
        response = client.get("/api/studies")
    assert response.status_code == 200
    studies = response.json()["studies"]
    assert len(studies) == response.json()["commune_count"] == 32
    assert response.json()["point_count"] == 192
    assert [item["id"] for item in studies] == list(COMMUNES)
    assert [item["commune"] for item in studies] == list(COMMUNES.values())
    assert all(item["point_count"] == 6 for item in studies)


@pytest.mark.parametrize("study_id", ["comunas", *NEW_STUDIES])
def test_commune_table_links_are_available_without_key(study_id):
    def no_upstream(request):
        pytest.fail("Abrir una tabla no debe consultar TomTom")

    with study_client(no_upstream, key="") as client:
        response = client.get(f"/{study_id}")
    assert response.status_code == 200
    assert 'id="commune"' in response.text
    assert "Consultar velocidades y tiempos" in response.text
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("study_id", NEW_STUDIES)
def test_commune_snapshot_uses_only_its_configured_points(study_id):
    config = load_study(study_id)
    requested_points = []

    def upstream(request):
        assert "flowSegmentData" in request.url.path
        requested_points.append(request.url.params["point"])
        return flow_response(request)

    with study_client(upstream) as client:
        response = client.get(f"/api/studies/{study_id}/snapshot?include_incidents=false")
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == study_id
    assert data["commune"] == config.commune
    assert data["status"] == "complete"
    assert data["provider_requests_attempted"] == 6
    assert requested_points == [f"{point.latitude},{point.longitude}" for point in config.points]
    assert [item["point"]["id"] for item in data["flows"]] == [point.id for point in config.points]
    assert data["incidents"] is None
    assert all(item["flow"]["current_speed_kmh"] == 15 for item in data["flows"])
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("study_id", NEW_STUDIES)
def test_commune_csv_is_not_mixed_with_las_condes(study_id):
    config = load_study(study_id)
    with study_client(successful_upstream) as client:
        response = client.get(f"/api/studies/{study_id}/snapshot.csv")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 6
    assert {row["study_id"] for row in rows} == {study_id}
    assert {row["commune"] for row in rows} == {config.commune}
    assert {row["uoct_id"] for row in rows} == {point.id for point in config.points}
    assert all(row["status"] == "ok" for row in rows)
    assert study_id.replace("-", "_") in response.headers["content-disposition"]
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("study_id", NEW_STUDIES)
def test_commune_routes_and_incidents_use_the_selected_area(study_id):
    config = load_study(study_id)
    requested_routes = []
    requested_bbox = []

    def upstream(request):
        if "calculateRoute" in request.url.path:
            requested_routes.append(request.url.path.split("/")[-2])
        if request.url.path.endswith("/incidents/details"):
            requested_bbox.append(request.url.params["bbox"])
        return successful_upstream(request)

    with study_client(upstream) as client:
        response = client.get(f"/api/studies/{study_id}/snapshot?include_routes=true")
        points_response = client.get(f"/api/studies/{study_id}/points.geojson")
    assert response.status_code == points_response.status_code == 200
    data = response.json()
    assert data["provider_requests_attempted"] == 9
    assert [item["id"] for item in data["routes"]] == [pair.id for pair in config.route_pairs]
    assert requested_bbox == [config.bbox.to_query()]
    points = {point.id: point for point in config.points}
    expected_routes = []
    for pair in config.route_pairs:
        origin, destination = points[pair.origin_id], points[pair.destination_id]
        expected_routes.append(
            f"{origin.latitude},{origin.longitude}:{destination.latitude},{destination.longitude}"
        )
    assert requested_routes == expected_routes
    assert {feature["properties"]["commune"] for feature in points_response.json()["features"]} == {
        config.commune
    }


@pytest.mark.parametrize("suffix", ["", "/snapshot", "/snapshot.csv", "/points.geojson"])
def test_unknown_commune_returns_404_without_provider_requests(suffix):
    def no_upstream(request):
        pytest.fail("Una comuna desconocida no debe consumir cuota")

    with study_client(no_upstream) as client:
        response = client.get(f"/api/studies/not-configured{suffix}")
    assert response.status_code == 404


def test_study_loader_rejects_arbitrary_file_names():
    with pytest.raises(UnknownStudyError):
        load_study("../config")
