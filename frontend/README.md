# Vía · App móvil de conducción (Flutter)

«Vía» es la app móvil del proyecto CAPSTONE de control adaptativo de semáforos. Muestra al conductor el próximo
semáforo de su ruta, con la cuenta regresiva para el cambio, y estima el combustible del recorrido. La app vive en
la rama `dev-benja`. Habla **solo con el backend Go** del proyecto (`backend/` en la rama `master`), que a su vez
consulta la simulación de tránsito, OSRM y Nominatim. La arquitectura completa está en `docs/arquitectura.md` de
`master`.

## Cómo funciona

### La pantalla de conducción

El fondo es un **mapa 3D low poly navegable** de Santiago: se arrastra, se acerca y aleja con dos dedos, se gira
y se inclina. Muestra la ruta elegida (en amarillo, con sus paradas A y B), los semáforos por los que pasa y, durante
un recorrido, el próximo semáforo con el color que tiene en ese momento. El punto azul es el usuario (con un círculo
cuando la ubicación es aproximada) y el punto amarillo, el vehículo de un viaje simulado.

La cámara sigue al usuario durante el recorrido. Al mover el mapa con los dedos deja de seguirlo, y el botón de
recentrar (sobre el panel de recorrido) la devuelve. Sin recorrido, al elegir una ruta propuesta el mapa la encuadra
completa.

Sobre el mapa:

- **Próximo semáforo** (arriba): luces, nombre del cruce, el cambio que viene (por ejemplo «Rojo → verde») y los
  segundos que faltan.
- **Indicación de la ruta**: la siguiente maniobra, por ejemplo «↑  Continúa por Av. Alameda».
- **Cámara**: «Conducción» (cerca, inclinada y mirando hacia donde avanza el usuario) o «Desde arriba» (cenital,
  con el norte arriba).
- **Ubicación** (indicador del encabezado): «Exacta», «≈ 500 m» o «Sin ubicación». Tocarlo permite cambiarla.
- **Gasolina** (tarjeta izquierda): elige 93, 95 o 97 octanos. Es informativo; no cambia el consumo.
- **Gasto energético** (tarjeta derecha): litros estimados, distancia, equivalente en kWh y consumo de referencia,
  que se ajusta con «Ajustar» entre 4 y 14 L/100 km.
- **Recorrido** (abajo): selector de destino, botón para proponer una ruta, tiempo estimado e
  «Iniciar / Finalizar recorrido».

Cálculos: consumo = distancia × L/100 km ÷ 100. La equivalencia de 8,9 kWh/L es un supuesto ilustrativo.

### Ubicación: exacta o por rango

La primera vez que se abre la app pregunta cómo compartir la ubicación:

| Opción | Qué se usa | Para qué alcanza |
|---|---|---|
| **Exacta** | La posición del GPS tal cual | Próximo semáforo y distancia precisos |
| **Aproximada** (250 m, 500 m o 1 km) | El centro de una cuadrícula del tamaño elegido; mientras el usuario se mueve dentro de una celda, la posición no cambia | Ver la zona en el mapa; el próximo semáforo pasa a ser una estimación |
| **Ahora no** | Nada; no se pide permiso | Los recorridos van en demo |

La posición real nunca sale del celular en modo aproximado: la app la ajusta antes de mostrarla y antes de enviarla
al backend (con `precision_m` igual al rango). Después la app pide el permiso al sistema. En Android 12 o más el
diálogo del sistema también ofrece «Precisa» o «Aproximada»; si el sistema solo concede la aproximada, la app la
trata como un rango de 2 km y lo indica en el encabezado. La elección se guarda (`shared_preferences`) y se cambia
tocando el indicador de ubicación. Si el permiso quedó negado de forma permanente, el aviso ofrece ir a los ajustes.

### Tres modos según de dónde salen los datos

| Modo | Cuándo se usa | Semáforo y destinos | Etiqueta |
|---|---|---|---|
| **Demo** | El backend no responde | Simulados en la app: ciclo verde 30 s, amarillo 5 s y rojo 25 s; destinos fijos (Bustamante y Forestal) | DEMO |
| **Viaje simulado** | Se inicia un recorrido hacia un destino de la simulación | Un vehículo de la simulación recorre el destino; la app consulta cada segundo su próximo semáforo | EN VIVO |
| **Viaje GPS** | Se inicia una ruta propuesta (★) con permiso de ubicación | La app envía la ubicación del celular al backend, que responde el próximo semáforo de la ruta y su acceso | EN VIVO |

La app nunca se bloquea por falta de conexión: si el backend no está, o no hay permiso de ubicación, todo sigue en
modo demo.

En un viaje GPS solo aparecen los semáforos que existen en la red simulada (la franja del eje Alameda →
Providencia → Apoquindo); en calles fuera de ella el panel muestra «Sin semáforos en la ruta».

### Proponer una ruta

1. Toca el ícono de camino junto al selector de recorrido.
2. El origen viene puesto en tu ubicación (o en Plaza de Armas si no se conoce). Fija el destino, y si quieres hasta 3 paradas:
   - buscando por nombre (Enter o la lupa), con resultados limitados al Gran Santiago;
   - o tocando el mapa, y la app le pone nombre al punto.
3. Con origen y destino listos, la ruta se calcula sola. Elige entre la más rápida y sus alternativas.
4. «Proponer ruta» la agrega al selector con ★.

Desde ahí, la ruta se dibuja en el mapa principal, su distancia se usa en el gasto energético, su duración en el
tiempo estimado y su primera maniobra en la indicación de la ruta.

| Qué | Servicio | Archivo |
|---|---|---|
| Mapa 3D low poly | Teselas vectoriales de **OpenFreeMap** (datos de OpenStreetMap) con MapLibre y un estilo propio: edificios como bloques de color plano según su altura, sin íconos ni comercios | `lib/mapa_low_poly.dart` |
| Buscar lugares y nombrar el punto tocado | Backend `GET /v1/lugares` (Nominatim) | `lib/rutas_osm.dart` |
| Rutas, alternativas, indicaciones y semáforos de cada ruta | Backend `POST /v1/rutas` (OSRM) | `lib/rutas_osm.dart` |

## Cómo ejecutarla

Requisitos: Flutter con Dart 3.13.5 o superior, e internet para el mapa y las rutas.

La app está en la carpeta `frontend/` del repositorio (rama `dev-benja`), así que se ejecuta desde ahí:

```powershell
cd "D:\ruta\a\tu\copia\del\repo\frontend"   # la carpeta que contiene pubspec.yaml
flutter pub get
flutter run -d chrome   # o `flutter run` con un celular conectado
```

Si `flutter run` responde «No pubspec.yaml file found», la terminal está en otra carpeta, casi siempre la raíz
del repositorio: entra a `frontend/`. En VS Code, abrir directamente la carpeta `frontend/` hace que la terminal,
el botón ▶ y F5 funcionen sin el `cd`.

Mientras corre: `r` recarga los cambios, `R` reinicia la app y `q` sale.

En Windows, compilar para Android puede pedir activar el **Modo de desarrollador** (Configuración → Para
programadores), porque la app usa plugins nativos (`maplibre_gl` y `geolocator`).

### Con el backend (en vivo)

1. En el PC, en la rama `master`: `docker compose up --build` desde la raíz. Sin Docker, en dos terminales:
   `python simulacion/run.py` y `go run ./cmd/via-backend` dentro de `backend/`.
2. Si usas un celular por USB, ejecuta `adb reverse tcp:8080 tcp:8080`. Hay que repetirlo cada vez que se
   reconecta el cable.
3. `flutter run`. Al abrir, los destinos cambian a los de la simulación; con «Iniciar recorrido» la etiqueta pasa
   a EN VIVO. La primera vez la app pregunta cómo compartir la ubicación (exacta o por rango).

Los endpoints que usa la app, con ejemplos para probarlos y una prueba de humo
(`backend/pruebas/probar-endpoints.ps1`), están en `docs/integracion-app/endpoints.md` de `master`.

### Configuración al compilar

La URL del backend se cambia con `--dart-define`, por ejemplo
`flutter run --dart-define=API_URL=http://192.168.1.50:8080` (por Wi-Fi, con el puerto 8080 abierto en el
firewall del PC).

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `API_URL` | Backend Go de «Vía» | `http://127.0.0.1:8080` |

Las consultas a Nominatim y OSRM las hace el backend, que respeta el límite de 1 consulta por segundo de
Nominatim y guarda las respuestas en caché. Las teselas del mapa se piden directo a OpenFreeMap, que es gratis,
sin clave ni límite de visitas; para producción conviene alojar teselas propias.

### Verificar

```powershell
flutter analyze
flutter test
```

Hay 28 pruebas:

- **Diseño:** los controles caben en pantallas de 320×568, 360×640, 390×844 y 1440×1000.
- **Paneles:** gasolina, consumo, cámara y ciclo del semáforo.
- **Modo en vivo:** con una API simulada, incluidos los casos límite: sin semáforo en la ruta, semáforo apagado,
  cuenta regresiva estimada y finalizar mientras se crea el viaje.
- **Proponer rutas:**
  - lectura de las respuestas del backend (`/v1/rutas` y `/v1/lugares`), con errores, paradas y semáforos;
  - el flujo completo: una ruta propuesta va como viaje GPS, cada ubicación del GPS va al backend y el panel
    muestra el semáforo que responde; un destino de la simulación va como viaje simulado;
  - sin permiso de ubicación, la ruta propuesta se recorre en demo;
  - el mapa principal recibe la ruta elegida, sus paradas y la ubicación, y deja de seguir al usuario cuando este
    toca el mapa hasta que se recentra.
- **Ubicación:** la primera apertura pregunta y guarda la elección; el modo aproximado ajusta la posición a la
  cuadrícula del rango (y no cambia dentro de una celda); «Ahora no» no pide permiso ni vuelve a preguntar; si el
  sistema solo da ubicación aproximada, el encabezado lo indica.
- **Mapa low poly:** el estilo usa OpenFreeMap y levanta los edificios en colores planos sin íconos; el mapa solo
  se redibuja cuando cambian las rutas o las paradas; elegir paleta y tocar el mapa fija una parada. MapLibre es
  una vista nativa, así que las pruebas usan un mapa falso en su lugar.

Las pruebas no usan internet: las respuestas de los servicios son simuladas.

## Estructura del código

| Archivo | Contenido |
|---|---|
| `lib/main.dart` | Pantalla de conducción: mapa navegable, cámara que sigue al usuario, estado de los tres modos, paneles y controles |
| `lib/via_api.dart` | Cliente del backend: destinos simulados, viajes GPS y simulados, ubicación y próximo semáforo |
| `lib/rutas_osm.dart` | Búsqueda de lugares y rutas vía backend, y los modelos `Lugar`, `Paso` y `RutaPropuesta` |
| `lib/ubicacion.dart` | GPS del celular (`geolocator`) detrás de la interfaz `FuenteUbicacion`: preferencia exacta o por rango, permiso del sistema y ajuste a la cuadrícula |
| `lib/permiso_ubicacion.dart` | Hoja «¿Cómo quieres compartir tu ubicación?» |
| `lib/proponer_ruta.dart` | Pantalla «Proponer ruta»: paradas, búsqueda, alternativas y selector de paleta |
| `lib/mapa_low_poly.dart` | Mapa 3D low poly (MapLibre + OpenFreeMap): estilo, tres paletas, rutas, paradas, semáforos, marcador de posición con su zona y cámara que sigue |
| `test/widget_test.dart` | Pruebas de diseño, paneles y modo en vivo |
| `test/rutas_test.dart` | Pruebas de proponer rutas |
| `test/mapa_test.dart` | Pruebas del estilo low poly, las paletas y la conexión con el mapa |
| `test/ubicacion_test.dart` | Pruebas de la elección de ubicación, el modo aproximado y el marcador en el mapa |
| `test/apoyo.dart` | GPS y mapa falsos que comparten las pruebas |

Cada clase y función tiene un comentario que explica qué hace y por qué.

## Historial de cambios

| Fecha | Autor | Cambio |
|---|---|---|
| 15-oct-2026 | Benjamín Quiroz | Mockup inicial: vista de conducción, semáforo simulado, paneles de gasolina y gasto energético, cámara «Desde arriba» y diseño adaptable a teléfono y escritorio |
| 3-nov-2026 | Gabriel Cárdenas | Conexión con la simulación en vivo (`5c4b7e3`): cliente `via_api.dart`, panel del semáforo, destinos y estado del recorrido desde la API, permiso de red en Android y prueba del modo en vivo |
| 3-nov-2026 | Benjamín Quiroz | Proponer rutas con OpenStreetMap (`70c005f`): búsqueda con Nominatim, rutas y alternativas con OSRM, mapa con `flutter_map` y 5 pruebas nuevas |
| 4-nov-2026 | Benjamín Quiroz | Documentación del código y de este README |
| 4-nov-2026 | Benjamín Quiroz | Correcciones del modo en vivo, con 4 pruebas nuevas: un viaje finalizado mientras se creaba ya no queda abierto en la simulación; sin semáforo en la ruta, o con el semáforo apagado, el panel muestra «—» y luces apagadas en vez de datos del demo o rojo; una cuenta regresiva no exacta se muestra como «≈12s · estimado» |
| 4-nov-2026 | Gabriel Cárdenas | Mapa 3D low poly en «Proponer ruta»: MapLibre (`maplibre_gl`) con teselas vectoriales de OpenFreeMap en lugar de `flutter_map` y teselas raster; edificios extruidos de color plano, cámara inclinada y tres paletas (Noche, Maqueta, Pastel) |
| 4-nov-2026 | Gabriel Cárdenas | La app habla solo con el backend Go (`/v1`): lugares, rutas con sus semáforos y viajes. Las rutas propuestas se recorren como viaje GPS con la ubicación del celular (`lib/ubicacion.dart`, permisos de ubicación en Android) |
| 4-nov-2026 | Benjamín Quiroz | El proyecto Flutter pasa de `mockup/` a la raíz del repositorio en `dev-benja`, con el `.gitignore` de Flutter (el anterior dejaba fuera `android/`, `ios/` y `macos/`). Se movió con `git mv`, así que el historial de cada archivo se conserva (`git log --follow`) |
| 4-nov-2026 | Gabriel Cárdenas | Mapa navegable en la pantalla principal en lugar de los dibujos fijos: ruta elegida con sus semáforos, próximo semáforo con su color, usuario o vehículo simulado, cámara que sigue y botón de recentrar. Ubicación exacta o por rango (250 m, 500 m, 1 km) elegida al abrir la app y guardada; el origen de «Proponer ruta» parte en la ubicación del usuario. 7 pruebas nuevas |
| 4-nov-2026 | Benjamín Quiroz | Todo el proyecto Flutter pasa a la carpeta `frontend/` del repositorio, junto con su `.gitignore`; en la raíz queda solo un `.gitignore` para la configuración local del editor. Se movió con `git mv`, así que el historial de cada archivo se conserva (`git log --follow`) |

## Limitaciones conocidas y pendientes

- **GPS:** el seguimiento funciona con la app abierta (sin ubicación en segundo plano). En modo aproximado el
  próximo semáforo es una estimación: el backend lo calcula sobre el centro de la zona.
- **Mapa principal:** los destinos de demostración de la simulación no traen trazado, así que en un viaje simulado
  el mapa muestra el vehículo pero no la línea de la ruta.
- **Rutas propuestas:** se guardan solo en memoria y se pierden al cerrar la app.
- **Mapa low poly:** MapLibre funciona en Android, iOS y web, pero no en Windows, macOS ni Linux de escritorio (ahí
  la pantalla muestra un fondo liso con un aviso). La paleta elegida se recuerda solo mientras la app está abierta.
- **Simulación:**
  - el origen es fijo (Alameda frente a Plaza de Armas);
  - solo hay dos destinos (Bustamante y Matucana), porque la red simulada no está conectada de punta a punta.
- **iOS:** falta la excepción de ATS para conectarse por HTTP al backend en desarrollo (la descripción de uso de
  ubicación ya está en `Info.plist`, pero no se ha probado en un iPhone).
- **Identificador de la app:** es `com.example.mockup`, y también se usa para identificarse ante OpenStreetMap.
  Conviene cambiarlo por el definitivo.
