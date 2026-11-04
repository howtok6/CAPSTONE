# Vía · Mockup Flutter

Vista de conducción móvil en tonos oscuros y amarillo. La ciudad en perspectiva
ocupa todo el fondo, con el auto al centro y casas y edificios a ambos lados.

- Semáforo superpuesto arriba, con cuenta regresiva y ciclo completo.
- Tarjetas desplegables: gasolina a la izquierda y gasto energético a la derecha.
- Selector de recorrido y botón de inicio en la parte inferior de la misma vista.
- Tocar Gasolina muestra 93, 95 y 97 octanos; elegir una opción cierra el panel.
- Tocar Gasto energético muestra distancia, energía equivalente y consumo base.
- El botón Ajustar del detalle permite modificar el consumo de referencia.
- Selector Conducción / Desde arriba con el mismo vehículo y ruta seleccionada.
- En Chrome de escritorio se centra una vista de hasta 430 px de ancho.
- En móvil se adapta al espacio disponible; las ventanas bajas escalan la vista
  completa para mantener los controles visibles sin desplazamiento.

Consumo = distancia × L/100 km ÷ 100. El octanaje no cambia el rendimiento.
La equivalencia de 8,9 kWh/L es un supuesto ilustrativo de energía del combustible.
El mapa, las rutas y el tráfico son conceptuales. Inicio y fin cambian el estado
demostrativo; no hay GPS ni desplazamiento real del auto.
No requiere API de mapas ni dependencias adicionales.

Ejecutar: `flutter run` o `flutter run -d chrome`.
Verificar: `flutter analyze` y `flutter test`.


## Conexión con la simulación en vivo

Desde noviembre de 2026 la app puede leer el panel «Próximo semáforo» desde la API de simulación de la tesis
(`tsc-thesis/api` en la rama `master`). Si la API no responde, todo sigue funcionando en modo demo, como antes.

1. En el PC, desde `tsc-thesis/`: `python scripts/run_api.py`.
2. Con el celular conectado por USB: `adb reverse tcp:8000 tcp:8000`.
3. `flutter run` (o instalar el APK). Al abrir, los destinos cambian a los de la simulación; con
   «Iniciar recorrido» la etiqueta pasa de DEMO a EN VIVO y el semáforo muestra el cruce real de la ruta, su
   distancia y los segundos para el cambio.

Por Wi-Fi: `flutter run --dart-define=API_URL=http://<IP del PC>:8000`.

El cliente está en `lib/via_api.dart`; `test/widget_test.dart` incluye una prueba del modo en vivo con una API simulada.

## Proponer rutas (OpenStreetMap)

El botón junto al selector de recorrido abre «Proponer ruta». Ahí el usuario fija el origen (por defecto Plaza de
Armas), el destino y hasta tres paradas, buscándolos por nombre o tocando el mapa. La app compara la ruta más
rápida con sus alternativas y la elegida se agrega al selector con ★. Su distancia alimenta el gasto energético,
y su primera indicación aparece sobre el auto.

| Qué | Servicio | Archivo |
|---|---|---|
| Mapa | Teselas de OpenStreetMap con `flutter_map` (modo oscuro) | `lib/proponer_ruta.dart` |
| Buscar lugares y nombrar el punto tocado | Nominatim, limitado al Gran Santiago | `lib/rutas_osm.dart` |
| Rutas, alternativas e indicaciones | OSRM, perfil auto | `lib/rutas_osm.dart` |

- Las rutas propuestas no existen en la red de la simulación: se recorren en modo demo, aunque la API esté activa.
- Los servidores públicos son solo para desarrollo. Nominatim admite 1 consulta por segundo (la app lo respeta y
  busca solo al confirmar, sin autocompletar), y las teselas de OSM piden identificar la app y no usarlas a gran
  escala. Para producción se cambian al compilar:
  `flutter run --dart-define=OSRM_URL=https://... --dart-define=NOMINATIM_URL=https://...`
- Las rutas propuestas se guardan solo en memoria: se pierden al cerrar la app.
