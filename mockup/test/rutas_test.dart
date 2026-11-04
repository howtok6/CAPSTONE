import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mockup/main.dart';
import 'package:mockup/rutas_osm.dart';
import 'package:mockup/via_api.dart';

http.Response _json(Object cuerpo, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(cuerpo)),
  status,
  headers: {'content-type': 'application/json'},
);

Map<String, dynamic> _paso(String tipo, String? modificador, String calle) => {
  'name': calle,
  'distance': 100.0,
  'maneuver': {'type': tipo, 'modifier': ?modificador},
};

/// Respuesta de OSRM recortada: dos alternativas, [lon, lat] en GeoJSON.
final _osrm = {
  'code': 'Ok',
  'routes': [
    {
      'distance': 4167.7,
      'duration': 461.4,
      'geometry': {
        'coordinates': [
          [-70.6506, -33.4378],
          [-70.6275, -33.4372],
        ],
      },
      'legs': [
        {
          'steps': [
            _paso('depart', 'left', 'Plaza de Armas'),
            _paso('turn', 'right', 'Bandera'),
            _paso('new name', 'straight', 'Alameda'),
            _paso('arrive', null, ''),
          ],
        },
      ],
    },
    {
      'distance': 5300.0,
      'duration': 600.0,
      'geometry': {
        'coordinates': [
          [-70.6506, -33.4378],
          [-70.6400, -33.4300],
          [-70.6275, -33.4372],
        ],
      },
      'legs': [
        {
          'steps': [_paso('depart', null, 'Plaza de Armas')],
        },
      ],
    },
  ],
};

const _destino = Lugar('Cerro Santa Lucía', LatLng(-33.4372, -70.6275));

void main() {
  test('Enrutador pide la ruta a OSRM e interpreta distancia, trazado y pasos', () async {
    late Uri pedido;
    final enrutador = Enrutador(
      baseUrl: 'http://osrm.test',
      client: MockClient((req) async {
        pedido = req.url;
        return _json(_osrm);
      }),
    );
    final rutas = await enrutador.calcular([
      const Lugar('Plaza de Armas', LatLng(-33.4378, -70.6506)),
      _destino,
    ]);

    expect(
      pedido.path,
      '/route/v1/driving/-70.6506,-33.4378;-70.6275,-33.4372',
    );
    expect(pedido.queryParameters['alternatives'], 'true');
    expect(rutas, hasLength(2));
    final r = rutas.first;
    expect(r.nombre, 'Plaza de Armas → Cerro Santa Lucía');
    expect(r.distanciaKm, closeTo(4.17, .01));
    expect(r.duracionMin, closeTo(7.69, .01));
    // GeoJSON viene como [lon, lat]: el primer punto debe quedar en la latitud.
    expect(r.trazado.first.latitude, -33.4378);
    expect(r.trazado.first.longitude, -70.6506);
    expect(r.pasos.map((p) => p.indicacion), [
      '←  Sal por Plaza de Armas',
      '→  Gira a la derecha por Bandera',
      '↑  Continúa por Alameda',
      '⚑  Llegas a tu destino',
    ]);
  });

  test('Con paradas intermedias, la llegada de cada tramo es una parada', () {
    final ruta = RutaPropuesta.fromOsrm(
      {
        'distance': 1000,
        'duration': 120,
        'geometry': {'coordinates': []},
        'legs': [
          {
            'steps': [_paso('depart', null, 'A'), _paso('arrive', null, '')],
          },
          {
            'steps': [_paso('depart', null, 'B'), _paso('arrive', null, '')],
          },
        ],
      },
      [plazaDeArmas, _destino],
    );
    expect(ruta.pasos.map((p) => p.tipo), ['depart', 'parada', 'arrive']);
  });

  test(
    'Sin ruta posible, OSRM responde 400 y se informa con un mensaje claro',
    () async {
      final enrutador = Enrutador(
        baseUrl: 'http://osrm.test',
        client: MockClient(
          (_) async =>
              _json({'code': 'NoRoute', 'message': 'Impossible route'}, 400),
        ),
      );
      expect(
        () => enrutador.calcular([plazaDeArmas, _destino]),
        throwsA(
          isA<ServicioMapaException>().having(
            (e) => e.mensaje,
            'mensaje',
            'No hay ruta en auto entre esos puntos',
          ),
        ),
      );
    },
  );

  test(
    'BuscadorLugares limita la búsqueda a Santiago y lee Nominatim',
    () async {
      late Uri pedido;
      final buscador = BuscadorLugares(
        baseUrl: 'http://nominatim.test',
        client: MockClient((req) async {
          pedido = req.url;
          return _json([
            {
              'name': 'Costanera Center',
              'display_name': 'Costanera Center, Providencia, Santiago, Chile',
              'lat': '-33.4176',
              'lon': '-70.6064',
            },
          ]);
        }),
      );
      final lugares = await buscador.buscar('Costanera');
      expect(pedido.path, '/search');
      expect(pedido.queryParameters['q'], 'Costanera');
      expect(pedido.queryParameters['countrycodes'], 'cl');
      expect(pedido.queryParameters['bounded'], '1');
      expect(lugares.single.nombre, 'Costanera Center');
      expect(lugares.single.punto, const LatLng(-33.4176, -70.6064));
    },
  );

  testWidgets('El usuario propone una ruta y queda elegida en el selector', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    // Simulación activa: las rutas propuestas conviven con sus destinos.
    final llamadas = <String>[];
    final simulacion = MockClient((req) async {
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
          return _json({
            'id': 'v1',
            'estado': 'esperando',
            'ruta': 0,
            'destino': 'Av. General Bustamante',
          }, 201);
      }
      return http.Response('', 204);
    });
    await tester.pumpWidget(
      MaterialApp(
        home: MobilityPage(
          api: ViaApi(baseUrl: 'http://api.test', client: simulacion),
          buscador: BuscadorLugares(
            baseUrl: 'http://nominatim.test',
            client: MockClient(
              (_) async => _json([
                {
                  'name': 'Cerro Santa Lucía',
                  'display_name': 'Cerro Santa Lucía, Santiago, Chile',
                  'lat': '-33.4372',
                  'lon': '-70.6275',
                },
              ]),
            ),
          ),
          enrutador: Enrutador(
            baseUrl: 'http://osrm.test',
            client: MockClient((_) async => _json(_osrm)),
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Av. General Bustamante · 1,7 km'), findsOneWidget);

    await tester.tap(find.byKey(const Key('propose-route')));
    await tester.pumpAndSettle();
    expect(find.text('Plaza de Armas'), findsOneWidget);
    expect(find.text('Elige el destino'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('place-search')),
      'Santa Lucía',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cerro Santa Lucía').last);
    await tester.pumpAndSettle();

    expect(find.text('Más rápida · 4,2 km · 8 min'), findsOneWidget);
    expect(find.text('Alternativa 1 · 5,3 km · 10 min'), findsOneWidget);
    await tester.tap(find.byKey(const Key('alternative-1')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('confirm-route')));
    await tester.pumpAndSettle();

    expect(
      find.text('★ Plaza de Armas → Cerro Santa Lucía · 5,3 km'),
      findsOneWidget,
    );
    expect(find.text('Desde Plaza de Armas · 10 min'), findsOneWidget);
    expect(find.text('↑  Sal por Plaza de Armas'), findsOneWidget);

    // Las rutas propuestas no existen en la simulación: se recorren en demo.
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    expect(find.text('Recorrido en curso · Demo'), findsOneWidget);
    expect(find.text('DEMO'), findsOneWidget);
    expect(llamadas, isNot(contains('POST /viajes')));

    // Volver a un destino de la simulación termina el recorrido y lo inicia en vivo.
    await tester.tap(find.byKey(const Key('route-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Av. General Bustamante · 1,7 km').last);
    await tester.pumpAndSettle();
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    await tester.pump();
    expect(llamadas, contains('POST /viajes'));
    expect(find.text('EN VIVO'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
