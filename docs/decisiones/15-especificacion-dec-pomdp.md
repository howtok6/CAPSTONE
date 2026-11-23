# 15 · Especificación formal del problema como Dec-POMDP (OE3)

Fecha: 23-nov-2026 · Escenario Las Condes + Providencia · Código: `src/tsc/rl_env.py`,
`src/tsc/observations.py`, `src/tsc/mappo.py`, `scripts/train_rl.py`

El control de los semáforos del área se modela como un proceso de decisión de Markov
descentralizado y parcialmente observable (Dec-POMDP, Bernstein et al., 2002):

$$\mathcal{M} = \langle \mathcal{I}, \mathcal{S}, \{\mathcal{A}_i\}, P, \{R_i\}, \{\Omega_i\}, O, \gamma, T \rangle$$

## Agentes $\mathcal{I}$

Un agente por semáforo controlado. Escenario completo: los 487 semáforos de `tls_eje.json`, que
tienen código UOCT y entre 2 y 4 fases verdes. Variante MAPPO (opción A): los 206 de
Providencia (`tls_providencia.json`). Los demás semáforos de la red (107 en el escenario completo)
siguen su programa de tiempo fijo y son parte del entorno.

## Estado $\mathcal{S}$

El estado completo de la simulación SUMO en el instante $t$: posición, velocidad, ruta y tiempo
de espera acumulado de cada vehículo, fase y tiempo en fase de los 594 semáforos, y los vehículos
pendientes de entrar. Ningún agente lo observa completo.

## Acciones $\mathcal{A}_i$

$a_i \in \{0, \dots, F_i - 1\}$: la fase verde que el semáforo $i$ quiere tener durante el próximo
intervalo de decisión, con $F_i \in \{2, 3, 4\}$ fases verdes. La red compartida tiene 4 salidas y
una salida $\ge F_i$ se interpreta como la fase 0 (`accion_real`, igual en entrenamiento y
evaluación). Restricciones que impone el entorno, no el agente:

* Decisión cada $\Delta = 5$ s; cambiar de fase inserta 3 s de amarillo.
* Verde mínimo de 10 s: antes de eso, la acción no tiene efecto.
* Verde máximo de 60 s: si el agente insiste en la misma fase, se fuerza la siguiente
  (`SubsetSumoEnvironment._apply_actions`). sumo-rl guarda este parámetro pero no lo aplica.

## Transición $P$

$P(s' \mid s, \mathbf{a})$ es la dinámica de SUMO 1.27 durante $\Delta$ s, con el modelo de
seguimiento Krauss y cambio de pista LC2013. Es estocástica por la semilla de la simulación
(imperfección del conductor, inserción) y por la demanda: en cada episodio cambia la réplica
(`route_pool`, 6 réplicas de entrenamiento del conjunto mixto valle + punta tarde).

## Observaciones $\Omega_i$, $O$

Observación local por fase (`PhaseObservation`): 22 columnas en $[0,1]$, con el mismo significado
en todos los cruces para que una sola red sirva a todos.

| Columnas | Contenido |
|---|---|
| 0–3 | Fase verde actual (one-hot) |
| 4–7 | Fases que existen en el cruce |
| 8 | Puede cambiar (ya cumplió el verde mínimo) |
| 9 | Tiempo en la fase / (verde máximo + amarillo) |
| 10–13 | Por fase: densidad media de las pistas que atiende |
| 14–17 | Por fase: cola media (vehículos detenidos) de esas pistas |
| 18–21 | Por fase: densidad media de las pistas a las que descarga |

Densidad = vehículos en la pista / vehículos que caben en ella (largo / (separación mínima +
largo del vehículo)). Cola = vehículos detenidos / los que caben. La observación es parcial: el
agente no ve más allá de sus pistas de entrada y salida, ni la demanda que viene, ni las fases de
los vecinos. $O$ es determinista dado $s$.

**MAPPO:** se agrega un bloque global de 11 columnas (`GlobalPhaseObservation`): densidad y cola
medias de los 4 semáforos controlados más cercanos (8), y la densidad media, la cola media y la
fracción de cruces con cola sobre todos los controlados (3). El actor lo recibe en cero
(`MaskedActorCriticPolicy`); solo lo usa el crítico.

## Recompensa $R_i$

Diferencia de espera acumulada (`diff-waiting-time` de sumo-rl), por agente:

$$r_i^t = W_i^{t-1} - W_i^t, \qquad W_i^t = \frac{1}{100} \sum_{\ell \in \text{entrada}(i)} \sum_{v \in \ell} w_v^t$$

donde $w_v^t$ es la espera acumulada del vehículo $v$ en esa pista. Es positiva cuando la espera
en las entradas baja. Cada agente optimiza su propia recompensa (no hay recompensa común), lo que
hace al problema un juego estocástico general y no un Dec-POMDP cooperativo puro. La cooperación
se induce por el parámetro compartido y, en MAPPO, por el crítico con información global.

## Horizonte y descuento

Episodios de $T = 3600$ s simulados (720 decisiones por agente, con 300 s de calentamiento en la
evaluación) y descuento $\gamma = 0{,}95$ (horizonte efectivo de ~20 decisiones, unos 100 s).

## Solución: IPPO y MAPPO con parámetros compartidos

| | IPPO | MAPPO |
|---|---|---|
| Política $\pi_\theta(a_i \mid o_i)$ | MLP 64-64 tanh, compartida | igual, con el bloque global en cero |
| Crítico | $V_\phi(o_i)$, local | $V_\phi(o_i, g_i)$, con información global |
| Entrenamiento | PPO-clip (Schulman et al., 2017), cada agente es una muestra del lote | igual |
| Ejecución | descentralizada | descentralizada (el actor no usa $g_i$) |

Hiperparámetros comunes (`train_rl.py`): Adam (ε = 1e-5), tasa 3e-4 con decaimiento lineal,
`n_steps` 256, lote 256, 10 épocas, GAE λ = 0,95, recorte 0,2, coeficiente de entropía 0,01,
gradiente máximo 0,5, 3 M de muestras y 3 semillas.

## Supuestos y limitaciones

* Sensores ideales: densidad y cola exactas por pista, como si hubiera detectores en toda la
  pista. En la calle serían espiras o cámaras con error.
* Sin comunicación entre agentes en la ejecución; la coordinación solo es implícita.
* Recompensa local: un agente puede mejorar su espera empujando cola a un vecino. La densidad de
  salida en la observación mitiga en parte esto.
* No se modelan peatones, buses con prioridad ni ciclovías; los cruces peatonales semaforizados
  siguen tiempo fijo.
