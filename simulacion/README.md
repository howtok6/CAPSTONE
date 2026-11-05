# Servicio de simulación — entorno de pruebas del backend

Mantiene una simulación SUMO de `tsc-thesis/scenarios/eje_comunal` corriendo a velocidad real, con los semáforos en
el **plan Webster coordinado**, y la expone como **proveedor de tráfico** para el backend Go: semáforos y su estado
por acceso, tráfico por calle y viajes simulados. **La app no lo consulta directamente**; en producción se
reemplaza por una fuente real de datos con el mismo contrato.

Está fuera del alcance experimental de la tesis: solo **importa** `tsc-thesis/src`, sin modificarlo.

## Cómo funciona

Cada recorrido que inicia la app agrega a la simulación un **vehículo propio** con la ruta elegida. Con él, SUMO
entrega el próximo semáforo de la ruta (`vehicle.getNextTLS`), su distancia y su color, y la API calcula cuántos
segundos faltan para el cambio recorriendo el programa del semáforo desde la fase actual.

Todo el acceso a SUMO ocurre en un solo hilo (libsumo no admite llamadas concurrentes); los pedidos HTTP leen
instantáneas protegidas por un candado.

## Ejecutar

Desde `simulacion/`:

```bash
python run.py                 # tiempo real, 127.0.0.1:8000
python run.py --velocidad 5   # 5 veces más rápido, para pruebas
python -m pytest tests        # pruebas
```

Con Docker, desde la raíz del repositorio: `docker compose up --build` (levanta también el backend).

Arranca en unos segundos: calienta 300 s simulados para que haya tránsito y luego avanza a velocidad real.
La documentación interactiva queda en http://127.0.0.1:8000/docs.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/estado` | Tiempo simulado, vehículos en la red, controlador y viajes activos |
| GET | `/semaforos` | Semáforos: ubicación, calles y accesos con su rumbo de llegada (estático) |
| GET | `/semaforos/estado?ids=` | Color, segundos para el cambio y color siguiente de cada acceso |
| GET | `/red/calles` | Calles con su geometría y velocidad libre (estático) |
| GET | `/trafico` | Velocidad media, vehículos y nivel de servicio por calle (cada 5 s simulados) |
| GET | `/destinos` | Destinos disponibles con su distancia desde el origen, el trazado `[lat, lon]` que sigue el vehículo y los semáforos que cruza, en orden |
| POST | `/viajes` | Inicia un recorrido. Cuerpo: `{"ruta": 0}` |
| GET | `/viajes/{id}` | Estado del recorrido y próximo semáforo |
| DELETE | `/viajes/{id}` | Finaliza el recorrido y retira el vehículo |

Ejemplo de `GET /viajes/v1` (medido el 3-nov-2026):

```json
{
  "id": "v1", "estado": "en_ruta", "ruta": 0, "destino": "Av. General Bustamante",
  "tiempo_sim": 437.0, "distancia_total_m": 1665, "distancia_restante_m": 1268,
  "posicion": {"lat": -33.4417, "lon": -70.6449}, "velocidad_kmh": 52.0,
  "proximo_semaforo": {
    "id": "GS_…", "nombre": "Alameda × Av. Portugal", "calles": ["Alameda", "Av. Portugal"],
    "distancia_m": 447, "color": "rojo", "segundos_para_cambio": 11, "siguiente_color": "verde",
    "exacto": true, "margen_s": 1
  }
}
```

Estados del recorrido: `esperando` (aún no entra a la red), `en_ruta`, `llego`, `finalizado`, `reiniciado`.

## Precisión de la cuenta regresiva

SUMO avanza en pasos de 1 s y aplica cada cambio de fase en un segundo entero, mientras que el plan Webster tiene
duraciones con decimales. Medido sobre 170 cambios en la red del eje: sin corrección el cambio llegaba 0,6 a 1,7 s
tarde; con la corrección de `segundos_visibles`, 150 de 170 predicciones son exactas y el resto se desvía 1 s.

Con un controlador **adaptativo** (Max-Pressure o el agente) el cambio se decide cada 5 s, así que solo se conoce
un mínimo (el verde mínimo). Cuando se incorpore, `exacto` pasa a `false` y la app debe mostrarlo como estimación.

## Limitaciones conocidas

- **La red del eje no está conectada de punta a punta.** Desde la Alameda se llega hasta Bustamante (C03), pero no
  hacia el oriente por Providencia; de Tobalaba al oriente (C07 a C13) no hay ruta con la Alameda en ningún sentido.
  Por eso los destinos son Bustamante (oriente, 1,7 km) y Matucana (poniente, 2,9 km).
- La demanda (`routes.rou.xml`) dura una hora simulada; al terminar, la simulación se reinicia con otra semilla y
  los recorridos abiertos quedan como `reiniciado`.
- El origen es fijo (Alameda frente a Plaza de Armas). Rutas alternativas, origen libre y WebSocket son las
  etapas siguientes.

## Pruebas

`tests/test_simulacion.py`: la cuenta regresiva sobre un programa sintético, la predicción contra el cambio real en
SUMO, el rumbo y el nivel de servicio, y el servicio de punta a punta sobre la red del eje (viajes y proveedor de
tráfico).

El estado de un acceso usa el enlace que sigue derecho; si el acceso no tiene, el de giro a la derecha y luego a la
izquierda. Los niveles de servicio comparan la velocidad media con la libre: `fluido` ≥ 70 %, `moderado` ≥ 40 %,
`congestionado` por debajo; `libre` es una calle sin vehículos.
