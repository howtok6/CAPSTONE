# 13 · Escenario Las Condes + Providencia (17–18 nov 2026)

Desde el 17-nov el escenario principal de la tesis son las comunas completas de
Las Condes y Providencia. El eje Alameda–Providencia–Apoquindo (`12-demanda-eod.md`)
queda como estudio piloto ya terminado.

## 1. Semáforos: inventario UOCT 2023

`tsc-thesis/scripts/importar_uoct.py` descarga y lee el «Listado de intersecciones
conectadas a Sistema de Control / Región Metropolitana», rev. 15-mayo-2023
(transporteinforma.cl, SHA-256 `f8a7ebc0…f4a1d`).

- 3 468 cruces con coordenadas (3 330 en Gran Santiago, 3 130 vehiculares).
- El PDF agrupa los decimales con comas y a veces trae menos dígitos
  (`-3,342,883` = −33,42883): se recuperan quitando separadores.
- 21 cruces marcados `revisar` (lejos de su comuna, aislados, baja precisión o
  código duplicado). No se corrige nada a mano.
- No trae fases, ciclos ni estado operativo: solo ubicación y código.

Salida: `tsc-thesis/data/uoct/semaforos_uoct_rm_2023.{geojson,csv}`. El PDF queda fuera de git.

## 2. Red SUMO

`tsc-thesis/scripts/build_comunas.py`:

1. polígonos comunales (Nominatim; relaciones OSM 162991 y 162983);
2. área = comunas + 400 m, recortada al oriente en −70,488 (cordillera sin semáforos): 82,8 km²;
3. OSM en recuadros desde la API principal;
4. netconvert con las opciones de `build_santiago.py`, sin `living_street`, `service` ni `track`;
5. empareja la UOCT con los semáforos de la red (`emparejar_uoct.py`, ≤ 40 m) y
   semaforiza con `--tls.set` los cruces UOCT que OSM no marcó.

| | |
|---|---|
| Arcos / nodos / km-pista | 12 415 / 5 725 / 1 954 |
| Semáforos en la red | 603, de ellos 508 con código UOCT |
| Cruces UOCT vehiculares con semáforo en la red | 544 de 565 (96 %) |
| Sin cruce en la red (revisar a mano) | 21 vehiculares |
| No controlables (una fase verde) | 36 |
| Arcos < 25 m entre dos semáforos | 40 |

`scripts/listar_tls_area.py` deja en `tls_eje.json` los semáforos que controlan
los agentes: 480 (código UOCT y 2 a 4 fases verdes). La observación por fase admite
hasta 4 fases; un cruce con 5 queda en tiempo fijo junto con los 27 UOCT de una
fase y los 95 sin código.

Costo medido (`scripts/medir_costo_red.py`, i3-12100F): una hora con 10 000 veh/h
aleatorios tarda 153 s; observar los 603 semáforos con libsumo agrega solo 4 s.

## 3. Demanda EOD por área

`tsc-thesis/scripts/build_demand_area.py`. Cada viaje en auto de la EOD 2012 se
clasifica respecto del área: **interno**, **sale**, **entra** o **paso** (la recta
origen-destino cruza ≥ 1 km). Extremos internos: arco cercano al punto de la
encuesta. Extremos externos: entrada o salida del borde cercana al punto donde la
recta cruza el límite. Mismos perfiles y nombres de archivo que el eje.

Con expansión EOD × crecimiento 1,49 × factor de hora punta, la punta mañana
suma ~267 000 veh/h que tocan el área. Asignados a la ruta más corta, Apoquindo y
Providencia quedan ~4 veces sobre el censo del proyecto: **escala 0,25** (por
defecto). Con ella, Apoquindo / Alcántara lleva 1 983 veh/h al poniente en punta
mañana (censo 1 800–2 700) y Providencia / P. de Valdivia ~5 250 en ambos sentidos
(censo ~4 600).

| Perfil (escala 0,25) | Vehículos en 1 h |
|---|---|
| Valle | 27 813 |
| Punta mañana | 66 674 |
| Punta tarde | 48 487 |
| Sobresaturado | 86 874 |

Con los planes fijos de OSM la punta mañana se bloquea (15 % de teletransportes con
umbral de 300 s, ~37 min de cómputo por hora simulada). Valle: 4 %, ~10 min.

## 4. Tanda del 18-nov

`tsc-thesis/scripts/tanda_area.py` (00:34–04:43, sin fallas):

- Webster por perfil (calibrado con el voraz), tiempo fijo, voraz y Max-Pressure.
- Dos IPPO (semillas 0 y 1), obs por fase, recompensa de espera, 3,07 M muestras
  cada uno, entrenados con el conjunto mixto valle + punta tarde (3 réplicas de cada uno).
- Evaluación con 3 réplicas en valle y punta tarde y 1 corrida en punta mañana.
- `scripts/resumen_area.py`: `results/las_condes_providencia_resumen.{md,json}` y
  `results/figuras_las_condes_providencia/`.

Demora media por vehículo incluyendo los que no terminan (s), media ± IC 95 %:

| Controlador | Valle | Punta tarde | Punta mañana (n = 1) |
|---|---|---|---|
| Tiempo fijo | 571 ± 69 | 962 ± 44 | 1 244 |
| Webster | 389 ± 33 | 894 ± 24 | 1 191 |
| Voraz | 414 ± 87 | 845 ± 68 | 1 168 |
| Max-Pressure | 378 ± 96 | 867 ± 56 | 1 153 |
| IPPO mixto s0 | **373 ± 87** | **811 ± 31** | **1 137** |
| IPPO mixto s1 | 482 ± 65 | 909 ± 51 | 1 184 |

Lectura:

- Todos los adaptativos le ganan al tiempo fijo (valle −28 a −35 %, punta tarde −7 a −16 %).
- IPPO s0 es el mejor en los tres perfiles, pero frente al mejor clásico la diferencia
  es de −1,2 % (valle) y −4,0 % (punta tarde), con intervalos superpuestos. Con
  n = 3 el Wilcoxon pareado no baja de p = 0,25: **no es significativo**.
- Donde IPPO s0 más se distingue es en la cola de la red (−61 % en valle frente a
  tiempo fijo) y en los viajes terminados (+20 %).
- Las semillas difieren mucho (s1 es peor que todos los clásicos salvo tiempo fijo):
  el entrenamiento no es estable con ~9 h simuladas por modelo.
- La curva de aprendizaje oscila según el episodio sea de valle o de punta tarde;
  no sirve para juzgar convergencia.
- Punta mañana queda bloqueada con cualquier controlador (~36 000 vehículos en la
  red al cierre).

## 5. Limitaciones

- 3 réplicas (1 en punta mañana) y 2 semillas.
- Red de OSM sin depurar y planes de tiempo fijo genéricos.
- EOD 2012, escala global calibrada en dos secciones, sin buses.
- Max-Pressure con la configuración del eje.
- Incluso en valle quedan ~8 000 vehículos en la red al cierre: la red podría tener
  menos capacidad que la real o la escala podría ser alta.

## 6. Reproducir

```
cd tsc-thesis
python scripts/importar_uoct.py --out data/uoct
python scripts/build_comunas.py --comunas "Las Condes,Providencia" --out scenarios/las_condes_providencia \
    --uoct data/uoct/semaforos_uoct_rm_2023.geojson --etiquetas-uoct "LAS CONDES,PROVIDENCIA,VITACURA/LAS CONDES"
python scripts/listar_tls_area.py --scenario scenarios/las_condes_providencia
python scripts/build_demand_area.py --profiles eod_valle,eod_punta_tarde --train-replicas 3 --eval-replicas 3
python scripts/build_demand_area.py --profiles eod_punta_manana,eod_sobresaturado
python scripts/tanda_area.py
```

Fuera de git (se regeneran): descargas OSM, `net_base.net.xml`, rutas y réplicas,
checkpoints y logs de la tanda.
