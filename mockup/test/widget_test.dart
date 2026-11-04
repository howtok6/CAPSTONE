import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mockup/main.dart';
import 'package:mockup/via_api.dart';

http.Response _json(Object cuerpo, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(cuerpo)),
  status,
  headers: {'content-type': 'application/json'},
);

void main() {
  for (final size in [
    const Size(320, 568),
    const Size(360, 640),
    const Size(390, 844),
    const Size(1440, 1000),
  ]) {
    testWidgets('All driving controls stay inside the phone view at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MyApp());
      final scene = tester.getRect(find.byKey(const Key('driving-view')));
      for (final key in [
        'traffic-panel',
        'fuel-panel',
        'energy-panel',
        'route-controls',
        'view-selector',
      ]) {
        final rect = tester.getRect(find.byKey(Key(key)));
        expect(
          scene.contains(rect.topLeft),
          isTrue,
          reason: '$key must be inside scene',
        );
        expect(
          scene.contains(rect.bottomRight),
          isTrue,
          reason: '$key must be inside scene',
        );
      }
      final fuel = tester.getRect(find.byKey(const Key('fuel-panel')));
      final energy = tester.getRect(find.byKey(const Key('energy-panel')));
      final signal = tester.getRect(find.byKey(const Key('traffic-panel')));
      final controls = tester.getRect(find.byKey(const Key('route-controls')));
      expect(fuel.right, lessThan(energy.left));
      expect(signal.bottom, lessThan(fuel.top));
      expect(fuel.bottom, lessThan(controls.top));
      expect(energy.bottom, lessThan(controls.top));
      expect(scene.width, lessThanOrEqualTo(430));
      expect(find.byType(SingleChildScrollView), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    });
  }

  testWidgets('Mobile fuel, route, consumption and traffic controls work', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const MyApp());
    expect(find.text('0.36 L'), findsOneWidget);
    expect(find.byKey(const Key('octane-97')), findsNothing);
    await tester.tap(find.byKey(const Key('fuel-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('octane-97')));
    await tester.pumpAndSettle();
    expect(find.text('97 oct.'), findsOneWidget);
    expect(find.byKey(const Key('octane-97')), findsNothing);
    expect(find.text('0.36 L'), findsOneWidget);
    await tester.tap(find.byKey(const Key('route-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Forestal · 6,2 km').last);
    await tester.pumpAndSettle();
    expect(find.text('0.47 L'), findsOneWidget);
    await tester.tap(find.byKey(const Key('energy-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('adjust-consumption')));
    await tester.pumpAndSettle();
    await tester.drag(
      find.byKey(const Key('efficiency-slider')),
      const Offset(60, 0),
    );
    await tester.pump();
    await tester.tap(find.text('Listo'));
    await tester.pumpAndSettle();
    expect(find.text('0.47 L'), findsNothing);
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    expect(find.text('Recorrido en curso · Demo'), findsOneWidget);
    await tester.tap(find.text('Finalizar recorrido'));
    await tester.pump();
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'Camera switching preserves route and expandable controls on small phones',
    (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MyApp());
      expect(find.byKey(const Key('rear-scene')), findsOneWidget);
      await tester.tap(find.byKey(const Key('view-above')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('overhead-scene')), findsOneWidget);
      await tester.tap(find.byKey(const Key('fuel-toggle')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('octane-93')), findsOneWidget);
      final controls = tester.getRect(find.byKey(const Key('route-controls')));
      expect(
        tester.getRect(find.byKey(const Key('fuel-panel'))).bottom,
        lessThan(controls.top),
      );
      await tester.tap(find.byKey(const Key('energy-toggle')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('octane-93')), findsNothing);
      expect(find.text('Equivalente'), findsOneWidget);
      expect(
        tester.getRect(find.byKey(const Key('energy-panel'))).bottom,
        lessThan(controls.top),
      );
      await tester.tap(find.byKey(const Key('view-driving')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('rear-scene')), findsOneWidget);
      expect(find.text('0.36 L'), findsOneWidget);
      await tester.tap(find.byKey(const Key('energy-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Equivalente'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets('Traffic light cycles through all colors', (tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('24s'), findsOneWidget);
    await tester.pump(const Duration(seconds: 24));
    expect(find.text('Amarillo → rojo'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    expect(find.text('Rojo → verde'), findsOneWidget);
    await tester.pump(const Duration(seconds: 25));
    expect(find.text('Verde → amarillo'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('En vivo: el panel muestra el semáforo de la simulación', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final llamadas = <String>[];
    final viaje = {
      'id': 'v1',
      'ruta': 0,
      'destino': 'Av. General Bustamante',
      'tiempo_sim': 400.0,
      'distancia_total_m': 1700,
    };
    final cliente = MockClient((req) async {
      final clave = '${req.method} ${req.url.path}';
      llamadas.add(clave);
      switch (clave) {
        case 'GET /destinos':
          return _json([
            {
              'ruta': 0,
              'nombre': 'Av. General Bustamante',
              'distancia_km': 1.7,
            },
            {'ruta': 1, 'nombre': 'Matucana', 'distancia_km': 2.9},
          ]);
        case 'POST /viajes':
          return _json({...viaje, 'estado': 'esperando'}, 201);
        case 'GET /viajes/v1':
          return _json({
            ...viaje,
            'estado': 'en_ruta',
            'distancia_restante_m': 1500,
            'proximo_semaforo': {
              'id': 'GS_1',
              'nombre': 'Alameda × Santa Rosa',
              'distancia_m': 120,
              'color': 'rojo',
              'segundos_para_cambio': 17,
              'siguiente_color': 'verde',
              'exacto': true,
            },
          });
        case 'DELETE /viajes/v1':
          return http.Response('', 204);
      }
      return http.Response('no encontrado', 404);
    });
    await tester.pumpWidget(
      MaterialApp(
        home: MobilityPage(
          api: ViaApi(baseUrl: 'http://api.test', client: cliente),
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Av. General Bustamante · 1,7 km'), findsOneWidget);

    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    await tester.pump();
    expect(find.text('EN VIVO'), findsOneWidget);

    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
    expect(find.text('Alameda × Santa Rosa'), findsOneWidget);
    expect(find.text('17s'), findsOneWidget);
    expect(find.text('Rojo → verde · a 120 m'), findsOneWidget);
    expect(
      find.text('Recorrido en curso · Simulación en vivo'),
      findsOneWidget,
    );

    await tester.tap(find.text('Finalizar recorrido'));
    await tester.pump();
    expect(find.text('DEMO'), findsOneWidget);
    expect(llamadas, contains('DELETE /viajes/v1'));
    await tester.pumpWidget(const SizedBox());
  });

  group('En vivo: casos límite del semáforo', () {
    /// Abre la app contra una simulación simulada, inicia un recorrido y espera
    /// una consulta. [viaje] es lo que responde `GET /viajes/v1`.
    Future<void> iniciarEnVivo(
      WidgetTester tester,
      Map<String, Object?> viaje,
    ) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final base = {'id': 'v1', 'ruta': 0, 'destino': 'Av. General Bustamante'};
      final cliente = MockClient((req) async {
        switch ('${req.method} ${req.url.path}') {
          case 'GET /destinos':
            return _json([
              {
                'ruta': 0,
                'nombre': 'Av. General Bustamante',
                'distancia_km': 1.7,
              },
            ]);
          case 'POST /viajes':
            return _json({...base, 'estado': 'esperando'}, 201);
          case 'GET /viajes/v1':
            return _json({...base, ...viaje});
        }
        return http.Response('', 204);
      });
      await tester.pumpWidget(
        MaterialApp(
          home: MobilityPage(
            api: ViaApi(baseUrl: 'http://api.test', client: cliente),
          ),
        ),
      );
      await tester.pump();
      await tester.tap(find.text('Iniciar recorrido'));
      await tester.pump();
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();
    }

    String segundos(WidgetTester tester) =>
        tester.widget<Text>(find.byKey(const Key('traffic-seconds'))).data!;

    testWidgets('sin semáforo en la ruta no muestra segundos del demo', (
      tester,
    ) async {
      await iniciarEnVivo(tester, {'estado': 'esperando'});
      expect(find.text('Entrando a la vía…'), findsOneWidget);
      expect(segundos(tester), '—');
      // Pasan 5 s del reloj demo: en vivo el panel no debe cambiar.
      await tester.pump(const Duration(seconds: 5));
      expect(segundos(tester), '—');
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('un semáforo apagado no se muestra en rojo', (tester) async {
      await iniciarEnVivo(tester, {
        'estado': 'en_ruta',
        'proximo_semaforo': {
          'nombre': 'Alameda × Lira',
          'distancia_m': 80,
          'color': 'apagado',
          'segundos_para_cambio': null,
          'siguiente_color': null,
        },
      });
      expect(find.text('Semáforo apagado · a 80 m'), findsOneWidget);
      expect(segundos(tester), '—');
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('una cuenta regresiva no exacta se marca como estimada', (
      tester,
    ) async {
      await iniciarEnVivo(tester, {
        'estado': 'en_ruta',
        'proximo_semaforo': {
          'nombre': 'Alameda × Santa Rosa',
          'distancia_m': 200,
          'color': 'verde',
          'segundos_para_cambio': 12,
          'siguiente_color': 'amarillo',
          'exacto': false,
        },
      });
      expect(segundos(tester), '≈12s');
      expect(find.text('estimado'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });
  });

  testWidgets('Finalizar mientras se crea el viaje retira el vehículo', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final llamadas = <String>[];
    final creacion = Completer<http.Response>();
    final cliente = MockClient((req) async {
      final clave = '${req.method} ${req.url.path}';
      llamadas.add(clave);
      switch (clave) {
        case 'GET /destinos':
          return _json([
            {
              'ruta': 0,
              'nombre': 'Av. General Bustamante',
              'distancia_km': 1.7,
            },
          ]);
        case 'POST /viajes':
          return creacion.future; // la API todavía no responde
      }
      return http.Response('', 204);
    });
    await tester.pumpWidget(
      MaterialApp(
        home: MobilityPage(
          api: ViaApi(baseUrl: 'http://api.test', client: cliente),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    await tester.tap(find.text('Finalizar recorrido'));
    await tester.pump();
    // La API responde tarde: el viaje ya no corresponde y debe retirarse.
    creacion.complete(
      _json({
        'id': 'v9',
        'estado': 'esperando',
        'ruta': 0,
        'destino': 'Av. General Bustamante',
      }, 201),
    );
    await tester.pump();
    await tester.pump();

    expect(llamadas, contains('DELETE /viajes/v9'));
    expect(find.text('DEMO'), findsOneWidget);
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
