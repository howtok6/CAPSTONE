# Documentos de la tesis

Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente
Gabriel Cárdenas · Ingeniería en Informática, DUOC UC

Última actualización: 29 de octubre de 2026 (documentos agrupados por categoría).

Importancia: ★★★ esencial · ★★ referencia de trabajo · ★ consulta ocasional.

## Estado y entregables

| Archivo | Qué es | Importancia |
|---|---|---|
| `../ESTADO_DEL_PROYECTO.md` | Diagnóstico del estado actual, avance por objetivo, resultados preliminares y hoja de ruta. | ★★★ |
| `anteproyecto/Anteproyecto_Tesis_Semaforos_Adaptativos.docx` | Anteproyecto formal entregado al profesor guía. El `.pdf` es la misma versión. | ★★★ |
| `anteproyecto/01-anteproyecto-v1.md` | El mismo anteproyecto en texto plano, para buscar y citar. | ★★ |
| `informe/1.4 Informe -v1.docx` | Borrador del informe final de la tesis. | ★★★ |

## Decisiones registradas — `decisiones/`

| Archivo | Qué decide | Importancia |
|---|---|---|
| `07-decision-escenario.md` | Nivel comunal; MVP en el eje Alameda → Providencia → Apoquindo dentro de Santiago, Providencia y Las Condes. | ★★★ |
| `08-decision-tiempos-semaforicos.md` | Semáforos desde OSM; tiempos con Webster + terreno + calibración por tiempo de viaje. Por qué Waze no sirve. | ★★★ |
| `11-decision-agente.md` | PPO con parámetros compartidos, Adam (RMSprop alternativo), 64 semáforos controlados. | ★★★ |
| `10-decision-base-de-datos.md` | GeoPackage + GeoParquet + DuckDB; cuándo pasar a PostGIS. | ★★ |
| `02-windows-vs-wsl2.md` | Entorno: Windows nativo (corrige una recomendación anterior). | ★ |

## Datos — `datos/`

| Archivo | Qué es | Importancia |
|---|---|---|
| `09-protocolo-terreno.md` | Cruces a medir, calendario, procedimiento con video, formato de los CSV. | ★★★ |
| `06-fuentes-de-datos.md` | Fuentes de flujos, tiempos de viaje y programación semafórica; solicitud de transparencia lista. | ★★ |

## Entorno — `entorno/`

| Archivo | Qué es | Importancia |
|---|---|---|
| `04-entorno-y-stack.md` | Stack capa por capa, resultados de sanidad y trampas encontradas. | ★★ |
| `05-visualizacion.md` | Ver la simulación en vivo y grabar video. | ★ |
| `03-montaje-wsl2.md` | Runbook de WSL2. Solo si se migra (fase MAPPO). | ★ |

## Modelo UML — `uml/`

| Archivo | Qué es | Importancia |
|---|---|---|
| `uml/README.md` | Actores, catálogo de 22 casos de uso trazados a scripts y objetivos, y especificación de los principales. | ★★ |
| `uml/*.svg`, `uml/*.png` | Diagrama de actores, vista general y uno por subsistema (escenario, control, análisis). | ★★ |
| `uml/*.puml`, `uml/gen.py` | Fuentes PlantUML; `gen.py` regenera los cuatro diagramas de casos de uso desde un solo modelo. | ★ |

## Lo que sigue

La hoja de ruta vigente, con criterio de término por paso, está en la sección 8 de `../ESTADO_DEL_PROYECTO.md`.

## El código

Está en `../tsc-thesis/`. Su `README.md` explica cómo correr todo.
