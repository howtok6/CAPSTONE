"""Qué archivo de demanda usa cada corrida.

Las réplicas de un perfil son realizaciones distintas de la demanda
(`scripts/build_demand_profiles.py --train-replicas N --eval-replicas N`):

    demand/train/routes_<perfil>_tNN.rou.xml   las ve solo el entrenamiento
    demand/eval/routes_<perfil>_sNN.rou.xml    las ven solo las evaluaciones

La réplica k de evaluación se usa con la semilla k en todos los controladores,
de modo que la comparación sigue siendo pareada y la política nunca se mide
sobre viajes que vio al entrenar.
"""
from __future__ import annotations

import glob
import os


def ruta_evaluacion(scenario: str, profile: str | None, seed: int, por_defecto: str) -> str:
    """Demanda de la réplica `seed`; `por_defecto` si el perfil no tiene réplicas."""
    if profile:
        ruta = os.path.join(scenario, "demand", "eval", f"routes_{profile}_s{seed:02d}.rou.xml")
        if os.path.exists(ruta):
            return ruta
    return por_defecto


def rutas_entrenamiento(scenario: str, profile: str | None) -> list:
    """Demandas de entrenamiento del perfil, ordenadas; vacío si no hay."""
    if not profile:
        return []
    patron = os.path.join(scenario, "demand", "train", f"routes_{profile}_t*.rou.xml")
    return sorted(glob.glob(patron))
