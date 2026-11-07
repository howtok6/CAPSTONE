import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

FAKE_KEY = "test-key-not-a-real-secret"
FLOW_PATH = "/api/traffic/flow?lat=-33.4489&lon=-70.6693"
INCIDENTS_PATH = "/api/traffic/incidents?bbox=-70.70,-33.47,-70.63,-33.42"
TILE_PATH = "/api/traffic/flow/tiles/12/2103/1346"
ROUTE_PATH = (
    "/api/traffic/route?origin_lat=52.3676&origin_lon=4.9041"
    "&destination_lat=51.4426&destination_lon=3.5735"
)


def settings(**overrides):
    return Settings(_env_file=None, tomtom_api_key=FAKE_KEY, **overrides)


def client_for(handler, config=None):
    return TestClient(
        create_app(
            config if config is not None else settings(),
            transport=httpx.MockTransport(handler),
        )
    )


def no_upstream(request):
    pytest.fail("Esta solicitud no debe consultar TomTom")


def test_missing_key_keeps_health_available_and_blocks_traffic():
    config = Settings(_env_file=None, tomtom_api_key="   ")
    with client_for(no_upstream, config) as client:
        assert client.get("/health").json() == {"status": "ok", "tomtom_configured": False}
        for path in (FLOW_PATH, INCIDENTS_PATH, ROUTE_PATH, TILE_PATH):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "TOMTOM_NOT_CONFIGURED"


def test_flow_returns_normalized_units_geometry_and_delay():
    def upstream(request):
        assert request.url.path == "/traffic/services/4/flowSegmentData/absolute/15/json"
        assert request.url.params["key"] == FAKE_KEY
        assert request.url.params["point"] == "-33.4489,-70.6693"
        assert request.url.params["unit"] == "kmph"
        return httpx.Response(
            200,
            json={
                "flowSegmentData": {
                    "currentSpeed": 30,
                    "freeFlowSpeed": 60,
                    "currentTravelTime": 180,
                    "freeFlowTravelTime": 90,
                    "confidence": 0.9,
                    "roadClosure": False,
                    "coordinates": {
                        "coordinate": [
                            {"latitude": -33.4489, "longitude": -70.6693},
                            {"latitude": -33.4490, "longitude": -70.6694},
                        ]
                    },
                }
            },
        )

    with client_for(upstream) as client:
        response = client.get(FLOW_PATH)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "tomtom"
    assert data["current_speed_kmh"] == 30
    assert data["current_travel_time_s"] == 180
    assert data["delay_s"] == 90
    assert len(data["coordinates"]) == 2
    assert data["fetched_at"].endswith("Z")
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("incidents", [[], [{"type": "Feature", "properties": {"id": "abc"}}]])
def test_incidents_uses_orbis_headers_and_preserves_results(incidents):
    def upstream(request):
        assert request.url.path == "/maps/orbis/traffic/incidents/details"
        assert request.url.params["apiVersion"] == "2"
        assert request.url.params["bbox"] == "-70.7,-33.47,-70.63,-33.42"
        assert request.url.params["timeValidity"] == "present"
        assert request.headers["TomTom-Api-Key"] == FAKE_KEY
        assert request.headers["Attributes"] == "incidents"
        assert "key" not in request.url.params
        return httpx.Response(200, json={"incidents": incidents})

    with client_for(upstream) as client:
        response = client.get(INCIDENTS_PATH)
    assert response.status_code == 200
    assert response.json()["incidents"] == incidents


@pytest.mark.parametrize(
    "path",
    [
        "/api/traffic/flow?lat=91&lon=-70",
        "/api/traffic/flow?lat=-33&lon=-181",
        "/api/traffic/flow?lat=nan&lon=-70",
        "/api/traffic/flow?lat=-33&lon=-70&zoom=23",
        "/api/traffic/flow?lon=-70",
        "/api/traffic/incidents?bbox=invalid",
        "/api/traffic/incidents?bbox=-70,-33,-69",
        "/api/traffic/incidents?bbox=-70,-33,-71,-32",
        "/api/traffic/incidents?bbox=-70,-33,-69,-34",
        "/api/traffic/incidents?bbox=nan,-33,-69,-32",
        "/api/traffic/incidents?bbox=-181,-33,-69,-32",
        "/api/traffic/incidents?bbox=-100,-60,-50,-10",
        ROUTE_PATH.replace("52.3676", "91"),
        ROUTE_PATH.replace("4.9041", "181"),
        ROUTE_PATH.replace("51.4426", "nan"),
        ROUTE_PATH.replace("3.5735", "-181"),
        "/api/traffic/route?origin_lat=-33&origin_lon=-70",
        "/api/traffic/flow/tiles/23/0/0",
        "/api/traffic/flow/tiles/-1/0/0",
        "/api/traffic/flow/tiles/12/4096/0",
        "/api/traffic/flow/tiles/12/0/4096",
        "/api/traffic/flow/tiles/12/-1/0",
        "/api/traffic/flow/tiles/12/0/-1",
        "/api/traffic/flow/tiles/12/1.5/0",
    ],
)
def test_invalid_coordinates_do_not_consume_provider_requests(path):
    with client_for(no_upstream) as client:
        assert client.get(path).status_code == 422


@pytest.mark.parametrize("path", [FLOW_PATH, INCIDENTS_PATH, ROUTE_PATH, TILE_PATH])
@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_code"),
    [
        (401, 502, "TOMTOM_ACCESS_DENIED"),
        (403, 502, "TOMTOM_ACCESS_DENIED"),
        (429, 503, "TOMTOM_RATE_LIMITED"),
        (500, 502, "TOMTOM_UPSTREAM_ERROR"),
    ],
)
def test_provider_errors_are_safe(path, upstream_status, expected_status, expected_code):
    def upstream(request):
        # El proveedor podría incluir la clave o la URL en su mensaje de error.
        return httpx.Response(upstream_status, text=f"Rejected key: {FAKE_KEY}")

    with client_for(upstream) as client:
        response = client.get(path)
    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (httpx.ReadTimeout, 504, "TOMTOM_TIMEOUT"),
        (httpx.ConnectError, 502, "TOMTOM_UNREACHABLE"),
    ],
)
def test_connection_failures(error, expected_status, expected_code):
    def upstream(request):
        raise error(f"Error with {FAKE_KEY}", request=request)

    with client_for(upstream) as client:
        response = client.get(FLOW_PATH)
    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("path", [FLOW_PATH, INCIDENTS_PATH, ROUTE_PATH])
@pytest.mark.parametrize("payload", ["not JSON", "[]", "{}"])
def test_invalid_provider_payload_returns_controlled_error(path, payload):
    with client_for(lambda request: httpx.Response(200, text=payload)) as client:
        response = client.get(path)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "TOMTOM_INVALID_RESPONSE"


def test_openapi_and_cors_are_available():
    config = settings(cors_origins=["http://localhost:5173"])
    with client_for(no_upstream, config) as client:
        assert client.get("/docs").status_code == 200
        assert "/api/traffic/flow" in client.get("/openapi.json").json()["paths"]
        allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
        denied = client.get("/health", headers={"Origin": "https://other.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_settings_load_dotenv_and_hide_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"TOMTOM_API_KEY=  {FAKE_KEY}  \n", encoding="utf-8")
    config = Settings(_env_file=env_file)
    assert config.tomtom_configured
    assert config.tomtom_api_key.get_secret_value() == FAKE_KEY
    assert FAKE_KEY not in repr(config)


def test_route_uses_orbis_v2_live_traffic_and_normalizes_result():
    def upstream(request):
        assert request.url.path == (
            "/maps/orbis/routing/calculateRoute/52.3676,4.9041:51.4426,3.5735/json"
        )
        assert request.url.params["apiVersion"] == "2"
        assert request.url.params["key"] == FAKE_KEY
        assert request.url.params["traffic"] == "live"
        assert request.url.params["departAt"] == "now"
        assert request.url.params["routeType"] == "fast"
        assert request.url.params["travelMode"] == "car"
        assert "computeTravelTimeFor" not in request.url.params
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "summary": {
                            "lengthInMeters": 180000,
                            "travelTimeInSeconds": 7200,
                            "trafficDelayInSeconds": 600,
                            "trafficLengthInMeters": 12000,
                            "departureTime": "2026-11-04T12:00:00+01:00",
                            "arrivalTime": "2026-11-04T14:00:00+01:00",
                        },
                        "legs": [
                            {
                                "points": [
                                    {"latitude": 52.3676, "longitude": 4.9041},
                                    {"latitude": 51.4426, "longitude": 3.5735},
                                ]
                            }
                        ],
                    }
                ]
            },
        )

    with client_for(upstream) as client:
        response = client.get(ROUTE_PATH)
    assert response.status_code == 200
    data = response.json()
    assert data["origin"] == {"latitude": 52.3676, "longitude": 4.9041}
    assert data["destination"] == {"latitude": 51.4426, "longitude": 3.5735}
    assert data["traffic"] == "live"
    assert data["distance_m"] == 180000
    assert data["travel_time_s"] == 7200
    assert data["traffic_delay_s"] == 600
    assert data["traffic_length_m"] == 12000
    assert data["arrival_time"] == "2026-11-04T14:00:00+01:00"
    assert len(data["coordinates"]) == 2
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"routes": []},
        {"routes": [{"summary": {}, "legs": []}]},
        {
            "routes": [
                {
                    "summary": {
                        "lengthInMeters": -1,
                        "travelTimeInSeconds": 100,
                        "trafficDelayInSeconds": 0,
                    },
                    "legs": [{"points": [{"latitude": 0, "longitude": 0}]}],
                }
            ]
        },
    ],
)
def test_route_rejects_empty_or_invalid_results(payload):
    with client_for(lambda request: httpx.Response(200, json=payload)) as client:
        response = client.get(ROUTE_PATH)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "TOMTOM_INVALID_RESPONSE"


@pytest.mark.parametrize("content", [b"", b"\x1a\x00"])
def test_tile_preserves_binary_content_and_uses_header_auth(content):
    def upstream(request):
        assert request.url.path == "/maps/orbis/traffic/flow/vector/tile/12/2103/1346"
        assert request.url.params["apiVersion"] == "2"
        assert "key" not in request.url.params
        assert request.headers["TomTom-Api-Key"] == FAKE_KEY
        assert request.headers["Accept"] == "application/vnd.mapbox-vector-tile"
        return httpx.Response(
            200,
            content=content,
            headers={"Content-Type": "application/vnd.mapbox-vector-tile"},
        )

    with client_for(upstream) as client:
        response = client.get(TILE_PATH)
        openapi = client.get("/openapi.json").json()
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert (
        "application/vnd.mapbox-vector-tile"
        in (
            openapi["paths"]["/api/traffic/flow/tiles/{zoom}/{x}/{y}"]["get"]["responses"]["200"][
                "content"
            ]
        )
    )


def test_tile_rejects_json_in_successful_provider_response():
    with client_for(lambda request: httpx.Response(200, json={"error": FAKE_KEY})) as client:
        response = client.get(TILE_PATH)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "TOMTOM_INVALID_RESPONSE"
    assert FAKE_KEY not in response.text
