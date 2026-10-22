"""Verifica el cálculo de tiempos semafóricos a partir de marcas de terreno."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from procesar_terreno import parse_t, resumir  # noqa: E402


def _escribir(tmp_path, mediciones, eventos):
    (tmp_path / "mediciones.csv").write_text(
        "medicion_id,cruce_id,fecha,hora_inicio,franja,observador,metodo,video_archivo,clima,notas\n"
        + mediciones, encoding="utf-8")
    (tmp_path / "eventos.csv").write_text("medicion_id,grupo,color,t,notas\n" + eventos, encoding="utf-8")


def test_parse_t_formatos():
    assert parse_t("12.5") == 12.5
    assert parse_t("1:02.5") == 62.5
    assert parse_t("01:00:00") == 3600


def test_ciclo_fijo_de_90_segundos(tmp_path):
    # eje: verde 50 s, amarillo 3 s, rojo 37 s; tres ciclos completos de 90 s
    ev = ""
    for k in range(4):
        base = 10 + 90 * k
        ev += f"M1,eje,verde,{base},\n"
        if k < 3:
            ev += f"M1,eje,amarillo,{base + 50},\nM1,eje,rojo,{base + 53},\n"
    _escribir(tmp_path, "M1,C04,2026-10-27,18:05,punta_pm,GC,video,c04.mp4,despejado,\n", ev)
    (fila,) = resumir(str(tmp_path))
    assert fila["ciclos_completos"] == 3
    assert fila["ciclo_media_s"] == 90.0
    assert (fila["verde_media_s"], fila["amarillo_media_s"], fila["rojo_media_s"]) == (50.0, 3.0, 37.0)
    assert fila["ciclo_variable"] == "no"


def test_ciclo_incompleto_se_descarta(tmp_path):
    # falta el amarillo del segundo ciclo: solo debe contar el primero
    ev = ("M1,eje,verde,0,\nM1,eje,amarillo,40,\nM1,eje,rojo,43,\n"
          "M1,eje,verde,90,\nM1,eje,rojo,133,\nM1,eje,verde,180,\n")
    _escribir(tmp_path, "M1,C04,2026-10-27,18:05,punta_pm,GC,video,,,\n", ev)
    (fila,) = resumir(str(tmp_path))
    assert fila["ciclos_completos"] == 1
