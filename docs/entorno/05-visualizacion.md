# Cómo ver la simulación

Estado al 24-ago-2026. Verificado funcionando.

## En vivo (GUI de SUMO)

```
sumo-gui -c scenarios/apoquindo/apoquindo.sumocfg
```

Play, y el campo *Delay (ms)* controla la velocidad (0 = máxima, 30–50 =
observable). En Windows la ventana abre nativa; en WSL2, vía WSLg.

`scenarios/apoquindo/gui-settings.xml` define el esquema propio `tesis`:
vista centrada en el corredor, fondo claro y **vehículos coloreados por
velocidad — rojo = detenido**, así la cola se ve sola. El zoom equivale
aproximadamente a `460000 / metros_visibles`: 350 ≈ el corredor completo,
750 ≈ dos o tres intersecciones con autos bien visibles.

**La GUI sola corre tiempo fijo.** Los controladores adaptativos viven en el
código Python, no en el archivo de red.

## Grabar video

```
python scripts/record_run.py --scenario scenarios/apoquindo \
    --controller maxpressure --begin 900 --seconds 300 \
    --zoom 750 --center 1200,900
# en Linux sin monitor: anteponer  xvfb-run -a -s "-screen 0 1600x900x24"
# en Windows no hace falta: hay pantalla real
```

Usa sumo-gui real (no un dibujo aparte) y el controlador decide a su intervalo
real, así que el video es la ejecución auténtica. Banderas: `--controller`
(fixed/webster/greedy/maxpressure), `--zoom`, `--center x,y`, `--begin`
(saltar el arranque con la red vacía), `--every`, `--fps`.

Red comunal en coordenadas de red: x de 342 a 2925, y de 644 a 1551.
Centro 1634,1097.

## Trampa encontrada

Sin `--quit-on-end true`, sumo-gui queda abierto al terminar la simulación y
`traci.close()` nunca retorna: el script parece colgado sin dar error. Ya está
en `record_run.py`; recordarlo al escribir cualquier otro script con GUI.

Además, `libsumo` no tiene GUI. `SumoSimulation` cambia a TraCI
automáticamente cuando `gui=True`.

## Qué mirar

- **Colas que no despejan en un verde** → intersección saturada o plan malo.
- **Bloqueo hacia atrás** (cola que alcanza la intersección anterior) →
  invalida la comparación: mide el largo de la cuadra, no el controlador.
- **Progresión** de pelotones de verde en verde → es lo que Max-Pressure no
  optimiza explícitamente y el agente aprendido podría descubrir solo.
- **Giros a la izquierda**: donde OSM se equivoca más. Autos que se detienen
  sin razón aparente suelen indicar una pista de viraje faltante.

## Videos generados (24-ago-2026)

Tres tomas de 15 s sobre la red comunal, a partir del segundo 900 de simulación:
`comunal_maxpressure_general` (red completa), y en detalle sobre la
misma intersección `comunal_maxpressure_detalle` y `comunal_fixed_detalle`
para contrastar. Se regeneran con `make video SCENARIO=scenarios/comunal`.
