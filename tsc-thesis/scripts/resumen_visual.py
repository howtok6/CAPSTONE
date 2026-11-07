#!/usr/bin/env python3
"""Resume results/visual/colas_*.json para la pÃ¡gina comparativa.

Agrupa los semÃ¡foros del eje en tramos de 500 m y el tiempo en bloques de 2
minutos (cola total del tramo, promedio del bloque). AsÃ­ el diagrama espacio-
tiempo queda chico sin perder dÃ³nde y cuÃ¡ndo se forma la congestiÃ³n.

    python scripts/resumen_visual.py
"""
import glob
import json
import os
import statistics as st

TRAMO_M, BLOQUE_S = 500, 240
salida = {"tramo_m": TRAMO_M, "bloque_s": BLOQUE_S, "perfiles": {}}
for ruta in sorted(glob.glob("results/visual/colas_*.json")):
    d = json.load(open(ruta, encoding="utf-8"))
    p, c = d["perfil"], d["controlador"]
    pos = d["posicion_m"]
    n_tramos = max(pos) // TRAMO_M + 1
    t = d["tiempos"]
    bloques = sorted({x // BLOQUE_S for x in t})
    mapa = []
    for b in bloques:
        filas = [i for i, x in enumerate(t) if x // BLOQUE_S == b]
        fila = [0.0] * n_tramos
        for i in filas:
            for k, q in enumerate(d["cola"][i]):
                fila[pos[k] // TRAMO_M] += q / len(filas)
        mapa.append([round(v) for v in fila])
    perfil = salida["perfiles"].setdefault(p, {"controladores": {}})
    # avenida dominante de cada tramo, para rotular el eje
    av = {}
    for k, x in enumerate(pos):
        av.setdefault(x // TRAMO_M, []).append(d["avenida"][k])
    perfil["avenidas"] = [max(set(av.get(i, [""])), key=av.get(i, [""]).count) for i in range(n_tramos)]
    perfil["controladores"][c] = {
        "mapa": mapa,
        "detenidos": [r["detenidos"] for r in d["red"]][::2],
        "esperando": [r["esperando_entrar"] for r in d["red"]][::2],
        "llegados": [r["llegados"] for r in d["red"]][::2],
        "cola_eje_media": round(st.fmean(sum(x) for x in d["cola"]), 1),
    }
    perfil["t_curvas"] = t[::2]
with open("results/visual/resumen.json", "w", encoding="utf-8") as f:
    json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
print(os.path.getsize("results/visual/resumen.json"), "bytes")
