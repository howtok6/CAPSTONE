import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mockup/main.dart';
import 'package:mockup/mapa_low_poly.dart';
import 'package:mockup/rutas_osm.dart';
import 'package:mockup/ubicacion.dart';
import 'package:mockup/via_api.dart';

http.Response _json(Object cuerpo, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(cuerpo)),
  status,
  headers: {'content-type': 'application/json'},
);

Map<String, dynamic> _paso(String tipo, String? modificador, String calle) => {
  'tipo': tipo,
  'modificador': ?modificador,
  'calle': calle,
  'distancia_m': 100.0,
};

/// Respuesta de `POST /v1/rutas` recortada: dos alternativas, trazado [lat, lon].
final _rutas = [
  {
    'distancia_km': 4.1677,
    'duracion_min': 7.69,
    'trazado': [
      [-33.4378, -70.6506],
      [-33.4372, -70.6275],
    ],
    'pasos': [
      _paso('depart', 'left', 'Plaza de Armas'),
      _paso('turn', 'right', 'Bandera'),
      _paso('new name', 'straight', 'Alameda'),
      _paso('arrive', null, ''),
    ],
    'semaforos': [
      {
        'id': 'GS_1',
        'nombre': 'Alameda × San Antonio',
        'lat': -33.44,
        'lon': -70.645,
        'distancia_desde_inicio_m': 1054,
      },
    ],
  },
  {
    'distancia_km': 5.3,
    'duracion_min': 10.0,
    'trazado': [
      [-33.4378, -70.6506],
      [-33.4300, -70.6400],
      [-33.4372, -70.6275],
    ],
    'pasos': [_paso('depart', null, 'Plaza de Armas')],
    'semaforos': <Object>[],
  },
];

const _destino = Lugar('Cerro Santa Lucía', LatLng(-33.4372, -70.6275));

/// MapLibre es una vista nativa: en las pruebas se reemplaza por un recuadro.
Widget _mapaFalso(DatosMapa _) => const ColoredBox(color: Colors.black);

/// GPS falso: concede o niega el permiso y entrega las posiciones que se le pasen.
class _GpsFalso implements FuenteUbicacion {
  _GpsFalso({this.permite = true});
  final bool permite;
  final posiciones = StreamController<Posicion>.broadcast();
  @override
  Future<bool> permitir() async => permite;
  @override
  Stream<Posicion> seguir() => posiciones.stream;
}

void main() {
  test('Enrutador pide la ruta al backend e interpreta distancia, trazado, pasos y semáforos', () async {
    late http.Request pedido;
    final enrutador = Enrutador(
      baseUrl: 'http://api.test',
      client: MockClient((req) async {
        pedido = req;
        return _json(_rutas);
      }),
    );
    final rutas = await enrutador.calcular([
      const Lugar('Plaza de Armas', LatLng(-33.4378, -70.6506)),
      _destino,
    ]);

    expect(pedido.method, 'POST');
    expect(pedido.url.path, '/v1/rutas');
    final cuerpo = jsonDecode(pedido.body) as Map<String, dynamic>;
    expect(cuerpo['alternativas'], true);
    expect(cuerpo['paradas'], [
      {'lat': -33.4378, 'lon': -70.6506},
      {'lat': -33.4372, 'lon': -70.6275},
    ]);
    expect(rutas, hasLength(2));
    final r = rutas.first;
    expect(r.nombre, 'Plaza de Armas → Cerro Santa Lucía');
    expect(r.distanciaKm, closeTo(4.17, .01));
    expect(r.duracionMin, closeTo(7.69, .01));
    expect(r.trazado.first.latitude, -33.4378);
    expect(r.trazado.first.longitude, -70.6506);
    expect(r.trazadoLatLon.first, [-33.4378, -70.6506]);
    expect(r.semaforos.single.nombre, 'Alameda × San Antonio');
    expect(r.pasos.map((p) => p.indicacion), [
      '←  Sal por Plaza de Armas',
      '→  Gira a la derecha por Bandera',
      '↑  Continúa por Alameda',
      '⚑  Llegas a tu destino',
    ]);
  });

  test(
    'Las paradas intermedias que marca el backend se muestran como parada',
    () {
      final ruta = RutaPropuesta.fromJson(
        {
          'distancia_km': 1.0,
          'duracion_min': 2.0,
          'trazado': <Object>[],
          'pasos': [
            _paso('depart', null, 'A'),
            _paso('parada', null, ''),
            _paso('arrive', null, ''),
          ],
        },
        [plazaDeArmas, _destino],
      );
      expect(ruta.pasos.map((p) => p.indicacion), [
        '↑  Sal por A',
        '◉  Llegas a la parada',
        '⚑  Llegas a tu destino',
      ]);
      expect(ruta.semaforos, isEmpty);
    },
  );

  test('Sin ruta posible, el backend responde sin_ruta y se informa con un mensaje claro', () async {
    final enrutador = Enrutador(
      baseUrl: 'http://api.test',
      client: MockClient(
        (_) async => _json({
          'error': {'codigo': 'sin_ruta', 'mensaje': 'no hay ruta'},
        }, 422),
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
  });

  test('BuscadorLugares consulta /v1/lugares en el backend', () async {
    late Uri pedido;
    final buscador = BuscadorLugares(
      baseUrl: 'http://api.test',
      client: MockClient((req) async {
        pedido = req.url;
        return _json([
          {
            'nombre': 'Costanera Center',
            'detalle': 'Costanera Center, Providencia, Santiago, Chile',
            'lat': -33.4176,
            'lon': -70.6064,
          },
        ]);
      }),
    );
    final lugares = await buscador.buscar('Costanera');
    expect(pedido.path, '/v1/lugares');
    expect(pedido.queryParameters['q'], 'Costanera');
    expect(lugares.single.nombre, 'Costanera Center');
    expect(lugares.single.punto, const LatLng(-33.4176, -70.6064));
  });

  testWidgets('El usuario propone una ruta y queda elegida en el selector', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    // Simulación activa: las rutas propuestas conviven con sus destinos.
    final llamadas = <String>[];
    final cuerpos = <String>[];
    final gps = _GpsFalso();
    final simulacion = MockClient((req) async {
      final clave = '${req.method} ${req.url.path}';
      llamadas.add(clave);
      if (clave == 'POST /v1/viajes') cuerpos.add(req.body);
      switch (clave) {
        case 'GET /v1/simulacion/destinos':
          return _json([
            {
              'ruta': 0,
              'nombre': 'Av. General Bustamante',
              'distancia_km': 1.7,
            },
          ]);
        case 'POST /v1/viajes':
          final cuerpo = jsonDecode(req.body) as Map<String, dynamic>;
          if (cuerpo['modo'] == 'gps') {
            return _json({
              'id': 'vg',
              'modo': 'gps',
              'estado': 'en_ruta',
              'destino': cuerpo['nombre_destino'],
              'semaforos_en_ruta': 1,
              'proximo_semaforo': null,
            }, 201);
          }
          return _json({
            'id': 'v1',
            'modo': 'simulado',
            'estado': 'esperando',
            'ruta': 0,
            'destino': 'Av. General Bustamante',
          }, 201);
        case 'POST /v1/viajes/vg/ubicacion':
          return _json({
            'id': 'vg',
            'modo': 'gps',
            'estado': 'en_ruta',
            'destino': 'Cerro Santa Lucía',
            'ubicacion': {'lat': -33.4378, 'lon': -70.6506},
            'proximo_semaforo': {
              'id': 'GS_1',
              'nombre': 'Alameda × San Antonio',
              'distancia_m': 140,
              'color': 'verde',
              'segundos_para_cambio': 9,
              'siguiente_color': 'amarillo',
              'exacto': true,
            },
          });
      }
      return http.Response('', 204);
    });
    await tester.pumpWidget(
      MaterialApp(
        home: MobilityPage(
          api: ViaApi(baseUrl: 'http://api.test', client: simulacion),
          buscador: BuscadorLugares(
            baseUrl: 'http://api.test',
            client: MockClient(
              (_) async => _json([
                {
                  'nombre': 'Cerro Santa Lucía',
                  'detalle': 'Cerro Santa Lucía, Santiago, Chile',
                  'lat': -33.4372,
                  'lon': -70.6275,
                },
              ]),
            ),
          ),
          enrutador: Enrutador(
            baseUrl: 'http://api.test',
            client: MockClient((_) async => _json(_rutas)),
          ),
          ubicacion: gps,
          constructorMapa: _mapaFalso,
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

    // Una ruta propuesta se recorre como viaje GPS con el trazado elegido.
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    await tester.pump();
    expect(find.text('EN VIVO'), findsOneWidget);
    expect(find.text('Recorrido en curso · GPS en vivo'), findsOneWidget);
    expect(find.text('Buscando tu ubicación…'), findsOneWidget);
    final pedidoGps = jsonDecode(cuerpos.single) as Map<String, dynamic>;
    expect(pedidoGps['modo'], 'gps');
    expect(pedidoGps['nombre_destino'], 'Cerro Santa Lucía');
    expect(pedidoGps['trazado'], hasLength(3)); // la alternativa 1 elegida

    // Cada ubicación del GPS va al backend, que responde el próximo semáforo.
    gps.posiciones.add(const Posicion(-33.4378, -70.6506, rumbo: 90));
    await tester.pump();
    await tester.pump();
    expect(llamadas, contains('POST /v1/viajes/vg/ubicacion'));
    expect(find.text('Alameda × San Antonio'), findsOneWidget);
    expect(find.text('9s'), findsOneWidget);
    expect(find.text('Verde → amarillo · a 140 m'), findsOneWidget);

    // Volver a un destino de la simulación termina el recorrido y lo inicia en vivo.
    await tester.tap(find.byKey(const Key('route-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Av. General Bustamante · 1,7 km').last);
    await tester.pumpAndSettle();
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    await tester.pump();
    expect(llamadas, contains('DELETE /v1/viajes/vg'));
    expect(jsonDecode(cuerpos.last)['modo'], 'simulado');
    expect(find.text('EN VIVO'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'Sin permiso de ubicación, la ruta propuesta se recorre en demo',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final llamadas = <String>[];
      final backend = MockClient((req) async {
        llamadas.add('${req.method} ${req.url.path}');
        if (req.url.path == '/v1/lugares') {
          return _json([
            {'nombre': 'Cerro Santa Lucía', 'lat': -33.4372, 'lon': -70.6275},
          ]);
        }
        if (req.url.path == '/v1/rutas') return _json(_rutas);
        return http.Response('', 503);
      });
      await tester.pumpWidget(
        MaterialApp(
          home: MobilityPage(
            api: ViaApi(baseUrl: 'http://api.test', client: backend),
            buscador: BuscadorLugares(
              baseUrl: 'http://api.test',
              client: backend,
            ),
            enrutador: Enrutador(baseUrl: 'http://api.test', client: backend),
            ubicacion: _GpsFalso(permite: false),
            constructorMapa: _mapaFalso,
          ),
        ),
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('propose-route')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('place-search')),
        'Santa Lucía',
      );
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cerro Santa Lucía').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-route')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar recorrido'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Recorrido en curso · Demo'), findsOneWidget);
      expect(
        find.text('Activa la ubicación para seguir la ruta en vivo: modo demo'),
        findsOneWidget,
      );
      expect(llamadas, isNot(contains('POST /v1/viajes')));
      await tester.pumpWidget(const SizedBox());
    },
  );
}
