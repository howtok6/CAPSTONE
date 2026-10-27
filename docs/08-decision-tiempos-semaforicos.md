# Decisión: ubicación y tiempos de los semáforos

Registrada el 22-oct-2026. Estado: **decidida por el autor.**

## Decisión

| Dato | Fuente | Rol |
|---|---|---|
| **Ubicación** de los semáforos | OpenStreetMap (`highway=traffic_signals`) | Dato de entrada de la red SUMO |
| **Tiempos** (ciclo, verdes, entreverdes) | Estimación con Webster + muestra medida en terreno | Planes de tiempo fijo y línea base |
| **Tiempos de viaje** por tramo y franja | Google (tiempos típicos), Waze consultado a mano, GPS de buses DTPM si llega | Calibración y validación del escenario |

No se compran programaciones a la UOCT por ahora. Queda como respaldo (ver «Alternativa descartada»).

## Por qué Waze no se usa para inferir los tiempos

1. **No entrega lo necesario.** `WazeRouteCalculator` devuelve solo tiempo y distancia de una ruta completa. Los métodos publicados para inferir ciclo y reparto de verde parten de trayectorias de vehículos individuales que cruzan la intersección (por ejemplo, transformada de Fourier sobre puntos GPS de vehículos sonda). Un tiempo de viaje agregado de varios kilómetros mezcla decenas de semáforos y no permite despejar el ciclo de cada uno.
2. **Términos de uso.** Las condiciones de Waze prohíben el acceso automatizado (robots, *scrapers*) sin permiso escrito. `scripts/fetch_waze_data.py` y `scripts/analyze_santiago_congestion.py` quedan como material exploratorio: no se amplían ni se publican sus datos. Waze sí puede consultarse a mano, de forma puntual, como referencia de tiempo de viaje.

Fuentes: [WazeRouteCalculator](https://www.github.com/kovacsbalu/WazeRouteCalculator) · [Waze Terms of Use](https://support.google.com/waze/answer/12373727) · [Estimación de ciclo con GPS de vehículos sonda (hEART 2018)](https://transp-or.epfl.ch/heart/2018/abstracts/5260.pdf).

## Método de estimación de tiempos (tres capas)

1. **Plan base estimado.** Para cada semáforo del eje: ciclo y repartos con Webster (`scripts/build_webster.py`) a partir de la demanda estimada, con entreverdes y verdes mínimos realistas.
2. **Muestra de terreno.** Ciclo, verde, amarillo y rojo medidos en 13 cruces del eje (de Matucana al término de Av. Apoquindo), en tres franjas horarias. Protocolo en `09-protocolo-terreno.md`; datos en `tsc-thesis/data/terreno/`. La muestra se usa para:
    - **anclar el ciclo por tramo y franja:** si los cruces medidos de un mismo tramo comparten ciclo (corredor coordinado), ese ciclo se impone a los cruces no medidos del tramo y Webster solo reparte los verdes;
    - **medir el error de la estimación:** diferencia entre el plan Webster y lo medido en los 13 cruces (error absoluto medio de ciclo y de verde), que se declara en la tesis;
    - **detectar cruces actuados o adaptativos:** ciclo que varía más de 4 s entre ciclos consecutivos.
3. **Calibración por tiempo de viaje.** Se ajustan ciclo, desfases y demanda hasta que el tiempo de viaje simulado por tramo y franja reproduzca el observado dentro de una tolerancia declarada.

## Plan Webster de la red del eje (27-oct-2026)

`scripts/build_webster.py` genera el plan en tres pasos:

1. **Calibración:** una hora simulada con tiempo fijo mide el flujo por fase de los 86 semáforos.
2. **Webster por semáforo:** ciclo óptimo y reparto de verdes.
3. **Coordinación del eje** (si existe `tls_eje.json`):
    - **ciclo común por avenida** (Alameda 27, Providencia 19, Apoquindo 18 semáforos): el mayor del grupo, para
      que el cruce más cargado no se sature;
    - **onda verde** en el sentido de la punta, a 40 km/h: hacia el poniente en punta mañana, hacia el oriente en
      punta tarde y sobresaturado, sin onda en valle;
    - las 22 transversales conservan su Webster aislado.

El controlador (`WebsterController`) escala los verdes para que el **ciclo real** (verdes + amarillos + rojos del
programa) sea exactamente el ciclo objetivo, y arranca cada semáforo en la posición del ciclo que le corresponde
según su desfase. Sin ese ajuste, semáforos con «el mismo ciclo» en el papel tendrían ciclos reales distintos y la
coordinación se perdería en pocos minutos. Con `--profile <perfil>` se genera `webster_plan_<perfil>.json`, que
`run_baselines.py --profile` usa automáticamente.

**Resultado con la demanda sintética actual** (`routes.rou.xml`, 2 semillas, 1 800 s, demora incluyendo no
terminados): tiempo fijo 228 y 227 s; Webster coordinado 149 y 148 s (−35 %); Webster con onda verde al oriente
147 y 148 s.

**Advertencia:** los ciclos resultantes (40 a 49 s) son cortos para avenidas de Santiago. La carga media de los cruces
del eje es baja (Y = 0,17, máx. 0,53) porque la demanda de prueba son viajes aleatorios repartidos en toda la red, y
Webster cae a su ciclo mínimo. Por la misma razón la onda verde no cambia nada: la demanda no tiene sentido dominante.
El plan definitivo se genera por perfil cuando existan los perfiles de demanda del eje, y se ancla en la medición de
terreno.

## Limitaciones que se declaran en la tesis

- Los cruces no medidos usan tiempos estimados, no la programación oficial.
- Los desfases (coordinación entre cruces) no se miden directamente; se infieren en la calibración.
- Una muestra de pocos ciclos por franja no captura toda la variación de un sistema adaptativo.

## Alternativa descartada (por ahora)

Comprar las programaciones oficiales a la UOCT (trámite «Solicitar información de tránsito», Decreto Exento N° 41). Tarifa publicada: 0,1389 UF por intersección y período; un piloto de 10 cruces × 3 períodos cuesta ~4,2 UF (~$171.500 con la UF de octubre de 2026). Se reconsidera si la calibración no alcanza la tolerancia. Fuente: [ChileAtiende](https://www.chileatiende.gob.cl/fichas/23628-solicitar-informacion-de-transito).
