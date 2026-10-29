**DUOC UC**

Escuela de Informática y Telecomunicaciones --- Ingeniería en
Informática

**ANTEPROYECTO DE TÍTULO**

**Control adaptativo de semáforos mediante aprendizaje por refuerzo
multi-agente**

*Evaluación comparativa frente a estrategias clásicas de control en una
red a nivel comunal de Santiago de Chile*

**Autor: Gabriel Ignacio Cárdenas Valdés**

Profesor guía: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Santiago de Chile --- 2026

**Índice**

*Al abrir el documento en Word, actualizar este índice con clic derecho
sobre él → Actualizar campos → Actualizar toda la tabla.*

**Resumen ejecutivo**

La congestión vehicular en las grandes ciudades es, en buena medida, un
problema de coordinación: la infraestructura existe, pero el reparto del
tiempo verde entre movimientos que compiten por la misma intersección
responde a planes fijos o semi-adaptativos que no se ajustan con la
rapidez suficiente a la demanda real. Este anteproyecto propone diseñar,
implementar y evaluar un sistema de control adaptativo de semáforos
basado en aprendizaje por refuerzo multi-agente (MARL), y contrastarlo
de manera rigurosa contra las estrategias de control clásicas que hoy
constituyen el estado de la práctica.

El trabajo se desarrollará íntegramente sobre simulación microscópica en
SUMO, usando como escenario un corredor real de Santiago de Chile
reconstruido desde OpenStreetMap y calibrado con datos públicos de
demanda. La contribución esperada no es un nuevo algoritmo de
aprendizaje profundo, sino evidencia experimental reproducible sobre
cuánto margen de mejora ofrece el control aprendido frente al control
clásico bien sintonizado, en una red urbana latinoamericana concreta y
bajo condiciones de demanda realistas.

**Enfoque seleccionado:** evaluación comparativa (planes de tiempo fijo,
Webster y Max-Pressure como líneas base) contra un agente MARL con
entrenamiento centralizado y ejecución descentralizada. Este diseño
garantiza resultados medibles aun si el agente aprendido no supera a los
baselines, lo que elimina el riesgo principal de una tesis basada
exclusivamente en aprendizaje profundo.

**1. Planteamiento del problema**

**1.1 Contexto**

El control de semáforos en las ciudades chilenas está a cargo de la
Unidad Operativa de Control de Tránsito (UOCT), organismo dependiente
del Ministerio de Transportes y Telecomunicaciones creado en 1990, con
cobertura en nueve regiones del país y sede nacional en Providencia,
Santiago. La UOCT monitorea en tiempo real la operación de la mayoría de
los semáforos de las ciudades bajo su gestión mediante una red de
comunicaciones dedicada, y opera sobre plataformas de control
centralizado de tipo UTC/SCATS.

Estos sistemas representan un avance sustantivo respecto del control de
tiempo fijo: ajustan duración de ciclo, reparto de verdes y desfases
entre intersecciones a partir de mediciones de lazos detectores. Sin
embargo, operan dentro de un espacio de planes predefinidos y con
lógicas heurísticas diseñadas décadas atrás, lo que limita su capacidad
de reaccionar a patrones de demanda que se desvían de los históricos:
cortes de calles, eventos masivos, incidentes o cambios estructurales en
la partición modal.

**1.2 Problema de investigación**

El problema abordado es el siguiente: los esquemas de control de
semáforos actualmente desplegados asignan tiempo verde a partir de
reglas fijas o de un catálogo acotado de planes, y por lo tanto no
explotan toda la información disponible sobre el estado instantáneo de
la red. Esto se traduce en demoras evitables, colas que se propagan
aguas arriba y, en casos extremos, bloqueo de intersecciones.

La literatura reciente sostiene que un controlador que aprende una
política de conmutación de fases directamente desde el estado observado
de la red puede superar a los esquemas clásicos, pero la evidencia
proviene mayoritariamente de redes sintéticas o de escenarios calibrados
sobre ciudades europeas y chinas. No existe evidencia sistemática y
reproducible sobre el desempeño relativo de estas técnicas en la
geometría vial, la composición del parque vehicular y los patrones de
demanda característicos de Santiago de Chile.

**1.3 Preguntas de investigación**

1.  **PI1.** ¿Qué mejora porcentual en demora media por vehículo y en
    tiempo de viaje logra un controlador basado en aprendizaje por
    refuerzo multi-agente frente a planes de tiempo fijo, Webster y
    Max-Pressure, sobre un corredor real de Santiago?

2.  **PI2.** ¿Cómo varía esa ventaja según el nivel de demanda (valle,
    punta mañana, punta tarde y demanda sobresaturada)?

3.  **PI3.** ¿Qué esquema de coordinación entre agentes (aprendizaje
    independiente, entrenamiento centralizado con ejecución
    descentralizada, o comunicación basada en grafos) ofrece el mejor
    compromiso entre desempeño y costo computacional para una red de
    escala media?

4.  **PI4.** ¿Qué robustez presenta la política aprendida ante
    perturbaciones no vistas en entrenamiento, como el cierre de un
    carril o un aumento repentino de la demanda?

**1.4 Justificación**

-   **Relevancia social y económica.** La congestión impone costos
    directos en tiempo de viaje, consumo de combustible y emisiones. Una
    mejora marginal en el reparto de verdes, replicada sobre cientos de
    intersecciones, tiene un impacto agregado no despreciable y no
    requiere obra civil.

-   **Relevancia técnica.** El control adaptativo aprendido es un caso
    de estudio canónico de sistemas multi-agente con observabilidad
    parcial, y permite ejercitar de forma integrada simulación,
    ingeniería de datos, aprendizaje profundo y diseño experimental.

-   **Vacío identificado.** Los benchmarks de referencia del área
    utilizan escenarios de Hangzhou, Jinan, Colonia e Ingolstadt.
    Aportar un escenario santiaguino calibrado y publicado abre la
    puerta a comparaciones futuras y constituye en sí mismo un artefacto
    reutilizable.

-   **Factibilidad.** Todo el trabajo se realiza en simulación, con
    herramientas de código abierto y sin necesidad de convenios
    institucionales ni de intervención sobre infraestructura real.

**2. Objetivos e hipótesis**

**2.1 Objetivo general**

**Diseñar, implementar y evaluar experimentalmente un sistema de control
adaptativo de semáforos basado en aprendizaje por refuerzo multi-agente,
cuantificando su desempeño frente a estrategias de control clásicas
sobre un corredor urbano real de Santiago de Chile simulado en SUMO.**

**2.2 Objetivos específicos**

Cada objetivo específico se formula de modo verificable y con un
producto asociado.

  ----------------------------------------------------------------------------
  **N.º**   **Objetivo específico**           **Producto verificable**
  --------- --------------------------------- --------------------------------
  OE1       Construir y calibrar un escenario Red SUMO (.net.xml), matriz de
            de simulación microscópica de un  demanda y archivos de ruta
            corredor de Santiago con al menos versionados en el repositorio,
            ocho intersecciones               con reporte de calibración.
            semaforizadas, a partir de datos  
            de OpenStreetMap y de fuentes     
            públicas de demanda.              

  OE2       Implementar tres controladores de Módulos de control ejecutables y
            referencia: plan de tiempo fijo,  reproducibles, con pruebas
            plan optimizado según el método   unitarias sobre la lógica de
            de Webster y controlador          conmutación de fases.
            Max-Pressure.                     

  OE3       Formular el control de la red     Especificación formal
            como un problema de decisión de   documentada e implementada como
            Markov descentralizado,           entorno compatible con
            definiendo espacio de             PettingZoo.
            observación, espacio de acción y  
            función de recompensa por         
            intersección.                     

  OE4       Entrenar y ajustar al menos dos   Políticas entrenadas, curvas de
            configuraciones de agentes MARL   aprendizaje y registro de
            (aprendizaje independiente y      hiperparámetros.
            entrenamiento centralizado con    
            ejecución descentralizada).       

  OE5       Evaluar comparativamente todos    Protocolo experimental, tablas
            los controladores bajo escenarios de resultados con intervalos de
            de demanda diferenciados, con     confianza y pruebas de
            réplicas independientes y         hipótesis.
            análisis estadístico de           
            significancia.                    

  OE6       Analizar la robustez de la        Batería de escenarios de
            política aprendida ante           perturbación y análisis de
            perturbaciones no presentes en el degradación del desempeño.
            entrenamiento.                    

  OE7       Documentar hallazgos,             Informe final de tesis y
            limitaciones y condiciones bajo   repositorio reproducible.
            las cuales el enfoque aprendido   
            resulta o no ventajoso.           
  ----------------------------------------------------------------------------

**2.3 Hipótesis**

**H1.** Un controlador basado en aprendizaje por refuerzo multi-agente
reduce la demora media por vehículo en al menos un 10 % respecto de un
plan de tiempo fijo optimizado con el método de Webster, bajo
condiciones de demanda de hora punta, con significancia estadística al
95 %.

**H2.** La ventaja del controlador aprendido sobre Max-Pressure es menor
que su ventaja sobre el tiempo fijo, y se concentra en regímenes de
demanda cercanos a la saturación.

**H3.** Los esquemas de entrenamiento centralizado con ejecución
descentralizada superan al aprendizaje independiente en métricas de red,
a costa de un mayor tiempo de entrenamiento.

*Nota metodológica: el umbral del 10 % en H1 es una hipótesis a
contrastar, no un resultado comprometido. Un resultado negativo bien
fundamentado (por ejemplo, que Max-Pressure iguale al agente aprendido
con una fracción del costo computacional) constituye un hallazgo válido
y publicable, y así se declara desde el diseño.*

**3. Marco teórico y estado del arte**

**3.1 Fundamentos del control de intersecciones semaforizadas**

Una intersección semaforizada reparte un recurso escaso ---el derecho de
paso--- entre movimientos incompatibles. Los conceptos operativos
centrales son la fase (conjunto de movimientos que reciben verde
simultáneamente), el ciclo (tiempo que toma recorrer todas las fases),
el reparto o split (fracción del ciclo asignada a cada fase), el desfase
u offset (corrimiento temporal entre intersecciones vecinas) y el tiempo
perdido asociado a los intervalos de ámbar y rojo total.

**3.1.1 Control de tiempo fijo y método de Webster**

El control de tiempo fijo aplica un plan invariante derivado de aforos
históricos. La formulación clásica de Webster (1958) entrega la duración
de ciclo que minimiza la demora total en función del tiempo perdido por
ciclo y de los grados de saturación de cada fase, junto con un reparto
proporcional a dichos grados. Es un método analítico, barato y
sorprendentemente competitivo cuando la demanda es estable, razón por la
cual constituye una línea base obligatoria.

**3.1.2 Control actuado y adaptativo desplegado**

Los sistemas actuados extienden el verde mientras los detectores
registran demanda continua. Los sistemas centralizados de tipo UTC
---SCATS y SCOOT, entre otros--- seleccionan o interpolan planes en
función de mediciones agregadas y coordinan desfases a lo largo de
corredores. Esta familia es la que opera en Chile bajo la administración
de la UOCT y define el estado de la práctica contra el cual debe medirse
cualquier propuesta.

**3.1.3 Max-Pressure**

Max-Pressure, formalizado por Varaiya (2013) a partir de resultados de
control de redes de colas, selecciona en cada instante de decisión la
fase que maximiza la diferencia entre las colas aguas arriba y aguas
abajo de los movimientos habilitados. Su atractivo es doble: es
descentralizado ---cada intersección decide con información local--- y
cuenta con una garantía teórica de estabilidad, en el sentido de
maximizar la región de demandas para las cuales las colas permanecen
acotadas. Sus limitaciones prácticas conocidas incluyen el supuesto de
colas ilimitadas aguas abajo, la ausencia de coordinación explícita de
progresión y la penalización insuficiente de los cambios frecuentes de
fase, aspecto abordado por trabajos posteriores que incorporan la
pérdida por conmutación.

**3.2 Aprendizaje por refuerzo aplicado al control de semáforos**

El control de una intersección se modela naturalmente como un proceso de
decisión de Markov: el agente observa un estado (densidades y colas por
carril, fase actual, tiempo transcurrido en la fase), escoge una acción
(mantener la fase o conmutar a otra fase del conjunto admisible) y
recibe una recompensa que penaliza demora, colas o detenciones. Los
algoritmos de valor tipo DQN (Mnih et al., 2015) y de política tipo PPO
(Schulman et al., 2017) son los más utilizados en el área.

Cuando el problema se extiende a una red, aparece la dimensión
multi-agente. La literatura reciente organiza las soluciones en tres
familias:

-   **Aprendizaje independiente (DTDE).** Cada intersección entrena su
    propia política con observación local y sin comunicación. Es simple
    y escala linealmente, pero sufre de no estacionariedad: desde la
    perspectiva de cada agente, el entorno cambia cuando los demás
    aprenden.

-   **Entrenamiento centralizado, ejecución descentralizada (CTDE).**
    Métodos como QMIX, VDN, MADDPG o MAPPO utilizan información global
    durante el entrenamiento ---una función de valor conjunta o un
    crítico centralizado--- pero cada agente ejecuta con información
    local. Mitiga la no estacionariedad y el problema de asignación de
    crédito.

-   **Métodos basados en grafos y comunicación.** PressLight (Wei et
    al., 2019) incorpora la noción de presión de Max-Pressure en la
    función de recompensa del agente aprendido; CoLight (Wei et
    al., 2019) usa atención sobre el grafo de vecindad para que cada
    intersección pondere la influencia de sus vecinas. Son el estado del
    arte en desempeño de red, con mayor costo de implementación.

**3.3 Simuladores y benchmarks**

SUMO (Simulation of Urban MObility), desarrollado por el DLR alemán, es
el simulador microscópico de código abierto más utilizado en
investigación de control de semáforos; expone la interfaz TraCI/libsumo
para control en línea. Sobre él se han construido entornos
estandarizados de aprendizaje: sumo-rl expone la simulación como entorno
Gymnasium (agente único) y PettingZoo (multi-agente), con observación
por defecto compuesta por codificación one-hot de la fase, indicador de
verde mínimo, densidad y cola por carril, y recompensa basada en la
variación de la demora acumulada; es compatible con Stable-Baselines3 y
RLlib y se distribuye bajo licencia MIT. RESCO (Ault y Sharon, 2021)
provee un conjunto de escenarios y líneas base estandarizadas para
comparación reproducible, incluyendo redes calibradas de Colonia e
Ingolstadt.

**3.4 Brechas identificadas**

Las revisiones sistemáticas recientes del área (por ejemplo, Donatus et
al., 2025) coinciden en señalar como desafíos abiertos la escalabilidad
ante el crecimiento exponencial del espacio conjunto de estados y
acciones, la no estacionariedad del aprendizaje simultáneo, la
asignación de crédito individual sobre objetivos colectivos, la
transferencia de simulación a infraestructura real y el diseño de
funciones de recompensa. A ello se suma, desde la perspectiva de esta
tesis, una brecha geográfica: la escasez de escenarios calibrados y de
resultados comparativos publicados sobre redes latinoamericanas.

**4. Selección del enfoque técnico**

Se evaluaron tres alternativas de enfoque antes de fijar la metodología.
El criterio de decisión combina valor académico del aporte, riesgo de no
obtener resultados y ajuste a la disponibilidad de tiempo declarada
(aproximadamente seis meses con dedicación parcial, del orden de 240
horas efectivas).

+-------------+------------------+------------------+------------------+
| **Al        | **Fortalezas**   | **Riesgos**      | **Ajuste al      |
| ternativa** |                  |                  | proyecto**       |
+=============+==================+==================+==================+
| A. MARL     | Máximo valor     | Si el agente no  | Alto riesgo para |
| puro como   | académico.       | supera a los     | un plazo acotado |
| único       |                  | baselines, la    | y sin cluster de |
| aporte      | Alineado con la  | tesis queda sin  | cómputo.         |
|             | frontera del     | resultado.       |                  |
|             | área.            |                  |                  |
|             |                  | Entrenamiento    |                  |
|             |                  | costoso y        |                  |
|             |                  | sensible a       |                  |
|             |                  | hiperparámetros. |                  |
+-------------+------------------+------------------+------------------+
| B.          | Implementación   | Aporte           | Bajo riesgo,     |
| Algoritmos  | directa.         | incremental      | pero también     |
| clásicos y  |                  | bajo.            | bajo valor       |
| meta        | Resultados       |                  | diferenciador.   |
| heurísticas | garantizados.    | Terreno muy      |                  |
|             |                  | explorado desde  |                  |
|             | Fácil de         | los años 60.     |                  |
|             | defender.        |                  |                  |
+-------------+------------------+------------------+------------------+
| C.          | Resultados       | Mayor volumen de | Ajuste adecuado: |
| Comparativa | asegurados por   | implementación.  | el riesgo se     |
| rigurosa    | los baselines.   |                  | concentra en una |
| clásicos    |                  | Exige disciplina | componente y no  |
| vs. MARL    | El agente MARL   | en el diseño     | compromete la    |
|             | aporta la        | experimental.    | tesis completa.  |
|             | componente de    |                  |                  |
|             | innovación.      |                  |                  |
|             |                  |                  |                  |
|             | El escenario     |                  |                  |
|             | calibrado es un  |                  |                  |
|             | artefacto        |                  |                  |
|             | reutilizable.    |                  |                  |
+-------------+------------------+------------------+------------------+

**Enfoque adoptado: alternativa C.** El núcleo del aporte es el agente
MARL con coordinación CTDE, pero el diseño se estructura de modo que las
líneas base clásicas ---tiempo fijo, Webster y Max-Pressure--- sean
resultados de primera clase y no meros puntos de comparación. Si el
agente aprendido supera a los baselines, la tesis reporta una mejora
cuantificada sobre una red santiaguina real; si no lo hace, reporta bajo
qué condiciones el control clásico bien sintonizado sigue siendo
competitivo, lo cual es un hallazgo igualmente valioso y menos frecuente
en la literatura publicada.

**5. Metodología**

**5.1 Tipo de investigación**

Investigación aplicada, de carácter cuantitativo y experimental, con
diseño comparativo de tratamientos (controladores) sobre un mismo
entorno simulado, con réplicas independientes y control de variables
exógenas mediante semillas aleatorias fijadas.

**5.2 Escenario de simulación**

Se trabajará sobre un corredor arterial real de Santiago con entre ocho
y doce intersecciones semaforizadas consecutivas ---se evaluarán como
candidatos diferentes ejes y redes viales a nivel comunal, abarcando 
información de tránsito de todas las comunas de Santiago---,
seleccionado según tres criterios: densidad de intersecciones
semaforizadas, disponibilidad de información pública de demanda y
presencia de congestión recurrente documentada.

**5.2.1 Construcción de la red**

1.  Extracción de la geometría vial desde OpenStreetMap y conversión a
    formato SUMO mediante netconvert / osmWebWizard.

2.  Depuración manual en netedit: corrección de conectividad, número de
    carriles, movimientos permitidos, prioridades y geometría de las
    intersecciones.

3.  Definición de programas semafóricos base a partir de la estructura
    de fases observable en terreno o en imágenes satelitales y de calle.

4.  Verificación de que la red simula sin bloqueos ni advertencias de
    teletransporte bajo demanda baja.

**5.2.2 Demanda vehicular**

La demanda se construirá en dos capas. La primera es una estimación de
flujos por acceso a partir de fuentes públicas: la Encuesta Origen
Destino de Viajes del Gran Santiago publicada por SECTRA, los conjuntos
de datos de movilidad del portal de datos abiertos del Estado y los
antecedentes de aforos disponibles. La segunda es un ajuste iterativo
mediante las herramientas de calibración de SUMO, de modo que los flujos
simulados en secciones de control reproduzcan los volúmenes de
referencia dentro de una tolerancia declarada.

**Advertencia de factibilidad:** la disponibilidad de aforos
direccionales por intersección para Santiago no está garantizada al
inicio del proyecto. El plan de contingencia consiste en calibrar contra
volúmenes agregados por eje y declarar explícitamente el nivel de
fidelidad alcanzado; el diseño comparativo sigue siendo válido, porque
todos los controladores se enfrentan a la misma demanda.

Se definirán cuatro perfiles de demanda: valle, punta mañana, punta
tarde y un escenario de sobresaturación construido escalando la punta
más alta, destinado a estresar los controladores fuera del régimen para
el que fueron sintonizados.

**5.3 Formulación del problema de aprendizaje**

  ------------------------------------------------------------------------
  **Componente**   **Definición propuesta**
  ---------------- -------------------------------------------------------
  Agentes          Un agente por intersección semaforizada. Se explorará
                   adicionalmente el agrupamiento de intersecciones muy
                   cercanas en un agente único.

  Observación      Por agente: codificación one-hot de la fase activa,
                   tiempo transcurrido en la fase, indicador de verde
                   mínimo cumplido, densidad de ocupación y longitud de
                   cola por carril de aproximación. Variante extendida:
                   agregado de las colas de las intersecciones vecinas
                   inmediatas.

  Acción           Espacio discreto sobre el conjunto de fases admisibles:
                   elegir la próxima fase verde cada intervalo de decisión
                   (valor inicial 5 s), con inserción automática de ámbar
                   y rojo total al conmutar, y respeto de verde mínimo y
                   máximo.

  Recompensa       Línea base: variación negativa de la demora acumulada
                   entre pasos de decisión. Variantes a evaluar: presión
                   de la intersección en el sentido de Max-Pressure, y una
                   combinación penalizada por número de conmutaciones.

  Restricciones de Verde mínimo, verde máximo, secuencia de fases
  seguridad        admisible y tiempos de despeje se imponen como
                   restricciones duras del entorno, no como penalizaciones
                   aprendidas.
  ------------------------------------------------------------------------

**5.4 Controladores a implementar**

  ------------------------------------------------------------------------------
  **Controlador**   **Tipo**                 **Rol en el experimento**
  ----------------- ------------------------ -----------------------------------
  FIXED             Tiempo fijo con el plan  Piso de comparación; representa la
                    base de la red.          operación no optimizada.

  WEBSTER           Tiempo fijo con ciclo y  Línea base fuerte y justa: es lo
                    repartos calculados por  mínimo que un ingeniero de tránsito
                    el método de Webster     haría.
                    para cada perfil de      
                    demanda.                 

  MAXPRESSURE       Descentralizado, sin     Estado del arte no aprendido; la
                    aprendizaje, con         comparación más exigente.
                    garantía teórica de      
                    estabilidad.             

  IQL / IPPO        MARL con aprendizaje     Establece cuánto aporta el
                    independiente por        aprendizaje sin coordinación
                    intersección.            explícita.

  MAPPO (CTDE)      MARL con crítico         Configuración principal del aporte
                    centralizado y ejecución de la tesis.
                    descentralizada.         
  ------------------------------------------------------------------------------

**5.5 Métricas de evaluación**

-   **Primarias:** demora media por vehículo (s), tiempo de viaje
    medio (s) y tiempo de espera total en la red.

-   **Secundarias:** longitud media y máxima de cola por acceso,
    throughput (vehículos que completan su ruta por hora), número medio
    de detenciones por vehículo y velocidad media de recorrido.

-   **Externalidades:** consumo de combustible y emisiones de CO₂ y NOx,
    estimadas con los modelos HBEFA incorporados en SUMO.

-   **Equidad:** percentil 95 del tiempo de espera, para detectar
    políticas que optimizan el promedio a costa de penalizar
    sistemáticamente los movimientos menores.

-   **Costo:** tiempo de entrenamiento, número de pasos de simulación
    consumidos y tiempo de inferencia por decisión.

**5.6 Diseño experimental**

1.  Cada combinación de controlador y perfil de demanda se ejecuta con
    al menos treinta semillas aleatorias independientes, idénticas entre
    controladores para permitir comparación pareada.

2.  Se descarta un período de calentamiento inicial de la simulación
    antes de comenzar a registrar métricas.

3.  Los agentes se entrenan sobre un conjunto de semillas y se evalúan
    sobre un conjunto disjunto, para evitar sobreajuste al escenario
    concreto.

4.  Las diferencias entre controladores se contrastan con pruebas no
    paramétricas (Wilcoxon para muestras pareadas), reportando tamaño de
    efecto e intervalos de confianza al 95 %, y no solamente el valor p.

5.  Todos los experimentos se ejecutan mediante scripts parametrizados,
    con semillas, versiones e hiperparámetros registrados, de modo que
    cualquier tabla del informe pueda regenerarse desde el repositorio.

**5.7 Pruebas de robustez**

Sobre la mejor política aprendida se aplicarán perturbaciones no vistas
durante el entrenamiento: cierre de un carril en un tramo del corredor,
incremento súbito del 30 % en la demanda de un acceso, falla simulada de
un detector con observación degradada, e inserción de vehículos pesados
o de transporte público con paradas. Se reportará la degradación
relativa del desempeño frente a Max-Pressure bajo las mismas
perturbaciones.

**5.8 Stack tecnológico**

  -----------------------------------------------------------------------
  **Componente**      **Herramienta**
  ------------------- ---------------------------------------------------
  Simulación          SUMO (Eclipse), con libsumo para acelerar el
  microscópica        entrenamiento.

  Entorno de          sumo-rl (interfaces Gymnasium y PettingZoo,
  aprendizaje         licencia MIT).

  Algoritmos de RL    Stable-Baselines3 y Ray RLlib para las variantes
                      multi-agente.

  Lenguaje y análisis Python 3.11+, NumPy, pandas, SciPy, Matplotlib.

  Seguimiento de      MLflow o Weights & Biases para registro de corridas
  experimentos        e hiperparámetros.

  Control de          Git, con el escenario, el código y los scripts de
  versiones           análisis en un único repositorio.

  Cómputo             Estación local para desarrollo; entrenamiento en
                      instancias con GPU bajo demanda si el costo lo
                      justifica.
  -----------------------------------------------------------------------

**6. Alcance y limitaciones**

**6.1 Dentro del alcance**

-   Construcción y calibración de un escenario de simulación de un
    corredor real de Santiago.

-   Implementación de tres controladores clásicos y al menos dos
    configuraciones de agentes MARL.

-   Evaluación comparativa cuantitativa con análisis estadístico y
    pruebas de robustez.

-   Repositorio reproducible con escenario, código, configuraciones y
    scripts de análisis.

**6.2 Fuera del alcance**

-   Despliegue en infraestructura real o integración con los sistemas
    operativos de la UOCT.

-   Control de vehículos conectados o autónomos; se asume una flota
    convencional conducida por personas.

-   Optimización conjunta con otros modos de gestión (tarificación vial,
    gestión de estacionamientos, prioridad activa de buses más allá de
    su modelamiento como vehículos).

-   Modelamiento detallado del comportamiento peatonal más allá de las
    fases peatonales necesarias para la validez del plan.

-   Predicción de demanda a partir de datos históricos como línea de
    investigación independiente.

**6.3 Limitaciones reconocidas**

-   **Brecha simulación--realidad.** Los resultados son válidos dentro
    del modelo de simulación. La transferencia a operación real requiere
    validación adicional que excede este trabajo y así se declarará en
    las conclusiones.

-   **Calidad de la calibración.** La fidelidad del escenario está
    acotada por la granularidad de los datos públicos disponibles.

-   **Escala.** Un corredor de ocho a doce intersecciones no permite
    extrapolar directamente a la red completa de Santiago, que involucra
    miles de intersecciones.

-   **Supuesto de observabilidad.** Se asume disponibilidad de
    mediciones de cola y densidad por carril, superior a la
    instrumentación de lazos actualmente desplegada. Se incluirá al
    menos un experimento con observación degradada para dimensionar el
    efecto de este supuesto.

**7. Plan de trabajo y cronograma**

El plan considera el desarrollo hasta diciembre de este año (2026), con una dedicación aproximada de
diez horas semanales. Se
organiza en hitos verificables, cada uno con un entregable que permite
al profesor guía evaluar avance sin depender de la percepción del autor.

+------+-------------------+-----------------------+------------------+
| **M  | **Fase**          | **Actividades         | **Entregable /   |
| es** |                   | principales**         | hito**           |
+======+===================+=======================+==================+
| Sep  | Fundamentos y     | Revisión, instalación | H1: Red SUMO     |
|      | líneas base       | del stack. Selección  | funcional y      |
|      |                   | y depuración de red.  | baselines (FIXED |
|      |                   | Recolección de datos  | y WEBSTER).      |
|      |                   | y calibración.        |                  |
+------+-------------------+-----------------------+------------------+
| Oct  | Max-Pressure y    | Max-Pressure,         | H2: Los tres     |
|      | entorno RL        | formulación del       | baselines        |
|      |                   | Dec-POMDP e           | listos + entorno |
|      |                   | integración con       | RL con           |
|      |                   | sumo-rl y PettingZoo. | entrenamiento    |
|      |                   | Entrenamiento MARL.   | IQL/IPPO inicial |
+------+-------------------+-----------------------+------------------+
| Nov  | CTDE y            | Implementación de     | H3: Tablas de    |
|      | experimentación   | MAPPO. Ejecución de   | resultados       |
|      |                   | la batería completa   | completas con    |
|      |                   | con réplicas.         | análisis         |
|      |                   | Pruebas de robustez.  | estadístico.     |
+------+-------------------+-----------------------+------------------+
| Dic  | Análisis y        | Análisis e            | H4: Informe      |
|      | redacción         | interpretación.       | final,           |
|      |                   | Redacción del informe | repositorio y    |
|      |                   | final. Limpieza del   | presentación.    |
|      |                   | repo y defensa.       |                  |
+------+-------------------+-----------------------+------------------+

**Regla de corte:** si al término de noviembre no se dispone de una
política aprendida que al menos iguale al plan de tiempo fijo, se
congela la exploración de arquitecturas y se redirige el esfuerzo hacia
la profundización del análisis comparativo entre los controladores
clásicos y las variantes de recompensa. Esto protege la entrega del
informe frente al riesgo principal del proyecto.

**8. Análisis de riesgos**

  ----------------------------------------------------------------------------------
  **Riesgo**         **Prob.**   **Impacto**   **Mitigación**
  ------------------ ----------- ------------- -------------------------------------
  No se obtienen     Alta        Medio         Calibrar con volúmenes agregados y
  datos de demanda                             declarar el nivel de fidelidad. El
  con granularidad                             diseño comparativo permanece válido
  suficiente para el                           porque todos los controladores
  corredor elegido.                            enfrentan la misma demanda.

  El entrenamiento   Media       Alto          Partir de una sola intersección antes
  MARL no converge o                           de escalar; reutilizar
  resulta inestable.                           hiperparámetros publicados en sumo-rl
                                               y RESCO; aplicar la regla de corte
                                               del mes 4.

  Costo              Media       Medio         Usar libsumo en lugar de TraCI
  computacional del                            (aceleración cercana a un orden de
  entrenamiento                                magnitud); reducir la resolución
  superior al                                  temporal de decisión; acotar el
  previsto.                                    número de intersecciones.

  La red importada   Media       Medio         Reservar tiempo explícito de
  desde OSM presenta                           depuración en netedit durante el mes
  errores de                                   1; considerar un corredor alternativo
  conectividad                                 más simple como respaldo.
  difíciles de                                 
  depurar.                                     

  El agente          Media       Bajo          Está contemplado en el diseño: se
  aprendido no                                 reporta como hallazgo, con análisis
  supera a                                     de las condiciones bajo las cuales
  Max-Pressure.                                cada enfoque domina.

  Sobrecarga por     Media       Alto          Hitos mensuales con entregables
  trabajo y carga                              acotados; el alcance del mes 5 es el
  académica                                    primer candidato a reducción si se
  paralela.                                    acumula atraso.
  ----------------------------------------------------------------------------------

**9. Resultados esperados y contribución**

-   **Un escenario de simulación calibrado** de un corredor de Santiago,
    publicado como artefacto reutilizable, inexistente hoy en los
    benchmarks del área.

-   **Evidencia cuantitativa y estadísticamente respaldada** del
    desempeño relativo de cinco estrategias de control sobre una red
    urbana latinoamericana, en cuatro regímenes de demanda.

-   **Una caracterización de las condiciones** bajo las cuales el
    control aprendido justifica su complejidad frente a Max-Pressure,
    que es descentralizado, sin entrenamiento y con garantías teóricas.

-   **Un repositorio reproducible** que permita a terceros regenerar
    cada resultado del informe.

-   **Una discusión fundamentada sobre viabilidad de despliegue,**
    incluyendo requerimientos de instrumentación y la brecha entre los
    supuestos de observabilidad del modelo y la infraestructura
    efectivamente disponible en Santiago.

**Referencias preliminares**

*Listado de partida, a ampliar durante la revisión bibliográfica del
mes 1. Las referencias deben verificarse y normalizarse al formato
exigido por la escuela antes de la entrega formal.*

Ault, J., & Sharon, G. (2021). Reinforcement Learning Benchmarks for
Traffic Signal Control. Proceedings of the 35th Conference on Neural
Information Processing Systems (NeurIPS), Datasets and Benchmarks Track.

Alegre, L. N. (2019). SUMO-RL: Reinforcement Learning environments for
Traffic Signal Control with SUMO. Repositorio de software, licencia MIT.
https://github.com/LucasAlegre/sumo-rl

Donatus, R. E., Ter, K., & Udekwe, D. (2025). Multi-Agent Reinforcement
Learning in Intelligent Transportation Systems: A Comprehensive Survey.
arXiv:2508.20315.

Lopez, P. A., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd,
Y.-P., Hilbrich, R., Lücken, L., Rummel, J., Wagner, P., & Wießner, E.
(2018). Microscopic Traffic Simulation using SUMO. IEEE International
Conference on Intelligent Transportation Systems (ITSC), 2575--2582.

Mnih, V., Kavukcuoglu, K., Silver, D., et al. (2015). Human-level
control through deep reinforcement learning. Nature, 518(7540),
529--533.

Schulman, J., Wolski, F., Dhariwal, P., Radford, A., & Klimov, O.
(2017). Proximal Policy Optimization Algorithms. arXiv:1707.06347.

Varaiya, P. (2013). Max pressure control of a network of signalized
intersections. Transportation Research Part C: Emerging Technologies,
36, 177--195.

Webster, F. V. (1958). Traffic Signal Settings. Road Research Technical
Paper No. 39. Her Majesty\'s Stationery Office, Londres.

Wei, H., Chen, C., Zheng, G., Wu, K., Gayah, V., Xu, K., & Li, Z.
(2019). PressLight: Learning Max Pressure Control to Coordinate Traffic
Signals in Arterial Network. Proceedings of the 25th ACM SIGKDD
International Conference on Knowledge Discovery & Data Mining.

Wei, H., Xu, N., Zhang, H., Zheng, G., Zang, X., Chen, C., Zhang, W.,
Zhu, Y., Xu, K., & Li, Z. (2019). CoLight: Learning Network-level
Cooperation for Traffic Signal Control. Proceedings of the 28th ACM
International Conference on Information and Knowledge Management (CIKM).

Zhang, L., Wu, Q., Shen, J., Lü, L., Du, B., & Wu, J. (2022). Expression
might be enough: representing pressure and demand for reinforcement
learning based traffic signal control. Proceedings of the 39th
International Conference on Machine Learning (ICML), PMLR 162.

SECTRA --- Secretaría de Planificación de Transporte, Ministerio de
Transportes y Telecomunicaciones de Chile. Encuesta Origen Destino de
Viajes del Gran Santiago. https://www.sectra.gob.cl/

Unidad Operativa de Control de Tránsito (UOCT), Ministerio de
Transportes y Telecomunicaciones de Chile. https://www.uoct.cl/

Eclipse SUMO. Documentación oficial: importación desde OpenStreetMap y
calibración de demanda. https://sumo.dlr.de/docs/
