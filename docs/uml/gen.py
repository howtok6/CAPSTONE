"""Genera los diagramas PlantUML de casos de uso desde un único modelo.

Una sola fuente de verdad: si cambia un caso de uso, se regeneran los cuatro
diagramas (general + uno por subsistema) y quedan consistentes entre sí.
"""
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

STYLE = """skinparam shadowing false
skinparam defaultFontName "DejaVu Sans"
skinparam defaultFontSize 12
skinparam packageStyle rectangle
skinparam actorStyle awesome
skinparam usecase {
  BackgroundColor #FFFFFF
  BorderColor #2F4F6F
  ArrowColor #2F4F6F
}
skinparam rectangle {
  BorderColor #2F4F6F
  FontStyle bold
}
skinparam package {
  BackgroundColor #F5F7FA
  BorderColor #9AA9B8
}
skinparam note {
  BackgroundColor #FFFBE6
  BorderColor #C9B458
}"""

ACTORS = {
    "INV": ("Investigador", False),
    "REV": ("Revisor", False),
    "PG": ("Profesor guía", False),
    "CE": ("Comisión evaluadora", False),
    "EXT": ("Investigador externo", False),
    "OSM": ("OpenStreetMap", True),
    "FDM": ("Fuentes de datos\\nde movilidad", True),
    "SUMO": ("SUMO\\n(libsumo / TraCI)", True),
}
# actores a la izquierda (iniciadores) y a la derecha (revisores y sistemas)
LEFT = {"INV"}

PACKAGES = [
    ("esc", "1. Escenario", [
        ("UC01", "Construir red\\ndel eje comunal"),
        ("UC02", "Descargar geometría\\ndesde OSM"),
        ("UC03", "Diagnosticar red"),
        ("UC04", "Corregir semáforos\\ny geometría"),
        ("UC05", "Seleccionar semáforos\\ncontrolados"),
        ("UC06", "Generar perfiles\\nde demanda"),
        ("UC07", "Calibrar demanda\\ncon datos observados"),
        ("UC08", "Procesar mediciones\\nde terreno"),
        ("UC09", "Validar escenario\\n(tiempos de viaje)"),
    ]),
    ("ctl", "2. Control", [
        ("UC10", "Calcular plan\\nWebster coordinado"),
        ("UC11", "Ejecutar líneas base\\n(Fixed, Webster,\\nMax-Pressure, Greedy)"),
        ("UC12", "Entrenar agente\\n(IPPO / MAPPO)"),
        ("UC13", "Ajustar recompensa,\\noptimizador e\\nhiperparámetros"),
        ("UC14", "Simular episodio"),
        ("UC15", "Calcular métricas\\n(tripinfo)"),
        ("UC16", "Evaluar política\\nentrenada"),
    ]),
    ("ana", "3. Análisis y difusión", [
        ("UC17", "Comparar controladores\\n(Wilcoxon, IC 95 %,\\ntamaño de efecto)"),
        ("UC18", "Ejecutar pruebas\\nde robustez"),
        ("UC19", "Visualizar simulación"),
        ("UC20", "Grabar video\\nde la ejecución"),
        ("UC21", "Reproducir resultados\\ndesde el repositorio"),
        ("UC22", "Revisar avance\\npor hito"),
    ]),
]

ASSOC = [  # actor, caso de uso
    ("INV", "UC01"), ("INV", "UC04"), ("INV", "UC05"), ("INV", "UC06"),
    ("INV", "UC07"), ("INV", "UC08"), ("INV", "UC09"),
    ("INV", "UC10"), ("INV", "UC11"), ("INV", "UC12"), ("INV", "UC16"),
    ("INV", "UC17"), ("INV", "UC18"), ("INV", "UC19"),
    ("REV", "UC19"), ("REV", "UC21"), ("PG", "UC22"),
    ("OSM", "UC02"), ("FDM", "UC07"), ("FDM", "UC09"),
    ("SUMO", "UC14"), ("SUMO", "UC19"),
]
INCLUDE = [
    ("UC01", "UC02"), ("UC01", "UC03"), ("UC04", "UC03"),
    ("UC11", "UC10"), ("UC11", "UC14"), ("UC12", "UC05"), ("UC12", "UC14"),
    ("UC16", "UC14"), ("UC14", "UC15"), ("UC17", "UC15"), ("UC21", "UC17"),
]
EXTEND = [  # extensión, base
    ("UC07", "UC06"), ("UC13", "UC12"), ("UC18", "UC16"), ("UC20", "UC19"),
]
GENERALIZATION = [("PG", "REV"), ("CE", "REV"), ("EXT", "REV")]

ALL_UC = {u: (pkg, label) for pkg, _, ucs in PACKAGES for u, label in ucs}


def actor_decl(a):
    name, system = ACTORS[a]
    stereo = " <<sistema>>" if system else ""
    return f'actor "{name}" as {a}{stereo}'


def render(name, title, pkgs, focus=None):
    """pkgs: paquetes a mostrar completos. focus: si se da, se muestran
    además (fuera de foco) los casos de uso de otros paquetes que se relacionan."""
    shown = {u for p, _, ucs in PACKAGES if p in pkgs for u, _ in ucs}
    extra = set()
    if focus:
        for a, b in INCLUDE + EXTEND:
            if a in shown and b not in shown:
                extra.add(b)
            if b in shown and a not in shown:
                extra.add(a)
    visible = shown | extra
    assoc = [(a, u) for a, u in ASSOC if u in shown]
    actors = {a for a, _ in assoc}
    gens = [(c, p) for c, p in GENERALIZATION if p in actors]
    actors |= {c for c, _ in gens}

    L = [f"@startuml {name}", f"' Generado por gen.py — no editar a mano", "left to right direction", STYLE, "",
         f"title {title}", ""]
    for a in ACTORS:
        if a in actors:
            L.append(actor_decl(a))
    L.append("")
    L.append('rectangle "Plataforma experimental tsc-thesis" {')
    for p, ptitle, ucs in PACKAGES:
        members = [(u, lbl) for u, lbl in ucs if u in visible]
        if not members:
            continue
        L.append(f'  package "{ptitle}" {{')
        for u, lbl in members:
            style = " #EEF1F4;line.dashed" if u in extra else ""
            L.append(f'    usecase "{u} {lbl}" as {u}{style}')
        L.append("  }")
    L.append("}")
    L.append("")
    for a, u in assoc:
        L.append(f"{a} -- {u}" if a in LEFT else f"{u} -- {a}")
    for a, b in INCLUDE:
        if a in visible and b in visible:
            L.append(f"{a} ..> {b} : <<include>>")
    for a, b in EXTEND:
        if a in visible and b in visible:
            L.append(f"{a} ..> {b} : <<extend>>")
    for c, p in gens:
        L.append(f"{p} <|-- {c}")
    if focus:
        L += ["", f"legend right\n  Casos de uso en gris y borde discontinuo:\n  pertenecen a otro subsistema.\nendlegend"]
    L.append("@enduml")
    (OUT / f"{name}.puml").write_text("\n".join(L) + "\n", encoding="utf-8")


render("casos-de-uso-general",
       "Diagrama de casos de uso — Plataforma experimental de control de semáforos",
       {"esc", "ctl", "ana"})
render("casos-de-uso-escenario", "Subsistema 1 — Escenario de simulación", {"esc"}, focus=True)
render("casos-de-uso-control", "Subsistema 2 — Control de semáforos", {"ctl"}, focus=True)
render("casos-de-uso-analisis", "Subsistema 3 — Análisis y difusión", {"ana"}, focus=True)
print("ok")
