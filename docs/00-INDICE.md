# Documentos de la tesis

Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente
Gabriel Cárdenas · Ingeniería en Informática, DUOC UC

Última actualización: 22 de octubre de 2026.

## Qué hay aquí

| Archivo | Qué es | Cuándo mirarlo |
|---|---|---|
| `../ESTADO_DEL_PROYECTO.md` | Diagnóstico exhaustivo del estado actual del proyecto, avance de objetivos, resultados preliminares y plan de acción. | Estado consolidado y avance a octubre de 2026. |
| `Anteproyecto_Tesis_Semaforos_Adaptativos.docx` | Anteproyecto formal, 18 páginas. Problema, objetivos, hipótesis, marco teórico, metodología, cronograma y bibliografía. | Es el documento que va al profesor guía. El `.pdf` es la misma versión, para leer sin Word. |
| `01-anteproyecto-v1.md` | El mismo anteproyecto en texto plano. | Para buscar, citar o copiar fragmentos sin abrir Word. |
| `02-windows-vs-wsl2.md` | Dónde montar el entorno, y la corrección de una recomendación anterior que estaba equivocada. | Decisión vigente: Windows nativo. |
| `03-montaje-wsl2.md` | Runbook paso a paso de WSL2, con verificación en cada paso. | Solo si migras a WSL2 (probablemente en la fase de MAPPO). |
| `04-entorno-y-stack.md` | El stack elegido capa por capa, la red comunal, resultados de sanidad y las trampas encontradas. | Referencia técnica general del proyecto. |
| `05-visualizacion.md` | Cómo ver la simulación en vivo y cómo grabar video. | Cuando quieras mirar o mostrar la ejecución. |
| `06-fuentes-de-datos.md` | De dónde sacar flujos, tiempos de viaje y programación real de semáforos, con la solicitud de transparencia lista. | Ahora. Las solicitudes tardan semanas. |
| `07-decision-escenario.md` | Paso a nivel comunal y alcance del MVP (eje Apoquindo → Providencia → Alameda), cobertura de las redes actuales y decisiones abiertas. | Antes de construir la red del eje o fijar cuántos semáforos controla el agente. |
| `08-decision-tiempos-semaforicos.md` | Ubicación de semáforos desde OSM y tiempos estimados (Webster + terreno + calibración por tiempo de viaje). Por qué Waze no sirve para inferir tiempos. | Al generar planes de tiempo fijo o justificar la metodología. |
| `09-protocolo-terreno.md` | Cruces a medir, calendario, procedimiento con video, formato de los CSV y control de calidad. | Antes y después de cada salida a terreno. |
| `10-decision-base-de-datos.md` | GeoPackage + GeoParquet + DuckDB para los datos de la tesis; cuándo pasar a PostGIS. | Al guardar resultados o capas del mapa. |

## Estado del proyecto

- **Red elegida:** nivel comunal. El MVP es el eje Alameda → Providencia → Apoquindo dentro de los límites de
  Santiago, Providencia y Las Condes: de Matucana al término de Av. Apoquindo (~13,5 km, ~86 puntos semaforizados).
  Hoy ninguna red incluye la Alameda ni Apoquindo al oriente de Alonso de Córdova; detalle en `07`.
- **Tiempos semafóricos:** ubicación desde OSM; tiempos estimados con Webster, anclados en una muestra de terreno de
  13 cruces y calibrados por tiempo de viaje (`08`, `09`).
- **Entorno:** Windows nativo. Todo el stack tiene rueda de Windows, incluido
  `libsumo`, y las pruebas ya pasan en esta máquina.
- **Pipeline:** funcionando de punta a punta — escenario, cuatro controladores
  clásicos, agente PPO, análisis estadístico y grabación de video.
- **Lo que bloquea:** depurar la geometría en `netedit` y conseguir datos de
  demanda reales. Ambos están detallados en `04` y `06`.

## Lo que sigue

La hoja de ruta vigente, con criterio de término por paso, está en la sección 8 de `../ESTADO_DEL_PROYECTO.md`. En corto:

1. Construir la red del eje completo Apoquindo → Providencia → Alameda hasta que `diagnose_net.py` la declare APTA.
2. Decidir si el agente controla solo los semáforos del eje o todos los de la red.
3. Arreglar el contador `phase_switches` y medir la cola de inserción en el arnés.
4. Regenerar los cuatro perfiles de demanda para la nueva red y validarlos contra datos observados (ver `06`).
5. Baselines completos con 10 semillas; luego entrenamiento IPPO y ablation de recompensa.
6. MAPPO con crítico centralizado.
7. Pruebas de robustez.

## El código

Está en `..\tsc-thesis\`. El `README.md` de esa carpeta explica cómo correr todo.
