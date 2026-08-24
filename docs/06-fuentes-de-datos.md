# Fuentes de datos reales para el corredor Apoquindo

Investigado el 24-ago-2026.
Página completa: https://claude.ai/code/artifact/28410e8c-42e6-4a0a-93fa-2d5090fbf678

## Distinción clave

**Calibrar** (ajustar la demanda para que el modelo reproduzca la realidad) necesita
flujos direccionales por intersección — difíciles de conseguir.
**Validar** (mostrar que el modelo calibrado se comporta como el corredor real)
necesita tiempos de viaje y velocidades observadas — están al alcance de inmediato.

Una tesis con calibración modesta y validación sólida se defiende. Al revés, no.

## Fuentes útiles, en orden de prioridad

| Fuente | Qué entrega | Cómo | Plazo |
|---|---|---|---|
| **UOCT / MTT** (Ley 20.285) | Programaciones semafóricas vigentes + registros de detectores = aforos reales | portaltransparencia.cl | 20 días hábiles + 10 |
| **Municipalidad Las Condes** | Estudios de tránsito propios; IMIV aprobados en la comuna | Portal transparencia municipal | Mismo marco |
| **IMIV / ex-EISTU** | Aforos direccionales medidos en terreno por intersección, hora punta | Transparencia a SEREMITT RM o municipio | Medio |
| **DTPM — posicionamiento de buses** | GPS de toda la flota cada minuto → velocidades y tiempos por tramo | Formulario en dtpm.cl | ~10 días hábiles |
| **DACoT** | Proyecto que digitalizó datos de semáforos de la UOCT RM | dacot.feriadesoftware.cl | Un correo |
| **Conteo propio en video** | Aforos por movimiento en 2–3 accesos clave | Terreno, 2 jornadas | Un fin de semana |
| **Tiempos típicos de Google Maps** | Curva de tiempo de viaje por franja horaria | Manual | Una tarde |
| **Observación de fases en calle** | Estructura real de fases de las 11 intersecciones | Terreno + cronómetro | Alto pero acotado |

## Descartadas — verificado

- **«Flujo Vehicular en el AMS» (OCUC, ArcGIS Hub)** — parece ideal pero NO sirve.
  Se consultó el FeatureServer: el campo `flujo_v_h` tiene solo **17 valores
  distintos** en toda la región (0, 111, 556, 1111, 1666, 2221, 3332…, casi todos
  múltiplos de 111). Es una variable clasificada, no mediciones. No citarla como
  fuente de aforos.
  Servicio: `services9.arcgis.com/kKJR3Qt68ohAWuet/.../Calculo_de_flujo_vehicular_en_AMS/FeatureServer`
- **transporteinforma.cl** (sitio público de la UOCT) — estado en tiempo real,
  incidentes y obras. Sin datos descargables, sin estadísticas, sin cámaras.
- **EOD SECTRA** — matriz de viajes por zona, no conteos por intersección. Sirve para
  repartir demanda, no como aforo.
- **Censos TMDA de Vialidad** — rutas interurbanas, fuera de escala.
- **simiv.cl, aimiv.cl y similares** — son consultoras que *elaboran* IMIV, no
  repositorios donde consultarlos. Salen primero al buscar y confunden.

## Solicitud de transparencia (texto para copiar)

Entrar a **portaltransparencia.cl**, elegir Ministerio de Transportes y
Telecomunicaciones — Subsecretaría de Transportes, y pegar esto ajustando el tramo:

```
Solicito la siguiente información referida a las intersecciones semaforizadas
de Avenida Apoquindo, comuna de Las Condes, en el tramo comprendido entre
[calle inicial] y [calle final]:

1. Programación semafórica vigente de cada una de esas intersecciones,
   incluyendo: estructura de fases y movimientos habilitados en cada fase,
   duración de ciclo, repartos de verde por fase y desfases entre
   intersecciones, para cada plan horario en operación (punta mañana,
   fuera de punta, punta tarde).

2. Registros de los detectores vehiculares asociados a esas intersecciones
   para una semana típica reciente, agregados en intervalos de 15 minutos,
   identificando el detector y el movimiento que mide.

3. Plano o listado que identifique la ubicación de los detectores en cada
   intersección.

Solicito la información en formato digital procesable (CSV, XLSX o el formato
nativo de exportación del sistema de control), no en PDF escaneado.

Esta información será utilizada exclusivamente con fines académicos, en el
marco de mi proyecto de título en Ingeniería en Informática en DUOC UC, sobre
control adaptativo de semáforos mediante simulación. Agradeceré que, en caso
de que parte de lo solicitado no esté disponible en el formato indicado, se
me entregue lo que sí lo esté, señalando qué no fue posible entregar.
```

**Por qué está redactada así.** El punto 3 parece menor y no lo es: sin saber dónde
está cada detector, los conteos del punto 2 no se pueden asociar a un movimiento y
quedan inservibles. El párrafo final evita el rechazo total por un ítem imposible.

Mandar la misma solicitud, adaptada, a la Municipalidad de Las Condes por su propio
portal, agregando un cuarto punto que pida los IMIV aprobados en el corredor en los
últimos cinco años, con sus anexos de aforos.

## Orden recomendado

1. **Esta semana:** enviar solicitudes (UOCT/MTT, Las Condes), formulario DTPM,
   correo a DACoT. Los relojes legales parten al enviar.
2. **Semanas 1–2:** definir tramo exacto y depurar geometría en netedit.
3. **Semanas 2–3:** terreno — estructura de fases de las 11 intersecciones y conteo
   en video de 2–3 accesos.
4. **Semana 3:** tiempos típicos de Google por franja horaria.
5. **Semanas 4–6:** calibrar con lo que llegó y declarar la fidelidad alcanzada.

## Si no llega nada

El diseño comparativo sigue válido: todos los controladores enfrentan la misma
demanda. Cambia el alcance de la conclusión, y eso va en limitaciones. Una negativa
formal también es citable: documentar qué se pidió, a quién y qué respondieron es una
observación legítima sobre disponibilidad de datos públicos de movilidad en Chile.

## Incógnita abierta

No se sabe si la UOCT entregará efectivamente los registros de detectores. No se
encontró ningún caso documentado, ni a favor ni en contra. Solo se resuelve enviando.
