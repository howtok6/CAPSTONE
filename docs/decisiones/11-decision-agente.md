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
