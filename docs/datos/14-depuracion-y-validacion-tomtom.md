# 14 · Depuración de la red y validación con TomTom (Las Condes + Providencia)

Fecha: 18-nov-2026 · Rama `escenario-las-condes-providencia`

## 1. Por qué

La tanda del 18-nov (IPPO vs líneas base, n = 3) no dio diferencias significativas y la
simulación quedaba trabada: en punta tarde quedaban ~24.000 vehículos dentro de la red al
cumplirse la hora y ~6.000 teletransportes (con espera de 300 s). Antes de seguir entrenando
había que saber si eso era la ciudad o un defecto del escenario.

## 2. Diagnóstico de bloqueos (`scripts/puntos_bloqueo.py`)

Simula una hora con planes fijos, teletransporta a los 300 s de detención y agrupa los
teletransportes por cruce y causa (`jam` = cola, `yield` = esperando ceder el paso,
`wrong lane` = no logra cambiarse de pista).

| Corrida (réplica s00) | Insertados | En red al final | Teletransportes | jam / yield / pista | Cruces con bloqueo |
|---|---:|---:|---:|---|---:|
| Valle, red original | 27.220 | 9.230 | 1.331 | 669 / 608 / 52 | 216 |
| Valle, red depurada (pasos 1–2) | 27.196 | 9.226 | 1.307 | 640 / 598 / 67 | 220 |
| Valle, depurada + `--ignore-junction-blocker 20` | 27.319 | 8.548 | 1.209 | 610 / 530 / 35 | 195 |
| Punta tarde, red original | 44.701 | 24.008 | 5.961 | 3.105 / 2.452 / 398 | 641 |
| Punta tarde, red depurada (pasos 1–2) | 44.780 | 23.554 | 5.527 | 2.875 / 2.262 / 385 | 616 |

Lectura: los arreglos de semáforos (paso 1 y 2) bajan los bloqueos solo 2–7 %, y la opción de
SUMO para destrabar cruces bloqueados, otro 7 %. Los bloqueos no se concentran en unos pocos
cruces mal modelados (solo 4–7 % son de pista): están repartidos en 200–640 cruces, la mitad
en semáforos y la mitad en cruces de prioridad, y los peores están en las calles del borde
(José Miguel Claro, Bilbao, Vicuña Mackenna). Es decir, el problema principal no era la
geometría sino **demanda y velocidades**, que es lo que mostró TomTom.

## 3. Captura TomTom (`scripts/tomtom_muestreo.py`)

* 120 puntos fijos sobre arcos de la red (`data/tomtom/puntos_las_condes_providencia.json`):
  muestra estratificada dentro de las dos comunas — 48 troncales/primarias, 42 secundarias,
  30 terciarias —, arcos ≥ 80 m y puntos a ≥ 250 m entre sí, semilla 42.
* API Traffic Flow `flowSegmentData` (zoom 15). La clave se lee del `.env` de la API de
  Benja (ignorado por git) y no se imprime. Las capturas crudas quedan en
  `data/tomtom/las_condes_providencia/` y **no se suben al repositorio** (condiciones de uso
  de TomTom); al repo van solo los puntos, las métricas agregadas y dos figuras de dispersión
  (red original y configuración propuesta).
* Primera captura: miércoles 18-nov-2026 18:57 (punta tarde), 120/120 respuestas, confianza 0,97.

| Estrato | n | v actual (km/h) | v flujo libre TomTom | Límite en la red original | Índice v/v libre (mediana) |
|---|---:|---:|---:|---:|---:|
| Troncal | 48 | 26,6 | 40,0 | 55,8 | 0,63 |
| Secundaria | 42 | 23,1 | 31,7 | 58,1 | 0,73 |
| Terciaria | 30 | 23,3 | 28,2 | 56,0 | 0,83 |
| Todos | 120 | 24,5 | 34,2 | 56,7 | 0,73 |

En la realidad, a las 19:00 de un día hábil solo 3 de 120 arcos (2,5 %) estaban bajo el 25 %
de su velocidad libre. En la simulación, 26 %.

## 4. Hallazgo 1: velocidades máximas de la red

netconvert asigna la velocidad por tipo de vía cuando OSM no trae `maxspeed`: primarias y
secundarias a **100 km/h** y terciarias a **80 km/h**. Eran ~72 km de avenidas urbanas
(Bilbao, Manquehue, Pedro de Valdivia, Providencia, Los Leones, Riesco, Colón, Tomás Moro…),
y además el ruteo (camino más rápido) cargaba artificialmente esas avenidas.

Corrección (paso 1b de `depurar_red_area.py`, `limitar_velocidades`): toda vía que no sea
autopista con ≥ 79 km/h pasa a 50 km/h (Ley 21.103, límite urbano); las de 60–70 km/h vienen
de `maxspeed` en OSM y se respetan; en autopistas se acota a 100 km/h. Resultado: 942 arcos,
74,5 km. Los ID de arcos y nodos no cambian.

## 5. Hallazgo 2: velocidad deseada y demanda

Con la red corregida se regeneró la demanda (rutas nuevas) a tres escalas y se comparó cada
una con la captura (`scripts/comparar_tomtom.py`: misma réplica de punta tarde, planes fijos,
sin teletransporte como en el arnés, medición entre 900 s y 3.600 s; v_sim = velocidad media
del arco ponderada por tiempo, que incluye la espera en cola igual que TomTom).

| Configuración | v TomTom / sim (km/h) | Sesgo | MAE | r | Índice TomTom / sim | ρ índice | % arcos atascados (TomTom 2,5 %) | Cómputo |
|---|---|---:|---:|---:|---|---:|---:|---:|
| Red original, escala 0,25 (la de la tanda) | 24,1 / 31,1 | +7,0 | 18,2 | 0,31 | 0,71 / 0,57 | 0,23 | 26,3 % | 872 s |
| Red depurada, 0,25 | 24,1 / 30,4 | +6,3 | 15,5 | 0,36 | 0,71 / 0,60 | 0,27 | 20,3 % | 603 s |
| Red depurada, 0,18 | 24,1 / 34,4 | +10,3 | 16,2 | 0,40 | 0,71 / 0,67 | 0,25 | 11,9 % | 447 s |
| Red depurada, 0,12 | 24,1 / 36,0 | +11,9 | 16,4 | 0,40 | 0,71 / 0,71 | 0,19 | 7,6 % | 273 s |
| Depurada, 0,25, speedFactor 0,7 | 24,1 / 21,9 | −2,2 | 9,7 | 0,38 | 0,71 / 0,61 | 0,35 | 20,3 % | 717 s |
| **Depurada, 0,18, speedFactor 0,7** | 24,1 / 24,6 | **+0,6** | **8,7** | 0,41 | 0,71 / 0,69 | 0,30 | 11,0 % | 506 s |
| Depurada, 0,12, speedFactor 0,7 | 24,1 / 25,6 | +1,5 | 8,3 | 0,39 | 0,71 / 0,72 | 0,21 | 6,8 % | 253 s |
| Depurada, 0,18, sf 0,7 + reruteo dinámico | 24,1 / 24,5 | +0,5 | 8,2 | 0,43 | 0,71 / 0,69 | 0,29 | 6,8 % | 1.219 s |
| Depurada, 0,25, sf 0,7 + reruteo dinámico | 24,1 / 23,0 | −1,0 | 8,2 | 0,46 | 0,71 / 0,64 | 0,37 | 11,9 % | 2.366 s |

(Índice sim = v_sim / (límite × speedFactor). ρ = Spearman. «Atascado» = índice < 0,25.)

Lectura:

1. **La velocidad deseada es el ajuste que más pesa.** En SUMO los conductores van, en
   promedio, al límite (speedFactor 1,0). TomTom mide a flujo libre ~0,67 del límite (34 de
   51 km/h): fricción urbana que el modelo no tiene (buses detenidos, estacionamiento,
   peatones). Con speedFactor 0,7 el sesgo de velocidad pasa de +6…+12 km/h a −2…+1,5 km/h y
   el MAE baja de 15–18 a 8–10 km/h, para cualquier escala.
2. **La escala decide cuánta red se atasca.** Con 0,25 (calibrada contra el censo con
   asignación a ruta más corta) se atasca el 20 % de los arcos; con 0,18 el 11 %; con 0,12
   el 7 %. TomTom: 2,5 %. La calibración contra el censo y la de TomTom no coinciden porque
   la asignación todo-o-nada concentra los viajes; el reruteo dinámico (que aproxima el
   equilibrio) baja los atascos de 11 % a 7 % con 0,18, pero cuesta 2,4 veces el cómputo:
   no es viable para entrenar 3M pasos. El dato clave: **la demanda del censo (0,25) con
   reruteo dinámico atasca lo mismo que 0,18 sin reruteo** (11,9 % vs 11,0 %; sesgo −1,0
   vs +0,6 km/h). O sea, 0,18 con rutas fijas es el equivalente práctico de la demanda
   censal cuando los conductores se reparten, y no una demanda inventada a la baja.
3. **La correlación espacial sigue débil** (r ≈ 0,4; ρ ≈ 0,2–0,35): la escala y la velocidad
   acercan el nivel, no qué arco está peor. Es esperable con demanda sintética de la EOD
   2012 y planes fijos genéricos (no los de la UOCT); se declara como limitación.

### Valle (captura del jueves 19-nov, 15:04)

La captura de punta mañana del 19-nov no se hizo (el PC no estaba conectado entre 08:05 y
09:00); queda pendiente para otro día hábil. Valle: 120/120 respuestas, confianza 0,99,
v media 29,5 km/h, índice mediano 0,85 y **ningún arco atascado** (troncales 0,77,
secundarias 0,85, terciarias 1,00).

| Configuración (red depurada, speedFactor 0,7) | v TomTom / sim | Sesgo | MAE | r | Índice TomTom / sim | ρ índice | % atascado (TomTom 0 %) | Cómputo |
|---|---|---:|---:|---:|---|---:|---:|---:|
| **Escala 0,18** | 29,0 / 26,4 | −2,5 | 8,0 | 0,40 | 0,86 / 0,74 | 0,16 | 3,4 % | 160 s |
| Escala 0,25 | 29,0 / 25,8 | −3,2 | 8,5 | 0,38 | 0,86 / 0,72 | 0,18 | 7,8 % | 225 s |

Con la misma configuración que en punta tarde, valle queda algo más congestionado que la
realidad (índice 0,74 vs 0,86, sesgo −2,5 km/h), pero con un error del mismo orden (MAE
8 km/h). Se mantiene una sola escala, 0,18, para todos los perfiles: el sesgo va hacia el
lado conservador (más congestión que la real) y evita calibrar por perfil con una sola
captura de cada uno.

## 6. Configuración adoptada

* Red: depurada (pasos 1, 1b y 2).
* Demanda: escala **0,18** con speedFactor **0,7**, sin reruteo dinámico. El speedFactor va en
  las rutas (vType `auto`, `build_demand_area.py --speed-factor 0.7`), así que el arnés no cambia.
  Es el mejor compromiso: sesgo de velocidad ≈ 0, índice 0,69 vs 0,71 y un nivel de atasco
  que sigue siendo exigente (11 %) sin la parálisis que tapaba las diferencias entre
  controladores. 0,12 calza mejor el índice, pero deja la demanda a la mitad del censo.
* Validada en punta tarde (18-nov) y valle (19-nov). Punta mañana no se capturó: usa los
  resultados de punta tarde (sección 9). Queda como trabajo futuro repetir punta tarde otro día
  para ver la variación entre días.

## 7. Qué queda obsoleto

Todo lo que corrió sobre la red original: planes de Webster (`webster_plan_*.json`), modelos
IPPO y la tabla de la tanda del 18-nov. Hay que regenerar demanda (train y eval), Webster,
líneas base y volver a entrenar sobre la configuración final.

Punta tarde ya se rehízo con la configuración propuesta (`scripts/tanda_v2_pt.ps1`, lanzado
el 18-nov a las 22:43): demanda 0,18 + speedFactor 0,7 (3 réplicas de entrenamiento y 10 de
evaluación), Webster y las cuatro líneas base con 10 réplicas. Registro en `logs/tanda_v2/`.
La demanda anterior quedó en `demand/_red_original/` (ignorada por git). Valle se lanzó el
19-nov a las ~15:15 con la misma cadena (`scripts/tanda_v2_valle.ps1`); punta mañana espera
su captura y su plan de Webster sigue obsoleto.

### Líneas base de punta tarde con la configuración nueva (19-nov, 10 réplicas)

Media ± IC95 (t de Student). Demanda v2: ~35.000 vehículos por réplica; tanda del 18-nov:
~45.000 y n = 3. `delay_all` incluye a los que no alcanzaron a terminar. Archivo:
`results/las_condes_providencia_eod_punta_tarde_baselines.json`.

| Controlador | delay_all (s) | timeLoss (s) | Cola media (veh) | Terminados | En red al final |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 655 ± 22 | 288 ± 10 | 3.282 ± 97 | 18.039 ± 561 | 15.645 ± 435 |
| **Webster** | **564 ± 18** | 221 ± 10 | 2.631 ± 116 | **19.421 ± 424** | **14.403 ± 339** |
| Voraz | 597 ± 25 | **206 ± 10** | **2.587 ± 119** | 18.533 ± 482 | 15.217 ± 455 |
| Max-Pressure | 620 ± 18 | 209 ± 10 | 2.740 ± 97 | 18.050 ± 432 | 15.682 ± 386 |
| *Tanda 18-nov (red original, n = 3)* | | | | | |
| Tiempo fijo | 962 ± 44 | 254 ± 26 | 5.525 ± 356 | 18.089 ± 1.509 | 25.059 ± 1.419 |
| Webster | 894 ± 24 | 229 ± 42 | 4.926 ± 133 | 19.529 ± 878 | 23.972 ± 520 |
| Voraz | 845 ± 68 | 196 ± 34 | 4.444 ± 420 | 20.689 ± 1.688 | 23.038 ± 1.344 |
| Max-Pressure | 867 ± 56 | 211 ± 21 | 4.537 ± 224 | 20.003 ± 1.661 | 23.775 ± 1.150 |

Lectura:

* Con 10 réplicas los intervalos se angostaron a ±18–25 s y ahora **las diferencias son
  claras**: todos los controladores le ganan al tiempo fijo (−35 a −91 s en delay_all,
  −67 a −82 s en timeLoss), sin traslape de intervalos. Con n = 3 y la red trabada no se
  distinguían.
* Webster recalibrado es la mejor línea base en demora total y en vehículos que terminan.
  Los adaptativos (voraz, Max-Pressure) bajan más el timeLoss de quienes terminan, pero
  dejan más vehículos sin terminar. Esa es la vara que tiene que superar IPPO.
* La red sigue cargada (~15.000 vehículos dentro al cumplirse la hora, con ~35.000
  insertados), pero ya no paralizada: la cola media bajó de ~5.000 a ~2.600–3.300.
* Max-Pressure no se reajustó para la red nueva (pendiente del status check).

### Líneas base de valle con la configuración nueva (19-nov, 10 réplicas)

Demanda v2 de valle: ~20.000 vehículos por réplica. La cadena completa (demanda, Webster y
líneas base en paralelo) tardó 42 min. Archivo:
`results/las_condes_providencia_eod_valle_baselines.json`.

| Controlador | delay_all (s) | timeLoss (s) | Cola media (veh) | Terminados | En red al final |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 332 ± 12 | 258 ± 3 | 1.035 ± 29 | 14.554 ± 157 | 5.338 ± 121 |
| **Webster** | **201 ± 12** | 155 ± 3 | 513 ± 26 | **15.795 ± 202** | **4.162 ± 183** |
| Voraz | 258 ± 17 | 141 ± 3 | 557 ± 40 | 14.967 ± 229 | 4.952 ± 193 |
| Max-Pressure | 227 ± 12 | **128 ± 2** | **486 ± 30** | 15.269 ± 166 | 4.669 ± 172 |
| *Tanda 18-nov (red original, n = 3)* | | | | | |
| Tiempo fijo | 571 ± 69 | 268 ± 21 | 2.152 ± 442 | 16.590 ± 933 | 10.446 ± 1.167 |
| Webster | 389 ± 33 | 196 ± 23 | 1.247 ± 95 | 19.418 ± 838 | 7.981 ± 590 |
| Voraz | 413 ± 87 | 180 ± 8 | 1.279 ± 206 | 18.856 ± 1.204 | 8.485 ± 1.212 |
| Max-Pressure | 377 ± 96 | 178 ± 28 | 1.140 ± 177 | 19.344 ± 1.075 | 8.127 ± 1.563 |

Mismo patrón que en punta tarde: todos superan al tiempo fijo con intervalos separados
(delay_all −74 a −131 s), Webster es el mejor en demora total y en vehículos que terminan, y
Max-Pressure es el mejor en timeLoss y cola. Con la red original y n = 3, Webster, voraz y
Max-Pressure no se distinguían entre sí.

### Resultados finales de la tanda v2, todos en la red actual (24-nov)

Todo lo que sigue corrió en la misma red (con la corrección de verdes inseguros) y con las mismas
réplicas de demanda. Media ± IC95; p = Wilcoxon pareado por réplica; demora total =
`delay_all` × vehículos considerados. Las secciones fechadas el 23-nov más abajo quedan como
registro (mezclaban dos versiones de la red).

**Valle (10 réplicas)**

| Controlador | delay_all (s) | vs Webster | p | timeLoss (s) | Cola media | Terminados |
|---|---:|---:|---:|---:|---:|---:|
| Tiempo fijo | 335 ± 15 | +64,3 % | 0,002 | 259 ± 4 | 1.028 ± 28 | 14.521 |
| **Webster** | **204 ± 13** | — | — | 157 ± 4 | 519 ± 28 | **15.771** |
| Voraz | 254 ± 11 | +24,5 % | 0,002 | 141 ± 3 | 545 ± 33 | 15.015 |
| Max-Pressure ajustado | 223 ± 12 | +9,5 % | 0,014 | **128 ± 2** | 473 ± 43 | 15.314 |
| IPPO s0 | 241 ± 13 | +18,4 % | 0,002 | 150 ± 3 | 373 ± 29 | 15.223 |
| IPPO s1 | 268 ± 19 | +31,7 % | 0,002 | 147 ± 4 | 436 ± 49 | 14.726 |
| IPPO s2 | 249 ± 14 | +22,0 % | 0,002 | 139 ± 3 | **359 ± 31** | 15.030 |

**Punta tarde (10 réplicas)**

| Controlador | delay_all (s) | vs Webster | p | timeLoss (s) | Cola media | Terminados |
|---|---:|---:|---:|---:|---:|---:|
| Tiempo fijo | 631 ± 17 | +14,7 % | 0,002 | 292 ± 9 | 3.168 ± 93 | 18.486 |
| **Webster** | **550 ± 17** | — | — | 225 ± 10 | 2.573 ± 82 | **19.765** |
| Voraz | 598 ± 21 | +8,8 % | 0,006 | 205 ± 10 | 2.547 ± 116 | 18.450 |
| Max-Pressure ajustado | 599 ± 19 | +8,9 % | 0,004 | 209 ± 11 | 2.627 ± 103 | 18.453 |
| IPPO s0 | 572 ± 25 | +3,9 % | 0,193 | 190 ± 8 | 2.036 ± 123 | 18.960 |
| IPPO s1 | 574 ± 16 | +4,3 % | 0,006 | **187 ± 7** | 2.012 ± 53 | 18.945 |
| IPPO s2 | 553 ± 18 | +0,5 % | 0,846 | 189 ± 7 | **1.902 ± 100** | 19.414 |

**H1 no se cumple:** el mejor IPPO (s2) empata con Webster en punta tarde (+0,5 %, p 0,85) y en
valle todos los IPPO quedan 18–32 % por encima. IPPO gana en cola (−26 % en punta tarde, −31 % en
valle con s2) y en timeLoss (−16 % en punta tarde), pero termina menos viajes que Webster.

**H3: IPPO vs MAPPO controlando solo los 206 semáforos de Providencia** (el resto, tiempo fijo;
3 semillas × 10 réplicas, comparación pareada por semilla y réplica, n = 30):

| Perfil | IPPO | MAPPO | MAPPO vs IPPO | p | IPPO vs tiempo fijo | MAPPO vs tiempo fijo |
|---|---:|---:|---:|---:|---:|---:|
| Valle | 299 ± 7 | 325 ± 11 | +8,6 % | < 0,001 | −10,8 % (p 0,002) | −3,1 % (p 0,16) |
| Punta tarde | 615 ± 7 | 616 ± 11 | +0,3 % | 0,79 | −2,6 % (p 0,02) | −2,3 % (p 0,19) |

Por semilla, MAPPO vs IPPO: valle +9,0 % (p 0,006), −0,2 % (p 1,0) y +17,4 % (p 0,002); punta
tarde +4,3 % (p 0,002), −1,8 % y −1,7 % (p 0,38). **H3 no se cumple:** el crítico centralizado no
mejora a IPPO; en valle lo empeora y aumenta la variación entre semillas. Controlar solo Providencia
deja a los dos lejos de Webster en toda el área (+12 % en punta tarde, +47–59 % en valle), lo que
es esperable: Webster ajusta los 594 semáforos y aquí los agentes controlan 206.

**Robustez: cierre de la pista central de autos de Av. Providencia** (sentido poniente, 9 tramos,
629 m, desde los 900 s; 5 réplicas frente a la misma base en la red actual):

| Controlador | delay_all base | Con cierre | Δ | p | En la red al final |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 620 ± 13 | 652 ± 19 | +5,2 % | 0,06 | 15.496 |
| Webster | 543 ± 19 | 573 ± 48 | +5,6 % | 0,06 | 14.417 |
| Voraz | 592 ± 47 | 603 ± 43 | **+1,9 %** | 0,63 | 15.306 |
| Max-Pressure ajustado | 611 ± 34 | 641 ± 29 | +4,9 % | 0,19 | 16.150 |
| IPPO s0 | 558 ± 49 | 585 ± 38 | +4,7 % | 0,06 | 14.940 |
| IPPO s1 | 570 ± 12 | 587 ± 26 | +2,9 % | 0,31 | 15.012 |
| **IPPO s2** | 541 ± 32 | **570 ± 27** | +5,3 % | 0,06 | 14.616 |

Con el cierre, IPPO s2 (570 s) y Webster (573 s) siguen empatados. El voraz es el que menos se
degrada (+1,9 %), porque reacciona a las colas que forma el cierre; los demás pierden entre 3 y 6 %.
Ninguna perturbación cambia el orden de los controladores (el alza del 30 % está más abajo).

### IPPO v2 frente a las líneas base (23-nov, 10 réplicas)

Media ± IC95; p = Wilcoxon pareado por réplica contra Webster en `delay_all` (con n = 10 el mínimo
posible es 0,002). Modelos: conjunto mixto valle + punta tarde, 3M muestras, semillas 0, 1 y 2.

**Valle**

| Controlador | delay_all (s) | Δ vs Webster | p | timeLoss (s) | Cola media |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 332 ± 12 | +64,9 % | 0,002 | 258 ± 3 | 1.035 ± 29 |
| **Webster** | **201 ± 12** | — | — | 155 ± 3 | 513 ± 26 |
| Voraz | 258 ± 17 | +28,4 % | 0,002 | 141 ± 3 | 557 ± 40 |
| Max-Pressure (por defecto) | 227 ± 12 | +12,7 % | 0,002 | **128 ± 2** | 486 ± 30 |
| IPPO s0 | 243 ± 13 | +20,6 % | 0,002 | 149 ± 4 | 377 ± 36 |
| IPPO s1 | 268 ± 19 | +33,4 % | 0,002 | 147 ± 4 | 436 ± 49 |
| IPPO s2 | 249 ± 14 | +23,6 % | 0,002 | 139 ± 3 | **359 ± 31** |

**Punta tarde**

| Controlador | delay_all (s) | Δ vs Webster | p | timeLoss (s) | Cola media |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 655 ± 22 | +16,1 % | 0,002 | 288 ± 10 | 3.282 ± 97 |
| Webster | 564 ± 18 | — | — | 221 ± 10 | 2.631 ± 116 |
| Voraz | 597 ± 25 | +5,8 % | 0,065 | 206 ± 10 | 2.587 ± 119 |
| Max-Pressure (por defecto) | 620 ± 18 | +9,9 % | 0,002 | 209 ± 10 | 2.740 ± 97 |
| IPPO s0 | 572 ± 25 | +1,3 % | 0,625 | 190 ± 8 | 2.036 ± 123 |
| IPPO s1 | 574 ± 16 | +1,7 % | 0,193 | **187 ± 7** | 2.012 ± 53 |
| **IPPO s2** | **553 ± 18** | **−2,0 %** | 0,846 | 189 ± 7 | **1.902 ± 100** |

**Punta mañana** (líneas base; IPPO no se entrenó con este perfil). *Corrida exploratoria, fuera
de las conclusiones: la demanda de la mañana no se pudo validar y la franja usa los resultados
de punta tarde (sección 9).*

| Controlador | delay_all (s) | Δ vs Webster | p | timeLoss (s) | En red al final |
|---|---:|---:|---:|---:|---:|
| Tiempo fijo | 902 ± 23 | +12,0 % | 0,002 | 342 ± 12 | 25.286 ± 518 |
| Webster | 806 ± 19 | — | — | 288 ± 10 | 23.684 ± 496 |
| **Voraz** | **788 ± 14** | −2,2 % | 0,049 | 273 ± 7 | 24.008 ± 366 |
| Max-Pressure (por defecto) | 847 ± 15 | +5,2 % | 0,027 | **248 ± 10** | 25.185 ± 251 |

Lectura:

* **H1 (IPPO ≥ 10 % mejor que la mejor línea base, p < 0,05): no se cumple.** En punta tarde las
  tres semillas empatan con Webster en demora total (−2,0 % a +1,7 %, p de 0,19 a 0,85); en valle
  Webster es claramente mejor (IPPO entre +21 y +33 %).
* **IPPO sí gana en cola y en demora de los que terminan:** en punta tarde, la cola media baja un
  23–28 % respecto de Webster y el timeLoss un 14–15 %; en valle tiene la menor cola de todos
  (359–436 contra 513). Despacha mejor lo que ya está en la red, pero deja entrar o terminar a
  menos vehículos que Webster.
* Ahora las tres semillas se comportan parecido (en la tanda del 18-nov una semilla salía mal):
  con la red y la demanda validadas el entrenamiento es estable.
* Punta mañana sigue sobresaturada incluso con la escala 0,18 (~24.000 vehículos en la red al
  final de la hora). No tiene captura TomTom todavía.
* Max-Pressure aparece aquí con sus valores por defecto; el ajuste (en curso) mostró en valle
  una configuración bastante mejor (`vehiculos`, penalización 0: 192 s en las réplicas de ajuste).

### Max-Pressure ajustado (24-nov, 10 réplicas)

Ajuste con `ajustar_baselines.py --solo maxpressure` sobre réplicas de entrenamiento (2 por
configuración, 12 configuraciones). Mejor configuración: valle `vehiculos` sin penalización de
cambio; punta tarde `cola` con penalización 2.

| Perfil | Webster | Max-Pressure por defecto | Max-Pressure ajustado | vs defecto | vs Webster |
|---|---:|---:|---:|---:|---:|
| Valle | 201 ± 12 | 227 ± 12 | 223 ± 12 | −1,6 % (p 0,77) | +11,0 % (p 0,006) |
| Punta tarde | 564 ± 18 | 620 ± 18 | 599 ± 19 | −3,3 % (p 0,23) | +6,2 % (p 0,006) |

El ajuste mejora poco y no cambia el orden: Webster sigue como la mejor línea base.

### Robustez (24-nov, punta tarde, 5 réplicas pareadas)

**Alza súbita del 30 % desde los 1.800 s** (+5.300 vehículos por réplica). `delay_all` casi no
se mueve (+1 % a +3 %) porque los vehículos extra entran tarde y alcanzan a acumular poca demora;
la medida que importa es la **demora total** (`delay_all` × vehículos considerados):

| Controlador | Demora total base (veh·h) | Con alza | Δ | En la red al final (con alza) |
|---|---:|---:|---:|---:|
| Tiempo fijo | 6.051 ± 93 | 7.084 ± 63 | +17,1 % | 19.082 ± 205 |
| **Webster** | 5.293 ± 165 | 6.249 ± 182 | +18,1 % | **17.714 ± 403** |
| Voraz | 5.773 ± 484 | 6.807 ± 435 | +17,9 % | 19.261 ± 676 |
| Max-Pressure ajustado | 5.960 ± 362 | 6.928 ± 342 | +16,3 % | 19.305 ± 571 |
| IPPO s0 | 5.444 ± 432 | 6.359 ± 439 | +16,8 % | 18.274 ± 931 |
| IPPO s1 | 5.564 ± 144 | 6.536 ± 63 | +17,5 % | 18.648 ± 203 |
| **IPPO s2** | 5.276 ± 321 | **6.232 ± 370** | +18,1 % | 18.011 ± 581 |

Todos absorben el alza de forma parecida (+16 a +18 %), sin reajustarse: el orden se mantiene y
IPPO s2 y Webster siguen empatados. Los modelos IPPO, entrenados sin alzas, no se degradan más que
los controladores clásicos.

**Cierre de pista: hubo que repetirlo.** La primera corrida cerró la pista 0 de Av. Providencia,
que en la red es Solo Bus (la demanda no tiene buses): no cambió nada, y Max-Pressure e IPPO dieron
resultados idénticos a los de la red sin cierre. Al cerrar la pista 1 (la primera de autos), SUMO
aborta porque esa pista lleva los virajes a la derecha y quedan rutas sin conexión. Se cierra la
pista central de autos (índice 2) y se repite después de MAPPO. La corrida inválida quedó en
`results/robustez_cierre_bus/` y sirve de **base de 5 réplicas en la red actual**
(`*_eod_punta_tarde_base5_baselines.json`), que es contra la que se comparan las perturbaciones.

**Efecto de la corrección de verdes inseguros.** Esa base deja ver algo que no esperaba: en las
réplicas 0-4 de punta tarde, corregir 2 enlaces de 2 semáforos movió la demora de fijo −2,6 %,
Webster −5,2 % y voraz +2,3 %. La red saturada amplifica cambios pequeños. Por eso se repiten, en
la red actual, fijo, Webster y voraz en valle y punta tarde, e IPPO s0 en valle
(`scripts/rehacer_base_red_corregida.py`, al final de la cadena), para que todas las comparaciones
sean sobre la misma red.

### Corrección de verdes inseguros (23-nov)

Al cargar la red, SUMO avisaba «Unsafe green phase 2 … Lane … is targeted by 2 'G'-links» en
2 semáforos (`cluster_10107215855_…_#11more` y `cluster_10930785153_240452429_647257544`).
Venía del paso 2 de la depuración: el viraje protegido pone en `G` todos los virajes que eran
permisivos, y en esos dos cruces dos de ellos desembocan en la misma pista. `fix_tls.py`
(`sin_verdes_dobles`) ahora deja `G` solo al enlace de mayor prioridad (pasante, derecha,
izquierda) y pasa los demás a `g` (ceden el paso). Se volvió a correr `depurar_red_area.py`:
0 avisos, mismos 594 semáforos y mismos arcos, y solo cambian esos 2 programas, un enlace
cada uno. Las fases no cambian, así que los planes de Webster (verdes por índice de fase) y
los modelos IPPO siguen siendo válidos. Las líneas base del 19-nov corrieron con la versión
anterior; el efecto esperado es despreciable (2 enlaces de 594 semáforos).

### Tanda v2, resto (lanzada el 23-nov ~16:40, encadenada en el PC)

| Etapa | Script | Qué hace |
|---|---|---|
| 1 | `tanda_v2_resto.ps1` A | Evaluación IPPO que faltó: s0 en punta tarde, s1 y s2 en valle y punta tarde (10 réplicas, a `results/ippo_v2/`); demanda v2 y Webster de punta mañana |
| 1 | `tanda_v2_resto.ps1` B, C | Junta IPPO en los JSON de líneas base; líneas base de punta mañana (10 réplicas); ajuste de Max-Pressure en valle y punta tarde (`ajustar_baselines.py --solo maxpressure`, réplicas de entrenamiento) |
| 2 | `maxpressure_ajustado.ps1` | `elegir_maxpressure.py` deja la mejor configuración en `maxpressure_<perfil>.json` (que ahora lee `run_baselines.py`) y vuelve a correr Max-Pressure con 10 réplicas; las filas anteriores quedan como `maxpressure_defecto` |
| 3 | `robustez.py` + `robustez.ps1` | OE6 en punta tarde, 5 réplicas pareadas: cierre de la pista derecha de Av. Providencia (sentido poniente) entre Los Leones y Pedro de Valdivia (9 tramos, 629 m) desde los 900 s, y alza súbita del 30 % de la demanda desde los 1.800 s (+5.300 vehículos por réplica). Las 4 líneas base y los 3 modelos IPPO, sin reajustarlos |
| 4 | `tanda_mappo_prov.py` | H3 (opción A): IPPO y MAPPO controlando solo los 206 semáforos de Providencia (`tls_providencia.json`), 3 semillas cada uno, 3M pasos, evaluados en valle y punta tarde con 10 réplicas |

Cambios de código que lo permiten:
* `TSC_SUMO_EXTRA`: opciones extra de SUMO para todas las corridas de un proceso (la leen
  `sumo_env.py` y `eval_rl.py`). Así se carga el cierre (`-a robustez_cierre.add.xml`, un
  `rerouter` con `closingLaneReroute`) sin tocar la red, los semáforos ni los modelos.
* MAPPO (`src/tsc/mappo.py`, doc `decisiones/15-especificacion-dec-pomdp.md`): observación
  `fase_global` (22 columnas locales + 11 globales) y una política con actor enmascarado y crítico
  centralizado; `train_rl.py --algo mappo --control providencia`. `eval_rl.py` toma el alcance
  (`--control`) de los metadatos del modelo. Pruebas: `tests/test_mappo.py` (el actor no cambia
  si cambia el bloque global; el crítico sí). Hay una prueba de humo de 105 mil muestras que
  entrena, guarda, carga y evalúa.
* `exportar_tiempos_app.py`: una carpeta de corridas por escenario y una fuente por escenario,
  para exportar la tabla del área sin pisar la del eje.

### Optimización del cómputo y uso de la GPU (23-nov)

PC: Intel i3-12100F (4 núcleos, 8 hilos), 32 GB, GeForce GTX 1650 de 4 GB.

**GPU: no conviene.** `scripts/medir_actualizacion_ppo.py` cronometra una actualización de PPO
(lote de 256 × agentes, minilotes de 256, 10 épocas, MLP 64-64), en un entorno virtual
`tsc-thesis/.venv` con torch 2.8 + CUDA 12.6 (el del sistema es solo CPU y no se tocó):

| Agentes | Algoritmo | CPU (1 hilo) | GPU GTX 1650 |
|---:|---|---:|---:|
| 206 | IPPO | 8,0 s | 13,6 s |
| 206 | MAPPO | 8,2 s | 14,4 s |
| 487 | IPPO | 19,4 s | 36,3 s |
| 487 | MAPPO | 20,9 s | 36,5 s |

Con minilotes de 256 y una red de ~12.000 parámetros (actor y crítico), copiar cada minilote a la tarjeta cuesta
más que el cálculo. Además, la actualización es menos del 10 % de una iteración (~380 s con
487 semáforos): el resto es la simulación, que SUMO corre en CPU. Para que la GPU ayudara habría
que subir el minilote a miles de muestras, lo que cambia los hiperparámetros con los que se
entrenaron los modelos v2. Se descarta.

**Lo que sí rendía: el envoltorio de PettingZoo.** Un perfil de la evaluación (487 semáforos,
900 s) mostró 132 de 224 s en accesos `__getattr__` de la cadena AEC → paralela de sumo-rl
(cada paso recalcula diccionarios de todos los agentes por cada agente: costo cuadrático) y
solo 35 s en SUMO. Cambios:

* `SubsetSumoParallelEnv` (`rl_env.py`): entorno paralelo nativo con la misma semántica.
  `scripts/verificar_entorno_paralelo.py` da **18 de 18 métricas idénticas**, y una iteración de
  entrenamiento deja **los mismos parámetros** (diferencia máxima 0,0). `TSC_ENV_AEC=1` vuelve
  a la cadena original.
* La evaluación ya no calcula la recompensa (`reward="nula"`), que la política no usa.
* Resultado en la evaluación: 128 s → 57 s de reloj para los mismos 900 s (×2,2). En el
  entrenamiento con 206 semáforos la ganancia es menor (~10 %): el costo cuadrático crece con
  el número de agentes.
* Las líneas base clásicas ya pasan el 76 % en SUMO (perfil de Max-Pressure): no hay mucho
  más que ganar sin tocar el simulador.

Las etapas de la cadena que todavía no arrancan (robustez, MAPPO) usan el entorno nuevo; las
evaluaciones de la etapa A ya iban por la mitad y siguieron con el anterior, que da los mismos
resultados.

## 8. Cruces UOCT vehiculares sin nodo en la red (21)

Se documentan y no se corrigen: o no existen como calle en la red (OSM sin el acceso) o el
semáforo ya está modelado a pocos metros. Distancia = al nodo más cercano / al semáforo más
cercano de la red.

| Grupo | Cruces UOCT | Por qué no hay nodo |
|---|---|---|
| Accesos a recintos (7) | J001391 Vitacura / acceso hospital (85 m) · J001911 Salvador / Hospital Salvador (52 m) · J057241 Las Condes / Hospital FACh (107 m) · J066221 Fleming / Clínica Cordillera (93 m) · J055191 Las Condes / Colegio Dunalastair (50 m; semáforo a 50 m) · J160351 Tomás Moro 272 / Colegio A. Edwards (116 m) · J103232 Isidora Goyenechea / Edificio Las Industrias (61 m; semáforo a 61 m) | Semáforo a mitad de cuadra para entrar a un recinto; el acceso es `service` y se quitó de la red. Efecto: falta un punto de detención en la avenida |
| Puentes y caleteras de Costanera (3) | J001832 Santa María / Puente Rakamalac · J002332 Santa María / Puente Nueva Tajamar · J003141 Tajamar Oriente / Costanera Andrés Bello | Geometría con desniveles; la red los resuelve como ramales sin un cruce semaforizado en ese punto |
| Coordenada corrida respecto del semáforo modelado (4) | J004241 Tobalaba / Carmen Sylva (79 m) · J998113 Luis Thayer Ojeda / Paseo Errázuriz (54 m) · J998146 San Antonio / Charles Hamilton (53 m) · J005193 Regimiento Cazadores / Bilbao Sur (56 m) | Hay un semáforo de la red a 50–80 m: probablemente el mismo cruce con la coordenada del PDF desplazada |
| Mitad de cuadra o calle local fuera de la red (7) | J001611 Suecia / Coronel-Las Bellotas · J005191 Pocuro altura 1920 · J005871 Suecia / Bustos · J061561 Camino El Alba / El Algarrobo · J057311 Las Condes / Angostura Inglesa (152 m) · J151961 F. Bulnes Correa / San Francisco de Asís · J998145 Los Militares / Estocolmo | Semáforo a mitad de cuadra o en una calle local que en OSM no forma ese cruce (o es `service` y se quitó) |

Son el 3,7 % de los 565 cruces vehiculares UOCT del área. El efecto en la simulación es
que en esas cuadras falta un punto de detención; en los 4 de coordenada corrida el cruce sí
tiene semáforo en la red, a 50–80 m del punto del PDF.

## 9. Punta mañana: se usan los resultados de la punta tarde (decisión del 24-nov)

No hubo captura TomTom de punta mañana antes de la entrega. La API de flujo que usa el
proyecto (`flowSegmentData`) solo da el tráfico del momento; el histórico de TomTom (Traffic
Stats, portal MOVE) pide otra clave, trabaja con consultas asíncronas y entrega tramos
propios que habría que volver a emparejar con la red, así que quedó fuera de plazo.

La única referencia disponible para la mañana es el **TomTom Traffic Index 2025 de
Santiago** (área metropolitana completa, https://www.tomtom.com/traffic-index/santiago-traffic/):

| Santiago 2025 | Punta mañana | Punta tarde |
|---|---:|---:|
| Tiempo para 10 km | 30 min 9 s | 34 min 53 s |
| Congestión media | 91,5 % | 110,6 % |
| Velocidad media | 19,9 km/h | 17,2 km/h |

En la ciudad real la mañana es **más liviana** que la tarde (≈ 16 % más rápida). En la
simulación pasa lo contrario: con la demanda EOD de 07:00–09:00 a escala 0,18, Webster da
806 s de demora contra 550 s en punta tarde y quedan ~24.000 vehículos en la red al final de
la hora. La demanda de la mañana no es creíble y no se puede validar.

**Decisión:** la punta mañana usa los resultados de la punta tarde, el perfil validado.

* **Tesis.** Las conclusiones de H1, H3 y robustez se sacan de valle y punta tarde. La tabla
  de líneas base de punta mañana (sección 7) queda como corrida exploratoria, fuera de las
  conclusiones.
* **App.** En la tabla de tiempos del área (`backend/datos/tiempos_area.json`) la franja
  `punta_manana` repite las velocidades de `punta_tarde` (`exportar_tiempos_app.py
  --manana-como-tarde`); la franja lleva una `nota` que lo dice.
* **Limitación.** Se reutiliza el *nivel* de congestión, no la *dirección*: en la mañana el
  flujo entra a Providencia y Las Condes y en la tarde sale. Una ruta hacia el oriente en la
  mañana se estima con las velocidades de la tarde, cuando ese sentido es el cargado; el
  error va hacia el lado conservador (más demora que la real) en el sentido de salida y al
  revés en el de entrada.

## 10. Cobertura de Las Condes y Providencia (24-nov)

Chequeo por comuna con `scripts/verificar_cobertura_comunas.py` (→ `results/cobertura_comunas.json`;
cada elemento se asigna a la comuna donde cae su punto medio, con los polígonos de `comunas.geojson`):

| Capa | Las Condes | Providencia |
|---|---|---|
| Calles para autos en la red | 769 km | 257 km |
| Grilla de 200 m con una calle a < 100 m | 70,5 % en la zona urbana (38,9 % de todo el polígono) | 95,8 % |
| Cruces vehiculares UOCT con semáforo en la red | 301 / 311 (97 %) | 222 / 233 (95 %) |
| Semáforos de la red | 278 | 224 |
| … con plan Webster (valle, punta tarde) | 278 | 224 |
| … controlados por los agentes | 260 (94 %) | 202 (90 %) |
| Viajes que salen / llegan (punta tarde) | 11.566 / 10.874 | 11.375 / 8.256 |
| Viajes que salen / llegan (valle) | 6.895 / 6.709 | 5.881 / 5.915 |
| Tabla de la app: red principal con velocidad (punta tarde) | 271 / 300 km (90 %) | 113 / 122 km (92 %) |
| Tabla de la app: calles locales con velocidad | 180 / 469 km (38 %) | 94 / 135 km (69 %) |

Lectura:

* **Las dos comunas están completas en todas las capas.** La red tiene todas las calles para
  autos de OSM (salvo las vías `service`, que la depuración quitó), todos los semáforos tienen
  plan y demanda que pasa por ellos, y el servicio de
  simulación y la tabla de tiempos de la app cubren el área entera.
* **Las Condes llega a la precordillera** (hasta lon −70,43), donde OSM no tiene calles para
  autos: la red termina en lon −70,49. Al poniente de ese límite la grilla queda cubierta en
  un 70,5 %; los puntos sin calle son parques, clubes de golf, cerros y quebradas
  (Parque Araucano, Cerro Apoquindo, Aguas de Ramón). En Providencia el hueco es el
  Parque Metropolitano.
* **21 cruces UOCT sin semáforo en la red** (10 en Las Condes, 11 en Providencia): son los de la
  sección 8, accesos a recintos y semáforos a mitad de cuadra.
* **40 semáforos de las comunas no los controla el agente** (18 en Las Condes, 22 en
  Providencia). Funcionan con su plan Webster: no tienen código UOCT, tienen una sola fase verde
  o más de 4 (criterio de `listar_tls_area.py`).
* **La tabla de la app** tiene velocidad en el 90–92 % de la red principal de ambas comunas.
  Las calles locales con poco tráfico (menos de 30 vehículos-muestra en tres horas simuladas)
  quedan sin dato y el backend las estima con el índice de congestión de la franja.
* **Servicio de simulación** (`simulacion/run.py`): el escenario por defecto pasa a ser el
  área (594 semáforos, demanda y plan Webster de punta tarde; `--perfil eod_valle` para valle),
  con 3 recorridos de demostración desde Av. Providencia con Manuel Montt hasta Apoquindo con
  Tomás Moro (7,2 km, 34 semáforos), Padre Hurtado con Av. Las Condes (9,9 km, por Costanera
  Norte) y Tobalaba con Bilbao (4,0 km, 18 semáforos).
* **Prueba de punta a punta (24-nov, backend + simulación locales):** ruta Manuel Montt →
  Apoquindo/Tomás Moro con 35 semáforos y cobertura 0,97 de la tabla; estimación de 13,3 min en
  valle y 22,1 min en punta mañana y punta tarde (21,3 min con el agente); `/v1/semaforos`
  devuelve los 594 semáforos y un viaje simulado entrega el próximo semáforo con su cuenta
  regresiva.

## Archivos

| Archivo | Qué es |
|---|---|
| `scripts/puntos_bloqueo.py` | Bloqueos por cruce y causa en una hora simulada |
| `scripts/depurar_red_area.py` | Depuración reproducible de la red (pasos 1, 1b, 2, 3, 4) |
| `scripts/tomtom_muestreo.py` | Captura TomTom en los 120 puntos fijos |
| `scripts/comparar_tomtom.py` | SUMO vs TomTom en los mismos arcos (métricas y figura) |
| `scripts/build_demand_area.py --carpeta --speed-factor` | Demanda a otra carpeta (calibración) y con velocidad deseada |
| `scripts/resumen_validacion.py` | Tabla agregada de las comparaciones (`results/validacion/`) |
| `scripts/verificar_cobertura_comunas.py` | Cobertura por comuna: red, semáforos, demanda y tabla de la app (sección 10) |
| `scripts/exportar_tiempos_app.py --manana-como-tarde` | Tabla de tiempos de la app; la punta mañana repite la tarde (sección 9) |
| `scenarios/las_condes_providencia/depuracion.json` | Informe de la depuración |
| `data/tomtom/puntos_las_condes_providencia.json` | Los 120 puntos de la muestra |
| `results/validacion/` | Métricas agregadas y figuras de cada comparación |
