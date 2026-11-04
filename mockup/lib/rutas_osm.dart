// Búsqueda de lugares y cálculo de rutas con servicios de OpenStreetMap.
//
// - Nominatim convierte texto en coordenadas (y coordenadas en un nombre).
//   Su política de uso pide máximo 1 consulta por segundo, identificarse y no
//   autocompletar letra por letra: por eso se busca solo al confirmar.
// - OSRM calcula rutas en auto con alternativas e indicaciones paso a paso.
//
// Los servidores públicos son de demostración. Para producción se cambian al
// compilar, apuntando a uno propio o a un proveedor:
//   flutter run --dart-define=OSRM_URL=https://... --dart-define=NOMINATIM_URL=https://...
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

const osrmUrl = String.fromEnvironment(
  'OSRM_URL',
  defaultValue: 'https://router.project-osrm.org',
);
const nominatimUrl = String.fromEnvironment(
  'NOMINATIM_URL',
  defaultValue: 'https://nominatim.openstreetmap.org',
);

/// Identificación ante Nominatim y el servidor de teselas de OSM.
const agenteUsuario = 'via-capstone/1.0 (com.example.mockup)';

/// Recuadro de búsqueda: Gran Santiago (oeste, norte, este, sur).
const recuadroSantiago = '-70.85,-33.30,-70.45,-33.65';

/// Punto de partida por defecto, el mismo origen del modo demo.
const plazaDeArmas = Lugar('Plaza de Armas', LatLng(-33.4378, -70.6504));

class Lugar {
  const Lugar(this.nombre, this.punto, {this.detalle = ''});
  final String nombre;
  final LatLng punto;
  final String detalle;

  factory Lugar.fromNominatim(Map<String, dynamic> j) {
    final completo = j['display_name'] as String? ?? '';
    final nombre = j['name'] as String? ?? '';
    return Lugar(
      nombre.isNotEmpty ? nombre : completo.split(',').first,
      LatLng(
        double.parse(j['lat'] as String),
        double.parse(j['lon'] as String),
      ),
      detalle: completo,
    );
  }
}

class Paso {
  const Paso(this.tipo, this.modificador, this.calle, this.distanciaM);
  final String tipo; // depart | turn | arrive | parada | roundabout | ...
  final String? modificador; // left | slight right | straight | uturn | ...
  final String calle;
  final double distanciaM;

  static const _flechas = {
    'straight': '↑',
    'slight right': '↗',
    'right': '→',
    'sharp right': '↘',
    'slight left': '↖',
    'left': '←',
    'sharp left': '↙',
    'uturn': '↩',
  };
  static const _giros = {
    'slight right': 'Mantente a la derecha',
    'right': 'Gira a la derecha',
    'sharp right': 'Gira cerrado a la derecha',
    'slight left': 'Mantente a la izquierda',
    'left': 'Gira a la izquierda',
    'sharp left': 'Gira cerrado a la izquierda',
    'uturn': 'Da la vuelta',
  };

  String get indicacion {
    final via = calle.isEmpty ? 'la vía' : calle;
    final flecha = _flechas[modificador] ?? '↑';
    switch (tipo) {
      case 'depart':
        return '$flecha  Sal por $via';
      case 'arrive':
        return '⚑  Llegas a tu destino';
      case 'parada':
        return '◉  Llegas a la parada';
      case 'roundabout':
      case 'rotary':
        return '⟳  Toma la rotonda hacia $via';
    }
    final giro = _giros[modificador];
    return giro == null
        ? '$flecha  Continúa por $via'
        : '$flecha  $giro por $via';
  }
}

class RutaPropuesta {
  const RutaPropuesta({
    required this.nombre,
    required this.paradas,
    required this.distanciaKm,
    required this.duracionMin,
    required this.trazado,
    required this.pasos,
  });
  final String nombre;
  final List<Lugar> paradas; // origen, paradas intermedias y destino
  final double distanciaKm;
  final double duracionMin;
  final List<LatLng> trazado;
  final List<Paso> pasos;

  factory RutaPropuesta.fromOsrm(Map<String, dynamic> j, List<Lugar> paradas) {
    // GeoJSON entrega [lon, lat]; LatLng espera (lat, lon).
    final coordenadas = (j['geometry'] as Map<String, dynamic>)['coordinates'];
    final tramos = j['legs'] as List;
    final pasos = <Paso>[];
    for (var t = 0; t < tramos.length; t++) {
      for (final s in (tramos[t] as Map<String, dynamic>)['steps'] as List) {
        final m =
            (s as Map<String, dynamic>)['maneuver'] as Map<String, dynamic>;
        var tipo = m['type'] as String;
        if (tipo == 'depart' && t > 0) continue;
        if (tipo == 'arrive' && t < tramos.length - 1) tipo = 'parada';
        pasos.add(
          Paso(
            tipo,
            m['modifier'] as String?,
            s['name'] as String? ?? '',
            (s['distance'] as num).toDouble(),
          ),
        );
      }
    }
    return RutaPropuesta(
      nombre: '${paradas.first.nombre} → ${paradas.last.nombre}',
      paradas: paradas,
      distanciaKm: (j['distance'] as num) / 1000,
      duracionMin: (j['duration'] as num) / 60,
      trazado: [
        for (final c in coordenadas as List)
          LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()),
      ],
      pasos: pasos,
    );
  }
}

class BuscadorLugares {
  BuscadorLugares({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? nominatimUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;
  DateTime? _ultimaConsulta;

  Future<List<Lugar>> buscar(String texto) async {
    final datos = await _consultar('/search', {
      'q': texto,
      'format': 'jsonv2',
      'limit': '5',
      'countrycodes': 'cl',
      'viewbox': recuadroSantiago,
      'bounded': '1',
    });
    if (datos is! List) {
      throw const ServicioMapaException('Respuesta inesperada del buscador');
    }
    return [
      for (final l in datos) Lugar.fromNominatim(l as Map<String, dynamic>),
    ];
  }

  /// Nombre del lugar tocado en el mapa; si no hay, sus coordenadas.
  Future<Lugar> nombrar(LatLng punto) async {
    final respaldo = Lugar(
      '${punto.latitude.toStringAsFixed(4)}, ${punto.longitude.toStringAsFixed(4)}',
      punto,
    );
    try {
      final datos = await _consultar('/reverse', {
        'lat': '${punto.latitude}',
        'lon': '${punto.longitude}',
        'format': 'jsonv2',
        'zoom': '17',
      });
      if (datos is! Map<String, dynamic> || datos['lat'] == null) {
        return respaldo;
      }
      final lugar = Lugar.fromNominatim(datos);
      // Conserva el punto exacto que tocó el usuario, no el del edificio.
      return Lugar(lugar.nombre, punto, detalle: lugar.detalle);
    } catch (_) {
      return respaldo;
    }
  }

  Future<dynamic> _consultar(
    String ruta,
    Map<String, String> parametros,
  ) async {
    // Máximo una consulta por segundo, como exige Nominatim.
    final ultima = _ultimaConsulta;
    if (ultima != null) {
      final espera =
          const Duration(seconds: 1) - DateTime.now().difference(ultima);
      if (espera > Duration.zero) await Future<void>.delayed(espera);
    }
    _ultimaConsulta = DateTime.now();
    final r = await _http
        .get(
          base.replace(
            path: ruta,
            queryParameters: {...parametros, 'accept-language': 'es'},
          ),
          // El navegador no deja fijar User-Agent; en web identifica el Referer.
          headers: kIsWeb ? null : {'User-Agent': agenteUsuario},
        )
        .timeout(const Duration(seconds: 8));
    return _json(r);
  }
}

class Enrutador {
  Enrutador({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? osrmUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;

  /// Rutas en auto entre las paradas, la más rápida primero. OSRM solo
  /// entrega alternativas cuando hay dos paradas (origen y destino).
  Future<List<RutaPropuesta>> calcular(List<Lugar> paradas) async {
    if (paradas.length < 2) {
      throw const ServicioMapaException('Faltan el origen o el destino');
    }
    final puntos = paradas
        .map((p) => '${p.punto.longitude},${p.punto.latitude}')
        .join(';');
    final r = await _http
        .get(
          base.replace(
            path: '/route/v1/driving/$puntos',
            queryParameters: {
              'overview': 'full',
              'geometries': 'geojson',
              'steps': 'true',
              'alternatives': 'true',
            },
          ),
        )
        .timeout(const Duration(seconds: 12));
    final datos = _json(r) as Map<String, dynamic>;
    if (datos['code'] != 'Ok') {
      throw ServicioMapaException(
        datos['code'] == 'NoRoute'
            ? 'No hay ruta en auto entre esos puntos'
            : 'No se pudo calcular la ruta (${datos['code']})',
      );
    }
    return [
      for (final ruta in datos['routes'] as List)
        RutaPropuesta.fromOsrm(ruta as Map<String, dynamic>, paradas),
    ];
  }
}

dynamic _json(http.Response r) {
  final cuerpo = utf8.decode(r.bodyBytes);
  // OSRM responde 400 con un JSON que explica el error (p. ej. NoRoute).
  if (r.statusCode >= 300 && !cuerpo.trimLeft().startsWith('{')) {
    throw ServicioMapaException('Servicio de mapas: error ${r.statusCode}');
  }
  return jsonDecode(cuerpo);
}

class ServicioMapaException implements Exception {
  const ServicioMapaException(this.mensaje);
  final String mensaje;
  @override
  String toString() => mensaje;
}
