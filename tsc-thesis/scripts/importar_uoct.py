#!/usr/bin/env python3
"""Inventario oficial de semáforos UOCT RM (rev. 15-mayo-2023) a GeoJSON y CSV.

Fuente: «Listado de intersecciones conectadas a Sistema de Control / Región
Metropolitana», transporteinforma.cl. Trae código UOCT, los dos accesos, comuna
y coordenadas de ~3 500 cruces. No trae fases, ciclos ni estado operativo.

El PDF agrupa los decimales con comas (-33,429,978 = -33.429978) y a veces trae
menos dígitos (-3,342,883 = -33.42883). Se recuperan quitando los separadores:
latitud = -33.xxxx y longitud = -70.xxxx / -71.xxxx.

Marca `revisar` (no se corrige nada a mano):
  lejos_de_su_comuna  > 8 km de la mediana de los cruces de su comuna
  aislado             en Gran Santiago, sin otro cruce a menos de 1,5 km
  baja_precision      3 decimales o menos
  codigo_duplicado    el código aparece más de una vez

Uso:
    python scripts/importar_uoct.py --out data/uoct
    python scripts/importar_uoct.py --pdf ruta/al.pdf --out data/uoct
Requiere pypdf (pip install pypdf).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import statistics
import sys
import urllib.request
from collections import Counter, defaultdict

URL = ("https://www.transporteinforma.cl/content/uploads/2023/10/"
       "Intersecciones-de-Semaforos-conectados-a-Sistema-UOCT-RM.pdf")
SHA256 = "f8a7ebc012c9f0dcd8ed3c71b20ed9561dd89d6b155faa8e2422539bfc3f4a1d"
GRAN_SANTIAGO = {
    "CERRILLOS", "CERRO NAVIA", "CONCHALI", "EL BOSQUE", "ESTACION CENTRAL", "HUECHURABA",
    "INDEPENDENCIA", "LA CISTERNA", "LA FLORIDA", "LA GRANJA", "LA PINTANA", "LA REINA",
    "LAS CONDES", "LO BARNECHEA", "LO ESPEJO", "LO PRADO", "MACUL", "MAIPU", "ÑUÑOA",
    "PEDRO AGUIRRE CERDA", "PEÑALOLEN", "PROVIDENCIA", "PUDAHUEL", "QUILICURA",
    "QUINTA NORMAL", "RECOLETA", "RENCA", "SAN JOAQUIN", "SAN MIGUEL", "SAN RAMON",
    "SANTIAGO", "VITACURA", "PUENTE ALTO", "SAN BERNARDO", "VITACURA/LAS CONDES",
}
PEATONAL = re.compile(r"PEATONAL|PEAT\.|\(P\)|\bP$")


def coordenada(raw: str, prefijo: str):
    if not re.fullmatch(r"-?[\d,\.]+", raw):
        return None, None
    d = re.sub(r"\D", "", raw)
    if not d.startswith(prefijo) or len(d) < 4:
        return None, None
    return -float(d[:2] + "." + d[2:]), len(d) - 2


def leer_pdf(ruta: str):
    from pypdf import PdfReader
    filas, malas = [], Counter()
    for pagina, page in enumerate(PdfReader(ruta).pages, 1):
        for linea in page.extract_text(extraction_mode="layout").splitlines():
            if not re.match(r"\s*J\d{6}\s", linea):
                continue
            cols = re.split(r"\s{2,}", linea.strip())
            if len(cols) != 6:
                malas["columnas_incompletas"] += 1
                continue
            codigo, a1, a2, comuna, rlat, rlon = cols
            lat, plat = coordenada(rlat, "33")
            lon, plon = coordenada(rlon, "7")
            if lat is None or lon is None:
                malas["sin_coordenadas"] += 1
                continue
            filas.append(dict(codigo=codigo, acceso_1=a1, acceso_2=a2, comuna=comuna,
                              lat=lat, lon=lon, decimales=min(plat, plon), pagina=pagina,
                              raw_lat=rlat, raw_lon=rlon,
                              peatonal=bool(PEATONAL.search(a1 + " " + a2)),
                              gran_santiago=comuna.upper() in GRAN_SANTIAGO))
    return filas, malas


def marcar(filas):
    def dist(a, b):
        return 111_000 * math.hypot(a["lat"] - b["lat"], (a["lon"] - b["lon"]) * 0.835)
    por_comuna = defaultdict(list)
    for r in filas:
        por_comuna[r["comuna"]].append(r)
    for rs in por_comuna.values():
        mla = statistics.median(x["lat"] for x in rs)
        mlo = statistics.median(x["lon"] for x in rs)
        for x in rs:
            x["_dmed"] = dist(x, {"lat": mla, "lon": mlo})
    # vecino más cercano en una grilla de ~1,5 km para no comparar todos con todos
    celda = defaultdict(list)
    for r in filas:
        celda[(int(r["lat"] / 0.0135), int(r["lon"] / 0.016))].append(r)
    for r in filas:
        i, j = int(r["lat"] / 0.0135), int(r["lon"] / 0.016)
        vecinos = [o for di in (-1, 0, 1) for dj in (-1, 0, 1) for o in celda[(i + di, j + dj)] if o is not r]
        r["_nn"] = min((dist(r, o) for o in vecinos), default=math.inf)
    dup = Counter(r["codigo"] for r in filas)
    for r in filas:
        m = []
        if r["_dmed"] > 8000:
            m.append("lejos_de_su_comuna")
        if r["gran_santiago"] and r["_nn"] > 1500:
            m.append("aislado")
        if r["decimales"] <= 3:
            m.append("baja_precision")
        if dup[r["codigo"]] > 1:
            m.append("codigo_duplicado")
        r["revisar"] = ";".join(m)
        del r["_dmed"], r["_nn"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", help="PDF ya descargado; si no se da, se descarga")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(a.out, exist_ok=True)
    pdf = a.pdf or os.path.join(a.out, "uoct_rm_2023.pdf")
    if not os.path.exists(pdf):
        print("Descargando inventario UOCT…")
        req = urllib.request.Request(URL, headers={"User-Agent": "tesis-semaforos-duoc/1.0"})
        open(pdf, "wb").write(urllib.request.urlopen(req, timeout=120).read())
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    if sha != SHA256:
        print(f"Aviso: el PDF no es la revisión esperada (sha256 {sha[:12]}…)")
    filas, malas = leer_pdf(pdf)
    marcar(filas)
    claves = ["codigo", "acceso_1", "acceso_2", "comuna", "gran_santiago", "peatonal",
              "decimales", "revisar", "pagina", "raw_lat", "raw_lon"]
    fc = {"type": "FeatureCollection",
          "metadata": {"fuente": "UOCT RM, Listado de intersecciones conectadas a Sistema de Control, Rev 15-Mayo-2023",
                       "url": URL, "sha256_pdf": sha,
                       "nota": "Ubicación de cruces. Sin fases, ciclos ni estado operativo actual."},
          "features": [{"type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                        "properties": {k: r[k] for k in claves}} for r in filas]}
    with open(os.path.join(a.out, "semaforos_uoct_rm_2023.geojson"), "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    with open(os.path.join(a.out, "semaforos_uoct_rm_2023.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["codigo", "acceso_1", "acceso_2", "comuna", "lat", "lon"] + claves[4:])
        w.writeheader()
        for r in filas:
            w.writerow({k: r[k] for k in w.fieldnames})
    gs = [r for r in filas if r["gran_santiago"]]
    print(f"Cruces con coordenadas: {len(filas)}  descartes: {dict(malas)}")
    print(f"Gran Santiago: {len(gs)} ({sum(not r['peatonal'] for r in gs)} vehiculares)")
    print(f"Marcados para revisar: {sum(bool(r['revisar']) for r in filas)}")


if __name__ == "__main__":
    main()
