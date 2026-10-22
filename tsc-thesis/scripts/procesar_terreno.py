#!/usr/bin/env python3
"""Convierte las marcas de tiempo medidas en terreno en tiempos semafóricos por cruce.

Entrada (data/terreno/):
  mediciones.csv  una fila por medición (cruce, fecha, franja, método)
  eventos.csv     una fila por cambio de color: medicion_id, grupo, color, t
                  color ∈ {verde, amarillo, rojo}; t en segundos desde el inicio
                  del video (12.4) o como mm:ss.s / hh:mm:ss.s
Salida:
  resumen_tiempos.csv  por medición y grupo: ciclos completos, ciclo, verde,
                       amarillo y rojo (media y desviación) y bandera de ciclo variable

Uso:
    python scripts/procesar_terreno.py [--dir data/terreno]
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
import sys
from collections import defaultdict

COLORES = ("verde", "amarillo", "rojo")
UMBRAL_VARIABLE_S = 4.0  # desviación de ciclo sobre la cual se marca el cruce como variable


def parse_t(valor: str) -> float:
    valor = valor.strip().replace(",", ".")
    partes = valor.split(":")
    seg = 0.0
    for p in partes:
        seg = seg * 60 + float(p)
    return seg


def ciclos_de_grupo(eventos: list[tuple[float, str]]) -> list[dict]:
    """Recorre la secuencia verde→amarillo→rojo→verde y devuelve un registro por ciclo completo."""
    eventos = sorted(eventos)
    verdes = [i for i, (_, c) in enumerate(eventos) if c == "verde"]
    ciclos = []
    for a, b in zip(verdes, verdes[1:]):
        tramo = eventos[a:b + 1]
        colores = [c for _, c in tramo]
        if colores[:3] != ["verde", "amarillo", "rojo"] or len(colores) != 4:
            continue  # ciclo incompleto o con eventos faltantes: se descarta
        t_v, t_a, t_r, t_v2 = (t for t, _ in tramo)
        ciclos.append({"ciclo": t_v2 - t_v, "verde": t_a - t_v,
                       "amarillo": t_r - t_a, "rojo": t_v2 - t_r})
    return ciclos


def resumir(dir_datos: str) -> list[dict]:
    with open(os.path.join(dir_datos, "mediciones.csv"), encoding="utf-8") as f:
        mediciones = {r["medicion_id"]: r for r in csv.DictReader(f)}
    por_grupo: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    with open(os.path.join(dir_datos, "eventos.csv"), encoding="utf-8") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):
            color = r["color"].strip().lower()
            if color not in COLORES:
                sys.exit(f"eventos.csv línea {n}: color '{r['color']}' no válido (usar {COLORES})")
            if r["medicion_id"] not in mediciones:
                sys.exit(f"eventos.csv línea {n}: medicion_id '{r['medicion_id']}' no existe en mediciones.csv")
            por_grupo[(r["medicion_id"], r["grupo"].strip())].append((parse_t(r["t"]), color))

    filas = []
    for (mid, grupo), evs in sorted(por_grupo.items()):
        cic = ciclos_de_grupo(evs)
        m = mediciones[mid]
        fila = {"medicion_id": mid, "cruce_id": m["cruce_id"], "franja": m["franja"],
                "fecha": m["fecha"], "grupo": grupo, "ciclos_completos": len(cic)}
        for k in ("ciclo", "verde", "amarillo", "rojo"):
            vals = [c[k] for c in cic]
            fila[f"{k}_media_s"] = round(st.mean(vals), 1) if vals else ""
            fila[f"{k}_sd_s"] = round(st.stdev(vals), 1) if len(vals) > 1 else ""
        sd = fila["ciclo_sd_s"]
        fila["ciclo_variable"] = "si" if sd != "" and sd > UMBRAL_VARIABLE_S else ("no" if sd != "" else "")
        filas.append(fila)
    return filas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), "..", "data", "terreno"))
    args = ap.parse_args()
    filas = resumir(args.dir)
    salida = os.path.join(args.dir, "resumen_tiempos.csv")
    if not filas:
        print("Sin eventos que procesar.")
        return
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} filas -> {salida}")
    pocos = [f"{r['medicion_id']}/{r['grupo']}" for r in filas if r["ciclos_completos"] < 3]
    if pocos:
        print("Aviso: menos de 3 ciclos completos en:", ", ".join(pocos))


if __name__ == "__main__":
    main()
