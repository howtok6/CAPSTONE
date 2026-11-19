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

## 6. Configuración propuesta (provisoria hasta las capturas del 19-nov)

* Red: depurada (pasos 1, 1b y 2).
* Demanda: escala **0,18** con speedFactor **0,7**, sin reruteo dinámico. El speedFactor va en
  las rutas (vType `auto`, `build_demand_area.py --speed-factor 0.7`), así que el arnés no cambia.
  Es el mejor compromiso: sesgo de velocidad ≈ 0, índice 0,69 vs 0,71 y un nivel de atasco
  que sigue siendo exigente (11 %) sin la parálisis que tapaba las diferencias entre
  controladores. 0,12 calza mejor el índice, pero deja la demanda a la mitad del censo.
* Pendiente: capturas de punta mañana y valle (jueves 19-nov, programadas) para fijar la
  escala por perfil, y repetir punta tarde otro día para ver la variación diaria.

## 7. Qué queda obsoleto

Todo lo que corrió sobre la red original: planes de Webster (`webster_plan_*.json`), modelos
IPPO y la tabla de la tanda del 18-nov. Hay que regenerar demanda (train y eval), Webster,
líneas base y volver a entrenar sobre la configuración final.

Punta tarde ya se rehízo con la configuración propuesta (`scripts/tanda_v2_pt.ps1`, lanzado
el 18-nov a las 22:43): demanda 0,18 + speedFactor 0,7 (3 réplicas de entrenamiento y 10 de
evaluación), Webster y las cuatro líneas base con 10 réplicas. Registro en `logs/tanda_v2/`.
La demanda anterior quedó en `demand/_red_original/` (ignorada por git). Valle y punta
mañana esperan las capturas TomTom del 19-nov; sus planes de Webster siguen obsoletos.

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

## Archivos

| Archivo | Qué es |
|---|---|
| `scripts/puntos_bloqueo.py` | Bloqueos por cruce y causa en una hora simulada |
| `scripts/depurar_red_area.py` | Depuración reproducible de la red (pasos 1, 1b, 2, 3, 4) |
| `scripts/tomtom_muestreo.py` | Captura TomTom en los 120 puntos fijos |
| `scripts/comparar_tomtom.py` | SUMO vs TomTom en los mismos arcos (métricas y figura) |
| `scripts/build_demand_area.py --carpeta --speed-factor` | Demanda a otra carpeta (calibración) y con velocidad deseada |
| `scripts/resumen_validacion.py` | Tabla agregada de las comparaciones (`results/validacion/`) |
| `scenarios/las_condes_providencia/depuracion.json` | Informe de la depuración |
| `data/tomtom/puntos_las_condes_providencia.json` | Los 120 puntos de la muestra |
| `results/validacion/` | Métricas agregadas y figuras de cada comparación |
