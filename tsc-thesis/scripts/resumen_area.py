#!/usr/bin/env python3
"""Tabla y gráficos comparativos de una tanda por escenario (por defecto, Las Condes + Providencia).

    python scripts/resumen_area.py --scenario scenarios/las_condes_providencia

Lee results/<escenario>_<perfil>_baselines.json (líneas base y modelos evaluados con
el mismo protocolo) y models/<escenario>/*_log/progress.csv (curvas de aprendizaje).
Escribe:
    results/<escenario>_resumen.md     tablas por perfil (media, IC 95 %, % frente a
                                       tiempo fijo y al mejor clásico)
    results/<escenario>_resumen.json   lo mismo en datos
    results/figuras_<escenario>/       demora_por_perfil.png, mejora_vs_fijo.png,
                                       metricas_<perfil>.png, aprendizaje.png

Métrica principal: demora media por vehículo incluyendo a los que no terminaron
(`delay_all_mean`), la misma del informe del eje.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PERFILES = [("eod_valle", "Valle"), ("eod_punta_tarde", "Punta tarde"),
            ("eod_punta_manana", "Punta mañana"), ("eod_sobresaturado", "Sobresaturado")]
CLASICOS = ["fixed", "webster", "greedy", "maxpressure"]
NOMBRES = {"fixed": "Tiempo fijo", "webster": "Webster", "greedy": "Voraz", "maxpressure": "Max-Pressure"}
# Paleta categórica de referencia (skill dataviz), en orden fijo: el color sigue al
# controlador en todos los gráficos.
PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TINTA, TINTA_2, GRILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
T95 = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 7: 2.45, 8: 2.36, 9: 2.31, 10: 2.26}
METRICAS = [("delay_all_mean", "Demora media (s/veh)\nincluye no terminados"),
            ("time_loss_mean", "Demora de viajes\nterminados (s/veh)"),
            ("queue_mean", "Cola media en la red\n(vehículos detenidos)"),
            ("vehicles_finished", "Viajes terminados\nen la hora")]


def ic95(xs):
    n = len(xs)
    return T95.get(n, 1.96) * statistics.stdev(xs) / math.sqrt(n) if n >= 2 else float("nan")


def nombre(c: str) -> str:
    if c in NOMBRES:
        return NOMBRES[c]
    return c.replace("ippo_mixto_s", "IPPO mixto s").replace("ippo_", "IPPO ")


def estilo(ax):
    ax.set_facecolor(FONDO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRILLA)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    ax.yaxis.label.set_color(TINTA_2)
    ax.xaxis.label.set_color(TINTA_2)
    ax.grid(axis="y", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)


def cargar(esc: str):
    datos = {}
    for perfil, _ in PERFILES:
        ruta = os.path.join("results", f"{esc}_{perfil}_baselines.json")
        if os.path.exists(ruta):
            datos[perfil] = json.load(open(ruta, encoding="utf-8"))
    return datos


def resumir(filas):
    por = {}
    for r in filas:
        por.setdefault(r["controller"], []).append(r)
    out = {}
    for c, rs in por.items():
        d = {"n": len(rs)}
        for m, _ in METRICAS + [("vehicles_pending_end", ""), ("vehicles_running_end", ""), ("throughput", "")]:
            xs = [r[m] for r in rs if r.get(m) is not None and not (isinstance(r[m], float) and math.isnan(r[m]))]
            if xs:
                d[m] = statistics.fmean(xs)
                d[m + "_ic95"] = ic95(xs)
        out[c] = d
    return out


def orden_controladores(todos):
    clas = [c for c in CLASICOS if c in todos]
    otros = sorted(c for c in todos if c not in CLASICOS)
    return clas + otros


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", default="scenarios/las_condes_providencia")
    a = ap.parse_args()
    esc = os.path.basename(os.path.normpath(a.scenario))
    figs = os.path.join("results", f"figuras_{esc}")
    os.makedirs(figs, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": TINTA, "figure.facecolor": FONDO})

    datos = cargar(esc)
    if not datos:
        sys.exit(f"No hay resultados en results/{esc}_<perfil>_baselines.json")
    res = {p: resumir(f) for p, f in datos.items()}
    todos = orden_controladores({c for r in res.values() for c in r})
    color = {c: PALETA[i % len(PALETA)] for i, c in enumerate(todos)}
    perfiles = [(p, t) for p, t in PERFILES if p in res]

    # ---------------------------------------------------------------- tablas
    md = [f"# Resumen de la tanda: {esc}\n",
          "Demora media por vehículo incluyendo a los que no terminaron (`delay_all_mean`), "
          "media de las réplicas ± IC 95 % (t de Student). Negativo = mejor.\n"]
    for p, titulo in perfiles:
        r = res[p]
        clas = {c: r[c]["delay_all_mean"] for c in r if c in CLASICOS and "delay_all_mean" in r[c]}
        mejor = min(clas, key=clas.get) if clas else None
        fijo = r.get("fixed", {}).get("delay_all_mean")
        md.append(f"\n## {titulo}  (mejor clásico: {nombre(mejor) if mejor else '—'})\n")
        md.append("| Controlador | n | Demora (s) | IC 95 % | vs. tiempo fijo | vs. mejor clásico | "
                  "Demora terminados (s) | Cola media | Terminan | En la red al final | Sin entrar |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for c in sorted(r, key=lambda c: r[c].get("delay_all_mean", float("inf"))):
            d = r[c]
            m = d.get("delay_all_mean", float("nan"))
            vf = f"{100 * (m / fijo - 1):+.1f} %" if fijo and c != "fixed" else "—"
            vm = f"{100 * (m / clas[mejor] - 1):+.1f} %" if mejor and c != mejor else "—"
            ic = d.get("delay_all_mean_ic95", float("nan"))
            md.append(f"| {nombre(c)} | {d['n']} | {m:.1f} | {'—' if math.isnan(ic) else f'±{ic:.1f}'} | {vf} | {vm} | "
                      f"{d.get('time_loss_mean', float('nan')):.1f} | {d.get('queue_mean', float('nan')):.0f} | "
                      f"{d.get('vehicles_finished', 0):,.0f} | {d.get('vehicles_running_end', 0):,.0f} | "
                      f"{d.get('vehicles_pending_end', 0):,.0f} |")
    open(os.path.join("results", f"{esc}_resumen.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(res, open(os.path.join("results", f"{esc}_resumen.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    # ---------------------------------------------------------------- demora por perfil
    fig, ax = plt.subplots(figsize=(9, 4.8))
    estilo(ax)
    ancho = 0.8 / len(todos)
    for i, c in enumerate(todos):
        xs, ys, es = [], [], []
        for j, (p, _) in enumerate(perfiles):
            d = res[p].get(c)
            if d and "delay_all_mean" in d:
                xs.append(j - 0.4 + ancho * (i + 0.5))
                ys.append(d["delay_all_mean"])
                e = d.get("delay_all_mean_ic95", float("nan"))
                es.append(0 if math.isnan(e) else e)
        ax.bar(xs, ys, width=ancho, color=color[c], edgecolor=FONDO, linewidth=1.5, label=nombre(c), zorder=2)
        ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=TINTA_2, elinewidth=1, capsize=2, zorder=3)
    ax.set_xticks(range(len(perfiles)))
    ax.set_xticklabels([t + (f"\n(n = {max(d['n'] for d in res[p].values())})") for p, t in perfiles], color=TINTA)
    ax.set_ylabel("Demora media (s por vehículo)")
    ax.set_title("Demora media por vehículo, Las Condes + Providencia", loc="left")
    ax.legend(ncol=min(3, len(todos)), frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.14))
    fig.tight_layout()
    fig.savefig(os.path.join(figs, "demora_por_perfil.png"), dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- mejora vs tiempo fijo
    otros = [c for c in todos if c != "fixed"]
    if otros and all("fixed" in res[p] for p, _ in perfiles):
        fig, ax = plt.subplots(figsize=(9, 4.4))
        estilo(ax)
        ancho = 0.8 / len(otros)
        for i, c in enumerate(otros):
            xs, ys = [], []
            for j, (p, _) in enumerate(perfiles):
                d, f = res[p].get(c), res[p]["fixed"].get("delay_all_mean")
                if d and "delay_all_mean" in d and f:
                    xs.append(j - 0.4 + ancho * (i + 0.5))
                    ys.append(100 * (d["delay_all_mean"] / f - 1))
            ax.bar(xs, ys, width=ancho, color=color[c], edgecolor=FONDO, linewidth=1.5, label=nombre(c), zorder=2)
            for x, y in zip(xs, ys):
                ax.annotate(f"{y:+.0f} %", (x, y), xytext=(0, -11 if y < 0 else 3), textcoords="offset points",
                            ha="center", fontsize=7.5, color=TINTA_2)
        ax.axhline(0, color=TINTA_2, linewidth=1)
        ax.set_xticks(range(len(perfiles)))
        ax.set_xticklabels([t for _, t in perfiles], color=TINTA)
        ax.set_ylabel("Cambio en la demora frente a tiempo fijo (%)")
        ax.set_title("Cuánto cambia la demora frente a tiempo fijo (negativo = mejor)", loc="left")
        ax.legend(ncol=min(3, len(otros)), frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.08))
        fig.tight_layout()
        fig.savefig(os.path.join(figs, "mejora_vs_fijo.png"), dpi=150)
        plt.close(fig)

    # ---------------------------------------------------------------- métricas por perfil
    for p, titulo in perfiles:
        cs = [c for c in todos if c in res[p]]
        fig, axs = plt.subplots(1, len(METRICAS), figsize=(13, 0.45 * len(cs) + 1.8), sharey=True)
        for ax, (m, etiqueta) in zip(axs, METRICAS):
            estilo(ax)
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=GRILLA, linewidth=0.8)
            ys = list(range(len(cs)))[::-1]
            vals = [res[p][c].get(m, float("nan")) for c in cs]
            errs = [0 if math.isnan(res[p][c].get(m + "_ic95", float("nan"))) else res[p][c][m + "_ic95"] for c in cs]
            ax.barh(ys, vals, height=0.62, color=[color[c] for c in cs], edgecolor=FONDO, linewidth=1.5, zorder=2)
            ax.errorbar(vals, ys, xerr=errs, fmt="none", ecolor=TINTA_2, elinewidth=1, capsize=2, zorder=3)
            for y, v, e in zip(ys, vals, errs):
                if not math.isnan(v):
                    ax.annotate(f"{v:,.0f}", (v + e, y), xytext=(5, 0), textcoords="offset points",
                                va="center", fontsize=8, color=TINTA)
            ax.set_title(etiqueta, loc="left", fontsize=9.5)
            ax.margins(x=0.22)
        axs[0].set_yticks(list(range(len(cs)))[::-1])
        axs[0].set_yticklabels([nombre(c) for c in cs], color=TINTA)
        n = max(d["n"] for d in res[p].values())
        fig.suptitle(f"{titulo}: métricas por controlador (n = {n} réplicas)", x=0.01, ha="left",
                     fontweight="bold", color=TINTA)
        fig.tight_layout()
        fig.savefig(os.path.join(figs, f"metricas_{p}.png"), dpi=150)
        plt.close(fig)

    # ---------------------------------------------------------------- curvas de aprendizaje
    curvas = sorted(glob.glob(os.path.join("models", esc, "ppo_*_log", "progress.csv")))
    curvas = [c for c in curvas if "smoke" not in c]
    if curvas:
        fig, ax = plt.subplots(figsize=(8, 4.2))
        estilo(ax)
        for k, ruta in enumerate(curvas):
            xs, ys = [], []
            with open(ruta, encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    if fila.get("rollout/ep_rew_mean") and fila.get("time/total_timesteps"):
                        xs.append(float(fila["time/total_timesteps"]) / 1e6)
                        ys.append(float(fila["rollout/ep_rew_mean"]))
            etiqueta = os.path.basename(os.path.dirname(ruta)).replace("ppo_fase_wait_adam_", "").replace("_log", "")
            c = next((x for x in todos if x.startswith("ippo") and etiqueta.endswith(x[-2:])), None)
            ax.plot(xs, ys, linewidth=2, color=color.get(c, PALETA[(4 + k) % 8]), label=etiqueta)
        ax.set_xlabel("Muestras de entrenamiento (millones; una por semáforo y decisión)")
        ax.set_ylabel("Recompensa media por episodio")
        ax.set_title("Curva de aprendizaje IPPO (recompensa: variación de la espera)", loc="left")
        ax.legend(frameon=False, fontsize=9)
        fig.tight_layout()
        fig.savefig(os.path.join(figs, "aprendizaje.png"), dpi=150)
        plt.close(fig)

    print("\n".join(md))
    print(f"\nOK  tablas -> results/{esc}_resumen.md · figuras -> {figs}")


if __name__ == "__main__":
    main()
