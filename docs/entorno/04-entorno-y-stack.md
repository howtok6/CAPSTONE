# Entorno experimental, stack y corredor

Estado al 24-ago-2026. Todo verificado corriendo de punta a punta.

> **Entorno vigente: Windows nativo.** Ver `02-windows-vs-wsl2.md`. Las
> instrucciones de instalación de esta ficha valen para ambas plataformas
> salvo donde se indique.

## Stack

| Capa | Elegido | Descartado |
|---|---|---|
| Simulación | `eclipse-sumo` 1.27 + `libsumo` | CityFlow, VISSIM/AIMSUN |
| Entorno RL | `sumo-rl` (Gymnasium + PettingZoo, MIT) | envoltorio propio sobre TraCI |
| Algoritmos fase 1 | Stable-Baselines3 (PPO, parameter sharing = IPPO) | DQN propio |
| Algoritmos fase 2 | Ray RLlib (MAPPO, QMIX — CTDE) | quedarse solo en SB3 |
| PettingZoo → VecEnv | SuperSuit | — |
| Análisis | pandas, SciPy (Wilcoxon), Matplotlib | R |
| Seguimiento | TensorBoard → MLflow | Weights & Biases (servicio externo) |
| Edición de red | `netedit` | editar XML a mano |

Cuello de botella real: la simulación SUMO en CPU, no la GPU. Con MLP pequeñas
conviene subir `--n-envs`/`--n-cpus` antes que tocar el modelo. La GPU rinde
recién con CNN o redes de grafos (CoLight).

## Versiones fijadas (no subir sin verificar)

`pettingzoo==1.24.3` — a partir de 1.25 rompe `sumo-rl` (`agent_selector` dejó
de ser una clase invocable). `stable-baselines3==2.9.0`, `supersuit==3.11.0`,
`gymnasium==1.3.0`, `eclipse-sumo==1.27.1`.

## Repositorio `tsc-thesis`

```
src/tsc/{sumo_env,runner,metrics,rl_env}.py
src/tsc/controllers/{base,fixed,webster,maxpressure,greedy}.py
scripts/{build_grid,build_santiago,build_webster,diagnose_net,
         run_baselines,train_rl,eval_rl,record_run,compare}.py
tests/test_pipeline.py     # 5 pruebas, ~3 s
Makefile                   # grid, apoquindo, webster, diagnose, baselines,
                           # train, eval, compare, video, gui, test
```

Principios: un solo arnés de medición (todos los controladores pasan por el
mismo parser de `tripinfo`); semillas pareadas entre controladores; verde
mínimo/máximo y ámbar como restricciones duras del entorno, no como
penalizaciones aprendidas; el valor p nunca se reporta sin intervalo de
confianza y tamaño de efecto.

---

## Red elegida a nivel comunal

Decidido con evidencia medida, no por preferencia, se evaluarán corredores a nivel comunal para todas las comunas.

| Candidato | Nivel | Extensión | Veredicto |
|---|---|---|---|
| **Red comunal de Santiago** | Comunal | Múltiples ejes | Elegido |
| Av. Providencia | Corredor | 1 324 m | Descartado |

Providencia queda fuera porque 18 señales en 1,3 km implican cuadras de 14 a
44 m entre semáforos consecutivos: la cola de una intersección alcanza a la
anterior antes de despejar, y ese acoplamiento domina el resultado por encima
de lo que haga el controlador. Además ahí conviven Providencia y Nueva
Providencia como par de sentidos únicos, lo que multiplica los errores de
importación.

Las redes a nivel comunal entregan la escala necesaria para el anteproyecto, abarcando todas las comunas para coordinar múltiples ejes.

### Cómo se reconstruye

```
make apoquindo        # descarga OSM + netconvert + demanda sintética
make diagnose SCENARIO=scenarios/apoquindo
```

Bbox de descarga: `-70.5950,-33.4200,-70.5650,-33.4080`
Recorte al corredor: `-70.59569,-33.41789,-70.56457,-33.40687`

**Overpass API no es alcanzable desde el contenedor de Cowork.** Se usa
`api.openstreetmap.org/api/0.6/map` (límite: 0,25 grados² y 50 000 nodos — un
corredor cabe, una comuna no). `build_santiago.py` intenta ambas fuentes en
orden.

### Estado de la red importada

749 arcos · 43 intersecciones semaforizadas (11 sobre el eje) · 0
teletransportes · 0 colisiones.

Pendiente de arreglar en `netedit`:

- `GS_252964499` tiene una sola fase verde: no es controlable.
- Arco `858537774#0` de 3,8 m entre dos semáforos — casi seguro dos nodos que
  OSM dejó separados y hay que fusionar. Otros dos arcos de 22,3 m a revisar.
- Contrastar la estructura de fases de las 11 intersecciones del eje contra
  Street View.

### Decisión pendiente

La red abarcará las intersecciones a nivel comunal. Recomendación:
que el agente controle las intersecciones de toda la red y las transversales menores queden en tiempo
fijo como demanda de contexto. Es lo que dice el anteproyecto, entrena más
rápido y se parece más a un despliegue real a nivel comunal.

### Herramienta: `scripts/diagnose_net.py`

Reporta, para cualquier red: semáforos con menos de dos fases verdes (no
controlables), fases verdes sin movimientos, arcos de menos de 25 m entre dos
semáforos (riesgo de bloqueo), y teletransportes/colisiones/atascos en una
simulación de prueba. Correrlo cada vez que se toque la geometría.

---

## Resultados de sanidad

**Grilla 4×4, 8 semillas, 1 h simulada.** Demora media por vehículo:
`fixed` 47,57 s · `greedy` 38,28 (−19,5 %) · `webster` 36,57 (−23,1 %) ·
`maxpressure` 33,05 (−30,5 %) · `ppo` 8k pasos 31,58 (−33,6 %). Todas
significativas (Wilcoxon pareado, p = 0,0078).

**Red comunal, 3 semillas, 1 h, demanda sintética.** `fixed` 130,94 s ·
`greedy` 95,81 (−26,8 %) · `webster` 97,09 (−25,9 %) · `maxpressure` 84,33
(−35,6 %).

**No son resultados de tesis**: la demanda es aleatoria y el agente entrenó
apenas 8 000 pasos. Sirven para demostrar que el arnés mide lo que dice medir,
ahora también sobre geometría real. Dato útil: el tiempo fijo pierde 131 s en
la red comunal contra 47 s en la grilla — la red real está bastante más cerca de la
saturación, que es donde la comparación se pone interesante.

Observación metodológica que anticipa el trabajo real: PPO supera a
Max-Pressure por poco en demora (−33,6 % vs −30,5 %) y por mucho en espera y
cola (−51,6 % y −57,9 %), porque su recompensa *es* la variación de la espera.
Al comparar hay que declarar qué optimiza cada controlador.

## Trampas encontradas (ya corregidas en el repo)

1. **Histéresis de Max-Pressure fuera de escala.** Con presiones normalizadas
   (0,1–0,5), `switch_penalty=0.5` congela el controlador en una fase y lo deja
   peor que tiempo fijo (59 s vs 46 s). Con 0,05 baja a 32 s. Si Max-Pressure no
   le gana a tiempo fijo, revisar esto antes que el algoritmo.
2. **Confundir ocupación con flujo** al calibrar Webster: promediar vehículos
   presentes mide densidad, no flujo, y subestima Y. Hay que contar vehículos
   distintos por pista, muestreando más rápido que el tiempo de recorrido de la
   pista más corta (2 s).
3. **Throughput no comparable.** `getArrivedNumber()` devuelve llegadas del
   último paso; llamarlo una vez por decisión cuenta distinto según el intervalo
   de cada controlador. Debe derivarse de `tripinfo`.
4. **Incompatibilidades de versiones** (ver arriba) y `env.seed()` inexistente
   en los VecEnv de SuperSuit: la semilla se fija con `set_random_seed()`, no en
   el constructor de PPO.
5. **Scripts con GUI que parecen colgados.** Sin `--quit-on-end true`, sumo-gui
   queda abierto al terminar y `traci.close()` nunca retorna.

## Siguientes pasos, con criterio de término

1. **Depurar Apoquindo en `netedit`.** Listo cuando `make diagnose` no reporta
   problemas estructurales.
2. **Fijar el alcance de control:** 11 semáforos del eje (recomendado) o los 43.
3. **Conseguir volúmenes reales y calibrar.** Ver `06-fuentes-de-datos.md`.
4. **Cuatro perfiles de demanda** (valle, punta AM, punta PM, sobresaturado).
   Listo cuando los cuatro simulan sin teletransportes bajo tiempo fijo.
5. **Entrenamiento en serio y ablation de recompensa** (`wait`/`queue`/`pressure`).
   Listo cuando las tres variantes tienen curvas estables y evaluación con 10
   semillas.
6. **MAPPO con crítico centralizado** vía Ray RLlib sobre el mismo entorno.
7. **Robustez:** corte de carril, alza súbita del 30 % en un acceso, detector
   caído con observación degradada.
