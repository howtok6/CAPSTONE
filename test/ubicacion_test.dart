import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:mockup/main.dart';
import 'package:mockup/mapa_low_poly.dart';
import 'package:mockup/ubicacion.dart';
import 'package:mockup/via_api.dart';

import 'apoyo.dart';

/// Distancia aproximada en metros entre dos puntos cercanos.
double _metros(double lat1, double lon1, double lat2, double lon2) {
  const r = 111320.0;
  final dx = (lon2 - lon1) * r * math.cos(lat1 * math.pi / 180);
  final dy = (lat2 - lat1) * r;
  return math.sqrt(dx * dx + dy * dy);
}

void main() {
  group('Ubicación aproximada', () {
    test('ajusta la lectura al centro de su celda, dentro del rango', () {
      const real = Posicion(-33.43781, -70.65042, rumbo: 90, precisionM: 8);
      final a = aproximar(real, 500);
      expect(_metros(real.lat, real.lon, a.lat, a.lon), lessThan(500));
      expect(a.precisionM, 500);
      expect(a.rumbo, 90); // el rumbo no revela la posición y el backend lo usa
      expect(a.lat, isNot(real.lat));
    });

    test('dentro de una misma celda la posición no cambia', () {
      final a = aproximar(const Posicion(-33.43781, -70.65042), 1000);
      final b = aproximar(const Posicion(-33.43790, -70.65050), 1000);
      expect(b.lat, a.lat);
      expect(b.lon, a.lon);
    });

    test('la preferencia se guarda y se recupera tal cual', () {
      for (final p in const [
        PreferenciaUbicacion.exacta(),
        PreferenciaUbicacion.aproximada(250),
        PreferenciaUbicacion.aproximada(1000),
        PreferenciaUbicacion.desactivada(),
      ]) {
        expect(PreferenciaUbicacion.decodificar(p.codificar()), p);
      }
      expect(PreferenciaUbicacion.decodificar('otra cosa'), isNull);
      expect(const PreferenciaUbicacion.aproximada(1000).etiqueta, '≈ 1 km');
    });
  });

  Future<void> abrir(WidgetTester tester, GpsFalso gps, MapaFalso mapa) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: MobilityPage(
          api: ViaApi(baseUrl: 'http://api.invalido'),
          ubicacion: gps,
          constructorMapa: mapa.construir,
        ),
      ),
    );
    await tester.pump();
    await tester.pumpAndSettle();
  }

  testWidgets(
    'La primera vez pregunta cómo compartir la ubicación y aplica el rango',
    (tester) async {
      final gps = GpsFalso(guardada: null);
      final mapa = MapaFalso();
      await abrir(tester, gps, mapa);

      expect(find.byKey(const Key('location-sheet')), findsOneWidget);
      await tester.tap(find.byKey(const Key('location-approximate')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('location-range-1000')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('location-continue')));
      await tester.pumpAndSettle();

      expect(gps.guardada, const PreferenciaUbicacion.aproximada(1000));
      expect(gps.pedidos, [const PreferenciaUbicacion.aproximada(1000)]);
      expect(find.text('≈ 1 km'), findsOneWidget);

      // El mapa muestra la zona, no la posición real.
      gps.posiciones.add(const Posicion(-33.43781, -70.65042, precisionM: 6));
      await tester.pump();
      await tester.pump();
      final marcador = mapa.ultimo!.posicion!;
      expect(marcador.radioM, 1000);
      expect(marcador.punto, isNot(const LatLng(-33.43781, -70.65042)));

      // Tocando el indicador se puede pasar a exacta.
      await tester.tap(find.byKey(const Key('location-chip')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('location-exact')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('location-continue')));
      await tester.pumpAndSettle();
      expect(find.text('Exacta'), findsOneWidget);
      expect(mapa.ultimo!.posicion, isNull); // la zona anterior se descarta
      gps.posiciones.add(const Posicion(-33.43781, -70.65042, precisionM: 6));
      await tester.pump();
      await tester.pump();
      expect(
        mapa.ultimo!.posicion!.punto,
        const LatLng(-33.43781, -70.65042),
      );
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets('Con «Ahora no» no se pide permiso ni se vuelve a preguntar', (
    tester,
  ) async {
    final gps = GpsFalso(guardada: null);
    await abrir(tester, gps, MapaFalso());
    await tester.tap(find.byKey(const Key('location-skip')));
    await tester.pumpAndSettle();
    expect(gps.pedidos, isEmpty);
    expect(gps.guardada, const PreferenciaUbicacion.desactivada());
    expect(find.text('Sin ubicación'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());

    final otra = GpsFalso(guardada: gps.guardada);
    await abrir(tester, otra, MapaFalso());
    expect(find.byKey(const Key('location-sheet')), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Si el sistema solo da ubicación aproximada, se indica', (
    tester,
  ) async {
    final gps = GpsFalso(resultado: ResultadoPermiso.soloAproximado);
    await abrir(tester, gps, MapaFalso());
    expect(find.text('≈ 2 km'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  test('El mapa solo redibuja la ruta si cambia; la posición va aparte', () {
    DatosMapa datos({LatLng? yo}) => DatosMapa(
      control: ControlMapa(),
      centro: const LatLng(-33.44, -70.65),
      paradas: const [],
      trazados: const [],
      elegida: 0,
      paleta: PaletaMapa.noche,
      alTocar: (_) {},
      posicion: yo == null ? null : MarcadorPosicion(yo),
    );
    final a = datos(yo: const LatLng(-33.44, -70.65));
    final b = datos(yo: const LatLng(-33.45, -70.66));
    expect(a.firma, b.firma);
    expect(a.firmaDinamica, isNot(b.firmaDinamica));
    expect(
      circuloGeografico(const LatLng(-33.44, -70.65), 500).first.latitude,
      closeTo(-33.44, 1e-9),
    );
  });
}
