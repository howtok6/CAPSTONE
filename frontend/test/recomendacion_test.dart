import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mockup/rutas_osm.dart';

/// `POST /v1/rutas` con estimación: el backend ya ordenó las rutas por lo que
/// demoran a la hora de salida y marcó la recomendada.
final _rutas = [
  {
    'distancia_km': 5.3,
    'duracion_min': 10.0,
    'trazado': [
      [-33.4378, -70.6506],
      [-33.4372, -70.6275],
    ],
    'pasos': <Object>[],
    'semaforos': <Object>[],
    'recomendada': true,
    'motivo': 'La más rápida en punta tarde: 16 min, 9 min menos que la siguiente.',
    'estimacion': {
      'franja': 'punta_tarde',
      'franja_nombre': 'Punta tarde',
      'duracion_min': 16.2,
      'duracion_adaptativo_min': 16.2,
      'ahorro_adaptativo_min': 0,
      'cobertura': 0.02,
      'fuente': 'simulacion',
    },
  },
  {
    'distancia_km': 4.2,
    'duracion_min': 7.7,
    'trazado': [
      [-33.4378, -70.6506],
      [-33.4372, -70.6275],
    ],
    'pasos': <Object>[],
    'semaforos': <Object>[],
    'estimacion': {
      'franja': 'punta_tarde',
      'franja_nombre': 'Punta tarde',
      'duracion_min': 25.0,
      'duracion_adaptativo_min': 15.4,
      'ahorro_adaptativo_min': 9.6,
      'cobertura': 0.87,
      'fuente': 'simulacion',
    },
  },
];

const _paradas = [
  Lugar('Plaza de Armas', LatLng(-33.4378, -70.6506)),
  Lugar('Cerro Santa Lucía', LatLng(-33.4372, -70.6275)),
];

void main() {
  test('Enrutador envía la hora de salida y lee la recomendación', () async {
    late Map<String, dynamic> cuerpo;
    final enrutador = Enrutador(
      baseUrl: 'http://api.test',
      ahora: () => DateTime.utc(2026, 11, 11, 21, 15),
      client: MockClient((req) async {
        cuerpo = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response.bytes(
          utf8.encode(jsonEncode(_rutas)),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    final rutas = await enrutador.calcular(_paradas);

    expect(cuerpo['hora'], '2026-11-11T21:15:00.000Z');
    final recomendada = rutas.first;
    expect(recomendada.recomendada, isTrue);
    expect(recomendada.motivo, contains('punta tarde'));
    // Se muestran los minutos estimados para esa hora, no los de flujo libre
    expect(recomendada.minutos, 16.2);
    expect(recomendada.duracionMin, 10.0);
    expect(recomendada.estimacion!.resumen, 'Punta tarde · 2 % de la ruta con datos del eje');

    final eje = rutas.last;
    expect(eje.recomendada, isFalse);
    expect(eje.minutos, 25.0);
    expect(
      eje.estimacion!.resumen,
      'Punta tarde · con semáforos adaptativos: 15 min (10 min menos) · '
      '87 % de la ruta con datos del eje',
    );
  });

  test('La hora de salida se puede fijar al calcular', () async {
    late Map<String, dynamic> cuerpo;
    final enrutador = Enrutador(
      baseUrl: 'http://api.test',
      client: MockClient((req) async {
        cuerpo = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('[]', 200);
      }),
    );
    await enrutador.calcular(_paradas, salida: DateTime.utc(2026, 11, 12, 10, 30));
    expect(cuerpo['hora'], '2026-11-12T10:30:00.000Z');
  });

  test('El resumen dice si el control adaptativo demora menos, igual o más', () {
    EstimacionRuta con(double adaptativo) => EstimacionRuta(
      franja: 'valle',
      franjaNombre: 'Valle',
      duracionMin: 13,
      duracionAdaptativoMin: adaptativo,
      ahorroAdaptativoMin: 13 - adaptativo,
      cobertura: 0.6,
    );
    expect(con(10).resumen, contains('10 min (3 min menos)'));
    expect(con(13.2).resumen, contains('demoraría lo mismo'));
    expect(con(14).resumen, contains('14 min (1 min más)'));
  });

  test('Sin estimación se muestran los minutos del enrutador', () {
    final ruta = RutaPropuesta.fromJson({
      'distancia_km': 4.2,
      'duracion_min': 7.7,
      'trazado': <Object>[],
    }, _paradas);
    expect(ruta.estimacion, isNull);
    expect(ruta.recomendada, isFalse);
    expect(ruta.minutos, 7.7);
  });
}
