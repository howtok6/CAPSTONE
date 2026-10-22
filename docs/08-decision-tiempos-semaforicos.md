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
2. **Muestra de terreno.** Ciclo, verde, amarillo y rojo medidos en 10 cruces del eje, en tres franjas horarias. Protocolo en `09-protocolo-terreno.md`; datos en `tsc-thesis/data/terreno/`. La muestra se usa para:
    - **anclar el ciclo por tramo y franja:** si los cruces medidos de un mismo tramo comparten ciclo (corredor coordinado), ese ciclo se impone a los cruces no medidos del tramo y Webster solo reparte los verdes;
    - **medir el error de la estimación:** diferencia entre el plan Webster y lo medido en los 10 cruces (error absoluto medio de ciclo y de verde), que se declara en la tesis;
    - **detectar cruces actuados o adaptativos:** ciclo que varía más de 4 s entre ciclos consecutivos.
3. **Calibración por tiempo de viaje.** Se ajustan ciclo, desfases y demanda hasta que el tiempo de viaje simulado por tramo y franja reproduzca el observado dentro de una tolerancia declarada.

## Limitaciones que se declaran en la tesis

- Los cruces no medidos usan tiempos estimados, no la programación oficial.
- Los desfases (coordinación entre cruces) no se miden directamente; se infieren en la calibración.
- Una muestra de pocos ciclos por franja no captura toda la variación de un sistema adaptativo.

## Alternativa descartada (por ahora)

Comprar las programaciones oficiales a la UOCT (trámite «Solicitar información de tránsito», Decreto Exento N° 41). Tarifa publicada: 0,1389 UF por intersección y período; un piloto de 10 cruces × 3 períodos cuesta ~4,2 UF (~$171.500 con la UF de octubre de 2026). Se reconsidera si la calibración no alcanza la tolerancia. Fuente: [ChileAtiende](https://www.chileatiende.gob.cl/fichas/23628-solicitar-informacion-de-transito).
