# Decisión: almacenamiento de datos geoespaciales de la tesis

Registrada el 24-oct-2026. Estado: **decidida por el autor** (comparativa completa en el documento
«Arquitecturas de bases de datos geoespaciales para la tesis», 24-oct-2026).

## Decisión

| Capa | Formato / motor | Contenido |
|---|---|---|
| Mapa | **GeoPackage** (OGC, un archivo SQLite) | Comunas, eje por tramos, cruces semaforizados, arcos de la red |
| Resultados y series | **GeoParquet** | Corridas, viajes (*tripinfo*), métricas por cruce, mediciones de terreno, tiempos de viaje |
| Consulta | **DuckDB + extensión espacial** | SQL sobre los archivos, sin servidor |

Los archivos viven en el repositorio y se regeneran con scripts de carga en Python. Cada corrida guarda
`version_red` y `commit_git`. Geometrías en WGS84 (EPSG:4326); distancias en UTM 19 sur (EPSG:32719).

## Por qué

- El volumen cabe en un computador personal (del orden de millones de filas de resultados).
- Sin servidor que instalar ni respaldar: funciona igual en Windows y Linux.
- Reproducibilidad: el anteproyecto exige poder regenerar cada tabla desde el repositorio.
- Plazo de diciembre: no hay tiempo para operar infraestructura que hoy no aporta.

## Descartado por ahora

- **PostgreSQL + PostGIS** (con pgRouting, TimescaleDB o MobilityDB): se adopta si aparece una aplicación que
  consulte en línea, trayectorias GPS (p. ej. buses DTPM) o análisis de red en la base. La migración es directa
  con `ogr2ogr`.
- **MongoDB**: sus operadores geoespaciales cubren intersección, contención y proximidad, sin procesamiento
  geométrico ni análisis de red; poco apta para agregar millones de filas.
