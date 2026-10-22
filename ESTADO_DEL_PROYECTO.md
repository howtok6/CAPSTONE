# Estado Actual del Proyecto de Tesis

**Proyecto:** Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente  
**Subtítulo:** Evaluación comparativa frente a estrategias clásicas de control en una red a nivel comunal de Santiago de Chile  
**Alcance del MVP:** eje Apoquindo → Providencia → Alameda (Las Condes, Providencia y Santiago). Ver `docs/07-decision-escenario.md`.  
**Autor:** Gabriel Ignacio Cárdenas Valdés  
**Programa:** Ingeniería en Informática, DUOC UC  
**Fecha de corte del informe:** 22 de octubre de 2026 (revisión del informe del 14 de octubre)  
**Entorno de ejecución:** Windows 11 nativo (Python 3.13 / SUMO 1.27.1 / libsumo / PyTorch 2.8.0 / PyG 2.8.0)  

> **Nota de revisión (22-oct-2026).** Esta versión corrige afirmaciones del informe del 14-oct que el código y los
> archivos de resultados no respaldaban: la demanda se describía como «calibrada» (son perfiles sintéticos), H1 y H2
> se daban por validadas (no se han contrastado sobre el corredor real), el enrutamiento GNN se presentaba como
> operativo (no está entrenado) y el escenario figuraba con 37 semáforos (tiene 36). El avance global se reestima
> de ~75 % a ~45 %. Cada corrección se verificó contra el repositorio el 22-oct.

---

## 1. Resumen Ejecutivo y Nivel de Madurez

El proyecto cierra el **mes 2 de 6** del cronograma del anteproyecto (inicio 23-ago-2026) con un avance global estimado
del **~45 %**. Va al día respecto del anteproyecto, con deuda en calibración de demanda y adelanto parcial en el
entorno de aprendizaje.

La infraestructura está sólida: **13/13 pruebas automatizadas pasan** (verificado el 22-oct), la red real del eje
**Alameda-Providencia** (520 arcos, 36 semáforos) está depurada y los tres controladores clásicos funcionan con un arnés
de medición único. La brecha principal está en el aprendizaje: **todavía no existe ninguna política entrenada sobre la
red real**; el único modelo guardado es `models/grid4x4/ppo_wait.zip` (8 000 pasos, grilla sintética, 23-ago).

### Semáforo de Estado del Proyecto
* 🟢 **Pipeline de simulación, métricas y controladores clásicos:** completado y verificado (13/13 pytest).
* 🟢 **Red vial real (`scenarios/alameda_providencia`):** depurada; `diagnose_net.py` la declara APTA (sin semáforos de fase única ni arcos críticos).
* 🟡 **Demanda:** 4 perfiles **sintéticos direccionados** generados (valle, punta mañana, punta tarde, sobresaturado). **No calibrados** contra datos observados.
* 🟡 **Infraestructura RL (PettingZoo / SB3 / IPPO):** funcional y probada en grilla 4×4; sin entrenamiento en la red real.
* ⚪ **MAPPO (Ray RLlib / CTDE) y pruebas de robustez:** no iniciados.

### Trabajo exploratorio fuera del alcance del anteproyecto
Se desarrollaron componentes que no forman parte de los objetivos y que **no deben reportarse como avance**:
1. **Telemetría Waze** (`WazeRouteCalculator`, cliente no oficial): una sola muestra, 16-sep-2026 18:47, en 12 ejes. Útil como referencia exploratoria; no es fuente citable de calibración.
2. **Desvíos dinámicos (*rerouting*)** en `runner.py`: apagados por defecto. Si se activan, cada controlador enfrenta una demanda distinta y se rompe el diseño comparativo.
3. **`GNNRouter`** (`torch_geometric`): lee densidad, colas y velocidades vía TraCI, pero **no tiene entrenamiento** (sin optimizador ni carga de pesos), por lo que opera con pesos aleatorios.

El enrutamiento dinámico queda fuera del alcance según la sección 6.2 del anteproyecto. Se propone moverlo a trabajo futuro.

---

## 2. Matriz de Cumplimiento de Objetivos Específicos

| N.º | Objetivo Específico | Producto Verificable | Estado | Avance | Detalle / Situación actual |
|:---:|:---|:---|:---:|:---:|:---|
| **OE1** | Construir y calibrar escenario microscópico de Santiago ($\ge 8$ intersecciones) en SUMO con datos públicos. | Red `.net.xml`, matriz de demanda y rutas `.rou.xml` versionadas con reporte de calibración. | 🟡 En progreso | 60 % | Red `scenarios/alameda_providencia` (36 semáforos) depurada y APTA. Perfiles de demanda generados con `randomTrips.py` y pesos heurísticos; **falta calibrar o validar contra datos observados** y emitir el reporte de calibración. |
| **OE2** | Implementar tres controladores de referencia: Tiempo Fijo, Webster y Max-Pressure. | Módulos ejecutables con pruebas unitarias sobre conmutación de fases. | 🟢 Completado | 100 % | `FixedTimeController`, `WebsterController` (plan para los 36 semáforos de Alameda-Providencia), `MaxPressureController` y `GreedyController` en `src/tsc/controllers/`, con pruebas. |
| **OE3** | Formular control como Dec-POMDP (observación, acción, recompensa por intersección). | Especificación formal documentada e implementada en PettingZoo. | 🟢 Casi completo | 85 % | Implementado en `src/tsc/rl_env.py` (sumo-rl + SuperSuit, parameter sharing, recompensas `wait`, `queue`, `pressure`, `speed`). Falta la especificación formal escrita para el informe. |
| **OE4** | Entrenar y ajustar al menos dos configuraciones de agentes MARL (independiente y CTDE). | Políticas entrenadas, curvas de aprendizaje y registro de hiperparámetros. | 🔴 Inicial | 10 % | Solo existe una prueba de IPPO en grilla 4×4 (8 000 pasos). Sin entrenamiento en red real; MAPPO no iniciado. |
| **OE5** | Evaluar comparativamente todos los controladores con réplicas independientes y test estadístico. | Protocolo experimental, tablas de resultados con IC 95 % y Wilcoxon pareado. | 🟡 En progreso | 35 % | Arnés listo con soporte `--profile`. En Alameda-Providencia solo hay una prueba de humo (perfil valle, 2 semillas, ~10 min medidos). Falta la batería: 4 perfiles × 5 controladores × 10–30 semillas × 1 h. |
| **OE6** | Analizar la robustez de la política aprendida ante perturbaciones no vistas en entrenamiento. | Batería de escenarios de perturbación y análisis de degradación. | 🔴 Inicial | 5 % | Requiere una política aprendida, que aún no existe. El perfil `sobresaturado` existe pero hoy no estresa la red (ver §6.5). |
| **OE7** | Documentar hallazgos, limitaciones y condiciones de ventaja del enfoque aprendido. | Informe final de tesis, repositorio reproducible y presentación de defensa. | 🟡 En progreso | 25 % | Anteproyecto entregado (DOCX y PDF), guías técnicas `docs/00` a `06`. Informe final no iniciado. |

*Los porcentajes son una estimación de juicio a partir de lo que existe en el repositorio, no una medición.*

---

## 3. Estado de Contraste de Hipótesis

Ninguna hipótesis está contrastada todavía. Todas se formulan sobre el corredor real; la única evidencia disponible
proviene de la grilla sintética.

* **H1:** *«Un controlador MARL reduce la demora media en $\ge 10\,\%$ respecto de tiempo fijo optimizado con Webster en hora punta ($p < 0.05$).»*  
  * **Estado: sin contrastar; señal preliminar favorable.** En la grilla 4×4 (demanda sintética baja, 8 semillas), PPO entrenado 8 000 pasos obtuvo 31,58 s frente a 36,57 s de Webster (−13,6 %). Falta repetirlo en el corredor real, en hora punta y con una política entrenada en serio.
* **H2:** *«La ventaja de MARL sobre Max-Pressure es menor que sobre tiempo fijo y se concentra cerca de la saturación.»*  
  * **Estado: sin contrastar.** En la grilla, la ventaja de PPO sobre Max-Pressure (−4,4 %) fue menor que sobre tiempo fijo (−33,6 %), lo que es coherente con la primera mitad de H2. La segunda mitad (concentración cerca de la saturación) no se ha medido: solo se probó demanda baja.
* **H3:** *«Esquemas CTDE (MAPPO) superan al aprendizaje independiente (IPPO) a costa de mayor costo computacional.»*  
  * **Estado: no evaluada.** Requiere MAPPO.

**Sobre la significancia.** El valor p = 0,0078 que aparece en la grilla es el mínimo posible de la prueba de Wilcoxon
bilateral con 8 semillas (2/256): se obtiene con cualquier diferencia consistente, sea grande o pequeña. Conforme al
anteproyecto, los resultados deben reportarse con tamaño de efecto e intervalo de confianza, no solo con el valor p.

---

## 4. Auditoría Técnica del Código y Repositorio

### 4.1 Estructura del Software
```
C:\Users\Gabriel\Desktop\TESIS\
├── docs/                                 # Documentación y anteproyecto formal
│   ├── 00-INDICE.md                      # Índice general
│   ├── 01-anteproyecto-v1.md             # Anteproyecto en texto plano
│   ├── 02-windows-vs-wsl2.md             # Decisión técnica: Windows nativo
│   ├── 03-montaje-wsl2.md                # Runbook alternativo WSL2
│   ├── 04-entorno-y-stack.md             # Stack técnico y lecciones aprendidas
│   ├── 05-visualizacion.md               # Guía de simulación visual y video
│   ├── 06-fuentes-de-datos.md            # Estrategia de aforos y solicitud UOCT
│   └── Anteproyecto_Tesis_*.{docx,pdf}   # Documento formal entregado
└── tsc-thesis/                           # Repositorio de código y experimentos
    ├── configs/                          # Configuraciones experimentales
    ├── models/                           # Políticas guardadas (no versionado en git)
    ├── resultados/                       # Muestra de telemetría Waze (exploratoria)
    ├── results/                          # Salidas JSON de baselines (versionadas desde 22-oct)
    ├── scenarios/                        # Escenarios SUMO
    │   ├── grid4x4/                      # Red sintética de verificación
    │   ├── apoquindo/                    # Red real, 42 semáforos (tramo oriente del eje)
    │   ├── alameda_providencia/          # Red real, 36 semáforos (tramo poniente del eje)
    │   └── providencia/                  # Red real, 72 semáforos (desaconsejada)
    ├── scripts/                          # Ejecución, calibración y diagnóstico
    ├── src/tsc/                          # Librería central del proyecto
    │   ├── controllers/                  # fixed, webster, maxpressure, greedy
    │   ├── gnn_router.py                 # GCN para rerouting (exploratorio, sin entrenar)
    │   ├── metrics.py                    # Parser de tripinfo y StepSampler
    │   ├── observations.py               # Observaciones extendidas Waze (exploratorio)
    │   ├── rl_env.py                     # Envoltorio PettingZoo/SuperSuit para SB3
    │   ├── runner.py                     # Ejecutor unificado de episodios SUMO
    │   └── sumo_env.py                   # Envoltorio de TraCI / libsumo
    └── tests/                            # Pruebas unitarias automatizadas (pytest)
```

### 4.2 Resultados de Pruebas Automatizadas
Ejecución en PowerShell el 22-oct-2026 (`python -m pytest -q` desde `tsc-thesis/`):
```
13 passed, 2 warnings in 41.93s
```
Incluye las 12 pruebas de `tests/` (`test_pipeline.py` y `test_demand_and_network.py`) más `scripts/test_waze_obs.py`,
que pytest recoge desde la raíz. Pruebas relevantes:
* `test_alameda_providencia_net_exists`: red real presente y legible.
* `test_demand_profiles_exist`: los 4 archivos de perfil existen y superan 100 KB.
* `test_fixed_controller_runs_on_valle_profile`: tiempo fijo simula sobre la red real con el perfil valle.
* `test_maxpressure_beats_fixed_time`: Max-Pressure supera a tiempo fijo.
* `test_webster_cycle_grows_with_demand`: el ciclo de Webster crece con el grado de saturación.
* `test_min_green_is_respected`: el verde mínimo se respeta como restricción dura.

### 4.3 Estado del control de versiones
* Repositorio remoto: `github.com/howtok6/CAPSTONE`, rama `master` (las ramas `main` y `dev-benja` contienen las evidencias de Fase 1 y el mockup de la app, con historia separada).
* Trabajo del 14-oct respaldado el 22-oct en los commits `eb7aa17` (código, escenario y resultados) y `7c80729` (documentación).
* `models/` sigue excluido de git; los JSON de `results/` se agregaron forzados y los nuevos resultados deben agregarse igual o ajustarse el `.gitignore`.
* `requirements.txt` no incluye `torch`, `torch_geometric` ni `WazeRouteCalculator`, que el código importa. Los pines se verificaron en Python 3.11/3.12; hoy se ejecuta en 3.13 sin entorno virtual.

---

## 5. Diagnóstico de las Redes de Simulación

Mediante `scripts/diagnose_net.py` se auditó la topología y viabilidad de cada escenario:

| Escenario | Arcos | Semáforos | Semáforos de fase única (< 2 fases verdes) | Arcos críticos (< 25 m entre semáforos distintos) | Veredicto |
|---|:---:|:---:|:---:|:---:|:---|
| **`grid4x4`** | 48 | 12 | 0 | 0 | 🟢 **APTA** (verificación unitaria). |
| **`alameda_providencia`** | 520 | 36 | 0 (fase de viraje corregida) | 0 (arcos internos de semáforos agrupados) | 🟢 **APTA** — tramo poniente del eje del MVP. |
| **`apoquindo`** | 749 | 42 | 1 (`GS_252964499`) | 2 (arcos de 22,3 m) | 🟡 **Requiere netedit** — tramo oriente del eje del MVP. |
| **`providencia`** | 788 | 72 | 5 | 3 | 🔴 **Desaconsejada** (alta densidad y acoplamiento); única red que cubre el tramo central. |

*Semáforos contados el 22-oct como elementos `tlLogic` en cada `net.net.xml`; las cifras previas de 43 y 75 provenían de diagnósticos anteriores.*

**Advertencia sobre teletransportes.** `sumo_env.py` y `diagnose_net.py` ejecutan SUMO con `--time-to-teleport -1`:
el teletransporte está desactivado por diseño para que los bloqueos se vean, así que «0 teletransportes» se cumple
siempre y no prueba que la red esté sana. Los indicadores útiles son los vehículos detenidos al final de la corrida y la
**cola de inserción** (vehículos cargados que no logran entrar a la red).

**Decisión de escenario (22-oct-2026), registrada en `docs/07-decision-escenario.md`.** El proyecto pasa a nivel
comunal y el MVP se centra en el eje Apoquindo → Providencia → Alameda. Ninguna red existente cubre el eje completo:
`alameda_providencia` llega por el oriente hasta −70,611 y `apoquindo` empieza en −70,598, por lo que faltan ~1,2 km de
Av. Providencia (entre Pedro de Valdivia y Tobalaba, aprox.). Quedan abiertos tres puntos: cómo construir la red del eje
completo, cuántos semáforos controla el agente y la validación con el profesor guía, porque el anteproyecto contempla un
corredor de 8–12 intersecciones. `diagnose_net.py` se modificó para no marcar los arcos cortos dentro de un mismo semáforo
agrupado (*joined TLS*); el criterio debe explicarse en la metodología.

---

## 6. Resultados Cuantitativos Registrados

Todos los resultados de esta sección son **pruebas de sanidad del arnés**, no resultados de tesis: usan demanda
sintética, pocas semillas y, en el caso del agente, un entrenamiento de apenas 8 000 pasos.

### 6.1 Benchmark Sintético Grilla 4×4 (8 semillas pareadas, 1 hora simulada)

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $47.57 \pm 0.12$ | — | $27.10 \pm 0.11$ | $22.57 \pm 0.11$ | $2899.1 \pm 1.7$ |
| **`greedy`** | $38.28 \pm 0.36$ | $-19.5\,\%$ | $17.79 \pm 0.23$ | $16.94 \pm 0.23$ | $2904.1 \pm 1.7$ |
| **`webster`** | $36.57 \pm 0.17$ | $-23.1\,\%$ | $17.19 \pm 0.13$ | $14.23 \pm 0.11$ | $2904.4 \pm 1.8$ |
| **`maxpressure`** | $33.05 \pm 0.20$ | $-30.5\,\%$ | $15.56 \pm 0.14$ | $14.65 \pm 0.16$ | $2907.9 \pm 1.6$ |
| **`ppo_8k`** | $31.58 \pm 0.05$ | $-33.6\,\%$ | $13.12 \pm 0.04$ | $9.51 \pm 0.05$ | $2912.5 \pm 1.4$ |

Todas las diferencias contra `fixed` dan p = 0,0078 (Wilcoxon pareado), que es el mínimo posible con 8 semillas.
PPO reduce más de 50 % la espera y la cola porque su recompensa *es* la variación de la espera (`diff-waiting-time`):
al comparar hay que declarar qué optimiza cada controlador.

### 6.2 Baselines en Escenario Real Apoquindo (3 semillas, demanda sintética)

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $130.94 \pm 0.85$ | — | $78.86 \pm 0.74$ | $103.55 \pm 0.18$ | $4725.7 \pm 3.5$ |
| **`webster`** | $97.09 \pm 2.96$ | $-25.9\,\%$ | $46.72 \pm 2.60$ | $50.16 \pm 0.81$ | $4704.3 \pm 7.5$ |
| **`greedy`** | $95.81 \pm 1.60$ | $-26.8\,\%$ | $42.84 \pm 1.19$ | $49.09 \pm 1.53$ | $4705.7 \pm 39.3$ |
| **`maxpressure`** | **$84.33 \pm 0.91$** | **$-35.6\,\%$** | **$35.28 \pm 0.50$** | **$35.88 \pm 1.05$** | **$4765.0 \pm 16.4$** |

### 6.3 Muestra Exploratoria de Congestión en Santiago (Waze)
`scripts/analyze_santiago_congestion.py` tomó **una sola muestra** el 16-sep-2026 a las 18:47 mediante
`WazeRouteCalculator` (cliente no oficial). Sirve como referencia de orden de magnitud, no como dato de calibración ni
fuente citable:
* **Alameda (Este-Oeste):** 11,11 km/h; 30,7 min para 5,68 km → índice de congestión 4,50.
* **Providencia (Este-Oeste):** 12,91 km/h → índice 3,87.
* **Alameda (Oeste-Este):** 15,76 km/h → índice 3,17.
* **Apoquindo:** 19,55–21,90 km/h → índice 2,28–2,56.

Para validar el escenario se recomiendan fuentes repetibles: tiempos típicos de Google por franja horaria y GPS de
buses de DTPM (ver `docs/06-fuentes-de-datos.md`).

### 6.4 Prueba de Humo en Alameda-Providencia (perfil valle, 2 semillas)
Corrida multi-controlador sobre el corredor Alameda-Providencia (36 semáforos, 520 arcos) con el perfil sintético
`valle`. Archivo: `results/alameda_providencia_valle_baselines.json`.

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $73.85 \pm 2.71$ | — | $45.42 \pm 2.12$ | $29.82 \pm 0.54$ | $1116.0 \pm 0.0$ |
| **`webster`** | $54.97 \pm 1.12$ | $-25.6\,\%$ | $25.01 \pm 0.49$ | $15.98 \pm 0.85$ | $1200.0 \pm 35.3$ |
| **`greedy`** | $47.51 \pm 2.41$ | $-35.7\,\%$ | $17.96 \pm 1.55$ | $14.48 \pm 0.57$ | $1227.0 \pm 29.4$ |
| **`maxpressure`** | **$41.71 \pm 0.18$** | **$-43.5\,\%$** | **$13.94 \pm 0.16$** | **$10.90 \pm 1.14$** | **$1272.0 \pm 11.8$** |

**Limitaciones de esta corrida:**
* **2 semillas** por controlador: el «±» no tiene interpretación de intervalo de confianza y no es posible aplicar Wilcoxon.
* Entre 186 y 213 vehículos terminados por corrida; el *throughput* es exactamente 6 × ese número, lo que indica una ventana de medición de ~10 minutos.
* `phase_switches` vale 0 para todos los controladores, incluido Max-Pressure, que necesariamente conmuta: **el contador no está registrando** y debe corregirse antes de la batería final.

La dirección del resultado (Max-Pressure < greedy < Webster < tiempo fijo) es coherente con la grilla y con Apoquindo,
pero la magnitud (−43,5 %) no debe citarse hasta repetirla con 10–30 semillas y 1 h simulada.

### 6.5 Perfiles Sintéticos de Demanda Horaria
Generados con `scripts/build_demand_profiles.py`, que invoca `randomTrips.py` con pesos de origen y destino fijados a
mano (80 / 15 / 5 entre los tercios poniente, centro y oriente de la red) y períodos de inserción fijos. **No hay un
paso de calibración contra datos observados.** Prueba de salud de 1 200 s:

| Perfil | Período | Cargados (aprox.) | Insertados | Sin insertar | Velocidad | Demora (*TimeLoss*) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`valle`** | 2,00 s | 600 | 600 | 0 % | 27,8 km/h | 86,4 s |
| **`punta_manana`** | 0,85 s | ~1 412 | 1 325 | ~6 % | 26,1 km/h | 136,6 s |
| **`punta_tarde`** | 0,72 s | ~1 667 | 1 490 | ~11 % | 21,1 km/h | 234,9 s |
| **`sobresaturado`** | 0,55 s | ~2 182 | 1 841 | ~16 % | 21,0 km/h | 231,2 s |

*«Cargados» = 1 200 s / período; `--validate` puede descartar algunos viajes, por lo que es una cota superior.*

**Hallazgo.** El perfil sobresaturado muestra *menos* demora que punta tarde. La causa es que los vehículos que no
logran entrar a la red no se cuentan en *TimeLoss*: la saturación queda fuera de la red, no dentro. Antes de usar estos
perfiles para comparar controladores hay que medir la cola de inserción y el retardo de salida (`depart_delay`) e
incluirlos en las métricas, o ajustar los períodos. Mientras tanto, el perfil `sobresaturado` no sirve como prueba de
estrés.

---

## 7. Deuda Técnica

### 7.1 Corregida en la sesión del 14-oct-2026
1. ✅ **`scripts/evaluate_waze_rerouting.py`:** `res.get('mean_delay_s')` reemplazado por `res.get('time_loss_mean')`.
2. ✅ **Codificación en Windows:** `sys.stdout.reconfigure(encoding='utf-8')` y `\u2192` reemplazado por `->` en `diagnose_net.py`, `build_webster.py`, `run_baselines.py`, `eval_rl.py` y `train_rl.py`.
3. ✅ **`map_alameda.osm` corrupto:** eliminado; `download_highway_osm.py` ahora envía `User-Agent` y usa timeouts.
4. ✅ **Residuos (`docs/index.bleve/`, logs):** `.gitignore` en la raíz del repositorio.
5. ✅ **Fase única en Providencia con Condell** (`cluster_133350020_482819423_5741781400`): corregida a dos fases verdes (`GrGGGGGrGGGG` pasante y `rGrrrrGrrrrr` viraje protegido).
6. ✅ **`diagnose_net.py`:** distingue arcos cortos dentro de un mismo semáforo agrupado.
7. ✅ **Generador de perfiles** `scripts/build_demand_profiles.py`.
8. ✅ **Parámetro `--profile`** en `run_baselines.py`, `train_rl.py` y `eval_rl.py`.
9. ✅ **`GNNRouter`:** reemplazados los datos simulados por lectura vía TraCI. *Nota: la red sigue sin entrenarse.*
10. ✅ **Pruebas:** `tests/test_demand_and_network.py` agregado.

### 7.2 Pendiente (detectada en la revisión del 22-oct-2026)
1. ⏳ **Contador `phase_switches`** devuelve 0 para todos los controladores.
2. ⏳ **Métrica de cola de inserción y `depart_delay`** ausente de la validación de perfiles; distorsiona punta tarde y sobresaturado.
3. ⏳ **Calibración de demanda** inexistente; los perfiles son sintéticos.
4. ⏳ **Red del eje completo y número de semáforos a controlar** (decisión de alcance registrada el 22-oct en `docs/07-decision-escenario.md`).
5. ⏳ **`requirements.txt` incompleto** (`torch`, `torch_geometric`, `WazeRouteCalculator`) y ejecución sin entorno virtual en Python 3.13.
6. ⏳ **Componentes exploratorios** (Waze, *rerouting*, GNN) por mover a trabajo futuro o documentar como fuera de alcance.
7. ✅ **Respaldo en git** del trabajo del 14-oct (resuelto el 22-oct: commits `eb7aa17` y `7c80729`).

---

## 8. Hoja de Ruta Priorizada

**Plazo pendiente de confirmar.** La versión del 14-oct proyectaba el cierre en diciembre; el anteproyecto contempla
seis meses desde el 23-ago (≈ fines de febrero de 2027). La regla de corte del anteproyecto (fin del mes 4: una política
aprendida que al menos iguale a tiempo fijo) cae hacia el 23-dic. Si el plazo real es diciembre, hay que adelantarla y
recortar alcance.

### Próximas semanas (fin de octubre – noviembre)
1. ✅ Commit y push del trabajo pendiente.
2. ✅ Corregir este informe de estado.
3. ✅ **Registrar la decisión de escenario** (`docs/07-decision-escenario.md`). Pendiente: validarla con el profesor guía.
3b. **Construir la red del eje completo** Apoquindo → Providencia → Alameda (cubrir la brecha de ~1,2 km). Listo cuando `diagnose_net.py` la declara APTA.
4. **Arreglar `phase_switches`.** Listo cuando Max-Pressure reporta conmutaciones > 0.
5. **Medir la cola de inserción** en el arnés. Listo cuando los cuatro perfiles quedan ordenados por demora de valle a sobresaturado.
6. **Fijar el alcance de control** (solo los semáforos del eje o todos los de la red). Listo cuando `rl_env.py` recibe la lista explícita.
7. **Baselines completos:** 4 perfiles × 4 controladores × 10 semillas × 1 h. Listo cuando `compare.py` entrega IC 95 % y tamaño de efecto.
8. **Primer IPPO en red real** (perfil punta tarde). Listo cuando la curva se estabiliza y la política iguala a tiempo fijo.
9. **Validación de demanda** con tiempos típicos por franja y, si llegan, datos de UOCT o DTPM.
10. **Completar `requirements.txt`** y crear un entorno virtual.

### Después
* **MAPPO con crítico centralizado** (Ray RLlib; en Windows está en beta, considerar WSL2 en esa fase).
* **Batería de robustez (OE6):** cierre de carril, alza súbita del 30 % en un acceso, pérdida de sensores.
* **Batería final:** 30 semillas pareadas por controlador y perfil.
* **Redacción del informe final,** reproducibilidad del repositorio (script maestro) y videos comparativos con `record_run.py`.
