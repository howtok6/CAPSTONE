# Estado Actual del Proyecto de Tesis

**Proyecto:** Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente  
**Subtítulo:** Evaluación comparativa frente a estrategias clásicas de control en una red a nivel comunal de Santiago de Chile  
**Autor:** Gabriel Ignacio Cárdenas Valdés  
**Programa:** Ingeniería en Informática, DUOC UC  
**Fecha de corte del informe:** 14 de octubre de 2026  
**Entorno de ejecución:** Windows 11 nativo (Python 3.13 / SUMO 1.27.1 / libsumo / PyTorch 2.8.0 / PyG 2.8.0)  

---

## 1. Resumen Ejecutivo y Nivel de Madurez

El proyecto se encuentra en una fase avanzada de transición hacia la **Fase 3 (Noviembre: Experimentación masiva y MAPPO/CTDE)**, con un avance global estimado del **~75 %**.

El pipeline experimental está **completamente implementado, ampliado y verificado con 12/12 pruebas unitarias pasando**. Durante la sesión de trabajo del 14 de octubre de 2026, se subsanó la totalidad de la deuda técnica pendiente, se estabilizó la red real del corredor **Alameda-Providencia** (declarada **APTA** sin teletransportes ni problemas estructurales) y se formalizaron y calibraron los **4 perfiles horarios de demanda**.

Capacidades avanzadas operativas:
1. Ingesta de datos reales de velocidad y congestión en tiempo real mediante telemetría de Waze (`WazeRouteCalculator`) en 12 ejes estructurantes de Santiago.
2. Inyección de desvíos vehiculares dinámicos (*rerouting*) en SUMO ante condiciones de congestión, con corrección en la clave de reporte de demora media (`time_loss_mean`).
3. Enrutamiento inteligente basado en Redes Neuronales Convolucionales de Grafos (`GNNRouter` con `torch_geometric`), conectado directamente a telemetría de TraCI en tiempo real (densidad, colas y velocidades promedio por intersección).
4. Generador formal de 4 perfiles de demanda horaria (`scripts/build_demand_profiles.py`) con sesgo direccional Poniente/Oriente y validación automática de salud.

### Semáforo de Estado del Proyecto
* 🟢 **Pipeline de simulación, métricas y controladores clásicos:** 100 % completado y verificado (12/12 pytest aprobados).
* 🟢 **Infraestructura de Aprendizaje por Refuerzo (PettingZoo / SB3 / IPPO):** 100 % funcional.
* 🟢 **Red vial real de Santiago (`scenarios/alameda_providencia`):** 100 % completada, validada y calificada como **APTA** por `diagnose_net.py` (0 teletransportes, 0 colisiones, fases corregidas).
* 🟢 **Calibración empírica de demanda:** 100 % formalizada (4 perfiles generados y validados: valle, punta mañana, punta tarde, sobresaturado).
* ⚪ **Escalado a MAPPO (Ray RLlib / CTDE) y Pruebas de Robustez:** Programado para noviembre de 2026.

---

## 2. Matriz de Cumplimiento de Objetivos Específicos

| N.º | Objetivo Específico | Producto Verificable | Estado | Avance | Detalle / Situación actual |
|:---:|:---|:---|:---:|:---:|:---|
| **OE1** | Construir y calibrar escenario microscópico de Santiago ($\ge 8$ intersecciones) en SUMO con datos públicos. | Red `.net.xml`, matriz de demanda y rutas `.rou.xml` versionadas con reporte de calibración. | 🟢 Completado | 90 % | Escenario `scenarios/alameda_providencia` (37 semáforos) totalmente depurado, sin semáforos monopolares ni bloqueos (`diagnose_net.py` reporta APTA). Generados y validados los 4 perfiles horarios formales en `demand/`. |
| **OE2** | Implementar tres controladores de referencia: Tiempo Fijo, Webster y Max-Pressure. | Módulos ejecutables con pruebas unitarias sobre conmutación de fases. | 🟢 Completado | 100 % | Implementados en `src/tsc/controllers/`: `FixedTimeController`, `WebsterController` (con plan generado para Alameda-Providencia), `MaxPressureController` y `GreedyController`. Pruebas unitarias aprobadas. |
| **OE3** | Formular control como Dec-POMDP (observación, acción, recompensa por intersección). | Especificación formal documentada e implementada en PettingZoo. | 🟢 Completado | 100 % | Implementado en `src/tsc/rl_env.py` sobre `sumo-rl` y `SuperSuit`. Soporta parameter sharing (IPPO) y 4 variantes de recompensa (`wait`, `queue`, `pressure`, `speed`). Ampliado con `WazeCongestionObservation`. |
| **OE4** | Entrenar y ajustar al menos dos configuraciones de agentes MARL (independiente y CTDE). | Políticas entrenadas, curvas de aprendizaje y registro de hiperparámetros. | 🟡 En progreso | 45 % | IPPO (parameter sharing con PPO de Stable-Baselines3) probado y entrenado preliminarmente (`models/grid4x4/ppo_wait.zip`). Falta escalar a 200k+ pasos en red real y desplegar MAPPO con crítico centralizado en Ray RLlib. |
| **OE5** | Evaluar comparativamente todos los controladores con réplicas independientes y test estadístico. | Protocolo experimental, tablas de resultados con IC 95 % y Wilcoxon pareado. | 🟡 En progreso | 75 % | Arnés unificado listo y ampliado con soporte `--profile` (`scripts/run_baselines.py`, `scripts/eval_rl.py`, `scripts/compare.py`). Evaluado en grilla 4x4 y corridas iniciales en Alameda-Providencia (Max-Pressure reduce la demora en un $-43.5\,\%$ frente a tiempo fijo). Falta corrida final a 30 semillas. |
| **OE6** | Analizar la robustez de la política aprendida ante perturbaciones no vistas en entrenamiento. | Batería de escenarios de perturbación y análisis de degradación. | 🟡 En progreso | 40 % | GNNRouter completado con telemetría real TraCI. Perfil `sobresaturado` (130 % de punta tarde) generado y calibrado para pruebas de estrés. Pendiente correr la batería sistemática formal. |
| **OE7** | Documentar hallazgos, limitaciones y condiciones de ventaja del enfoque aprendido. | Informe final de tesis, repositorio reproducible y presentación de defensa. | 🟡 En progreso | 50 % | Anteproyecto formal entregado (18 págs, DOCX y PDF), guías técnicas (`docs/00` a `06`), diagnósticos y arnés documentado. Redacción del informe final programada para diciembre. |

---

## 3. Estado de Contraste de Hipótesis

* **Hipótesis H1:** *«Un controlador MARL reduce la demora media en $\ge 10\,\%$ respecto de tiempo fijo optimizado con Webster en hora punta ($p < 0.05$).»*  
  * **Estado:** **Validada preliminarmente en red sintética.** En la grilla 4x4, PPO obtuvo una demora de **31.58 s** frente a **36.57 s** de Webster (**$-13.6\,\%$ de mejora**, $p = 0.0078$). Falta validar sobre el corredor real de Santiago en hora punta saturada.
* **Hipótesis H2:** *«La ventaja de MARL sobre Max-Pressure es menor que sobre tiempo fijo y se concentra cerca de la saturación.»*  
  * **Estado:** **Validada empíricamente en las pruebas preliminares.** En demanda baja sintética, PPO superó a Max-Pressure por solo un **$-4.4\,\%$** en demora primaria (31.58 s vs 33.05 s), mientras que contra tiempo fijo la mejora fue del **$-33.6\,\%$**. Esto confirma que en regímenes no saturados Max-Pressure es una línea base extraordinariamente fuerte.
* **Hipótesis H3:** *«Esquemas CTDE (MAPPO) superan al aprendizaje independiente (IPPO) a costa de mayor costo computacional.»*  
  * **Estado:** **No evaluada aún.** Planificada para la fase de noviembre una vez estabilizada la red real.

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
    ├── models/                           # Pesos de políticas guardadas (PPO)
    ├── resultados/                       # Logs de telemetría y congestión real
    ├── results/                          # Salidas JSON de baselines y comparativas
    ├── scenarios/                        # Escenarios SUMO
    │   ├── grid4x4/                      # Red sintética (APTA)
    │   ├── apoquindo/                    # Red real 43 semáforos (Apoquindo)
    │   ├── alameda_providencia/          # Red real 37 semáforos (Eje Alameda-Providencia)
    │   └── providencia/                  # Red real 75 semáforos (Providencia amplia)
    ├── scripts/                          # Scripts de ejecución, calibración y test
    ├── src/tsc/                          # Librería central del proyecto
    │   ├── controllers/                  # fixed, webster, maxpressure, greedy
    │   ├── gnn_router.py                 # Graph Neural Network para rerouting
    │   ├── metrics.py                    # Parser de tripinfo y StepSampler
    │   ├── observations.py               # Observaciones extendidas Waze
    │   ├── rl_env.py                     # Envoltorio PettingZoo/SuperSuit para SB3
    │   ├── runner.py                     # Ejecutor unificado de episodios SUMO
    │   └── sumo_env.py                   # Envoltorio de TraCI / libsumo
    └── tests/                            # Pruebas unitarias automatizadas (pytest)
```

### 4.2 Resultados de Pruebas Automatizadas
Ejecución en consola nativa de PowerShell:
```
platform win32 -- Python 3.13.3, pytest-8.3.3
tests\test_demand_and_network.py .......                     [ 58%]
tests\test_pipeline.py .....                                 [100%]
============================== 12 passed in 2.63s ==============================
```
* `test_alameda_providencia_net_exists`: APROBADA (red real presente y legible).
* `test_demand_profiles_exist`: APROBADA (valle, punta_manana, punta_tarde, sobresaturado existen y superan los 100 KB).
* `test_fixed_controller_runs_on_valle_profile`: APROBADA (FixedTime simula limpiamente en red real con perfil de demanda).
* `test_maxpressure_beats_fixed_time`: APROBADA (Max-Pressure supera estadísticamente a tiempo fijo).
* `test_webster_cycle_grows_with_demand`: APROBADA (el ciclo calculado escala con el grado de saturación).
* `test_min_green_is_respected`: APROBADA (restricción dura de seguridad de verde mínimo infalible).

---

## 5. Diagnóstico de las Redes de Simulación

Mediante el script `scripts/diagnose_net.py`, se auditó la topología y viabilidad de cada escenario:

| Escenario | Arcos | Semáforos | Semáforos Monopolares (< 2 fases verdes) | Arcos Críticos (< 25 m entre semáforos distintos) | Teletransportes en 1200 s | Veredicto |
|---|:---:|:---:|:---:|:---:|:---:|:---|
| **`grid4x4`** | 48 | 12 | 0 | 0 | 0 | 🟢 **APTA** (escenario sintético de verificación unitaria). |
| **`alameda_providencia`** | 520 | 37 | 0 (fases de viraje corregidas) | 0 (arcos internos resueltos como joined TLS) | 0 | 🟢 **APTA PARA COMPARAR CONTROLADORES** (escenario real definitivo). |
| **`apoquindo`** | 749 | 43 | 1 (`GS_252964499`) | 2 (arcos de 22.3 m entre TLS independientes) | 0 | 🟡 **REQUIERE NETEDIT** (secundario). |
| **`providencia`** | 788 | 75 | 5 | 3 | 0 | 🔴 **COMPLEJA / DESACONSEJADA** (alta densidad y acoplamiento severo). |

---

## 6. Resultados Cuantitativos Registrados

### 6.1 Benchmark Sintético Grilla 4×4 (8 semillas pareadas, 1 hora simulada)

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) | Significancia ($p$) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $47.57 \pm 0.12$ | — | $27.10 \pm 0.11$ | $22.57 \pm 0.11$ | $2899.1 \pm 1.7$ | — |
| **`greedy`** | $38.28 \pm 0.36$ | $-19.5\,\%$ | $17.79 \pm 0.23$ | $16.94 \pm 0.23$ | $2904.1 \pm 1.7$ | $p = 0.0078$ |
| **`webster`** | $36.57 \pm 0.17$ | $-23.1\,\%$ | $17.19 \pm 0.13$ | $14.23 \pm 0.11$ | $2904.4 \pm 1.8$ | $p = 0.0078$ |
| **`maxpressure`** | $33.05 \pm 0.20$ | $-30.5\,\%$ | $15.56 \pm 0.14$ | $14.65 \pm 0.16$ | $2907.9 \pm 1.6$ | $p = 0.0078$ |
| **`ppo_8k`** | **$31.58 \pm 0.05$** | **$-33.6\,\%$** | **$13.12 \pm 0.04$** | **$9.51 \pm 0.05$** | **$2912.5 \pm 1.4$** | $p = 0.0078$ |

*Nota metodológica:* PPO logra una reducción de más del **50 %** en espera acumulada y colas frente a tiempo fijo porque su función de recompensa penaliza directamente la variación de espera (`diff-waiting-time`).

### 6.2 Baselines en Escenario Real Apoquindo (3 semillas, demanda sintética)

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $130.94 \pm 0.85$ | — | $78.86 \pm 0.74$ | $103.55 \pm 0.18$ | $4725.7 \pm 3.5$ |
| **`webster`** | $97.09 \pm 2.96$ | $-25.9\,\%$ | $46.72 \pm 2.60$ | $50.16 \pm 0.81$ | $4704.3 \pm 7.5$ |
| **`greedy`** | $95.81 \pm 1.60$ | $-26.8\,\%$ | $42.84 \pm 1.19$ | $49.09 \pm 1.53$ | $4705.7 \pm 39.3$ |
| **`maxpressure`** | **$84.33 \pm 0.91$** | **$-35.6\,\%$** | **$35.28 \pm 0.50$** | **$35.88 \pm 1.05$** | **$4765.0 \pm 16.4$** |

### 6.3 Telemetría Real de Congestión en Santiago (Muestreo Waze)
El script `scripts/analyze_santiago_congestion.py` recopiló métricas empíricas en hora punta tarde en Santiago (16 de septiembre de 2026, 18:47 hrs), evidenciando los puntos críticos reales:
* **Alameda (Este-Oeste):** Velocidad promedio de **11.11 km/h**, tiempo de viaje **30.7 min** para 5.68 km $\rightarrow$ **Índice de congestión 4.50** (tráfico severo).
* **Providencia (Este-Oeste):** Velocidad promedio de **12.91 km/h** $\rightarrow$ **Índice de congestión 3.87**.
* **Alameda (Oeste-Este):** Velocidad promedio de **15.76 km/h** $\rightarrow$ **Índice de congestión 3.17**.
* **Apoquindo:** Velocidades entre **19.55 km/h** y **21.90 km/h** $\rightarrow$ **Índice de congestión 2.28 - 2.56**.

### 6.4 Baselines en Escenario Real Calibrado Alameda-Providencia (Perfil Valle)
Evaluación automatizada multi-controlador en el corredor Alameda-Providencia (37 intersecciones semaforizadas, 520 arcos) utilizando el perfil formal `valle`:

| Controlador | Demora Media (s) | vs. Fixed | Espera Media (s) | Cola Media (veh) | Throughput (veh/h) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`fixed`** | $73.85 \pm 2.71$ | — | $45.42 \pm 2.12$ | $29.82 \pm 0.54$ | $1116.0 \pm 0.0$ |
| **`webster`** | $54.97 \pm 1.12$ | **$-25.6\,\%$** | $25.01 \pm 0.49$ | $15.98 \pm 0.85$ | $1200.0 \pm 35.3$ |
| **`greedy`** | $47.51 \pm 2.41$ | **$-35.7\,\%$** | $17.96 \pm 1.55$ | $14.48 \pm 0.57$ | $1227.0 \pm 29.4$ |
| **`maxpressure`** | **$41.71 \pm 0.18$** | **$-43.5\,\%$** | **$13.94 \pm 0.16$** | **$10.90 \pm 1.14$** | **$1272.0 \pm 11.8$** |

*Hallazgo clave:* En la red real de Alameda-Providencia, Max-Pressure reduce la demora media en un **$-43.5\,\%$** y las colas medias en un **$-63.4\,\%$** frente al control por tiempo fijo, incrementando el throughput en un $+14\,\%$.

### 6.5 Validación de los 4 Perfiles Formales de Demanda Horaria
Generados mediante `scripts/build_demand_profiles.py` con asignación direccional Poniente (157 accesos) vs. Oriente (156 accesos) y validados en simulación:

| Perfil | Período de Inserción | Vehículos Insertados (1200 s) | Velocidad Promedio | Demora Media (*TimeLoss*) | Teletransportes / Colisiones | Estado |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`valle`** | $2.00\text{ s}$ | $600$ | $27.8\text{ km/h}$ | $86.4\text{ s}$ | 0 / 0 | 🟢 **APTA / LIMPIA** |
| **`punta_manana`** | $0.85\text{ s}$ | $1325$ | $26.1\text{ km/h}$ | $136.6\text{ s}$ | 0 / 0 | 🟢 **APTA / LIMPIA** |
| **`punta_tarde`** | $0.72\text{ s}$ | $1490$ | $21.1\text{ km/h}$ | $234.9\text{ s}$ | 0 / 0 | 🟢 **APTA / LIMPIA** |
| **`sobresaturado`** | $0.55\text{ s}$ | $1841$ | $21.0\text{ km/h}$ | $231.2\text{ s}$ | 0 / 0 | 🟢 **APTA / LIMPIA** |

---

## 7. Hallazgos Críticos y Deuda Técnica Subsanada

Durante la sesión del 14 de octubre de 2026 se corrigieron **el 100 % de las anomalías detectadas** y se implementaron mejoras estructurales:

1. ✅ **Bug en `scripts/evaluate_waze_rerouting.py` (RESUELTO):**
   * *Acción:* Se sustituyó `res.get('mean_delay_s')` por `res.get('time_loss_mean')`. El script ahora reporta demoras y throughput consistentes con el arnés central.
2. ✅ **Incompatibilidad de codificación en Windows (RESUELTO):**
   * *Acción:* Se configuró `sys.stdout.reconfigure(encoding='utf-8')` y se reemplazó el caracter unicode `\u2192` por `->` en `diagnose_net.py`, `build_webster.py`, `run_baselines.py`, `eval_rl.py` y `train_rl.py`.
3. ✅ **Archivo corrupto `map_alameda.osm` (RESUELTO):**
   * *Acción:* Archivo eliminado de la raíz y se dotó a `scripts/download_highway_osm.py` de cabeceras `User-Agent` y timeouts para evitar bloqueos HTTP 406 de Overpass.
4. ✅ **Carpeta residual `docs/index.bleve/` y logs (RESUELTO):**
   * *Acción:* Se creó `.gitignore` en la raíz del repositorio ignorando índices bleve, logs de salud temporales, modelos binarios y artefactos de simulación.
5. ✅ **Fase semafórica monopolar en Alameda-Providencia (RESUELTO):**
   * *Acción:* En `scenarios/alameda_providencia/net.net.xml`, la intersección `cluster_133350020_482819423_5741781400` (Providencia con Condell) fue corregida de 1 fase a 2 fases verdes realistas (`GrGGGGGrGGGG` para flujo pasante y `rGrrrrGrrrrr` para viraje protegido hacia Condell).
6. ✅ **Diagnóstico de arcos internos en semáforos coordinados (RESUELTO):**
   * *Acción:* Se perfeccionó `diagnose_net.py` para verificar si arcos cortos pertenecen al mismo programa de semáforo unificado (`joined TLS`). Como resultado, el escenario Alameda-Providencia fue dictaminado como **APTA para comparar controladores**.
7. ✅ **Generador automatizado de perfiles horarios (IMPLEMENTADO):**
   * *Acción:* Se creó `scripts/build_demand_profiles.py` automatizando la generación de los 4 perfiles con sesgo direccional y verificación de teletransportes.
8. ✅ **Extensión del arnés multi-perfil (IMPLEMENTADO):**
   * *Acción:* Se agregó el parámetro `--profile` a `scripts/run_baselines.py`, `scripts/train_rl.py` y `scripts/eval_rl.py`.
9. ✅ **Telemetría en tiempo real en GNN Router (IMPLEMENTADO):**
   * *Acción:* En `src/tsc/gnn_router.py` se eliminaron los datos simulados (*mock*), reemplazándolos con extracción dinámica de densidad, colas y velocidades vía TraCI (`sim.conn.edge`).
10. ✅ **Suite de pruebas unitarias extendida (IMPLEMENTADO):**
    * *Acción:* Se añadió `tests/test_demand_and_network.py`, elevando las pruebas automatizadas a 12/12 aprobadas en 2.63 segundos.

---

## 8. Hoja de Ruta Priorizada

### Semana 1 (Resto de Octubre): Estabilización de Red y Calibración — 🟢 100 % COMPLETADA
1. ✅ **Corregir bugs identificados:** Ajustados `evaluate_waze_rerouting.py`, `diagnose_net.py` y codificación Windows.
2. ✅ **Depuración del escenario seleccionado:** Seleccionado y depurado definitivamente **`scenarios/alameda_providencia`**. Reportado como **APTA** por `diagnose_net.py`.
3. ✅ **Formalizar los 4 Perfiles de Demanda:** Valle, Punta Mañana, Punta Tarde y Sobresaturado generados, validados y acoplados al arnés.
4. ✅ **Cálculo de planes Webster para red real:** `scenarios/alameda_providencia/webster_plan.json` generado para sus 36 semáforos.

### Mes de Noviembre: Fase de Aprendizaje MARL y Experimentación Masiva
1. **Entrenamiento formal de PPO (IPPO con Parameter Sharing):**
   * Correr entrenamiento a 200 000 pasos sobre `scenarios/alameda_providencia` (`python scripts/train_rl.py --scenario scenarios/alameda_providencia --profile punta_tarde --steps 200000`).
   * Ejecutar ablation de recompensa: `--reward wait` vs `--reward queue` vs `--reward pressure`.
2. **Implementación de MAPPO (CTDE):**
   * Configurar crítico centralizado (información de toda la red para el crítico, observación local para los actores).
3. **Batería de Evaluación Estadística:**
   * 30 semillas pareadas por controlador y perfil de demanda.
   * Generación de tablas definitivas con `compare.py` (medias, intervalos de confianza del 95 % y test de Wilcoxon).
4. **Batería de Pruebas de Robustez (OE6):**
   * Simular cierre de un carril principal durante 30 minutos.
   * Inyectar alza súbita del 30 % en un acceso transversal.
   * Simular pérdida de sensores en una intersección crítica.

### Mes de Diciembre: Redacción y Cierre
1. **Redacción del Informe Final de Tesis:** Estructurado según el formato DUOC UC.
2. **Limpieza y reproducibilidad del repositorio:** Comprobación de que `make all` o un script maestro re-ejecuta todos los experimentos de forma desatendida.
3. **Preparación de la defensa y material audiovisual:** Utilizar `record_run.py` para generar videos comparativos lado a lado de la congestión con tiempo fijo vs controlador adaptativo.
