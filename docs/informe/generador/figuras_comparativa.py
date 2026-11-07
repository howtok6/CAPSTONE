#!/usr/bin/env python3
"""Figuras del informe de comparativa (7-nov-2026).

Lee los resultados del repositorio y deja PNG en docs/informe/figuras/comparativa/.
Se corre desde la raíz del repositorio:

    python docs/informe/generador/figuras_comparativa.py
"""
import json
import os
import shutil
import statistics as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(RAIZ, "tsc-thesis", "results")
OUT = os.path.join(RAIZ, "docs", "informe", "figuras", "comparativa")
os.makedirs(OUT, exist_ok=True)

CTRL = [("fixed", "Tiempo fijo", "#eb6834"), ("webster", "Webster", "#eda100"),
        ("maxpressure", "Max-Pressure", "#1baf7a"), ("greedy", "Voraz por cola", "#e87ba4"),
        ("ppo_fase_s1", "IPPO", "#2a78d6")]
PERFILES = [("valle", "Valle"), ("punta_manana", "Punta mañana"), ("punta_tarde", "Punta tarde"),
            ("sobresaturado", "Sobresaturado")]
TINTA, TINTA2, GRILLA = "#16181a", "#52514e", "#e6e8e4"
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.edgecolor": GRILLA,
                     "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
                     "axes.spines.top": False, "axes.spines.right": False})


def demora():
    """Demora media por perfil y controlador, 10 demandas de evaluación."""
    filas = {}
    for p, _ in PERFILES:
        d = {}
        for r in json.load(open(os.path.join(RES, f"eje_comunal_{p}_baselines.json"))):
            d.setdefault(r["controller"], []).append(r["delay_all_mean"])
        filas[p] = {c: st.fmean(v) for c, v in d.items()}
    return filas


def fig_barras():
    D = demora()
    fig, ejes = plt.subplots(1, 4, figsize=(7.2, 2.9), sharey=True)
    for ax, (p, nombre) in zip(ejes, PERFILES):
        vals = [D[p][c] for c, _, _ in CTRL]
        y = np.arange(len(CTRL))[::-1]
        ax.barh(y, vals, color=[c for _, _, c in CTRL], height=0.62)
        for yi, v in zip(y, vals):
            ax.text(v + max(vals) * 0.02, yi, f"{v:,.0f}".replace(",", "."), va="center", fontsize=8, color=TINTA)
        ax.set_title(nombre, fontsize=9.5, color=TINTA, loc="left", fontweight="bold")
        ax.set_xlim(0, max(vals) * 1.32)
        ax.set_yticks(y, [n for _, n, _ in CTRL])
        ax.tick_params(axis="y", length=0)
        ax.xaxis.grid(True, color=GRILLA)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=7.5)
    ejes[0].set_xlabel("s por vehículo", fontsize=8)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(os.path.join(OUT, "fig1_demora_perfiles.png"), dpi=220)
    plt.close(fig)


def fig_mapas(perfil, archivo):
    R = json.load(open(os.path.join(RES, "visual", "resumen_pagina.json"), encoding="utf-8"))
    P = R["perfiles"][perfil]["controladores"]
    claves = [("fixed", "Tiempo fijo"), ("webster", "Webster"), ("maxpressure", "Max-Pressure"),
              ("greedy", "Voraz por cola"), ("ppo", "IPPO")]
    mapas = {k: np.array(P[k]["mapa"][:-1], float) for k, _ in claves}  # el último bloque es un solo instante
    vmax = max(m.max() for m in mapas.values())
    fig, ejes = plt.subplots(1, 5, figsize=(7.4, 2.7), sharey=True)
    for ax, (k, n) in zip(ejes, claves):
        m = mapas[k]
        im = ax.imshow(np.sqrt(m / vmax), cmap="Blues", vmin=0, vmax=1, aspect="auto",
                       extent=[0, m.shape[1] * 0.5, m.shape[0] * 4, 0], interpolation="nearest")
        ax.set_title(f"{n}\ncola media: {P[k]['cola_eje_media']:.0f} veh", fontsize=7.5, color=TINTA)
        ax.set_xticks([0, 5, 10], ["0", "5", "10 km"], fontsize=7)
        for x in (5.0, 8.5):  # límites aproximados Alameda | Providencia | Apoquindo
            ax.axvline(x, color="#9aa0a6", lw=0.6, ls=":")
    ejes[0].set_ylabel("minuto de la simulación", fontsize=8)
    ejes[0].set_yticks([0, 20, 40, 60])
    cb = fig.colorbar(im, ax=ejes, fraction=0.025, pad=0.02)
    cb.set_ticks([0, np.sqrt(0.25), np.sqrt(0.5), 1],
                 labels=["0", f"{vmax * 0.25:.0f}", f"{vmax * 0.5:.0f}", f"{vmax:.0f}"])
    cb.ax.tick_params(labelsize=7)
    cb.set_label("detenidos por tramo de 500 m", fontsize=7)
    fig.savefig(os.path.join(OUT, archivo), dpi=220, bbox_inches="tight")
    plt.close(fig)


def fig_red():
    R = json.load(open(os.path.join(RES, "visual", "resumen_pagina.json"), encoding="utf-8"))
    fig, ejes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    claves = [("fixed", "Tiempo fijo", "#eb6834"), ("webster", "Webster", "#eda100"),
              ("maxpressure", "Max-Pressure", "#1baf7a"), ("greedy", "Voraz por cola", "#e87ba4"),
              ("ppo", "IPPO", "#2a78d6")]
    for ax, (p, nombre) in zip(ejes, [("punta_tarde", "Punta tarde"), ("sobresaturado", "Sobresaturado")]):
        P = R["perfiles"][p]["controladores"]
        for k, n, c in claves:
            d = np.array(P[k]["detenidos"], float)
            d = np.convolve(np.pad(d, 1, mode="edge"), np.ones(3) / 3, mode="valid")  # media móvil 3 min
            t = (30 + 60 * np.arange(len(d))) / 60
            ax.plot(t, d, color=c, lw=1.6, label=n)
        ax.set_title(nombre, fontsize=9.5, color=TINTA, loc="left", fontweight="bold")
        ax.set_xlabel("minuto", fontsize=8)
        ax.yaxis.grid(True, color=GRILLA)
        ax.set_xlim(0, 60)
        ax.set_ylim(0)
    ejes[0].set_ylabel("vehículos detenidos en la red", fontsize=8)
    ejes[1].legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_detenidos_red.png"), dpi=220)
    plt.close(fig)


def copiar_cuadros():
    v = os.path.join(RES, "video")
    for origen, destino in (("punta_tarde_apoquindo_cuatro_muestra.png", "fig5_video_apoquindo.png"),
                            ("sobresaturado_eje_completo_muestra.png", "fig6_video_eje_completo.png")):
        shutil.copy(os.path.join(v, origen), os.path.join(OUT, destino))


if __name__ == "__main__":
    fig_barras()
    fig_mapas("punta_tarde", "fig2_mapa_punta_tarde.png")
    fig_mapas("sobresaturado", "fig3_mapa_sobresaturado.png")
    fig_red()
    copiar_cuadros()
    print("\n".join(sorted(os.listdir(OUT))))
