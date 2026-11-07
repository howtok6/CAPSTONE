"""Protecciones del catálogo territorial y de la importación del inventario."""

from itertools import combinations

import pytest

from app.communes import COMMUNES
from app.study import load_study
from scripts.import_uoct import CORRIDORS, coordinate, normalized_name, parse_inventory

EXPECTED_COMMUNES = {
    "Cerrillos",
    "Cerro Navia",
    "Conchalí",
    "El Bosque",
    "Estación Central",
    "Huechuraba",
    "Independencia",
    "La Cisterna",
    "La Florida",
    "La Granja",
    "La Pintana",
    "La Reina",
    "Las Condes",
    "Lo Barnechea",
    "Lo Espejo",
    "Lo Prado",
    "Macul",
    "Maipú",
    "Ñuñoa",
    "Pedro Aguirre Cerda",
    "Peñalolén",
    "Providencia",
    "Pudahuel",
    "Quilicura",
    "Quinta Normal",
    "Recoleta",
    "Renca",
    "San Joaquín",
    "San Miguel",
    "San Ramón",
    "Santiago",
    "Vitacura",
}


def test_catalog_is_exactly_the_province_of_santiago():
    assert set(COMMUNES.values()) == EXPECTED_COMMUNES
    assert len(COMMUNES) == 32
    points = [point for slug in COMMUNES for point in load_study(slug).points]
    assert len(points) == len({p.id for p in points}) == 192


@pytest.mark.parametrize("slug", CORRIDORS)
def test_new_communes_retain_source_coordinates_and_distinct_locations(slug):
    config = load_study(slug)
    assert len(config.points) == 6
    for point in config.points:
        assert normalized_name(point.source_commune) == normalized_name(config.commune)
        assert coordinate(point.source_latitude_raw, latitude=True) == point.latitude
        assert coordinate(point.source_longitude_raw, latitude=False) == point.longitude
        assert 1 <= point.source_page <= 29
    for a, b in combinations(config.points, 2):
        # No dos registros de una misma esquina/calzada a pocos metros.
        km_squared = (111 * (a.latitude - b.latitude)) ** 2 + (
            111 * 0.835 * (a.longitude - b.longitude)
        ) ** 2
        assert km_squared >= 0.08**2


@pytest.mark.parametrize(
    ("raw", "latitude"),
    [
        ("-3,342,883", True),
        ("-334,228", True),
        ("-33,442", True),
        ("33,429,978", True),
        ("-34,429,978", True),
        ("-33,999,999", True),
        ("-7,061,639", False),
        ("-70,999,999", False),
    ],
)
def test_import_does_not_guess_ambiguous_or_outlying_coordinates(raw, latitude):
    with pytest.raises(ValueError):
        coordinate(raw, latitude=latitude)


def test_import_handles_page_provenance_and_rejects_unusable_rows():
    rows, rejected = parse_inventory(
        [
            "CÓDIGO  ACCESO 1  ACCESO 2  COMUNA  Latitud  Longitud\n"
            "J001111  MIGUEL CLARO  PROVIDENCIA  PROVIDENCIA  -33,429,978  -70,622,176\n"
            "J001621  VITACURA  TAJAMAR  VITACURA/LAS CONDES  -33,416,966  -70,604,816\n"
            "J001312  PROVIDENCIA  LOS LEONES (PEATONAL)  PROVIDENCIA  -33,419,741  -70,606,015\n"
            "J410111  18 DE SEPTIEMBRE  EL VILLAR  PAINE\n",
            "J001111  MIGUEL CLARO  PROVIDENCIA  PROVIDENCIA  -33,429,978  -70,622,176\n"
            "J001142  NUEVA PROVIDENCIA  PROVIDENCIA  PROVIDENCIA  -3,342,883  -70,618,269\n"
            "J121811  MANUEL ANTONIO MATTA  SAN MARTIN  QUILICURA  -33,366,001  -70,522,052\n"
            "J032151  SAN PABLO  TENIENTE CRUZ  LO PRADO  -33,444,635  -70,740,566\n",
        ]
    )
    assert set(rows) == {"providencia", "lo-prado"}
    assert rows["providencia"][0].latitude == -33.429978
    assert rows["providencia"][0].raw_latitude == "-33,429,978"
    assert rows["lo-prado"][0].page == 2
    assert rejected == {
        "outside_scope_or_shared_commune": 1,
        "pedestrian_label": 1,
        "incomplete_or_malformed_row": 1,
        "duplicate_id": 1,
        "ambiguous_or_out_of_range_coordinates": 1,
        "manual_coordinate_outlier": 1,
    }
