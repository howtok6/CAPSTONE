# Endpoints de «Vía» para pruebas

Lista de todos los endpoints que intervienen en la app móvil, con un ejemplo listo para ejecutar, la respuesta
esperada y una columna para anotar el resultado cuando se prueben. El contrato completo está en
[`backend/README.md`](../../backend/README.md).

Verificado el 4 de noviembre de 2026 contra el backend local con la simulación `eje_comunal` (Webster): 26 de 26
pruebas respondieron lo esperado.

## Cómo probarlos

1. Levantar la simulación y el backend (dos terminales, desde la raíz del repositorio):

   ```powershell
   cd simulacion; python run.py            # :8000, solo la consulta el backend
   cd backend;    go run ./cmd/via-backend # :8080, el único que habla con la app
   ```

2. Elegir una forma de probar:

   | Herramienta | Archivo | Uso |
   |---|---|---|
   | Script de humo (PowerShell) | [`backend/pruebas/probar-endpoints.ps1`](../../backend/pruebas/probar-endpoints.ps1) | Recorre todos los endpoints de esta lista, encadena los ids (ruta → viaje → ubicación) y resume OK/FALLA. `-Base` cambia el servidor y `-Salida` guarda las respuestas. |
   | Peticiones sueltas | [`backend/pruebas/via.http`](../../backend/pruebas/via.http) | Para VS Code (extensión REST Client) o IntelliJ/GoLand: un clic por petición. |
   | curl | Ejemplos de abajo | En PowerShell usar `curl.exe`, no `curl` (que es un alias de `Invoke-WebRequest`). |

   ```powershell
   powershell -ExecutionPolicy Bypass -File backend\pruebas\probar-endpoints.ps1
   ```

3. Desde el celular por USB el backend se ve en `http://127.0.0.1:8080` después de `adb reverse tcp:8080 tcp:8080`;
   por Wi-Fi, con la IP del PC (`flutter run --dart-define=API_URL=http://192.168.x.x:8080`).

Base de los ejemplos: `http://127.0.0.1:8080`. Coordenadas WGS84; los trazados son listas de `[lat, lon]`.

## Resumen

**Usa la app** indica qué pantalla o acción llama a cada endpoint; los que no la tienen sirven para diagnóstico o para
futuras vistas (por ejemplo, una capa de tráfico en el mapa).

| # | Método | Ruta | Usa la app | Respuesta esperada | Resultado |
|---|---|---|---|---|---|
| 1 | GET | `/v1/salud` | — (diagnóstico) | 200 `estado: ok` o `degradado` | |
| 2 | GET | `/v1/lugares?q=` | Proponer ruta → buscar | 200, hasta 5 lugares | |
| 3 | GET | `/v1/lugares/inverso?lat=&lon=` | Proponer ruta → tocar el mapa | 200, nombre del lugar | |
| 4 | POST | `/v1/rutas` | Proponer ruta → alternativas | 200, rutas con trazado, pasos y semáforos | |
| 5 | GET | `/v1/semaforos?bbox=` | — | 200, semáforos con el estado de cada acceso | |
| 6 | GET | `/v1/semaforos/{id}` | — | 200, un semáforo | |
| 7 | GET | `/v1/semaforos/proximo?lat=&lon=&rumbo=` | — | 200, próximo semáforo sin viaje | |
| 8 | GET | `/v1/trafico?bbox=&incluir_libres=` | — | 200, nivel de servicio por calle | |
| 9 | GET | `/v1/simulacion/destinos` | Inicio → selector de recorrido y línea de la ruta en el mapa | 200, destinos con trazado y semáforos | |
| 10 | POST | `/v1/viajes` (`modo: gps`) | Iniciar recorrido con ruta propuesta | 201, viaje `en_ruta` | |
| 11 | POST | `/v1/viajes/{id}/ubicacion` | Cada ubicación durante el viaje GPS | 200, viaje con próximo semáforo | |
| 12 | POST | `/v1/viajes` (`modo: simulado`) | Iniciar recorrido con destino de demostración | 201, viaje `esperando` | |
| 13 | GET | `/v1/viajes/{id}` | Cada segundo durante el viaje | 200, viaje con próximo semáforo y ubicación | |
| 14 | DELETE | `/v1/viajes/{id}` | Finalizar recorrido, cambiar de ruta, cerrar la app | 204 | |
| 15 | GET | `tiles.openfreemap.org/planet` | Mapa (directo, sin backend) | 200, TileJSON | |
| 16 | GET | `tiles.openfreemap.org/fonts/…` | Mapa: nombres de calles | 200, glifos `.pbf` | |

Errores a probar: 400 (parámetros inválidos), 404 (viaje inexistente) y 409 (ubicación en un viaje terminado);
están al final.

## 1. Salud

```bash
curl http://127.0.0.1:8080/v1/salud
```

```json
{"estado": "ok", "version": "dev",
 "servicios": {"simulacion": {"ok": true, "detalle": {"lista": true, "escenario": "eje_comunal",
   "controlador": "webster", "tiempo_sim": 388, "vehiculos": 282, "viajes_activos": 0}}}}
```

Sin la simulación responde 200 con `estado: degradado`: lugares y rutas siguen funcionando, pero semáforos, tráfico y
viajes fallan con 503.

## 2. Buscar lugares

```bash
curl "http://127.0.0.1:8080/v1/lugares?q=Costanera%20Center"
```

```json
[{"nombre": "Costanera Center", "detalle": "Costanera Center, Providencia, …, Chile",
  "lat": -33.4180283, "lon": -70.606751}, "…"]
```

Hasta 5 resultados del Gran Santiago. Nominatim admite una consulta por segundo: el backend la respeta y guarda 24 h
en caché, así que repetir la misma búsqueda es instantáneo.

## 3. Nombrar un punto

```bash
curl "http://127.0.0.1:8080/v1/lugares/inverso?lat=-33.4372&lon=-70.6275"
```

```json
{"nombre": "Terranova", "detalle": "Terranova, Barrio Vaticano Chico, Providencia, …", "lat": -33.4372, "lon": -70.6275}
```

## 4. Calcular rutas

```bash
curl -X POST http://127.0.0.1:8080/v1/rutas -H "Content-Type: application/json" \
  -d '{"paradas": [{"lat": -33.4378, "lon": -70.6504}, {"lat": -33.4372, "lon": -70.6275}], "alternativas": true}'
```

```json
[{"distancia_km": 4.19, "duracion_min": 7.7,
  "trazado": [[-33.437252, -70.650493], [-33.437338, -70.65122], "…"],
  "pasos": [{"tipo": "depart", "modificador": "left", "calle": "Plaza de Armas", "distancia_m": 74.8}, "…"],
  "semaforos": [{"id": "GS_253251270", "nombre": "Av. Andrés Bello × Av. Cardenal José María Caro × Av. Vicuña Mackenna",
                 "lat": -33.436377, "lon": -70.635417, "distancia_desde_inicio_m": 2369}, "…"]},
 {"distancia_km": 3.98, "duracion_min": 8.07, "…": "…"}]
```

Entre 2 y 5 paradas; con más de dos no hay alternativas. La app dibuja `trazado` y `semaforos` en el mapa y manda
el `trazado` elegido al crear el viaje GPS (10).

## 5 y 6. Semáforos

```bash
curl "http://127.0.0.1:8080/v1/semaforos?bbox=-70.66,-33.45,-70.62,-33.43"
curl http://127.0.0.1:8080/v1/semaforos/224544128
```

```json
{"id": "224544128", "nombre": "Av. Providencia", "calles": ["Av. Providencia"], "lat": -33.428354, "lon": -70.619199,
 "accesos": [{"id": "453344285#2", "calle": "Av. Providencia", "rumbo": 244, "color": "rojo",
              "segundos_para_cambio": 2, "siguiente_color": "verde", "exacto": true}]}
```

`bbox` es `minLon,minLat,maxLon,maxLat`; sin él vienen los 86 semáforos de la red. Los ids con `#`, `GS_` o `cluster`
se pasan tal cual, codificados en la URL.

## 7. Próximo semáforo sin viaje

```bash
curl "http://127.0.0.1:8080/v1/semaforos/proximo?lat=-33.44406&lon=-70.6524&rumbo=92.5"
```

```json
{"proximo_semaforo": {"id": "GS_cluster_13356548834_13356548882_386140_500862085", "nombre": "Alameda × San Antonio",
  "calles": ["Alameda", "San Antonio"], "distancia_m": 456, "acceso": "223300795#5",
  "color": "verde", "segundos_para_cambio": 5, "siguiente_color": "amarillo", "exacto": true}}
```

Busca en un cono de ±40° hacia `rumbo` (grados desde el norte, en `[0, 360)`) y a menos de 500 m;
`proximo_semaforo` es `null` si no hay ninguno.

## 8. Tráfico

```bash
curl "http://127.0.0.1:8080/v1/trafico?bbox=-70.66,-33.45,-70.62,-33.43&incluir_libres=true"
```

```json
[{"id": "-1348254893#0", "nombre": "Padre Errázuriz", "nivel": "fluido", "velocidad_kmh": 58,
  "velocidad_libre_kmh": 50, "vehiculos": 1, "forma": [[-33.406674, -70.554874], "…"]}, "…"]
```

`nivel`: `libre`, `fluido`, `moderado` o `congestionado`. Sin `incluir_libres=true` omite las calles sin vehículos.

## 9. Destinos de demostración

```bash
curl http://127.0.0.1:8080/v1/simulacion/destinos
```

```json
[{"ruta": 0, "id": "bustamante", "nombre": "Av. General Bustamante", "origen": "Alameda frente a Plaza de Armas",
  "distancia_km": 1.7,
  "trazado": [[-33.443511, -70.648845], "…84 puntos…", [-33.43698, -70.63319]],
  "semaforos": [{"id": "GS_cluster_13356548834_13356548882_386140_500862085", "nombre": "Alameda × San Antonio",
                 "lat": -33.443104, "lon": -70.647623, "distancia_desde_inicio_m": 113}, "…5 en total…"]},
 {"ruta": 1, "id": "matucana", "nombre": "Matucana", "distancia_km": 2.9, "trazado": ["…109 puntos…"],
  "semaforos": ["…15 en total…"]}]
```

`trazado` es el camino exacto que hará el vehículo simulado y `semaforos`, los que cruza en orden (los mismos ids
que llegan en `proximo_semaforo` del viaje). La app los dibuja en el mapa apenas se elige el destino.

## 10 y 11. Viaje GPS

Es lo que hace la app al iniciar un recorrido por una ruta propuesta: crea el viaje con el trazado y luego envía cada
ubicación del celular.

```bash
curl -X POST http://127.0.0.1:8080/v1/viajes -H "Content-Type: application/json" \
  -d '{"modo": "gps", "nombre_destino": "Cerro Santa Lucía", "trazado": [[-33.437252, -70.650493], [-33.4372, -70.6275]]}'
# → 201 {"id": "v_d04ce1f10ff714af", "modo": "gps", "estado": "en_ruta", "distancia_total_m": 4183,
#        "semaforos_en_ruta": 3, "proximo_semaforo": null, …}

curl -X POST http://127.0.0.1:8080/v1/viajes/v_d04ce1f10ff714af/ubicacion -H "Content-Type: application/json" \
  -d '{"lat": -33.437252, "lon": -70.650493, "rumbo": 90, "velocidad_kmh": 30, "precision_m": 6}'
```

```json
{"id": "v_d04ce1f10ff714af", "modo": "gps", "estado": "en_ruta", "destino": "Cerro Santa Lucía",
 "distancia_total_m": 4183, "distancia_restante_m": 4183, "semaforos_en_ruta": 3,
 "ubicacion": {"lat": -33.437252, "lon": -70.650493, "rumbo": 90, "velocidad_kmh": 30, "precision_m": 6,
               "momento": "2026-11-04T17:00:41-03:00"},
 "proximo_semaforo": {"id": "GS_253251270", "nombre": "Av. Andrés Bello × …", "distancia_m": 2369,
                      "color": "rojo", "segundos_para_cambio": 8, "siguiente_color": "verde", "exacto": true}}
```

Con **ubicación aproximada** la app envía el centro de la zona y `precision_m` igual al rango elegido (250, 500 o
1000 m; 2000 si el sistema operativo solo concede aproximada). Para probarlo:

```bash
curl -X POST http://127.0.0.1:8080/v1/viajes/v_d04ce1f10ff714af/ubicacion -H "Content-Type: application/json" \
  -d '{"lat": -33.437252, "lon": -70.650493, "precision_m": 500}'
```

`rumbo`, `velocidad_kmh` y `precision_m` son opcionales; sin `rumbo` el backend lo estima con la ubicación anterior.

## 12 y 13. Viaje simulado

Un vehículo de la simulación hace el recorrido, para demostraciones sin moverse. La app consulta el viaje cada segundo
y usa `ubicacion` para mover el marcador del vehículo en el mapa.

```bash
curl -X POST http://127.0.0.1:8080/v1/viajes -H "Content-Type: application/json" -d '{"modo": "simulado", "destino": 0}'
# → 201 {"id": "v_80c4ccfd51f33810", "modo": "simulado", "estado": "esperando", "semaforos_en_ruta": 5, …}

curl http://127.0.0.1:8080/v1/viajes/v_80c4ccfd51f33810
```

```json
{"id": "v_80c4ccfd51f33810", "modo": "simulado", "estado": "en_ruta", "destino": "Av. General Bustamante",
 "distancia_total_m": 1665, "distancia_restante_m": 1658,
 "ubicacion": {"lat": -33.443503, "lon": -70.648721, "velocidad_kmh": 13.5, "momento": "…"},
 "proximo_semaforo": {"nombre": "Alameda × San Antonio", "distancia_m": 102, "color": "verde",
                      "segundos_para_cambio": 1, "siguiente_color": "amarillo", "exacto": true}}
```

Estados: `esperando` (aún no entra a la red), `en_ruta`, `llego`, `finalizado`, `reiniciado`.

## 14. Terminar un viaje

```bash
curl -X DELETE -i http://127.0.0.1:8080/v1/viajes/v_80c4ccfd51f33810   # → 204 sin cuerpo
```

En un viaje simulado retira el vehículo de la simulación. La app lo llama sin esperar respuesta.

## 15 y 16. Mapa (directo desde la app)

Las teselas y las fuentes del mapa no pasan por el backend:

```bash
curl -I https://tiles.openfreemap.org/planet
curl -I "https://tiles.openfreemap.org/fonts/Noto%20Sans%20Bold/0-255.pbf"
```

Si fallan, el mapa queda con el fondo liso pero rutas, paradas y marcadores se siguen dibujando.

## Errores esperados

| Prueba | Petición | Respuesta |
|---|---|---|
| Viaje inexistente | `GET /v1/viajes/v_no_existe` | 404 `no_encontrado` |
| Rumbo fuera de rango | `GET /v1/semaforos/proximo?lat=-33.44&lon=-70.65&rumbo=400` | 400 `solicitud_invalida` |
| Una sola parada | `POST /v1/rutas` con `{"paradas": [{"lat": -33.4378, "lon": -70.6504}]}` | 400 `solicitud_invalida` |
| Ubicación en viaje terminado | `POST /v1/viajes/{id}/ubicacion` después del `DELETE` | 409 `conflicto` |
| Simulación apagada | Cualquiera de 5–14 | 503 `servicio_no_disponible` |

Formato: `{"error": {"codigo": "conflicto", "mensaje": "operación no permitida en el estado actual: el viaje ya terminó"}}`.

## Servicio interno de simulación (`:8000`)

Solo lo consulta el backend; sirve para aislar una falla (¿es el backend o la simulación?). Documentación interactiva
en `http://127.0.0.1:8000/docs`.

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/estado` | Escenario, controlador, tiempo simulado y vehículos |
| GET | `/destinos` | Destinos de demostración |
| POST | `/viajes` | `{"ruta": 0}`: crea un vehículo |
| GET / DELETE | `/viajes/{id}` | Estado / retiro del vehículo |
| GET | `/semaforos` | Ubicación y accesos (estático) |
| GET | `/semaforos/estado?ids=` | Color y cuenta regresiva actual |
| GET | `/red/calles` | Geometría y velocidad libre de las calles |
| GET | `/trafico` | Velocidad y vehículos por calle (cada 5 s simulados) |
