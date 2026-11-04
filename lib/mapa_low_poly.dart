// Mapa 3D «low poly» de la pantalla Proponer ruta.
//
// Dibuja la ciudad con teselas vectoriales de OpenFreeMap (datos de
// OpenStreetMap, gratis y sin clave) y un estilo propio: edificios extruidos
// según su altura como bloques de color plano, calles simples, áreas verdes y
// agua, sin íconos ni comercios. La cámara va inclinada para ver el volumen.
//
// Lo usan la pantalla principal (mapa de navegación que sigue al usuario por
// su ruta) y «Proponer ruta». En ambas se puede mover, acercar, girar e
// inclinar con los dedos.
//
// Las pantallas no hablan con MapLibre directamente: le pasan los datos en
// [DatosMapa] y le piden movimientos a través de [ControlMapa]. Así las pruebas
// pueden usar un mapa falso, porque MapLibre es una vista nativa.
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
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

/// Un semáforo de la ruta dibujado en el mapa.
class SemaforoMapa {
  const SemaforoMapa(this.id, this.punto);
  final String id;
  final LatLng punto;
}

/// Lo que se mueve en el mapa: el usuario (GPS) o el vehículo de la simulación.
class MarcadorPosicion {
  const MarcadorPosicion(
    this.punto, {
    this.radioM = 0,
    this.vehiculo = false,
  });
  final LatLng punto;

  /// Radio de la zona en que puede estar, en metros (ubicación aproximada o
  /// precisión del GPS). Bajo 15 m no se dibuja.
  final double radioM;

  /// true para el vehículo de la simulación (amarillo); false para el usuario.
  final bool vehiculo;

  String get firma =>
      '${punto.latitude},${punto.longitude},${radioM.round()},$vehiculo';
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
    this.semaforos = const [],
    this.posicion,
    this.proximo,
    this.colorProximo = '#C9CED6',
    this.alInteractuar,
    this.zoom = 15,
    this.inclinacion = MapaLowPoly.inclinacion,
    this.margenInferior = 0,
  });
  final ControlMapa control;
  final LatLng centro;
  final List<ParadaMapa> paradas;
  final List<List<LatLng>> trazados; // alternativas de ruta
  final int elegida;
  final PaletaMapa paleta;
  final void Function(LatLng) alTocar;

  /// Semáforos por los que pasa la ruta elegida.
  final List<SemaforoMapa> semaforos;

  /// Usuario o vehículo, si se sabe dónde está.
  final MarcadorPosicion? posicion;

  /// Próximo semáforo del recorrido, que se dibuja con su color actual
  /// ([colorProximo], en hexadecimal).
  final SemaforoMapa? proximo;
  final String colorProximo;

  /// Se llama cuando el usuario toca o arrastra el mapa (p. ej., para dejar de
  /// seguirlo con la cámara).
  final VoidCallback? alInteractuar;

  /// Cámara inicial.
  final double zoom;
  final double inclinacion;

  /// Alto, en píxeles, de lo que tapa la parte de abajo del mapa. Si es mayor
  /// que 0, la brújula y el botón de atribución de OpenStreetMap van abajo a la
  /// izquierda, sobre ese espacio, para que no los tapen el encabezado ni los
  /// controles.
  final double margenInferior;

  /// Resumen de la ruta, paradas y semáforos: si no cambia, no se redibuja.
  String get firma => [
    elegida,
    for (final t in trazados)
      t.isEmpty ? '-' : '${t.length}:${t.first}:${t.last}',
    for (final p in paradas) '${p.etiqueta}@${p.punto}',
    for (final s in semaforos) s.id,
  ].join('|');

  /// Resumen de lo que cambia seguido (posición y próximo semáforo): se
  /// actualiza sin redibujar la ruta.
  String get firmaDinamica =>
      '${posicion?.firma}|${proximo?.id}@${proximo?.punto}|$colorProximo';
}

/// Construye el mapa; las pruebas pasan uno falso.
typedef ConstructorMapa = Widget Function(DatosMapa datos);

/// Movimientos que la pantalla le pide al mapa, sea cual sea.
class ControlMapa {
  void Function(LatLng punto, double zoom, double? inclinacion)? _mover;
  void Function(List<LatLng> puntos, double inclinacion)? _encuadrar;
  void Function(LatLng punto, double? rumbo, bool conduccion)? _seguir;

  /// Centra el mapa en [punto] con el [zoom] dado.
  void mover(LatLng punto, double zoom, {double? inclinacion}) =>
      _mover?.call(punto, zoom, inclinacion);

  /// Encuadra todos los [puntos] (por ejemplo, todas las alternativas) y deja
  /// la cámara con la [inclinacion] dada.
  void encuadrar(
    List<LatLng> puntos, {
    double inclinacion = MapaLowPoly.inclinacion,
  }) => _encuadrar?.call(puntos, inclinacion);

  /// Sigue al usuario: en modo [conduccion] la cámara va cerca, inclinada y
  /// mirando hacia el [rumbo]; si no, desde arriba y con el norte arriba.
  void seguir(LatLng punto, {double? rumbo, required bool conduccion}) =>
      _seguir?.call(punto, rumbo, conduccion);
}

/// El mapa real, con MapLibre.
class MapaLowPoly extends StatefulWidget {
  const MapaLowPoly(this.datos, {super.key});
  final DatosMapa datos;

  /// Inclinación de la cámara, en grados, para ver el volumen de los edificios.
  static const inclinacion = 55.0;

  /// Cámara del modo conducción: más cerca y más inclinada.
  static const inclinacionConduccion = 60.0;
  static const zoomConduccion = 17.0;

  @override
  State<MapaLowPoly> createState() => _MapaLowPolyState();
}

/// Polígono que aproxima un círculo de [radioM] metros alrededor de [centro].
List<LatLng> circuloGeografico(LatLng centro, double radioM, {int lados = 48}) {
  const metrosPorGrado = 111320.0;
  final dLat = radioM / metrosPorGrado;
  final dLon =
      radioM /
      (metrosPorGrado *
          math.cos(centro.latitude * math.pi / 180).abs().clamp(0.01, 1));
  return [
    for (var i = 0; i <= lados; i++)
      LatLng(
        centro.latitude + dLat * math.sin(2 * math.pi * i / lados),
        centro.longitude + dLon * math.cos(2 * math.pi * i / lados),
      ),
  ];
}

class _MapaLowPolyState extends State<MapaLowPoly> {
  ml.MapLibreMapController? _mapa;
  bool _estiloListo = false;
  ml.CameraPosition? _camara; // para no perder la vista al cambiar de paleta
  Future<void> _dibujando = Future.value();

  // Lo que dibuja este mapa, para borrar solo eso al redibujar.
  final _lineas = <ml.Line>[];
  final _circulos = <ml.Circle>[];
  final _simbolos = <ml.Symbol>[];
  ml.Fill? _zona; // rango de la ubicación
  ml.Circle? _punto; // usuario o vehículo
  ml.Circle? _proximo; // próximo semáforo

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
    control._seguir = _seguir;
  }

  void _mover(LatLng punto, double zoom, double? inclinacion) {
    _mapa?.animateCamera(
      ml.CameraUpdate.newCameraPosition(
        ml.CameraPosition(
          target: _ml(punto),
          zoom: zoom,
          tilt: inclinacion ?? _mapa?.cameraPosition?.tilt ?? MapaLowPoly.inclinacion,
          bearing: _mapa?.cameraPosition?.bearing ?? 0,
        ),
      ),
    );
  }

  void _seguir(LatLng punto, double? rumbo, bool conduccion) {
    final actual = _mapa?.cameraPosition;
    _mapa?.animateCamera(
      ml.CameraUpdate.newCameraPosition(
        ml.CameraPosition(
          target: _ml(punto),
          zoom: conduccion
              ? MapaLowPoly.zoomConduccion
              : math.max(actual?.zoom ?? 15, 14),
          tilt: conduccion ? MapaLowPoly.inclinacionConduccion : 0,
          bearing: conduccion ? (rumbo ?? actual?.bearing ?? 0) : 0,
        ),
      ),
      duration: const Duration(milliseconds: 700),
    );
  }

  Future<void> _encuadrar(List<LatLng> puntos, double inclinacion) async {
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
    // Encuadrar endereza la cámara; se vuelve a inclinar si corresponde.
    if (inclinacion > 0) {
      await mapa.animateCamera(ml.CameraUpdate.tiltTo(inclinacion));
    }
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
      _olvidar();
    } else if (anterior.datos.firma != widget.datos.firma) {
      _encolar(_dibujar);
    } else if (anterior.datos.firmaDinamica != widget.datos.firmaDinamica) {
      _encolar(_actualizarDinamico);
    }
  }

  /// Encadena los dibujos para que dos cambios seguidos no se mezclen.
  void _encolar(Future<void> Function() tarea) {
    _dibujando = _dibujando.then((_) => tarea()).catchError((_) {});
  }

  /// Un mapa recreado empieza sin nada dibujado.
  void _olvidar() {
    _lineas.clear();
    _circulos.clear();
    _simbolos.clear();
    _zona = null;
    _punto = null;
    _proximo = null;
  }

  /// Vuelve a dibujar todo: rutas, paradas, semáforos y, encima, la posición.
  Future<void> _dibujar() async {
    final mapa = _mapa;
    if (mapa == null || !_estiloListo) return;
    final d = widget.datos;
    await mapa.removeLines(List.of(_lineas));
    await mapa.removeCircles([..._circulos, ?_punto, ?_proximo]);
    await mapa.removeSymbols(List.of(_simbolos));
    if (_zona != null) await mapa.removeFill(_zona!);
    _olvidar();
    // Las alternativas primero y la elegida al final, para que quede encima.
    for (var i = 0; i < d.trazados.length; i++) {
      if (i == d.elegida || d.trazados[i].length < 2) continue;
      _lineas.add(
        await mapa.addLine(
          ml.LineOptions(
            geometry: [for (final p in d.trazados[i]) _ml(p)],
            lineColor: d.paleta.rutaAlternativa,
            lineWidth: 4,
            lineOpacity: 0.85,
            lineJoin: 'round',
          ),
        ),
      );
    }
    if (d.elegida < d.trazados.length && d.trazados[d.elegida].length >= 2) {
      final puntos = [for (final p in d.trazados[d.elegida]) _ml(p)];
      for (final (color, ancho) in [('#161A21', 9.0), ('#F5CB45', 6.0)]) {
        _lineas.add(
          await mapa.addLine(
            ml.LineOptions(
              geometry: puntos,
              lineColor: color,
              lineWidth: ancho,
              lineJoin: 'round',
            ),
          ),
        );
      }
    }
    for (final s in d.semaforos) {
      _circulos.add(
        await mapa.addCircle(
          ml.CircleOptions(
            geometry: _ml(s.punto),
            circleRadius: 5,
            circleColor: '#C9CED6',
            circleStrokeColor: '#161A21',
            circleStrokeWidth: 1.5,
          ),
        ),
      );
    }
    for (final p in d.paradas) {
      _circulos.add(
        await mapa.addCircle(
          ml.CircleOptions(
            geometry: _ml(p.punto),
            circleRadius: 10,
            circleColor: p.extremo ? '#F5CB45' : '#FFFFFF',
            circleStrokeColor: '#161A21',
            circleStrokeWidth: 2,
          ),
        ),
      );
      _simbolos.add(
        await mapa.addSymbol(
          ml.SymbolOptions(
            geometry: _ml(p.punto),
            textField: p.etiqueta,
            textSize: 11,
            textColor: '#161A21',
            fontNames: fuenteMapa,
          ),
        ),
      );
    }
    await _actualizarDinamico();
  }

  /// Mueve el marcador de posición, su zona y el próximo semáforo sin tocar la
  /// ruta. Crea o borra cada uno según haga falta.
  Future<void> _actualizarDinamico() async {
    final mapa = _mapa;
    if (mapa == null || !_estiloListo) return;
    final d = widget.datos;
    final pos = d.posicion;

    // Zona (rango o precisión), debajo de todo.
    final radio = pos == null ? 0.0 : pos.radioM;
    if (pos == null || radio < 15) {
      if (_zona != null) await mapa.removeFill(_zona!);
      _zona = null;
    } else {
      final zona = ml.FillOptions(
        geometry: [
          [for (final p in circuloGeografico(pos.punto, radio)) _ml(p)],
        ],
        fillColor: pos.vehiculo ? '#F5CB45' : '#4DA3FF',
        fillOpacity: 0.16,
        fillOutlineColor: pos.vehiculo ? '#F5CB45' : '#4DA3FF',
      );
      if (_zona == null) {
        _zona = await mapa.addFill(zona);
      } else {
        await mapa.updateFill(_zona!, zona);
      }
    }

    // Próximo semáforo, con el color que tiene ahora.
    final prox = d.proximo;
    if (prox == null) {
      if (_proximo != null) await mapa.removeCircle(_proximo!);
      _proximo = null;
    } else {
      final opciones = ml.CircleOptions(
        geometry: _ml(prox.punto),
        circleRadius: 9,
        circleColor: d.colorProximo,
        circleStrokeColor: '#161A21',
        circleStrokeWidth: 2.5,
      );
      if (_proximo == null) {
        _proximo = await mapa.addCircle(opciones);
      } else {
        await mapa.updateCircle(_proximo!, opciones);
      }
    }

    // Usuario o vehículo, encima de todo.
    if (pos == null) {
      if (_punto != null) await mapa.removeCircle(_punto!);
      _punto = null;
    } else {
      final opciones = ml.CircleOptions(
        geometry: _ml(pos.punto),
        circleRadius: pos.vehiculo ? 9 : 7,
        circleColor: pos.vehiculo ? '#F5CB45' : '#4DA3FF',
        circleStrokeColor: pos.vehiculo ? '#161A21' : '#FFFFFF',
        circleStrokeWidth: 2.5,
      );
      if (_punto == null) {
        _punto = await mapa.addCircle(opciones);
      } else {
        await mapa.updateCircle(_punto!, opciones);
      }
    }
  }

  /// MapLibre no tiene versión para Windows, macOS ni Linux de escritorio.
  static bool get _plataformaSinMapa =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.windows ||
          defaultTargetPlatform == TargetPlatform.macOS ||
          defaultTargetPlatform == TargetPlatform.linux);

  @override
  Widget build(BuildContext context) {
    final d = widget.datos;
    if (_plataformaSinMapa) {
      return ColoredBox(
        color: Color(int.parse('FF${d.paleta.fondo.substring(1)}', radix: 16)),
        child: const Center(
          child: Text(
            'El mapa 3D funciona en Android, iOS y web',
            style: TextStyle(color: Color(0xFF8A909B), fontSize: 12),
          ),
        ),
      );
    }
    // Listener no compite por los gestos: solo avisa que el usuario tocó el
    // mapa, y MapLibre igual recibe el arrastre, el pellizco y el giro.
    return Listener(
      onPointerDown: (_) => d.alInteractuar?.call(),
      child: ml.MapLibreMap(
        key: ValueKey(d.paleta.id),
        styleString: estiloLowPoly(d.paleta),
        initialCameraPosition:
            _camara ??
            ml.CameraPosition(
              target: _ml(d.centro),
              zoom: d.zoom,
              tilt: d.inclinacion,
              bearing: d.inclinacion > 0 ? -20 : 0,
            ),
        trackCameraPosition: true,
        compassEnabled: true,
        compassViewPosition: d.margenInferior > 0
            ? ml.CompassViewPosition.bottomLeft
            : ml.CompassViewPosition.topRight,
        compassViewMargins: d.margenInferior > 0
            ? math.Point(14, d.margenInferior + 40)
            : const math.Point(8, 8),
        attributionButtonPosition: d.margenInferior > 0
            ? ml.AttributionButtonPosition.bottomLeft
            : ml.AttributionButtonPosition.bottomRight,
        attributionButtonMargins: d.margenInferior > 0
            ? math.Point(14, d.margenInferior)
            : null,
        // El mapa toma todos los gestos que empiezan sobre él, aunque esté
        // dentro de otro widget que también reaccione a toques.
        gestureRecognizers: <Factory<OneSequenceGestureRecognizer>>{
          Factory<OneSequenceGestureRecognizer>(EagerGestureRecognizer.new),
        },
        onMapCreated: (c) => _mapa = c,
        onStyleLoadedCallback: () {
          _estiloListo = true;
          _encolar(_dibujar);
        },
        onMapClick: (_, punto) =>
            d.alTocar(LatLng(punto.latitude, punto.longitude)),
      ),
    );
  }
}
