# Arquitectura del proyecto

Registrada el 4-nov-2026. La app móvil habla con un único **backend en Go**; la **simulación** pasa a ser un
entorno de pruebas que provee datos de tráfico, y todos los servicios se comunican por HTTP.

```
┌──────────────┐  HTTP /v1   ┌──────────────┐  HTTP  ┌───────────────────────────┐
│ App Vía      │────────────▶│ Backend Go   │───────▶│ Simulación (Python, SUMO) │  entorno de pruebas
│ Flutter      │             │ backend/     │        │ simulacion/               │  → en producción, datos reales
│ (dev-benja)  │             │ :8080        │        │ :8000, solo red interna   │
└──────────────┘             │              │  HTTP  ┌───────────────────────────┐
                             │              │───────▶│ OSRM: rutas en auto       │
                             │              │  HTTP  ┌───────────────────────────┐
                             │              │───────▶│ Nominatim: lugares        │
                             └──────────────┘        └───────────────────────────┘
                                                      tsc-thesis/: investigación de la tesis
                                                      (la simulación importa su arnés y su red)
```

## Responsabilidades

| Componente | Carpeta | Responsable de | No hace |
|---|---|---|---|
| App «Vía» | `mockup/` en la rama `dev-benja` | Interfaz, GPS del celular, mapa | No llama a OSRM, Nominatim ni a la simulación |
| Backend | `backend/` | Contrato `/v1`, lógica de negocio (semáforos de una ruta, próximo semáforo, viajes), caché y límites de los servicios externos | No simula ni calcula rutas por sí mismo |
| Simulación | `simulacion/` | Estado de semáforos por acceso, tráfico por calle, viajes simulados | No conoce a la app ni a los usuarios |
| Tesis | `tsc-thesis/` | Experimentos: controladores, agente, evaluación | No depende de la app ni del backend |

## Decisiones (4-nov-2026)

| Decisión | Elegido | Por qué |
|---|---|---|
| Lenguaje del backend | Go 1.25, solo biblioteca estándar | Pedido del proyecto; binario único y sin dependencias |
| Comunicación entre servicios | HTTP + JSON | Cada servicio se reemplaza sin tocar los demás |
| Cómo se sigue al usuario | GPS real del celular + viaje simulado para demos | El GPS es el caso real; el simulado permite probar sin moverse |
| Dónde se guardan viajes y ubicaciones | En memoria, detrás de una interfaz | Suficiente para el prototipo; se cambia por una base de datos sin tocar la lógica |
| Ubicación en el repositorio | `backend/` y `simulacion/` en `master` | Junto a `tsc-thesis/`; la app sigue en `dev-benja` |
| Rol de la simulación | Proveedor de tráfico detrás de una interfaz (`servicios.ProveedorTrafico`) | En producción se conecta una fuente real (p. ej. UOCT) con el mismo contrato |

## Ejecutar todo

**Con Docker** (desde la raíz): `docker compose up --build`. El backend queda en `http://localhost:8080` y la
simulación solo en la red interna.

**Sin Docker**, en dos terminales:

```bash
cd simulacion && python run.py            # :8000
cd backend && go run ./cmd/via-backend    # :8080
```

**Celular por USB:** `adb reverse tcp:8080 tcp:8080`; la app usa `http://127.0.0.1:8080` por defecto.
**Por Wi-Fi:** `flutter run --dart-define=API_URL=http://<IP del PC>:8080` y permitir el puerto 8080 en el firewall.

## Contratos

- Backend `/v1` (lo que consume la app): [`../backend/README.md`](../backend/README.md).
- Simulación (lo que consume el backend): [`../simulacion/README.md`](../simulacion/README.md).

## Limitaciones conocidas

- La red simulada cubre solo una franja de 150 m alrededor del eje y no está conectada de punta a punta (ver
  [`integracion-app/avance-2026-11-03.md`](integracion-app/avance-2026-11-03.md)). Las rutas de OSRM pueden pasar
  por calles fuera de esa franja; sus semáforos no aparecen.
- Los servidores públicos de OSRM y Nominatim son para desarrollo; en producción se necesita uno propio.
- Viajes y ubicaciones viven en memoria: se pierden al reiniciar el backend.
