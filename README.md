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

