import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mockup/mapa_low_poly.dart';
import 'package:mockup/proponer_ruta.dart';
import 'package:mockup/rutas_osm.dart';

List<Map<String, dynamic>> _capas(PaletaMapa p) =>
    ((jsonDecode(estiloLowPoly(p)) as Map)['layers'] as List)
        .cast<Map<String, dynamic>>();

void main() {
  test(
    'El estilo low poly usa OpenFreeMap y levanta edificios de color plano',
    () {
      for (final p in PaletaMapa.todas) {
        final estilo = jsonDecode(estiloLowPoly(p)) as Map<String, dynamic>;
        expect(estilo['version'], 8);
        expect(
          estilo['sources']['openmaptiles']['url'],
          'https://tiles.openfreemap.org/planet',
        );
        final capas = _capas(p);
        final edificios = capas.singleWhere((c) => c['id'] == 'edificios');
        expect(edificios['type'], 'fill-extrusion');
        expect(edificios['source-layer'], 'building');
        expect(edificios['paint']['fill-extrusion-vertical-gradient'], false);
        expect(capas.first['paint']['background-color'], p.fondo);
        // Sin íconos, comercios ni etiquetas de lugares: solo nombres de avenidas.
        final capasFuente = capas.map((c) => c['source-layer']).toSet();
        expect(capasFuente, isNot(contains('poi')));
        expect(capasFuente, isNot(contains('place')));
        for (final c in capas.where((c) => c['type'] != 'background')) {
          expect(c['source'], 'openmaptiles', reason: c['id'] as String);
        }
      }
      final fondos = PaletaMapa.todas.map((p) => p.fondo).toSet();
      expect(fondos, hasLength(3), reason: 'cada paleta debe verse distinta');
    },
  );

  test('El mapa solo se redibuja si cambian rutas, paradas o la elegida', () {
    DatosMapa datos({int elegida = 0, LatLng? b}) => DatosMapa(
      control: ControlMapa(),
      centro: plazaDeArmas.punto,
      paradas: [
        ParadaMapa(plazaDeArmas.punto, 'A', extremo: true),
        ParadaMapa(b ?? const LatLng(-33.43, -70.62), 'B', extremo: true),
      ],
      trazados: [
        [plazaDeArmas.punto, const LatLng(-33.43, -70.62)],
        [
          plazaDeArmas.punto,
          const LatLng(-33.44, -70.63),
          const LatLng(-33.43, -70.62),
        ],
      ],
      elegida: elegida,
      paleta: PaletaMapa.noche,
      alTocar: (_) {},
    );
    expect(datos().firma, datos().firma);
    expect(datos(elegida: 1).firma, isNot(datos().firma));
    expect(datos(b: const LatLng(-33.42, -70.61)).firma, isNot(datos().firma));
  });

  testWidgets('Proponer ruta: elegir paleta y tocar el mapa fija una parada', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(() => ProponerRutaPageEstado.reiniciarPaleta());

    final buscador = BuscadorLugares(
      baseUrl: 'http://api.test',
      client: MockClient(
        (req) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'nombre': 'Cerro Santa Lucía',
              'lat': -33.4372,
              'lon': -70.6275,
            }),
          ),
          200,
        ),
      ),
    );
    late DatosMapa ultimo;
    await tester.pumpWidget(
      MaterialApp(
        home: ProponerRutaPage(
          buscador: buscador,
          enrutador: Enrutador(
            baseUrl: 'http://api.test',
            client: MockClient((_) async => http.Response('[]', 200)),
          ),
          constructorMapa: (d) {
            ultimo = d;
            return GestureDetector(
              key: const Key('mapa-falso'),
              onTap: () => d.alTocar(const LatLng(-33.4372, -70.6275)),
              child: ColoredBox(
                color: Colors.black,
                child: Center(child: Text('Mapa ${d.paleta.nombre}')),
              ),
            );
          },
        ),
      ),
    );
    expect(find.text('Mapa Noche'), findsOneWidget);
    expect(ultimo.paradas.single.etiqueta, 'A');

    await tester.tap(find.byKey(const Key('palette-maqueta')));
    await tester.pump();
    expect(find.text('Mapa Maqueta'), findsOneWidget);

    await tester.tap(find.byKey(const Key('mapa-falso')));
    await tester.pumpAndSettle();
    expect(find.text('Cerro Santa Lucía'), findsOneWidget);
    expect(ultimo.paradas.map((p) => p.etiqueta), ['A', 'B']);
    expect(ultimo.paradas.last.extremo, isTrue);
  });
}
