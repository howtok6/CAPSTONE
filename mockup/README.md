# Vía · App móvil de conducción (Flutter)

«Vía» es la app móvil del proyecto CAPSTONE de control adaptativo de semáforos. Muestra al conductor el próximo
semáforo de su ruta, con la cuenta regresiva para el cambio, y estima el combustible del recorrido. La app vive en
la rama `dev-benja`, y la simulación de tránsito que la alimenta, en la rama `master` (`tsc-thesis/api`).

## Cómo funciona

### La pantalla de conducción

La ciudad ocupa todo el fondo, con el auto al centro. Sobre ella:

- **Próximo semáforo** (arriba): luces, nombre del cruce, el cambio que viene (por ejemplo «Rojo → verde») y los
  segundos que faltan.
- **Indicación de la ruta**: la siguiente maniobra, por ejemplo «↑  Continúa por Av. Alameda».
- **Cámara**: «Conducción» (vista desde detrás del auto) o «Desde arriba» (plano de la ciudad).
- **Gasolina** (tarjeta izquierda): elige 93, 95 o 97 octanos. Es informativo; no cambia el consumo.
- **Gasto energético** (tarjeta derecha): litros estimados, distancia, equivalente en kWh y consumo de referencia,
  que se ajusta con «Ajustar» entre 4 y 14 L/100 km.
- **Recorrido** (abajo): selector de destino, botón para proponer una ruta, tiempo estimado e
  «Iniciar / Finalizar recorrido».

Cálculos: consumo = distancia × L/100 km ÷ 100. La equivalencia de 8,9 kWh/L es un supuesto ilustrativo.

### Tres modos según de dónde salen los datos

| Modo | Cuándo se usa | Semáforo y destinos | Etiqueta |
|---|---|---|---|
| **Demo** | La API de simulación no responde | Simulados en la app: ciclo verde 30 s, amarillo 5 s y rojo 25 s; destinos fijos (Bustamante y Forestal) | DEMO |
| **En vivo** | La API responde y se inicia un recorrido hacia uno de sus destinos | La simulación SUMO crea un vehículo en la ruta y la app consulta cada segundo su próximo semáforo | EN VIVO |
| **Ruta propuesta** | El usuario eligió una ruta propia (★ en el selector) | Ruta real de OpenStreetMap; el semáforo queda en demo | DEMO |

La app nunca se bloquea por falta de conexión: si la API no está, todo sigue en modo demo.

Las rutas propuestas se recorren en demo porque sus calles no existen en la red de la simulación, y por eso no
hay semáforos simulados para ellas.

### Proponer una ruta

1. Toca el ícono de camino junto al selector de recorrido.
2. El origen viene puesto en Plaza de Armas. Fija el destino, y si quieres hasta 3 paradas:
   - buscando por nombre (Enter o la lupa), con resultados limitados al Gran Santiago;
   - o tocando el mapa, y la app le pone nombre al punto.
3. Con origen y destino listos, la ruta se calcula sola. Elige entre la más rápida y sus alternativas.
4. «Proponer ruta» la agrega al selector con ★.

Desde ahí, su distancia se usa en el gasto energético, su duración en el tiempo estimado y su primera maniobra
en la indicación sobre el auto.

| Qué | Servicio | Archivo |
|---|---|---|
| Mapa de fondo | Teselas de OpenStreetMap con `flutter_map`, en modo oscuro | `lib/proponer_ruta.dart` |
| Buscar lugares y nombrar el punto tocado | **Nominatim** (texto ↔ coordenadas) | `lib/rutas_osm.dart` |
| Rutas, alternativas e indicaciones | **OSRM** (rutas en auto por calles reales) | `lib/rutas_osm.dart` |

## Cómo ejecutarla

Requisitos: Flutter con Dart 3.13.5 o superior, e internet para el mapa y las rutas.

```powershell
cd mockup            # la app está en esta carpeta, no en la raíz del repo
flutter pub get
flutter run -d chrome   # o `flutter run` con un celular conectado
```

Mientras corre: `r` recarga los cambios, `R` reinicia la app y `q` sale.

En Windows, compilar para Android puede pedir activar el **Modo de desarrollador** (Configuración → Para
programadores), porque `flutter_map` incluye un plugin nativo.

### Con la simulación en vivo (opcional)

1. En el PC, desde `tsc-thesis/` de la rama `master`, ejecuta `python scripts/run_api.py`. Requiere Python 3.13,
   SUMO y FastAPI.
2. Si usas un celular por USB, ejecuta `adb reverse tcp:8000 tcp:8000`. Hay que repetirlo cada vez que se
   reconecta el cable.
3. `flutter run`. Al abrir, los destinos cambian a los de la simulación; con «Iniciar recorrido» la etiqueta pasa
   a EN VIVO.

### Configuración al compilar

Cada servicio se puede cambiar con `--dart-define`, por ejemplo
`flutter run --dart-define=API_URL=http://192.168.1.50:8000`.

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `API_URL` | API de la simulación | `http://127.0.0.1:8000` |
| `OSRM_URL` | Cálculo de rutas | `https://router.project-osrm.org` |
| `NOMINATIM_URL` | Búsqueda de lugares | `https://nominatim.openstreetmap.org` |

Los servidores públicos de OpenStreetMap son solo para desarrollo. Nominatim admite 1 consulta por segundo (la
app lo respeta y no autocompleta mientras se escribe), y las teselas piden identificar la app y no usarlas a gran
escala. Para producción hay que usar un servidor propio o un proveedor.

### Verificar

```powershell
flutter analyze
flutter test
```

Hay 13 pruebas:

- **Diseño:** los controles caben en pantallas de 360×640, 390×844 y 1440×1000.
- **Paneles:** gasolina, consumo, cámara y ciclo del semáforo.
- **Modo en vivo:** con una API simulada.
- **Proponer rutas:**
  - lectura de las respuestas de OSRM y Nominatim, con errores y paradas;
  - el flujo completo con la simulación activa, que comprueba que una ruta propuesta va en demo y que un
    destino de la simulación va en vivo.

Las pruebas no usan internet: las respuestas de los servicios son simuladas.

## Estructura del código

| Archivo | Contenido |
|---|---|
| `lib/main.dart` | Pantalla de conducción, estado de los tres modos, paneles y controles |
| `lib/driving_scene.dart` | Dibujo de la ciudad en perspectiva, vista desde detrás del auto |
| `lib/overhead_scene.dart` | Dibujo del plano de la ciudad, vista desde arriba |
| `lib/via_api.dart` | Cliente de la API de simulación: destinos, viajes y próximo semáforo |
| `lib/rutas_osm.dart` | Clientes de Nominatim y OSRM, y los modelos `Lugar`, `Paso` y `RutaPropuesta` |
| `lib/proponer_ruta.dart` | Pantalla «Proponer ruta»: mapa, paradas, búsqueda y alternativas |
| `test/widget_test.dart` | Pruebas de diseño, paneles y modo en vivo |
| `test/rutas_test.dart` | Pruebas de proponer rutas |

Cada clase y función tiene un comentario que explica qué hace y por qué.

## Historial de cambios

| Fecha | Autor | Cambio |
|---|---|---|
| 15-oct-2026 | Benjamín Quiroz | Mockup inicial: vista de conducción, semáforo simulado, paneles de gasolina y gasto energético, cámara «Desde arriba» y diseño adaptable a teléfono y escritorio |
| 3-nov-2026 | Gabriel Cárdenas | Conexión con la simulación en vivo (`5c4b7e3`): cliente `via_api.dart`, panel del semáforo, destinos y estado del recorrido desde la API, permiso de red en Android y prueba del modo en vivo |
| 3-nov-2026 | Benjamín Quiroz | Proponer rutas con OpenStreetMap (`70c005f`): búsqueda con Nominatim, rutas y alternativas con OSRM, mapa con `flutter_map` y 5 pruebas nuevas |
| 4-nov-2026 | Benjamín Quiroz | Documentación del código y de este README |

## Limitaciones conocidas y pendientes

- **No hay GPS.** El auto no se mueve en pantalla; la ciudad dibujada es conceptual.
- **Rutas propuestas:**
  - se guardan solo en memoria y se pierden al cerrar la app;
  - se recorren en demo.
- **Simulación:**
  - el origen es fijo (Alameda frente a Plaza de Armas);
  - solo hay dos destinos (Bustamante y Matucana), porque la red simulada no está conectada de punta a punta.
- **Modo en vivo, detalles por corregir:**
  - si se finaliza el recorrido mientras se crea el viaje, el vehículo queda abierto en la simulación;
  - mientras no hay semáforo en la ruta, el panel muestra segundos del ciclo demo;
  - un semáforo `apagado` se muestra en rojo;
  - el campo `exacto` aún no se usa para avisar que la cuenta regresiva es una estimación.
- **iOS:** falta la excepción de ATS para conectarse por HTTP a la API en desarrollo.
- **Identificador de la app:** es `com.example.mockup`, y también se usa para identificarse ante OpenStreetMap.
  Conviene cambiarlo por el definitivo.
