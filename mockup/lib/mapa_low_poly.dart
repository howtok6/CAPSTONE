// Mapa 3D «low poly» de la pantalla Proponer ruta.
//
// Dibuja la ciudad con teselas vectoriales de OpenFreeMap (datos de
// OpenStreetMap, gratis y sin clave) y un estilo propio: edificios extruidos
// según su altura como bloques de color plano, calles simples, áreas verdes y
// agua, sin íconos ni comercios. La cámara va inclinada para ver el volumen.
//
// La pantalla no habla con MapLibre directamente: le pasa los datos en
// [DatosMapa] y le pide movimientos a través de [ControlMapa]. Así las pruebas
// pueden usar un mapa falso, porque MapLibre es una vista nativa.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';
import 'package:maplibre_gl/maplibre_gl.dart' as ml;

/// Colores de un estilo low poly.
class PaletaMapa {
  const PaletaMapa({
    required this.id,
    required this.nombre,
    required this.fondo,
    required this.agua,
    required this.verde,
    required this.calle,
    required this.calleMayor,
    required this.edificioBajo,
    required this.edificioAlto,
    required this.texto,
    required this.luz,
    required this.rutaAlternativa,
  });
  final String id;
  final String nombre;
  final String fondo;
  final String agua;
  final String verde;
  final String calle;
  final String calleMayor;
  final String edificioBajo; // edificios de 1-2 pisos
  final String edificioAlto; // torres de 40 m o más
  final String texto;
  final double luz; // intensidad de la luz que sombrea las caras de los bloques
  final String rutaAlternativa;

  /// Oscura, como el resto de la app.
  static const noche = PaletaMapa(
    id: 'noche',
    nombre: 'Noche',
    fondo: '#12161E',
    agua: '#1B3550',
    verde: '#1C3329',
    calle: '#262C36',
    calleMayor: '#363E4B',
    edificioBajo: '#2A313D',
    edificioAlto: '#566277',
    texto: '#8A909B',
    luz: 0.55,
    rutaAlternativa: '#8A909B',
  );

  /// Clara, como una maqueta de arquitectura en cartón blanco.
  static const maqueta = PaletaMapa(
    id: 'maqueta',
    nombre: 'Maqueta',
    fondo: '#E6E1D7',
    agua: '#A7C4D6',
    verde: '#C6D5B3',
    calle: '#F7F4EE',
    calleMayor: '#FFFFFF',
    edificioBajo: '#F1EDE5',
    edificioAlto: '#FFFFFF',
    texto: '#6B6458',
    luz: 0.35,
    rutaAlternativa: '#8C8577',
  );

  /// Colores suaves, estilo ilustración low poly.
  static const pastel = PaletaMapa(
    id: 'pastel',
    nombre: 'Pastel',
    fondo: '#F3EAE3',
    agua: '#8ECAE6',
    verde: '#B7E4C7',
    calle: '#FFFFFF',
    calleMayor: '#FFE8D6',
    edificioBajo: '#D7C3E3',
    edificioAlto: '#A9CFF5',
    texto: '#5C5470',
    luz: 0.4,
    rutaAlternativa: '#9C8FB0',
  );

  static const todas = [noche, maqueta, pastel];
}

const _openFreeMap = 'https://tiles.openfreemap.org/planet';
const _glifos = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
const fuenteMapa = ['Noto Sans Bold'];

/// Estilo MapLibre low poly sobre el esquema OpenMapTiles de OpenFreeMap.
String estiloLowPoly(PaletaMapa p) {
  const fuente = {'source': 'openmaptiles'};
  final altura = [
    'coalesce',
    ['get', 'render_height'],
    4,
  ];
  List<Object> clases(List<String> c) => [
    'in',
    ['get', 'class'],
    ['literal', c],
  ];
  return jsonEncode({
    'version': 8,
    'name': 'Vía low poly · ${p.nombre}',
    'sources': {
      'openmaptiles': {'type': 'vector', 'url': _openFreeMap},
    },
    'glyphs': _glifos,
    // Luz fija desde el noroeste: cada cara del bloque toma un tono distinto,
    // que es lo que da el aspecto facetado.
    'light': {
      'anchor': 'map',
      'color': '#FFFFFF',
      'intensity': p.luz,
      'position': [1.3, 315, 40],
    },
    'layers': [
      {
        'id': 'fondo',
        'type': 'background',
        'paint': {'background-color': p.fondo},
      },
      {
        ...fuente,
        'id': 'parques',
        'type': 'fill',
        'source-layer': 'park',
        'paint': {'fill-color': p.verde},
      },
      {
        ...fuente,
        'id': 'vegetacion',
        'type': 'fill',
        'source-layer': 'landcover',
        'filter': clases(['grass', 'wood', 'farmland']),
        'paint': {'fill-color': p.verde, 'fill-opacity': 0.7},
      },
      {
        ...fuente,
        'id': 'agua',
        'type': 'fill',
        'source-layer': 'water',
        'paint': {'fill-color': p.agua},
      },
      {
        ...fuente,
        'id': 'rios',
        'type': 'line',
        'source-layer': 'waterway',
        'paint': {'line-color': p.agua, 'line-width': 2},
      },
      {
        ...fuente,
        'id': 'calles',
        'type': 'line',
        'source-layer': 'transportation',
        'minzoom': 12,
        'filter': clases(['minor', 'service']),
        'layout': {'line-cap': 'round', 'line-join': 'round'},
        'paint': {
          'line-color': p.calle,
          'line-width': [
            'interpolate',
            ['exponential', 1.6],
            ['zoom'],
            12,
            0.5,
            18,
            9,
          ],
        },
      },
      {
        ...fuente,
        'id': 'avenidas',
        'type': 'line',
        'source-layer': 'transportation',
        'filter': clases([
          'motorway',
          'trunk',
          'primary',
          'secondary',
          'tertiary',
        ]),
        'layout': {'line-cap': 'round', 'line-join': 'round'},
        'paint': {
          'line-color': p.calleMayor,
          'line-width': [
            'interpolate',
            ['exponential', 1.6],
            ['zoom'],
            10,
            1,
            18,
            18,
          ],
        },
      },
      // Lejos, los edificios son manchas planas; al acercarse se levantan.
      {
        ...fuente,
        'id': 'edificios-planos',
        'type': 'fill',
        'source-layer': 'building',
        'minzoom': 13,
        'maxzoom': 14.5,
        'paint': {'fill-color': p.edificioBajo},
      },
      {
        ...fuente,
        'id': 'edificios',
        'type': 'fill-extrusion',
        'source-layer': 'building',
        'minzoom': 14,
        'filter': [
          '!',
          ['has', 'hide_3d'],
        ],
        'paint': {
          'fill-extrusion-color': [
            'interpolate',
            ['linear'],
            altura,
            0,
            p.edificioBajo,
            40,
            p.edificioAlto,
          ],
          'fill-extrusion-height': [
            'interpolate',
            ['linear'],
            ['zoom'],
            14,
            0,
            15,
            altura,
          ],
          'fill-extrusion-base': [
            'coalesce',
            ['get', 'render_min_height'],
            0,
          ],
          'fill-extrusion-opacity': 1,
          // Sin degradado: caras de color plano, como un modelo low poly.
          'fill-extrusion-vertical-gradient': false,
        },
      },
      // Solo los nombres de las avenidas, para orientarse.
      {
        ...fuente,
        'id': 'nombres-avenidas',
        'type': 'symbol',
        'source-layer': 'transportation_name',
        'minzoom': 14,
        'filter': clases(['trunk', 'primary', 'secondary']),
        'layout': {
          'symbol-placement': 'line',
          'text-field': ['get', 'name'],
          'text-font': fuenteMapa,
          'text-size': 11,
        },
        'paint': {
          'text-color': p.texto,
          'text-halo-color': p.fondo,
          'text-halo-width': 1.4,
        },
      },
    ],
  });
}

/// Una parada dibujada en el mapa.
class ParadaMapa {
  const ParadaMapa(this.punto, this.etiqueta, {required this.extremo});
  final LatLng punto;
  final String etiqueta; // A, B o el número de la parada
  final bool extremo; // origen o destino
}

/// Lo que la pantalla le entrega al mapa.
class DatosMapa {
  const DatosMapa({
    required this.control,
    required this.centro,
    required this.paradas,
    required this.trazados,
    required this.elegida,
    required this.paleta,
    required this.alTocar,
  });
  final ControlMapa control;
  final LatLng centro;
  final List<ParadaMapa> paradas;
  final List<List<LatLng>> trazados; // alternativas de ruta
  final int elegida;
  final PaletaMapa paleta;
  final void Function(LatLng) alTocar;

  /// Resumen de lo que se dibuja encima del mapa: si no cambia, no se redibuja.
  String get firma => [
    elegida,
    for (final t in trazados)
      t.isEmpty ? '-' : '${t.length}:${t.first}:${t.last}',
    for (final p in paradas) '${p.etiqueta}@${p.punto}',
  ].join('|');
}

/// Construye el mapa; las pruebas pasan uno falso.
typedef ConstructorMapa = Widget Function(DatosMapa datos);

/// Movimientos que la pantalla le pide al mapa, sea cual sea.
class ControlMapa {
  void Function(LatLng punto, double zoom)? _mover;
  void Function(List<LatLng> puntos)? _encuadrar;

  /// Centra el mapa en [punto] con el [zoom] dado.
  void mover(LatLng punto, double zoom) => _mover?.call(punto, zoom);

  /// Encuadra todos los [puntos] (por ejemplo, todas las alternativas).
  void encuadrar(List<LatLng> puntos) => _encuadrar?.call(puntos);
}

/// El mapa real, con MapLibre.
class MapaLowPoly extends StatefulWidget {
  const MapaLowPoly(this.datos, {super.key});
  final DatosMapa datos;

  /// Inclinación de la cámara, en grados, para ver el volumen de los edificios.
  static const inclinacion = 55.0;

  @override
  State<MapaLowPoly> createState() => _MapaLowPolyState();
}

class _MapaLowPolyState extends State<MapaLowPoly> {
  ml.MapLibreMapController? _mapa;
  bool _estiloListo = false;
  ml.CameraPosition? _camara; // para no perder la vista al cambiar de paleta
  Future<void> _dibujando = Future.value();

  static ml.LatLng _ml(LatLng p) => ml.LatLng(p.latitude, p.longitude);

  @override
  void initState() {
    super.initState();
    _conectar();
  }

  void _conectar() {
    final control = widget.datos.control;
    control._mover = _mover;
    control._encuadrar = _encuadrar;
  }

  void _mover(LatLng punto, double zoom) {
    _mapa?.animateCamera(
      ml.CameraUpdate.newCameraPosition(
        ml.CameraPosition(
          target: _ml(punto),
          zoom: zoom,
          tilt: MapaLowPoly.inclinacion,
          bearing: _mapa?.cameraPosition?.bearing ?? 0,
        ),
      ),
    );
  }

  Future<void> _encuadrar(List<LatLng> puntos) async {
    final mapa = _mapa;
    if (mapa == null || puntos.isEmpty) return;
    var sur = puntos.first.latitude, norte = sur;
    var oeste = puntos.first.longitude, este = oeste;
    for (final p in puntos) {
      if (p.latitude < sur) sur = p.latitude;
      if (p.latitude > norte) norte = p.latitude;
      if (p.longitude < oeste) oeste = p.longitude;
      if (p.longitude > este) este = p.longitude;
    }
    await mapa.animateCamera(
      ml.CameraUpdate.newLatLngBounds(
        ml.LatLngBounds(
          southwest: ml.LatLng(sur, oeste),
          northeast: ml.LatLng(norte, este),
        ),
        left: 40,
        top: 40,
        right: 40,
        bottom: 40,
      ),
    );
    // Encuadrar endereza la cámara; se vuelve a inclinar para ver los bloques.
    await mapa.animateCamera(ml.CameraUpdate.tiltTo(MapaLowPoly.inclinacion));
  }

  @override
  void didUpdateWidget(MapaLowPoly anterior) {
    super.didUpdateWidget(anterior);
    if (anterior.datos.control != widget.datos.control) _conectar();
    if (anterior.datos.paleta.id != widget.datos.paleta.id) {
      // Cambiar de paleta recrea el mapa (ver la clave en build); se guarda la
      // cámara para que la vista no salte.
      _camara = _mapa?.cameraPosition ?? _camara;
      _mapa = null;
      _estiloListo = false;
    } else if (anterior.datos.firma != widget.datos.firma) {
      _redibujar();
    }
  }

  /// Vuelve a dibujar rutas y paradas. Se encadenan para que dos cambios
  /// seguidos no se mezclen.
  void _redibujar() {
    _dibujando = _dibujando.then((_) => _dibujar()).catchError((_) {});
  }

  Future<void> _dibujar() async {
    final mapa = _mapa;
    if (mapa == null || !_estiloListo) return;
    final d = widget.datos;
    await mapa.clearLines();
    await mapa.clearCircles();
    await mapa.clearSymbols();
    // Las alternativas primero y la elegida al final, para que quede encima.
    for (var i = 0; i < d.trazados.length; i++) {
      if (i == d.elegida || d.trazados[i].length < 2) continue;
      await mapa.addLine(
        ml.LineOptions(
          geometry: [for (final p in d.trazados[i]) _ml(p)],
          lineColor: d.paleta.rutaAlternativa,
          lineWidth: 4,
          lineOpacity: 0.85,
          lineJoin: 'round',
        ),
      );
    }
    if (d.elegida < d.trazados.length && d.trazados[d.elegida].length >= 2) {
      final puntos = [for (final p in d.trazados[d.elegida]) _ml(p)];
      await mapa.addLine(
        ml.LineOptions(
          geometry: puntos,
          lineColor: '#161A21',
          lineWidth: 9,
          lineJoin: 'round',
        ),
      );
      await mapa.addLine(
        ml.LineOptions(
          geometry: puntos,
          lineColor: '#F5CB45',
          lineWidth: 6,
          lineJoin: 'round',
        ),
      );
    }
    for (final p in d.paradas) {
      await mapa.addCircle(
        ml.CircleOptions(
          geometry: _ml(p.punto),
          circleRadius: 10,
          circleColor: p.extremo ? '#F5CB45' : '#FFFFFF',
          circleStrokeColor: '#161A21',
          circleStrokeWidth: 2,
        ),
      );
      await mapa.addSymbol(
        ml.SymbolOptions(
          geometry: _ml(p.punto),
          textField: p.etiqueta,
          textSize: 11,
          textColor: '#161A21',
          fontNames: fuenteMapa,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.datos;
    return ml.MapLibreMap(
      key: ValueKey(d.paleta.id),
      styleString: estiloLowPoly(d.paleta),
      initialCameraPosition:
          _camara ??
          ml.CameraPosition(
            target: _ml(d.centro),
            zoom: 15,
            tilt: MapaLowPoly.inclinacion,
            bearing: -20,
          ),
      trackCameraPosition: true,
      compassEnabled: true,
      onMapCreated: (c) => _mapa = c,
      onStyleLoadedCallback: () {
        _estiloListo = true;
        _redibujar();
      },
      onMapClick: (_, punto) =>
          d.alTocar(LatLng(punto.latitude, punto.longitude)),
    );
  }
}
