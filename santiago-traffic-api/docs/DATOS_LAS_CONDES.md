# Obtener datos para Las Condes

## Qué está disponible ahora

Tenemos acceso comprobado a TomTom Traffic con la clave configurada en `.env`.
El piloto usa seis cruces de referencia en Apoquindo y Manquehue. No hay todavía
histórico propio, aforos medidos ni programaciones semafóricas.

Los códigos y coordenadas provienen del [inventario oficial de intersecciones
conectadas a UOCT RM, revisión 15 de mayo de 2023](https://www.transporteinforma.cl/content/uploads/2023/10/Intersecciones-de-Semaforos-conectados-a-Sistema-UOCT-RM.pdf).
Es un inventario de infraestructura, no mediciones de vehículos ni confirmación
del funcionamiento actual. Se normalizó la notación decimal de coordenadas a WGS84.

| Código UOCT | Cruce de referencia | Página del PDF |
| --- | --- | --- |
| J001421 | Apoquindo / Enrique Foster | 1 |
| J001431 | Apoquindo / Gertrudis Echenique - El Golf | 1 |
| J001441 | Apoquindo / Málaga | 1 |
| J158111 | Apoquindo / Manquehue | 25 |
| J059481 | Manquehue / Los Militares | 14 |
| J062151 | Manquehue / Colón | 15 |

La configuración editable está en `app/data/las_condes.json`. El rectángulo de
incidentes es una ventana del piloto, no el límite administrativo de Las Condes.

## Consultas desde el backend

Con el servidor iniciado, abre:

- [Configuración y fuentes](http://127.0.0.1:8000/api/studies/las-condes): no consulta TomTom.
- [Puntos en GeoJSON](http://127.0.0.1:8000/api/studies/las-condes/points.geojson): no consulta TomTom.
- [Captura actual](http://127.0.0.1:8000/api/studies/las-condes/snapshot): seis consultas de flujo y una de incidentes.
- [Captura con rutas](http://127.0.0.1:8000/api/studies/las-condes/snapshot?include_routes=true): agrega dos consultas de Routing.
- [CSV de flujo actual](http://127.0.0.1:8000/api/studies/las-condes/snapshot.csv): seis consultas de flujo; no descarga incidentes ni rutas.

Cada ejecución o descarga obtiene una muestra nueva. No hay recolector periódico,
base de datos ni caché de resultados en esta integración. El encabezado `Cache-Control`
de las capturas indica `no-store`.

También puedes obtener una captura directamente desde la terminal, sin iniciar Uvicorn:

```bash
cd santiago-traffic-api
source .venv/bin/activate
python -m app.capture_las_condes --include-routes
```

Para ver todos los datos y las geometrías en JSON:

```bash
python -m app.capture_las_condes --format json
```

Para imprimir las seis filas de flujo en CSV:

```bash
python -m app.capture_las_condes --format csv
```

El programa no guarda archivos automáticamente. Antes de construir un histórico
permanente o usar los resultados para entrenamiento, confirma los derechos de
retención y reutilización aplicables a tu cuenta de TomTom. No se asume que una
clave de API concede esos derechos. Los [términos del producto](https://docs.tomtom.com/legal/terms-and-conditions)
y tu acuerdo de servicio determinan el uso permitido.

## Qué significa cada dato

| Campo | Interpretación |
| --- | --- |
| `current_speed_kmh` | Velocidad actual estimada del tramo cercano |
| `free_flow_speed_kmh` | Referencia con flujo libre; no es el límite legal |
| `current_travel_time_s` | Tiempo actual de ese tramo |
| `free_flow_travel_time_s` | Tiempo de referencia del mismo tramo |
| `delay_s` | Diferencia no negativa entre tiempo actual y referencia |
| `confidence` | Calidad informada por TomTom, de 0 a 1 |
| `speed_ratio` | Velocidad actual / velocidad libre; `null` si el denominador es cero |
| `travel_time_ratio` | Tiempo actual / tiempo libre; `null` si el denominador es cero |
| `road_closed` | Indicación de cierre del tramo |
| `fetched_at` / `fetched_at_utc` | Momento en que el backend recibió el resultado, no fecha de medición del proveedor |
| `approach_validated` | Actualmente `false`: falta validar vía, sentido y acceso del cruce |

El CSV mantiene una fila por cada punto, también cuando falla. Las mediciones
faltantes quedan vacías con `status=error`; nunca se sustituyen por velocidad cero.
Las capturas JSON reportan `complete`, `partial` o `failed` y detallan los errores.
La clave rechazada y el límite de cuota detienen la captura para evitar insistir.

Las consultas son secuenciales y están fechadas individualmente. No sumes sus demoras:
los tramos pueden solaparse y tienen longitudes distintas. Consulta sus geometrías
antes de usarlos como observaciones independientes. Tampoco atribuyas automáticamente
la lentitud al semáforo: puede deberse a congestión, giros, obras o selección de otra vía.
En intersecciones a desnivel, una consulta al centro puede seleccionar un túnel,
paso inferior u otra calzada. Esto requiere especial revisión en Apoquindo con
Manquehue. El identificador UOCT corresponde al punto de referencia, no certifica
que el segmento elegido por TomTom sea el acceso superficial que se quiere estudiar.

Las rutas se calculan entre Enrique Foster y Manquehue en ambos sentidos, saliendo
ahora. Son recorridos elegidos por el motor, sin obligarlos a seguir Apoquindo. Los
tiempos incluyen tránsito y no son observaciones de cada acceso ni comparación con
una ruta fija libre de tráfico.

## De dónde obtener históricos

Para estudiar patrones previos, el producto específico es [TomTom Traffic Stats](https://docs.tomtom.com/traffic-stats/documentation/api/introduction):
ofrece análisis de rutas y áreas por períodos. Requiere acceso a ese producto;
no se presupone que la clave de Traffic API funcione allí. Confirma cobertura,
fechas disponibles, permisos y condiciones del acceso en MOVE antes de contratar.

Las capturas actuales no recuperan el tráfico de días anteriores. Para acumular una
serie propia primero hay que definir el permiso de almacenamiento, período,
intervalo de muestreo y presupuesto. Como diseño preliminar, seis puntos cada
15 minutos durante cuatro horas al día y 20 días equivalen a 1.920 consultas de
flujo. Una consulta de incidentes por captura agrega 320. Cada ruta adicional
consume otra consulta de Routing. Los horarios deben definirse con el estudio,
no se presentan como períodos punta ya comprobados.

## Datos que faltan para semáforos

TomTom Flow no entrega el ciclo, las fases, la duración de verde, los entreverdes,
los desfases, el aforo de cada giro ni todos los movimientos peatonales de un cruce.
Estos datos son necesarios para modelar y contrastar estrategias semafóricas.

UOCT ofrece el trámite oficial [Solicitud de información de tránsito](https://subtrans.cerofilas.gob.cl/categoria/7/procesos),
que menciona programaciones de semáforos y conteos vehiculares continuos y periódicos.
Preparé `docs/SOLICITUD_UOCT_LAS_CONDES.md` para completar y presentar tú mismo.
No se ha enviado ninguna solicitud en tu nombre.

También existe [documentación técnica pública de UOCT](https://www.transporteinforma.cl/acerca-de-sit-uoct/documentacion-y-licitaciones/)
con manuales de programación, configuración del controlador y el inventario usado.
El documento «Temporada Normal 2026» enlazado allí es una referencia de mediciones,
no un dataset con aforos de estos seis cruces.

Otra fuente es [TomTom Junction Analytics](https://docs.tomtom.com/junction-analytics/documentation/product-information/introduction):
informa demoras, detenciones, colas y proporciones de giro por acceso. Requiere
otro acceso y la [cobertura se valida por intersección](https://docs.tomtom.com/junction-analytics/documentation/product-information/market-coverage).
No se ha activado ni se da por disponible en Las Condes con nuestra clave.

## Próximo hito

1. Validar geometría y sentido de los tramos del piloto en el mapa.
2. Conseguir aforos y programaciones del mismo período mediante UOCT o la municipalidad.
3. Definir el acceso a histórico y la estrategia de muestreo permitida.
4. Calibrar un modelo con esos datos y evaluar rutas y semáforos en simulación.

Esta etapa entrega datos y diagnóstico; no aplica cambios a controladores reales.
