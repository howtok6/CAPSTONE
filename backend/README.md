# Backend Go — app «Vía»

Único servicio con el que habla la app móvil. Expone la API `/v1` y se comunica por HTTP con los demás servicios:
la **simulación** (entorno de pruebas que provee el tráfico), **OSRM** (rutas) y **Nominatim** (lugares).
Escrito en Go 1.25 solo con la biblioteca estándar.

```
App Vía ──/v1──▶ backend ──▶ simulación (semáforos, tráfico, viajes simulados)
                    ├──────▶ OSRM (rutas en auto)
                    └──────▶ Nominatim (buscar lugares, nombrar puntos)
```

## Ejecutar

```bash
cd backend
go run ./cmd/via-backend          # escucha en :8080
go test ./...
```

Necesita la simulación corriendo (`python simulacion/run.py`) para semáforos, tráfico y viajes; sin ella, lugares
y rutas siguen funcionando (las rutas sin semáforos) y `/v1/salud` informa `degradado`.

| Variable | Por defecto | Qué es |
|---|---|---|
| `VIA_DIRECCION` | `:8080` | Dirección de escucha |
| `VIA_SIMULACION_URL` | `http://127.0.0.1:8000` | Servicio de simulación |
| `VIA_OSRM_URL` | `https://router.project-osrm.org` | Servidor OSRM |
| `VIA_NOMINATIM_URL` | `https://nominatim.openstreetmap.org` | Servidor Nominatim |
| `VIA_AGENTE` | `via-capstone-backend/0.1 (...)` | User-Agent ante OSM |
| `VIA_TIEMPO_ESPERA` | `10s` | Límite por llamada a otro servicio |
| `VIA_VIAJE_INACTIVO` | `2h` | Se olvida un viaje sin actividad tras este plazo |

Los servidores públicos de OSRM y Nominatim sirven para desarrollo. Nominatim exige como máximo una consulta por
segundo: el backend la respeta y guarda las respuestas 24 h en caché. Para producción conviene un servidor propio.

## Estructura

| Carpeta | Contenido |
|---|---|
| `cmd/via-backend` | Arranque, configuración y apagado ordenado |
| `internal/api` | Contrato HTTP `/v1`, errores y middlewares (CORS, registro, recuperación) |
| `internal/servicios` | Lógica de negocio: rutas con sus semáforos, próximo semáforo, viajes |
| `internal/proveedores` | Clientes de simulación, OSRM y Nominatim, detrás de interfaces |
| `internal/almacen` | Viajes activos en memoria (reemplazable por una base de datos) |
| `internal/geo` | Distancias, rumbos y proyección sobre un trazado |
| `internal/dominio` | Modelo y errores de dominio |

## API v1

Todas las respuestas son JSON (UTF-8). Coordenadas en WGS84; los trazados son listas de `[lat, lon]`.

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/v1/salud` | Estado del backend y de la simulación |
| GET | `/v1/lugares?q=texto` | Buscar lugares en el Gran Santiago (hasta 5) |
| GET | `/v1/lugares/inverso?lat=&lon=` | Nombre del lugar en un punto |
| POST | `/v1/rutas` | Rutas en auto entre paradas, con los semáforos de cada una |
| GET | `/v1/semaforos?bbox=` | Semáforos con el estado de cada acceso |
| GET | `/v1/semaforos/{id}` | Un semáforo con el estado de cada acceso |
| GET | `/v1/semaforos/proximo?lat=&lon=&rumbo=` | Próximo semáforo hacia donde avanza el usuario, sin viaje |
| GET | `/v1/trafico?bbox=&incluir_libres=` | Velocidad y nivel de servicio por calle, con su geometría |
| GET | `/v1/simulacion/destinos` | Recorridos de demostración para viajes simulados |
| POST | `/v1/viajes` | Iniciar un viaje GPS o simulado |
| GET | `/v1/viajes/{id}` | Estado del viaje y próximo semáforo (actualizado) |
| POST | `/v1/viajes/{id}/ubicacion` | Enviar la ubicación del GPS; devuelve el viaje actualizado |
| DELETE | `/v1/viajes/{id}` | Terminar el viaje |

`bbox` es `minLon,minLat,maxLon,maxLat`. `/v1/trafico` omite las calles sin vehículos salvo `incluir_libres=true`.

### Rutas

```http
POST /v1/rutas
{"paradas": [{"lat": -33.4433, "lon": -70.6505}, {"lat": -33.43696, "lon": -70.63313}], "alternativas": true}
```

Entre 2 y 5 paradas. Respuesta: lista de rutas, la más rápida primero.

```json
[{
  "distancia_km": 3.13, "duracion_min": 5.4,
  "trazado": [[-33.44345, -70.65037], "..."],
  "pasos": [{"tipo": "depart", "modificador": "right", "calle": "Avenida Libertador Bernardo O'Higgins", "distancia_m": 369}, "..."],
  "semaforos": [{"id": "GS_…", "nombre": "Alameda × Nataniel Cox × Teatinos", "lat": -33.44, "lon": -70.65, "distancia_desde_inicio_m": 393}]
}]
```

`pasos[].tipo` sigue a OSRM (`depart`, `turn`, `arrive`, `roundabout`, …); las llegadas intermedias se marcan `parada`.

### Viajes

Dos modos:

- **`gps`**: la app envía la ubicación real del celular. Se crea con la ruta elegida (`trazado`, tal como vino de
  `/v1/rutas`), con `paradas` para que el backend la calcule, o sin ruta (el próximo semáforo sale del rumbo).
- **`simulado`**: un vehículo dentro de la simulación representa al usuario, para demos sin moverse.

```http
POST /v1/viajes
{"modo": "gps", "nombre_destino": "Av. General Bustamante", "trazado": [[-33.44345, -70.65037], "..."]}

POST /v1/viajes
{"modo": "simulado", "destino": 0}
```

```http
POST /v1/viajes/{id}/ubicacion
{"lat": -33.44406, "lon": -70.65240, "rumbo": 92.5, "velocidad_kmh": 38, "precision_m": 6}
```

`rumbo`, `velocidad_kmh` y `precision_m` son opcionales; sin `rumbo`, el backend lo estima con la ubicación anterior.

```json
{
  "id": "v_9a6e5d292b1700bb", "modo": "gps", "estado": "en_ruta", "destino": "Av. General Bustamante",
  "distancia_total_m": 3134, "distancia_restante_m": 2941, "semaforos_en_ruta": 5,
  "ubicacion": {"lat": -33.44406, "lon": -70.6524, "momento": "2026-11-04T01:12:03-03:00"},
  "proximo_semaforo": {
    "id": "GS_…", "nombre": "Alameda × Nataniel Cox × Teatinos", "calles": ["Alameda", "Nataniel Cox", "Teatinos"],
    "distancia_m": 199, "acceso": "4012…#2",
    "color": "verde", "segundos_para_cambio": 3, "siguiente_color": "amarillo", "exacto": true
  },
  "creado_en": "…", "actualizado_en": "…"
}
```

Estados: `esperando` (solo simulado, aún no entra a la red), `en_ruta`, `llego`, `finalizado`, `reiniciado` (la
simulación se reinició y perdió el vehículo). `exacto: false` significa que los segundos son una estimación
(controlador adaptativo); `color: "desconocido"` que no se pudo determinar el acceso.

### Errores

```json
{"error": {"codigo": "solicitud_invalida", "mensaje": "solicitud inválida: rumbo debe estar en [0, 360)"}}
```

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 400 | `solicitud_invalida` | Parámetros o JSON inválidos |
| 404 | `no_encontrado` | Viaje o semáforo inexistente |
| 409 | `conflicto` | Ubicación en un viaje simulado o terminado |
| 422 | `sin_ruta` | OSRM no encuentra ruta en auto |
| 503 | `servicio_no_disponible` | La simulación, OSRM o Nominatim no responden |
| 504 | `tiempo_agotado` | Un servicio tardó más de lo permitido |

## Cómo se elige el próximo semáforo

1. **Semáforos de una ruta:** los que quedan a menos de 35 m del trazado y tienen un acceso cuyo rumbo coincide
   (±60°) con el rumbo de la ruta en los 30 m previos. Así se descartan los de calles transversales cercanas.
2. **Con ruta:** se proyecta la ubicación sobre el trazado (sin retroceder más de 100 m) y el próximo es el primer
   semáforo que aún no se cruza. A más de 60 m del trazado, el usuario se considera fuera de ruta y se usa el rumbo.
3. **Sin ruta:** el semáforo más cercano en un cono de ±40° hacia donde avanza, a menos de 500 m, con un acceso
   compatible con ese rumbo.
4. **Estado:** el del acceso cuyo rumbo de llegada más se parece al del usuario.
