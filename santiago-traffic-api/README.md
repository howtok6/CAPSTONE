# Santiago Traffic API · CAPSTONE

API de tránsito en Python 3.12+ con FastAPI. Incluye flujo de un tramo cercano a una
coordenada, teselas vectoriales de flujo, incidentes dentro de una zona y rutas con tránsito.
Incluye configuración por `.env`, validación,
Swagger y manejo de errores de TomTom.

## Tablas por comuna

Abre <http://127.0.0.1:8000/comunas> y elige entre las **32 comunas de la provincia
de Santiago**. Hay **192 puntos de referencia**, seis por comuna, con la misma
tabla de velocidades, tiempos de referencia, demora, confianza y cierre.

Enlaces directos: [Providencia](http://127.0.0.1:8000/providencia),
[Ñuñoa](http://127.0.0.1:8000/nunoa),
[Lo Barnechea](http://127.0.0.1:8000/lo-barnechea),
[Vitacura](http://127.0.0.1:8000/vitacura) y
[Las Condes](http://127.0.0.1:8000/las-condes).

Cambiar de comuna no consulta TomTom. Cada captura realiza seis consultas de flujo
solo para la comuna seleccionada. Las descargas de la pantalla reutilizan esa
captura. Los puntos son referencias del inventario UOCT de 2023; no representan
todos los cruces ni acreditan el estado actual de los semáforos.

Consulta [la guía de comunas y endpoints](docs/DATOS_COMUNAS.md).

## Piloto Las Condes

Para leer las mediciones sin recorrer el JSON, abre la
[tabla de velocidades y tiempos](http://127.0.0.1:8000/las-condes) con el servidor iniciado.
Pulsa **Consultar velocidades y tiempos** para obtener una captura de los seis puntos.
La tabla muestra velocidad actual, velocidad de flujo libre, tiempo actual,
tiempo de referencia, demora, confianza y cierre. No hay aceleración disponible.
Los botones de descarga reutilizan la captura visible sin nuevas consultas a TomTom.

Ya puedes obtener datos actuales de seis puntos de referencia en Apoquindo y Manquehue:

```bash
python -m app.capture_las_condes --include-routes
```

Con el servidor iniciado, el endpoint
`GET /api/studies/las-condes/snapshot` devuelve flujo e incidentes; agrega
`?include_routes=true` para incluir dos recorridos. Para descargar velocidades
y demoras en CSV, usa `GET /api/studies/las-condes/snapshot.csv`.

La configuración y las fuentes se consultan en `GET /api/studies/las-condes`.
Los puntos del inventario UOCT de 2023 están en
`GET /api/studies/las-condes/points.geojson`. La captura no persiste resultados
automáticamente ni recupera históricos. La selección de vía y sentido está pendiente
de validación; no equivale a medir todos los accesos de cada semáforo.

Consulta [la guía de datos y sus limitaciones](docs/DATOS_LAS_CONDES.md) y el
[borrador para solicitar aforos y programaciones a UOCT](docs/SOLICITUD_UOCT_LAS_CONDES.md).

## Inicio rápido

El entorno `.venv` ya está creado en esta carpeta. Para usarlo:

```bash
cd santiago-traffic-api
source .venv/bin/activate
```

Edita `.env` y pega el **valor completo de la API key**, no su nombre ni su ID:

```dotenv
TOMTOM_API_KEY=pega_aqui_tu_api_key
```

No compartas ese archivo. `.gitignore` excluye `.env` y mantiene `.env.example`
como plantilla sin credenciales. Las variables del proceso tienen prioridad sobre
`.env`; si antes exportaste otra clave en la terminal, ejecuta `unset TOMTOM_API_KEY`
para usar la del archivo.

Inicia el servidor desde esta carpeta:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger: <http://127.0.0.1:8000/docs>
- Estado: <http://127.0.0.1:8000/health>
- Esquema OpenAPI: <http://127.0.0.1:8000/openapi.json>

Después de editar `.env`, detén el proceso con `Ctrl+C` y vuelve a iniciarlo.
La recarga del código no garantiza que se detecten cambios en `.env`.

## Consultas de ejemplo

### Teselas vectoriales de flujo (Traffic Orbis v2)

```bash
curl --fail-with-body \
  http://127.0.0.1:8000/api/traffic/flow/tiles/12/2103/1346 \
  --output flow.pbf
```

Esta ruta consulta `/maps/orbis/traffic/flow/vector/tile/{zoom}/{x}/{y}` en TomTom
con `apiVersion=2` y autenticación mediante el encabezado `TomTom-Api-Key`.
El frontend utiliza la URL local; no necesita conocer la clave.

`12` es el zoom y `2103/1346` son índices de una tesela del mapa, no coordenadas
GPS. El rango de zoom es 0–22 y los índices válidos van de 0 a `2^zoom - 1`.
Para una ubicación distinta hay que calcular sus índices o dejar que una biblioteca
de mapas solicite las teselas visibles usando esta plantilla local:

```text
http://127.0.0.1:8000/api/traffic/flow/tiles/{z}/{x}/{y}
```

La respuesta es **binaria MVT/PBF**, con tipo `application/vnd.mapbox-vector-tile`.
No es JSON, GeoJSON ni una imagen que pueda verse directamente en el navegador.
Swagger documenta su descarga; para visualizarla se requiere un renderizador
vectorial, un mapa base y un estilo para la capa `Traffic flow`.
Para análisis en el backend también puede decodificarse con una biblioteca MVT;
esta base retransmite los bytes sin decodificarlos ni convertirlos a JSON.

Por defecto, el proveedor incluye `relative_speed` como una fracción entre 0 y 1
respecto al flujo libre. `absolute_speed` en km/h es un atributo que debe solicitarse
expresamente; no se solicita en esta primera integración. La cobertura de calles
depende del zoom. Una tesela vacía no prueba que toda la zona esté sin congestión.

Usa `/api/traffic/flow?lat=...&lon=...` cuando necesites los datos de un tramo en JSON,
y `/api/traffic/route` cuando necesites calcular un trayecto entre dos puntos.

### Ruta con tránsito actual (Routing Orbis v2)

```bash
curl --get http://127.0.0.1:8000/api/traffic/route \
  --data-urlencode 'origin_lat=-33.4489' \
  --data-urlencode 'origin_lon=-70.6693' \
  --data-urlencode 'destination_lat=-33.4172' \
  --data-urlencode 'destination_lon=-70.6067'
```

El backend construye esta solicitud al proveedor, usando la clave del `.env`:

```text
https://api.tomtom.com/maps/orbis/routing/calculateRoute/{latOrigen},{lonOrigen}:{latDestino},{lonDestino}/json
```

Envía `apiVersion=2`, `traffic=live`, `departAt=now`, `travelMode=car`, `routeType=fast`,
`routeRepresentation=polyline`, `maxAlternatives=0` y la clave en `key`. Devuelve
una ruta con `distance_m`, `travel_time_s`, `traffic_delay_s`, `traffic_length_m`,
`departure_time`, `arrival_time` y `coordinates` como objetos latitude/longitude.
Los campos de distancia afectada y horas pueden ser `null` si el proveedor los omite.
`fetched_at` es la fecha de recepción del backend en UTC.

`travel_time_s` ya considera tránsito histórico y actual. `traffic_delay_s` es el
indicador de demora que proporciona TomTom; no se calcula restando otra consulta.
Orbis v2 no admite `computeTravelTimeFor=all` ni devuelve `noTrafficTravelTimeInSeconds`.
Se mantiene v2 para seguir el endpoint elegido para este proyecto.

Para reproducir el ejemplo de Países Bajos, utiliza `origin_lat=52.3676`,
`origin_lon=4.9041`, `destination_lat=51.4426` y `destination_lon=3.5735`.
La URL debe comenzar con `https://` y no debe contener saltos de línea o espacios.
Cambiar a Routing no garantiza resolver un rechazo de autenticación: la API key
debe ser válida y tener acceso al servicio solicitado.

### Estado

```bash
curl http://127.0.0.1:8000/health
```

`tomtom_configured` indica únicamente si ingresaste una clave no vacía; no valida
sus permisos ni realiza solicitudes a TomTom. Sin clave, el servidor y Swagger
funcionan y las rutas de tránsito responden `503 TOMTOM_NOT_CONFIGURED`.

### Flujo por coordenada

```bash
curl --get http://127.0.0.1:8000/api/traffic/flow \
  --data-urlencode 'lat=-33.4489' \
  --data-urlencode 'lon=-70.6693' \
  --data-urlencode 'zoom=15'
```

Devuelve velocidades en km/h, tiempos en segundos, confianza, estado de cierre y
coordenadas del tramo. `delay_s` es `max(0, tiempo_actual - tiempo_libre)`.
`fetched_at` es la fecha de recepción del backend en UTC, no una fecha de medición
proporcionada por TomTom. `requested_point` es el punto consultado, que puede
diferir del tramo devuelto. La consulta no recoge todas las calles de la zona.

### Incidentes por zona

```bash
curl --get http://127.0.0.1:8000/api/traffic/incidents \
  --data-urlencode 'bbox=-70.70,-33.47,-70.63,-33.42'
```

`bbox` usa **minLon,minLat,maxLon,maxLat** en WGS84. El backend valida rangos,
orden y un área aproximada máxima de 10.000 km². Se consultan incidentes presentes.
`incidents: []` es un resultado válido. Dentro de cada incidente se conservan las
propiedades y la geometría de TomTom; las coordenadas GeoJSON usan longitud,latitud.

Las coordenadas locales de ejemplo están en Santiago; adapta los puntos y la zona al proyecto.

## Configuración

| Variable | Uso |
| --- | --- |
| `TOMTOM_API_KEY` | Credencial de TomTom; inicialmente vacía |
| `TOMTOM_TIMEOUT_SECONDS` | Espera máxima por operación de red; predeterminado 10 s |
| `CORS_ORIGINS` | Lista JSON de orígenes del frontend autorizados |

`.env` se resuelve desde la raíz del proyecto, independientemente del directorio
de trabajo. La clave solo se utiliza en solicitudes del servidor hacia TomTom.
Evita registrar URLs completas de Flow o Routing, que reciben la clave en la query.

## Errores

| HTTP | Código / significado |
| --- | --- |
| 422 | Parámetros locales inválidos; no se consulta TomTom |
| 503 | `TOMTOM_NOT_CONFIGURED`: falta completar la clave |
| 502 | `TOMTOM_ACCESS_DENIED`: TomTom rechazó la clave o sus permisos |
| 503 | `TOMTOM_RATE_LIMITED`: TomTom respondió 429 |
| 504 | `TOMTOM_TIMEOUT`: tiempo de espera agotado |
| 502 | `TOMTOM_UNREACHABLE`, `TOMTOM_UPSTREAM_ERROR` o `TOMTOM_INVALID_RESPONSE` |

## Desarrollo y pruebas

Para recrear el entorno en otra máquina con Python 3.12+:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Ejecuta las verificaciones:

```bash
python -m pytest
ruff check .
ruff format --check .
```

Las pruebas simulan TomTom: no necesitan una clave real, no consumen cuota y cubren
validación, respuestas correctas, errores del proveedor y ausencia de credenciales.

## Estructura

```text
app/
  config.py    Configuración y lectura de .env
  main.py      Aplicación, cliente HTTP compartido, CORS y estado
  routes.py    Endpoints de tránsito
  schemas.py   Validación y contratos de respuesta
  tomtom.py    Integración HTTP y transformación de datos
  communes.py  Catálogo de las 32 comunas de la provincia de Santiago
  study.py     Captura acotada de una comuna y exportación CSV
  study_routes.py  Endpoints del piloto y puntos GeoJSON
  capture_study.py  Captura de una comuna desde la terminal
  capture_las_condes.py  Compatibilidad con el comando original de Las Condes
  data/*.json   Selecciones de cruces y procedencia de coordenadas por comuna
  static/communes.html  Tabla compartida con selector de comuna
tests/
  test_api.py  Pruebas sin conexiones externas
  test_study.py  Cobertura del piloto, faltantes, cuotas y exportación
docs/
  DATOS_LAS_CONDES.md  Fuentes, comandos y limitaciones
  SOLICITUD_UOCT_LAS_CONDES.md  Solicitud de aforos y programaciones para completar
```

## Alcance de esta base

Cada solicitud válida de tránsito realiza una consulta a TomTom. No hay sondeo
automático, caché, base de datos ni persistencia histórica. El servidor escucha
solo en tu computador por defecto. Antes de publicarlo, añade autenticación,
límites de consumo y una estrategia de caché según las condiciones de tu plan;
CORS por sí solo no restringe quién puede consumir la API.

Para flujo puntual se usa **TomTom Maps Flow Segment Data v4**. Para incidentes se
usa **Orbis v2** con `TomTom-Api-Key` y `Attributes`. Para rutas se usa **Routing Orbis v2**
con `traffic=live`. TomTom recomienda Orbis para
integraciones nuevas; el endpoint puntual de flujo pertenece a la familia Maps.
Estos datos describen velocidades, tiempos e incidentes, no conteos de vehículos.

Documentación oficial:

- [Obtener la API key](https://docs.tomtom.com/platform/documentation/my-tomtom/how-to-get-a-tomtom-api-key)
- [Flow Segment Data](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data)
- [Vector Flow Tiles Orbis v2](https://docs.tomtom.com/traffic-api/documentation/tomtom-orbis-maps/v2/traffic-flow/vector-flow-tiles)
- [Incident Details Orbis v2](https://docs.tomtom.com/traffic-api/documentation/tomtom-orbis-maps/v2/traffic-incidents/incident-details)
- [Calculate Route Orbis v2](https://docs.tomtom.com/routing-api/documentation/tomtom-orbis-maps/v2/calculate-route)
- [Migración a Routing Orbis v2](https://docs.tomtom.com/routing-api/documentation/tomtom-orbis-maps/v2/product-information/migration-guide)
- [Precios y cuotas](https://docs.tomtom.com/pricing)
