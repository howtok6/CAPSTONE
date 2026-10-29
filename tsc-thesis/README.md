# Control adaptativo de semáforos — entorno experimental

Repositorio base de la tesis *«Control adaptativo de semáforos mediante
aprendizaje por refuerzo multi-agente»* (Ingeniería en Informática, DUOC UC).

Todo el pipeline está verificado funcionando de punta a punta: escenario →
controladores clásicos → agente aprendido → análisis estadístico.

---

## Instalación rápida

```bash
python -m venv .venv && source .venv/bin/activate    # Linux / WSL2
pip install -r requirements.txt
make grid          # genera el escenario sintético 4x4
make test          # 27 pruebas, ~35 s
```

No hace falta instalar SUMO aparte: el paquete `eclipse-sumo` de PyPI trae los
binarios (`sumo`, `netconvert`, `netgenerate`, `netedit`) y el código fija
`SUMO_HOME` automáticamente.

> **Las versiones de `requirements.txt` están fijadas a propósito.**
> `pettingzoo >= 1.25` rompe `sumo-rl` (`agent_selector` pasó de ser una clase
> invocable a un módulo). No las subas sin verificar que `make test` sigue
> pasando.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/tsc/` | Librería: controladores, arnés de simulación, métricas y entorno RL. |
| `scripts/` | Pipeline: construir y diagnosticar redes, demanda, Webster, baselines, entrenamiento, evaluación, comparación y video. |
| `scripts/exploratorio/` | Waze, *rerouting* y descarga por Overpass. Fuera del alcance de la tesis; no se usan para resultados. Se ejecutan desde esta carpeta raíz (`python scripts/exploratorio/<script>.py`). |
| `scenarios/` | Redes SUMO. `eje_comunal` es la red del MVP. |
| `data/terreno/` | Mediciones de terreno (CSV). |
| `data/waze/` | Muestra exploratoria de Waze (no citable). |
| `results/` | Salidas JSON de las corridas. |
| `tests/` | Pruebas automatizadas. |

El modelo de casos de uso está en `../docs/uml/`.

## Pipeline completo

```bash
make grid                     # 1. escenario
make webster                  # 2. calibra el plan de Webster
make baselines SEEDS=10       # 3. controladores clásicos
make train STEPS=200000       # 4. entrena PPO
make eval SEEDS=10            # 5. evalúa la política
make compare                  # 6. tabla comparativa con test estadístico
```

## Resultados verificados (grilla 4x4, demanda baja, 8 semillas)

Demora media por vehículo, sobre tiempo fijo como línea base:

| Controlador       | Demora media (s) | vs tiempo fijo |
|-------------------|-----------------:|---------------:|
| `fixed`           |            47,57 |              — |
| `greedy`          |            38,28 |        −19,5 % |
| `webster`         |            36,57 |        −23,1 % |
| `maxpressure`     |            33,05 |        −30,5 % |
| `ppo` (8k pasos)  |            31,58 |        −33,6 % |

Todas las diferencias son significativas (Wilcoxon pareado, p = 0,0078).

**Cómo leer esto.** Son números de un escenario sintético con demanda baja y
un agente entrenado apenas 8 000 pasos: sirven para demostrar que el pipeline
mide lo que dice medir, **no** como resultado de tesis. Dos observaciones que
sí anticipan lo que vas a encontrar en la red real:

* La ventaja de PPO sobre Max-Pressure es pequeña en la métrica primaria
  (−33,6 % contra −30,5 %) y grande en espera y cola (−51,6 % y −57,9 %).
  No es casualidad: la recompensa del agente *es* la variación de la espera.
  El agente optimiza lo que se le pide medir, y eso hay que declararlo al
  comparar, no descubrirlo al final.
* En redes no saturadas casi cualquier control adaptativo le gana al tiempo
  fijo. La comparación interesante ocurre cerca de la saturación; por eso el
  diseño experimental contempla un escenario sobresaturado.

## Windows nativo o WSL2

El stack completo —**incluido `libsumo`**— tiene rueda oficial para
`win_amd64`, así que todo esto corre nativo en Windows. Verificado consultando
PyPI para Python 3.12: `eclipse-sumo`, `libsumo`, `sumo-rl`,
`stable-baselines3`, `supersuit`, `torch` y `ray` tienen wheel de Windows.

Tres diferencias reales al trabajar en Windows:

1. **No hay `make`.** Los objetivos del Makefile son atajos; corre los scripts
   directamente (`python scripts/run_baselines.py --scenario …`) o instala make
   con `winget install ezwinports.make`.
2. **No hay `fork()`.** Python usa `spawn`, así que cada worker reimporta el
   módulo. Todos los scripts ya traen guarda `if __name__ == "__main__":`, que
   es lo que eso exige. Aun así, deja `--n-cpus 1` hasta que el entrenamiento
   funcione, y súbelo después.
3. **`xvfb-run` no existe ni hace falta:** tienes pantalla real, así que
   `record_run.py` y `sumo-gui` funcionan directo.

**Ray está en beta en Windows** según su documentación oficial. Solo importa
en la fase de MAPPO (mes 5). Si da problemas ahí, esa es la razón para migrar
a WSL2 — no antes.

## Ver la simulación

En tu máquina, con la GUI de SUMO:

```bash
sumo-gui -c scenarios/apoquindo/apoquindo.sumocfg
```

Pulsa **Play**. El campo *Delay (ms)* de la barra superior controla la
velocidad: `0` va lo más rápido posible, `30–50` es cómodo para observar.
`gui-settings.xml` ya deja la vista centrada en el corredor y colorea los
vehículos por velocidad — **rojo es detenido**, así que la cola se ve sola.

Eso muestra la red con su plan de tiempo fijo. Para ver un controlador
adaptativo hay que correrlo desde Python, que es lo que hace el grabador:

```bash
# graba un video (sin GUI visible, sirve en servidores)
python scripts/record_run.py --scenario scenarios/apoquindo \
    --controller maxpressure --begin 900 --seconds 300 \
    --zoom 750 --center 1200,900

# o míralo en vivo, si tienes pantalla
DISPLAY=:0 python scripts/record_run.py --scenario scenarios/apoquindo \
    --controller maxpressure --begin 0 --seconds 3600 --every 999
```

En un servidor sin monitor, antepón `xvfb-run -a -s "-screen 0 1600x900x24"`.

| Bandera | Para qué |
|---|---|
| `--zoom` | `350` ≈ el corredor completo · `750` ≈ dos o tres intersecciones |
| `--center x,y` | Centro de la vista en coordenadas de la red |
| `--begin` | Segundos a saltar: al arrancar la red está vacía |
| `--every` | Un cuadro cada N segundos simulados |

## Estructura

```
src/tsc/
  sumo_env.py          Envoltorio de SUMO: fases, colas, densidades por pista
  runner.py            Ejecuta un controlador y devuelve métricas
  metrics.py           tripinfo + muestreo por paso
  rl_env.py            Entorno PettingZoo (sumo-rl) y adaptador a SB3
  controllers/
    base.py            Verde mínimo/máximo y ámbar: restricciones duras
    fixed.py           Tiempo fijo (piso de comparación)
    webster.py         Plan óptimo de Webster (1958)
    maxpressure.py     Max-Pressure (Varaiya, 2013)
    greedy.py          Voraz por cola (control de sanidad)
scripts/
  build_grid.py        Escenario sintético
  build_santiago.py    Escenario real desde OpenStreetMap
  diagnose_net.py      Salud de la red: fases, arcos cortos, teletransportes
  record_run.py        Graba un video de la ejecución con cualquier controlador
  build_webster.py     Calibración y cálculo del plan de Webster
  run_baselines.py     Evaluación de los clásicos con N semillas
  train_rl.py          Entrenamiento PPO con parameter sharing
  eval_rl.py           Evaluación de la política con el MISMO protocolo
  compare.py           Medias, IC 95 %, mejora % y Wilcoxon pareado
tests/                 Pruebas del pipeline
```

## Principios de diseño

**Un solo arnés de medición.** Clásicos y aprendidos pasan por el mismo
parser de `tripinfo` y la misma definición de throughput. Si cada controlador
midiera a su manera, las diferencias observadas serían del arnés y no de los
algoritmos.

**Semillas pareadas.** Todos los controladores se evalúan sobre las mismas
semillas, lo que permite usar Wilcoxon pareado y gana potencia estadística.

**Restricciones de seguridad en el entorno, no en la recompensa.** Verde
mínimo, verde máximo y ámbar los impone `PhaseSwitchingController`. Un
semáforo que *aprende* a respetar el verde mínimo no es desplegable.

**El valor p nunca va solo.** `compare.py` reporta siempre media, intervalo de
confianza, mejora porcentual y tamaño del efecto junto al p.

## Escenario de Santiago

```bash
python scripts/build_santiago.py \
    --bbox -70.6250,-33.4300,-70.5950,-33.4180 \
    --out scenarios/providencia
```

El script automatiza la descarga de OSM, `netconvert` y una demanda sintética.
**No entrega un escenario calibrado.** Faltan los dos pasos que son el trabajo
real de la tesis:

1. Depurar la red en `netedit` — conectividad, carriles, movimientos, fases.
2. Calibrar la demanda contra volúmenes observados.

Antes de comparar controladores sobre esa red, verifica que simula sin
advertencias con demanda baja. Si no lo hace, las diferencias que midas serán
artefactos de la geometría importada.

## Siguientes pasos

- [ ] Seleccionar el corredor definitivo y depurarlo en `netedit`
- [ ] Conseguir volúmenes de referencia y calibrar la demanda
- [ ] Perfiles de demanda: valle, punta mañana, punta tarde, sobresaturado
- [ ] Ablation de la función de recompensa (`--reward wait|queue|pressure`)
- [ ] MAPPO con crítico centralizado (Ray RLlib) sobre el mismo entorno
- [ ] Pruebas de robustez: corte de carril, alza súbita de demanda, detector caído
