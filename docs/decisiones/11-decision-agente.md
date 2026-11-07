# Decisión: configuración del agente de aprendizaje

Registrada el 24-oct-2026. Estado: **decidida por el autor**; los valores de hiperparámetros son iniciales y se
ajustan en las semanas 3 y 4 del plan de cierre.

## Algoritmo

**PPO con parámetros compartidos (IPPO)**, sobre Stable-Baselines3 y sumo-rl. Una sola red neuronal decide en los
64 semáforos del eje; cada semáforo aporta sus propias muestras al lote. Es la configuración base de OE4 y el punto
de comparación para MAPPO (crítico centralizado) en el tramo de Providencia.

## Cómo aprende de sus errores

1. **Ventaja.** Tras cada lote de experiencia, PPO compara el retorno que obtuvo cada acción con el que el crítico
   esperaba (ventaja, estimada con GAE, λ = 0,95). Las acciones que salieron peor de lo esperado pierden
   probabilidad; las que salieron mejor la ganan.
2. **Error de valor.** El crítico corrige su propia estimación con la diferencia entre lo que predijo y lo que
   ocurrió, para que la ventaja del siguiente lote sea más precisa.
3. **Corrección acotada.** El recorte de PPO (clip = 0,2) y el recorte de gradientes (`max_grad_norm = 0,5`) impiden
   que un episodio excepcionalmente malo desarme lo aprendido.
4. **Exploración.** Un bono de entropía (0,01) evita que la política se fije demasiado pronto en una sola fase.

## Optimizador: Adam por defecto, RMSprop como alternativa

| | Adam (por defecto) | RMSprop |
|---|---|---|
| Qué hace | Paso adaptativo por parámetro **más momento** | Paso adaptativo por parámetro, sin momento |
| Dónde se usa | Artículo original de PPO; por defecto en PPO de SB3 | DQN (Mnih 2015) y A2C; por defecto en A2C de SB3 |
| Por qué aquí | PPO hace 10 pasadas de minilotes sobre el mismo lote: el momento suaviza el ruido entre minilotes | Útil en el ablation si las recompensas resultan muy ruidosas |
| Parámetros | `eps = 1e-5` | `alpha = 0,99`, `eps = 1e-5` |

Se elige con `--optimizer adam|rmsprop` en `scripts/train_rl.py`. La tasa de aprendizaje parte en 3·10⁻⁴ y baja
linealmente a 0 al final del entrenamiento (`--lr-schedule linear`): las primeras actualizaciones exploran y las
últimas afinan.

## Qué semáforos controla

Solo los **64 del eje** (`scenarios/eje_comunal/tls_eje.json`, generado por `scripts/list_axis_tls.py`). Los 22 de
las transversales siguen su programa de tiempo fijo. `train_rl.py` y `eval_rl.py` usan la misma lista
(`--control auto|eje|todos`), así que no puede evaluarse un agente con un alcance distinto al de su entrenamiento.

## Condiciones del entrenamiento (5-nov-2026)

Revisión hecha antes de la primera corrida larga. Cada punto corrige algo que habría invalidado el resultado.

| Punto | Antes | Ahora |
|---|---|---|
| **Salidas sobrantes de la red** | 49 de los 64 semáforos tienen 2 fases y la red 4 salidas. Al entrenar, SuperSuit lleva las sobrantes a la fase 0; `eval_rl.py` usaba `a % n`, otra política | `accion_real()` replica a SuperSuit; una prueba compara ambas |
| **Verde máximo** | `sumo-rl` guarda `max_green` y no lo aplica | `SubsetSumoEnvironment._apply_actions` fuerza la fase siguiente en la última decisión que respeta los 60 s |
| **Variedad de episodios** | Una sola demanda y semilla fija: la misma hora repetida | 10 demandas de entrenamiento rotan por episodio, cada una con su semilla de SUMO |
| **Réplicas de evaluación** | Mismos viajes en todas las semillas; solo cambiaba la semilla de SUMO | 10 demandas propias (`demand/eval/`). La réplica k usa la semilla k en todos los controladores: sigue pareada y ningún viaje de evaluación se vio al entrenar |
| **Velocidad** | TraCI, con métricas por vehículo en cada decisión | libsumo y sin esas métricas (la evaluación usa `tripinfo`). Una simulación por proceso |
| **Corrida larga** | Solo se guardaba el modelo final | Checkpoints cada 250 000 muestras, curva en `progress.csv`, `--resume` y metadatos escritos al partir |

**Observación por fase (`--obs fase`).** La de `sumo-rl` trae una columna por pista. En el eje hay cruces de 4 a 23
pistas y 2 a 4 fases, así que al rellenar con ceros la misma columna es densidad en un cruce y cola en otro; con
parámetros compartidos eso impide generalizar. `PhaseObservation` tiene 22 columnas fijas: fase actual, fases
existentes, si puede cambiar, tiempo de verde y, por cada fase, densidad y cola de las pistas que atiende y densidad de
las pistas a las que descarga. Cada salida de la red queda ligada a las columnas de su fase. **No se adopta por
supuesto:** la primera tanda compara `fase` y `estandar`, y la elección se decide con la demora medida.

**Corrida inicial.** Perfil punta tarde, Adam, recompensa `wait`, 2 000 000 de muestras (unas 43 horas simuladas).
Corridas: `fase` semillas 0 y 1, `estandar` semilla 0. Se lanzan con `scripts/lanzar_entrenamiento.ps1`.

**Resultado (10 demandas de evaluación).** `fase` da 87,09 ± 1,18 s y 86,24 ± 1,02 s de demora incluyendo no
terminados; `estandar` da 216,64 ± 38,00 s, con réplicas bloqueadas. **Se adopta `fase`** como observación del agente.
La tabla completa está en `ESTADO_DEL_PROYECTO.md` §6.6. El agente de `fase` cambia de fase cada 19 a 24 s por semáforo:
la conmutación excesiva que se temía en la prueba del 24-oct no persistió.

**Comparabilidad con los controladores clásicos.** Los adaptativos (`greedy`, `maxpressure`) ahora avanzan con reloj de
1 s para que el ámbar dure 3 s, deciden cada 5 s como el agente y controlan los mismos 64 semáforos.
`scripts/verificar_paridad.py` corre la misma regla en ambos arneses: 109,4 s frente a 110,3 s (+0,8 %, 3 réplicas).

**Generalización.** Entrenado solo con punta tarde, el agente queda +3 % respecto del mejor baseline en valle y entre
−18 % y −32 % en punta mañana, punta tarde y sobresaturado, con baselines ajustados (`ESTADO_DEL_PROYECTO.md` §6.6). Por
ahora no hace falta entrenar por perfil.

**Límite conocido.** Las demandas siguen siendo sintéticas. Lo aprendido aquí sirve para comprobar que el agente aprende
y aplicar la regla de corte del 22-nov; el resultado de tesis exige reentrenar con la demanda validada contra terreno.

## Trazabilidad

Cada modelo se guarda con un `.json` al lado: optimizador y sus parámetros, tasa de aprendizaje, recompensa,
semáforos controlados, archivo de rutas, commit de git y duración. Es la fila de la tabla `corridas` de la base de
datos (`10-decision-base-de-datos.md`).

## Prueba de funcionamiento (24-oct-2026)

Red `eje_comunal`, demanda sintética de prueba (`routes.rou.xml`), 64 semáforos controlados, episodios de 900 s,
1 entorno, semilla 0, 49 152 muestras (3 actualizaciones). Solo verifica que el entrenamiento funciona; **no**
compara optimizadores.

| Optimizador | Recompensa media por actualización (1 → 2 → 3) | Duración |
|---|---|---|
| Adam | −0,64 → −0,54 → −0,41 | 191 s |
| RMSprop | −0,64 → −0,54 → −0,28 | 199 s |

- **Velocidad:** ~270 muestras/s, unos 21 s simulados por segundo real con 64 agentes. Un entrenamiento de 1 millón
  de muestras toma del orden de una hora.
- **Ambos aprenden** en la dirección correcta. RMSprop avanzó más en esta prueba, pero con una semilla y tres
  actualizaciones la diferencia no es concluyente. Se mantiene Adam por defecto y la comparación formal (3 semillas,
  entrenamiento completo, perfil punta tarde) queda en las semanas 3 y 4.
- **Evaluación** del modelo Adam (900 s): 3 061 cambios de fase, ~1 cada 16 s por semáforo, cerca del verde mínimo.
  Es lo esperable con tan poco entrenamiento; si persiste tras entrenar en serio, se evalúa la recompensa con
  penalización por conmutación.
- **Métrica corregida:** demora incluyendo no terminados 152 s, frente a 96 s contando solo viajes terminados (464
  vehículos seguían en la red al cierre). Confirma que `delay_all_mean` debe ser la métrica primaria.
