"""Genera los 27 pilotos nuevos desde el PDF oficial, sin consultar TomTom.

Uso: python -m scripts.import_uoct --pdf tmp/pdfs/uoct-rm-2023.pdf
Requiere el extra opcional `inventory`. Conserva los cinco pilotos originales.
Solo acepta coordenadas inequívocas con seis decimales; no repara cifras dudosas.
"""

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.communes import COMMUNES
from app.study import StudyConfig

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "https://www.transporteinforma.cl/content/uploads/2023/10/"
    "Intersecciones-de-Semaforos-conectados-a-Sistema-UOCT-RM.pdf"
)
PRESERVED = {"las-condes", "providencia", "nunoa", "lo-barnechea", "vitacura"}
# Revisión manual: esta longitud ubica el punto a ~17 km de los demás cruces
# del mismo eje. Se descarta el registro; no se inventa una coordenada corregida.
EXCLUDED = {"J121811": "Longitud incompatible con el resto del eje Matta en Quilicura"}
# Uno o dos ejes por piloto; son muestras de referencia, no cobertura comunal.
CORRIDORS = {
    "cerrillos": ("PEDRO AGUIRRE CERDA",),
    "cerro-navia": ("JOSE JOAQUIN PEREZ", "NEPTUNO"),
    "conchali": ("INDEPENDENCIA", "DORSAL"),
    "el-bosque": ("GRAN AVENIDA",),
    "estacion-central": ("ALAMEDA",),
    "huechuraba": ("RECOLETA", "PEDRO FONTOVA"),
    "independencia": ("INDEPENDENCIA",),
    "la-cisterna": ("GRAN AVENIDA",),
    "la-florida": ("VICUÑA MACKENNA",),
    "la-granja": ("SANTA ROSA",),
    "la-pintana": ("SANTA ROSA",),
    "la-reina": ("LARRAIN",),
    "lo-espejo": ("AV. CENTRAL", "LO ESPEJO"),
    "lo-prado": ("SAN PABLO",),
    "macul": ("QUILIN",),
    "maipu": ("PAJARITOS", "LOS PAJARITOS"),
    "pedro-aguirre-cerda": ("DEPARTAMENTAL",),
    "penalolen": ("GRECIA",),
    "pudahuel": ("SAN PABLO",),
    "quilicura": ("MANUEL ANTONIO MATTA", "LO CRUZAT"),
    "quinta-normal": ("CARRASCAL",),
    "recoleta": ("RECOLETA",),
    "renca": ("DOMINGO SANTA MARIA", "MIRAFLORES"),
    "san-joaquin": ("LAS INDUSTRIAS",),
    "san-miguel": ("GRAN AVENIDA",),
    "san-ramon": ("SANTA ROSA",),
    "santiago": ("ALAMEDA B. O'HIGGINS",),
}


def normalized_name(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.upper()) if not unicodedata.combining(c)
    )


def coordinate(raw: str, *, latitude: bool) -> float:
    # El PDF agrupa sus seis decimales con comas, p. ej. -33,429,978.
    prefix = "33" if latitude else "70"
    if not re.fullmatch(rf"-{prefix},\d{{3}},\d{{3}}", raw):
        raise ValueError("Formato de coordenada ambiguo o precisión insuficiente")
    value = -float(raw[1:3] + "." + raw[4:].replace(",", ""))
    lower, upper = (-33.70, -33.25) if latitude else (-70.95, -70.45)
    if not lower <= value <= upper:
        raise ValueError("Coordenada fuera de la ventana urbana de selección")
    return value


@dataclass(frozen=True)
class Intersection:
    id: str
    access_1: str
    access_2: str
    commune: str
    raw_latitude: str
    raw_longitude: str
    latitude: float
    longitude: float
    page: int


def parse_inventory(pages: list[str]) -> tuple[dict[str, list[Intersection]], dict]:
    names = {normalized_name(name): slug for slug, name in COMMUNES.items()}
    rows = defaultdict(list)
    rejected = Counter()
    seen = set()
    for page_number, page in enumerate(pages, 1):
        for line in page.splitlines():
            if not re.match(r"\s*J\d{6}\s", line):
                continue
            cols = re.split(r"\s{2,}", line.strip())
            if len(cols) != 6:
                rejected["incomplete_or_malformed_row"] += 1
                continue
            code, access_1, access_2, commune, raw_lat, raw_lon = cols
            if code in EXCLUDED:
                rejected["manual_coordinate_outlier"] += 1
                continue
            slug = names.get(normalized_name(commune))
            if slug is None:
                rejected["outside_scope_or_shared_commune"] += 1
                continue
            # No seleccionar pasos peatonales identificados como tales en el PDF.
            if re.search(r"PEATONAL|\(P\)|\bP$", access_1 + " " + access_2):
                rejected["pedestrian_label"] += 1
                continue
            try:
                lat = coordinate(raw_lat, latitude=True)
                lon = coordinate(raw_lon, latitude=False)
            except ValueError:
                rejected["ambiguous_or_out_of_range_coordinates"] += 1
                continue
            if code in seen:
                rejected["duplicate_id"] += 1
                continue
            seen.add(code)
            rows[slug].append(
                Intersection(
                    code, access_1, access_2, commune, raw_lat, raw_lon, lat, lon, page_number
                )
            )
    return dict(rows), dict(rejected)


def distance(a: Intersection, b: Intersection) -> float:
    """Distancia local aproximada en km, suficiente para espaciar la muestra."""
    return 111 * math.hypot(a.latitude - b.latitude, (a.longitude - b.longitude) * 0.835)


def select_points(rows: list[Intersection], corridors: tuple[str, ...]) -> list[Intersection]:
    candidates = sorted(
        (p for p in rows if set(corridors).intersection((p.access_1, p.access_2))),
        key=lambda p: p.id,
    )
    if len(candidates) < 6:
        raise ValueError(f"Menos de seis candidatos para {corridors}")
    # Muestreo determinista por separación espacial, sin inferencia estadística.
    lat_range = max(p.latitude for p in candidates) - min(p.latitude for p in candidates)
    lon_range = max(p.longitude for p in candidates) - min(p.longitude for p in candidates)
    key = (
        (lambda p: (p.latitude, p.id))
        if lat_range >= lon_range * 0.835
        else (lambda p: (p.longitude, p.id))
    )
    selected = [min(candidates, key=key)]
    while len(selected) < 6:
        remaining = [p for p in candidates if p not in selected]
        point = max(remaining, key=lambda p: min(distance(p, q) for q in selected))
        if min(distance(point, q) for q in selected) < 0.08:
            raise ValueError(f"No hay seis puntos separados al menos 80 m para {corridors}")
        selected.append(point)
    return sorted(selected, key=key)


def make_config(slug: str, selected: list[Intersection]) -> dict:
    corridors = CORRIDORS[slug]
    points = []
    for p in selected:
        corridor = next(c for c in corridors if c in (p.access_1, p.access_2))
        cross = p.access_2 if corridor == p.access_1 else p.access_1
        points.append(
            {
                "id": p.id,
                "name": f"{corridor} / {cross}",
                "corridor": corridor,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "source_page": p.page,
                "source_commune": p.commune,
                "source_latitude_raw": p.raw_latitude,
                "source_longitude_raw": p.raw_longitude,
            }
        )
    config = {
        "id": slug,
        "commune": COMMUNES[slug],
        "name": f"Piloto {COMMUNES[slug]}: " + " y ".join(corridors),
        "timezone": "America/Santiago",
        "scope": (
            "Seis cruces de referencia seleccionados en uno o dos ejes. "
            "La ventana piloto no es el límite administrativo ni representa toda la comuna."
        ),
        "inventory_source": SOURCE,
        "inventory_revision": "2023-05-15",
        "inventory_note": (
            "Referencia del inventario UOCT de 2023. Coordenadas de seis decimales "
            "normalizadas desde sus grupos de comas; se omiten formatos ambiguos. "
            "Comuna según el inventario, sin verificación con polígonos administrativos. "
            "Revalidar ubicación, vía, sentido y estado operativo antes de modelar accesos."
        ),
        "bbox": {
            "min_lon": round(min(p.longitude for p in selected) - 0.003, 6),
            "min_lat": round(min(p.latitude for p in selected) - 0.003, 6),
            "max_lon": round(max(p.longitude for p in selected) + 0.003, 6),
            "max_lat": round(max(p.latitude for p in selected) + 0.003, 6),
        },
        "points": points,
        "route_pairs": [
            {"id": f"{slug}-ida", "origin_id": selected[0].id, "destination_id": selected[-1].id},
            {
                "id": f"{slug}-regreso",
                "origin_id": selected[-1].id,
                "destination_id": selected[0].id,
            },
        ],
    }
    StudyConfig.model_validate(config)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    args = parser.parse_args()
    from pypdf import PdfReader

    data = args.pdf.read_bytes()
    reader = PdfReader(args.pdf)
    pages = [p.extract_text(extraction_mode="layout") for p in reader.pages]
    if len(pages) != 29 or "Rev 15-Mayo-2023" not in pages[0]:
        raise ValueError("Se esperaba el inventario de 29 páginas, revisión 15-Mayo-2023")
    rows, rejected = parse_inventory(pages)
    configs = {
        slug: make_config(slug, select_points(rows[slug], axes)) for slug, axes in CORRIDORS.items()
    }
    if set(configs) != set(COMMUNES) - PRESERVED:
        raise ValueError("La importación debe agregar exactamente las 27 comunas faltantes")
    # Validar todo antes de escribir. Los cinco archivos anteriores no se modifican.
    for slug, config in configs.items():
        path = ROOT / "app/data" / f"{slug.replace('-', '_')}.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    audit = {
        "source": SOURCE,
        "revision": "2023-05-15",
        "sha256": hashlib.sha256(data).hexdigest(),
        "pages": len(pages),
        "scope_source": "https://dprmetropolitana.dpr.gob.cl/conozca-la-region/",
        "scope": "32 comunas de la provincia de Santiago",
        "method": (
            "Se conservan los cinco pilotos originales. Para los 27 nuevos: comuna "
            "exacta del inventario, dos accesos, coordenadas -33,ddd,ddd / -70,ddd,ddd "
            "dentro de la ventana urbana, sin etiquetas peatonales. Seis puntos por "
            "separación espacial en los ejes indicados, al menos 80 m entre puntos. "
            "No confirma polígonos comunales, acceso vehicular ni vigencia del semáforo."
        ),
        "rejected_rows": rejected,
        "manual_exclusions": EXCLUDED,
        "new_studies": {
            slug: {
                "eligible_inventory_rows": len(rows[slug]),
                "corridors": list(CORRIDORS[slug]),
                "selected_ids": [p["id"] for p in config["points"]],
            }
            for slug, config in configs.items()
        },
    }
    (ROOT / "docs/INVENTARIO_COMUNAS.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    count = sum(len(c["points"]) for c in configs.values())
    print(f"Generados {len(configs)} pilotos, {count} puntos")
    for config in configs.values():
        print(
            config["commune"]
            + ": "
            + "; ".join(
                f"{p['id']} {p['name']} ({p['latitude']}, {p['longitude']}, p{p['source_page']})"
                for p in config["points"]
            )
        )


if __name__ == "__main__":
    main()
