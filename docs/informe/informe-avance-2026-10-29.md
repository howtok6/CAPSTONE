# Informe de avance — 15 al 29 de octubre de 2026

**Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente**

29 de octubre de 2026 · Gabriel Ignacio Cárdenas Valdés

> Versión exportada del documento vivo: https://claude.ai/artifact/RbuspZdgx2DShjT8SW9UNW

## Resumen

En estas dos semanas el proyecto fijó su alcance definitivo y construyó la red del MVP: el eje Alameda → Providencia → Apoquindo, de Matucana a Camino El Alba, con 86 semáforos, de los cuales el agente controla los 64 del eje. Sobre esa red ya funcionan el plan Webster coordinado y el entrenamiento del agente.

- **Decisiones cerradas:** escenario comunal, fuente de los tiempos semafóricos, almacenamiento de datos, configuración del agente y plazo de entrega (diciembre de 2026).
- **Código:** el arnés de medición cuenta conmutaciones y la demora de vehículos no terminados; las pruebas automatizadas pasaron de 13 a 27, todas en verde.
- **Orden:** el informe de estado se corrigió contra el repositorio (avance global reestimado de ~75 % a ~45 %), el repositorio quedó organizado por categoría y se agregó el modelo UML de casos de uso.
- **Bloqueo principal:** la demanda sigue siendo sintética y la medición en terreno aún no comienza; sin eso no hay resultados de tesis, solo pruebas del arnés.

Se registraron 14 commits entre el 22 y el 29 de octubre, que incluyen el respaldo del trabajo del 14 de octubre.

## Decisiones tomadas

Se registraron seis decisiones; todas quedan documentadas en `docs/decisiones/`. La de escenario está pendiente de validar con el profesor guía, porque el anteproyecto contemplaba un corredor de 8 a 12 intersecciones.

| Fecha | Decisión | Qué cambia | Documento |
| --- | --- | --- | --- |
| 24-oct | El agente controla solo los 64 semáforos del eje; las 22 transversales quedan en tiempo fijo | Menos agentes, entrenamiento más rápido y más cercano a un despliegue real | `11-decision-agente.md` |
| 24-oct | PPO con parámetros compartidos (IPPO); Adam por defecto, RMSprop como alternativa; tasa de aprendizaje lineal decreciente | Fija la configuración base de OE4 y el punto de comparación para MAPPO | `11-decision-agente.md` |
| 24-oct | Datos en GeoPackage + GeoParquet + DuckDB, sin servidor; PostGIS solo si aparece una necesidad concreta | Cada corrida guarda versión de red y commit para reproducibilidad | `10-decision-base-de-datos.md` |
| 24-oct | Entrega del informe final en diciembre de 2026; regla de corte adelantada al 22 de noviembre | Recortes declarados: 10 semillas, MAPPO solo en el tramo de Providencia, dos variantes de recompensa y dos perturbaciones | `ESTADO_DEL_PROYECTO.md` §8 |
| 22-oct | Tiempos semafóricos: ubicación desde OpenStreetMap; tiempos con Webster, anclados en una muestra de terreno de 13 cruces y calibrados por tiempo de viaje | Waze queda solo como referencia consultada a mano: no permite despejar ciclos y sus términos prohíben el acceso automatizado | `08-decision-tiempos-semaforicos.md` |
| 22-oct | Nivel comunal; MVP en el eje Alameda → Providencia → Apoquindo, dentro de los límites de Santiago, Providencia y Las Condes | La red pasa de un corredor de 11 semáforos a un eje de ~13,5 km con 86 | `07-decision-escenario.md` |

## Cambios técnicos

La red del eje completo existe y pasa el diagnóstico; los controladores clásicos y el agente ya corren sobre ella. Todos los números de esta sección usan demanda sintética: prueban que el sistema funciona, no son resultados de tesis.

### Red del eje comunal (24-oct)

- `scenarios/eje_comunal`: de Matucana a Camino El Alba, 1 130 arcos y 86 semáforos (64 sobre el eje y 22 en transversales). `diagnose_net.py` la declara APTA.
- Scripts nuevos: `download_axis_osm.py` (descarga el eje en recuadros desde la API de OSM y calcula la franja), `fix_tls.py` (corrige semáforos de una sola fase verde y virajes permisivos) y `list_axis_tls.py` (separa semáforos del eje y transversales en `tls_eje.json`).
- Antes de esta red, ninguna cubría el eje completo: `alameda_providencia` no incluía la Alameda y faltaban ~1,2 km de Av. Providencia.

### Arnés de medición (24-oct)

- El contador de conmutaciones (`phase_switches`) devolvía 0 para todos los controladores; ahora se cuenta observando la red y funciona con tiempo fijo, Max-Pressure y el agente.
- Nueva métrica primaria `delay_all_mean`: incluye la demora de los vehículos que siguen en la red o esperan entrar al cerrar el episodio. Se agregan `vehicles_running_end` y `vehicles_pending_end`.

### Agente (24-oct)

El entrenamiento funciona sobre la red real con los 64 semáforos del eje. Prueba de 49 152 muestras, episodios de 900 s, semilla 0:

| Optimizador | Recompensa media (actualización 1 → 2 → 3) | Duración |
| --- | --- | --- |
| Adam | −0,64 → −0,54 → −0,41 | 191 s |
| RMSprop | −0,64 → −0,54 → −0,28 | 199 s |

Velocidad medida: ~270 muestras/s, de modo que un millón de muestras toma del orden de una hora. La prueba no compara optimizadores: es una sola semilla y tres actualizaciones.

### Plan Webster coordinado (27-oct)

`build_webster.py` calibra el flujo por fase con una hora de tiempo fijo, calcula Webster por semáforo y coordina el eje: ciclo común por avenida (Alameda 27, Providencia 19, Apoquindo 18 semáforos) y onda verde a 40 km/h en el sentido de la punta. El controlador ajusta los verdes para que el ciclo real coincida con el objetivo.

Con la demanda sintética, la demora por vehículo bajó de 228 s con tiempo fijo a 149 s con Webster coordinado (−35 %, 2 semillas, 1 800 s). Advertencia: los ciclos quedan en 40–49 s porque la demanda de prueba carga poco el eje (Y medio 0,17); el plan definitivo se regenera por perfil.

### Terreno (22-oct)

Protocolo listo para medir ciclo, verde, amarillo y rojo en 13 cruces y tres franjas (39 mediciones, 4 días hábiles). `procesar_terreno.py` convierte las marcas de tiempo en tiempos semafóricos. Los CSV de medición están creados pero vacíos: la salida a terreno no se ha hecho.

### Respaldo y pruebas

- El trabajo del 14-oct (perfiles de demanda de Alameda-Providencia, plan Webster y correcciones) quedó respaldado en git el 22-oct.
- Pruebas automatizadas: de 13 a 27, con archivos nuevos para métricas, configuración del agente, terreno y Webster coordinado. Las 27 pasan al 29-oct.

## Repositorio y modelo UML (29-oct)

El repositorio quedó agrupado por categoría y con un mapa de importancia en el `README.md` de la raíz; se subió a la rama `master` de `howtok6/CAPSTONE`.

- **Documentos:** `docs/` separado en `anteproyecto/`, `informe/`, `decisiones/`, `entorno/`, `datos/` y `uml/`, con un índice que marca cada archivo como esencial, de referencia o de consulta ocasional.
- **Evidencias del ramo:** las autoevaluaciones y el diario de reflexión de fase 1, junto con los scripts que los generan, pasaron a `capstone/`, fuera del trabajo de tesis.
- **Material exploratorio:** los scripts de Waze, *rerouting* y Overpass pasaron a `tsc-thesis/scripts/exploratorio/`, y la muestra de Waze a `tsc-thesis/data/waze/`. Quedan visiblemente fuera del alcance, como pedía el informe de estado del 22-oct.
- **Modelo UML:** diagrama de actores, vista general de casos de uso y un diagrama por subsistema (escenario, control y análisis). Son 5 actores humanos (Investigador y Revisor, que se especializa en Profesor guía, Comisión evaluadora e Investigador externo), 3 sistemas externos (OpenStreetMap, fuentes de datos de movilidad y SUMO) y 22 casos de uso trazados a scripts y objetivos específicos. De ellos, 15 están implementados, 4 parcialmente y 3 pendientes (calibrar demanda, validar escenario y robustez).

Las 27 pruebas pasan antes y después de la reorganización.

## Avance por objetivo específico

Avanzaron cinco de los siete objetivos; OE4 dejó de ser solo una prueba en grilla sintética y OE6 sigue sin iniciar. Los porcentajes son los del informe de estado del 22-oct, una estimación de juicio; no se reestimaron para este informe.

| OE | Objetivo | Avance al 22-oct | Qué cambió en el período | Qué falta |
| --- | --- | --- | --- | --- |
| OE1 | Escenario calibrado de Santiago | 60 % | Red del eje completo (86 semáforos), APTA | Demanda calibrada o validada y reporte de calibración |
| OE2 | Tres controladores de referencia | 100 % | Webster coordinado para el eje: ciclo común por avenida y onda verde | — |
| OE3 | Formulación Dec-POMDP | 85 % | Alcance de control fijado: 64 semáforos del eje | Especificación formal escrita para el informe |
| OE4 | Entrenar al menos dos configuraciones MARL | 10 % | Configuración del agente decidida; primer entrenamiento sobre la red real | Entrenamiento completo de IPPO y MAPPO |
| OE5 | Evaluación comparativa con estadística | 35 % | Métrica `delay_all_mean` y contador de conmutaciones corregido | Batería: 4 perfiles × 4 controladores × 10 semillas |
| OE6 | Robustez de la política | 5 % | Sin cambios | Requiere una política entrenada |
| OE7 | Documentación y repositorio reproducible | 25 % | Informe de estado corregido, cuatro decisiones registradas, repositorio ordenado, modelo UML y borrador del informe 1.4 | Informe final y script maestro de reproducción |

Ninguna hipótesis está contrastada todavía: H1 y H2 requieren la batería sobre el eje real y H3 requiere MAPPO.

## Próximos pasos y riesgos

Lo urgente es salir a terreno y conseguir demanda realista: de eso dependen Webster definitivo, la batería de baselines y el entrenamiento en serio, todo antes de la regla de corte del 22 de noviembre de 2026.

- [ ] **Terreno:** medir los 13 cruces en las tres franjas (versión mínima: valle y punta tarde). Listo cuando `procesar_terreno.py` entrega al menos 3 ciclos completos por cruce y franja.
- [ ] **Validar el cambio de alcance con el profesor guía:** el anteproyecto decía 8–12 intersecciones y el MVP tiene 86 semáforos.
- [ ] **Perfiles de demanda del eje** y plan Webster por perfil (`build_webster.py --profile`).
- [ ] **Baselines completos:** 4 perfiles × 4 controladores × 10 semillas × 1 h. Listo cuando `compare.py` entrega IC 95 % y tamaño de efecto.
- [ ] **Primer IPPO en red real** (perfil punta tarde). Listo cuando la curva se estabiliza y la política iguala a tiempo fijo.
- [ ] **Validación de demanda** con tiempos típicos por franja y, si llegan, datos de UOCT o DTPM.
- [ ] **Completar `requirements.txt`** (faltan `torch`, `torch_geometric` y `WazeRouteCalculator`) y crear un entorno virtual.

**Riesgos**

- **Demanda sintética:** si no llegan datos de UOCT o DTPM, la calibración se apoya solo en terreno y tiempos típicos de viaje; la conclusión se acota y se declara en limitaciones.
- **Plazo:** si al 22 de noviembre de 2026 la política no iguala a tiempo fijo, se congela la exploración de arquitecturas y el esfuerzo pasa al análisis comparativo clásico. La entrega se planifica para el 13 de diciembre de 2026.
- **MAPPO en Windows:** Ray está en beta en Windows; si falla, se monta WSL2 esa semana (el runbook ya existe).

## Anexo: commits del período

Rama `master` de `howtok6/CAPSTONE`, 22 al 29 de octubre de 2026.

| Fecha | Commit | Cambio |
| --- | --- | --- |
| 29-oct | `98a4858` | Reorganiza el repositorio por categoría y agrega el modelo UML de casos de uso |
| 27-oct | `551e41c` | Documenta el plan Webster de la red del eje |
| 27-oct | `a1e2f13` | Webster coordinado para la red del eje |
| 24-oct | `1339bdd` | Documenta la decisión del agente y la prueba de funcionamiento |
| 24-oct | `4ef8d8b` | El agente controla solo los 64 semáforos del eje; optimizador Adam o RMSprop |
| 24-oct | `33ec636` | Documenta el plazo de diciembre, la decisión de base de datos y la red del eje |
| 24-oct | `f2ff307` | Red del eje completo (`scenarios/eje_comunal`): Matucana a Camino El Alba |
| 24-oct | `1000682` | Arnés: cuenta conmutaciones y demora de vehículos no terminados |
| 22-oct | `a928d44` | Límites del MVP = límites comunales de Santiago, Providencia y Las Condes |
| 22-oct | `51b2b07` | Decisión de tiempos semafóricos (OSM + Webster + terreno) y protocolo de terreno |
| 22-oct | `d11f179` | Registra la decisión de escenario (nivel comunal) |
| 22-oct | `d063d45` | Corrige el informe de estado (revisión del 22-oct) |
| 22-oct | `7c80729` | Informe de estado al 14-oct e índice actualizado |
| 22-oct | `eb7aa17` | Alameda-Providencia: perfiles de demanda, plan Webster y correcciones (trabajo del 14-oct) |
