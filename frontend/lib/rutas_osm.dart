// Búsqueda de lugares y cálculo de rutas, a través del backend Go de «Vía».
//
// La app ya no llama directo a OpenStreetMap: el backend (`/v1/lugares` y
// `/v1/rutas`) consulta Nominatim y OSRM, respeta sus límites de uso, guarda
// en caché y agrega a cada ruta los semáforos por los que pasa.
//
// La URL del backend es la misma de via_api.dart (API_URL). Solo las teselas
// del mapa se piden directo al servidor de OpenStreetMap.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import 'via_api.dart' show apiUrl;

/// Punto de partida por defecto, el mismo origen del modo demo.
const plazaDeArmas = Lugar('Plaza de Armas', LatLng(-33.4378, -70.6504));

/// Un punto con nombre: origen, parada o destino de una ruta.
class Lugar {
  const Lugar(this.nombre, this.punto, {this.detalle = ''});
  final String nombre;
  final LatLng punto;
  final String detalle;

  /// Lee un lugar del backend (`GET /v1/lugares`).
  factory Lugar.fromJson(Map<String, dynamic> j) => Lugar(
    j['nombre'] as String,
    LatLng((j['lat'] as num).toDouble(), (j['lon'] as num).toDouble()),
    detalle: j['detalle'] as String? ?? '',
  );

  Map<String, dynamic> toJson() => {
    'lat': punto.latitude,
    'lon': punto.longitude,
  };
}

/// Una maniobra de la ruta: salir, girar, continuar, parada o llegar.
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

  /// Texto para el conductor con su flecha, por ejemplo
  /// «→  Gira a la derecha por Bandera».
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

/// Semáforo por el que pasa una ruta, según el backend.
class SemaforoEnRuta {
  const SemaforoEnRuta(
    this.nombre,
    this.distanciaDesdeInicioM, {
    this.id = '',
    this.punto,
  });
  final String nombre;
  final double distanciaDesdeInicioM;

  /// Identificador del semáforo en la simulación (el mismo que trae el próximo
  /// semáforo de un viaje) y su ubicación, para dibujarlo en el mapa.
  final String id;
  final LatLng? punto;
}

/// Ruta calculada por el backend, lista para mostrarse en el mapa y en el selector.
class RutaPropuesta {
  const RutaPropuesta({
    required this.nombre,
    required this.paradas,
    required this.distanciaKm,
    required this.duracionMin,
    required this.trazado,
    required this.pasos,
    this.semaforos = const [],
  });
  final String nombre;
  final List<Lugar> paradas; // origen, paradas intermedias y destino
  final double distanciaKm;
  final double duracionMin;
  final List<LatLng> trazado;
  final List<Paso> pasos;
  final List<SemaforoEnRuta> semaforos;

  /// Lee una ruta de `POST /v1/rutas`. El backend ya unió los tramos y marcó
  /// como «parada» las llegadas intermedias; el trazado viene como [lat, lon].
  factory RutaPropuesta.fromJson(Map<String, dynamic> j, List<Lugar> paradas) {
    return RutaPropuesta(
      nombre: '${paradas.first.nombre} → ${paradas.last.nombre}',
      paradas: paradas,
      distanciaKm: (j['distancia_km'] as num).toDouble(),
      duracionMin: (j['duracion_min'] as num).toDouble(),
      trazado: [
        for (final c in j['trazado'] as List)
          LatLng((c[0] as num).toDouble(), (c[1] as num).toDouble()),
      ],
      pasos: [
        for (final p in j['pasos'] as List? ?? const [])
          Paso(
            p['tipo'] as String,
            p['modificador'] as String?,
            p['calle'] as String? ?? '',
            (p['distancia_m'] as num).toDouble(),
          ),
      ],
      semaforos: [
        for (final s in j['semaforos'] as List? ?? const [])
          SemaforoEnRuta(
            s['nombre'] as String,
            (s['distancia_desde_inicio_m'] as num).toDouble(),
            id: s['id'] as String? ?? '',
            punto: s['lat'] == null || s['lon'] == null
                ? null
                : LatLng(
                    (s['lat'] as num).toDouble(),
                    (s['lon'] as num).toDouble(),
                  ),
          ),
      ],
    );
  }

  /// Trazado en el formato que espera el backend: pares [lat, lon].
  List<List<double>> get trazadoLatLon => [
    for (final p in trazado) [p.latitude, p.longitude],
  ];
}

/// Busca lugares por nombre y nombra puntos del mapa (`/v1/lugares`).
class BuscadorLugares {
  BuscadorLugares({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? apiUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;

  /// Hasta 5 lugares del Gran Santiago que coinciden con [texto].
  Future<List<Lugar>> buscar(String texto) async {
    final r = await _http
        .get(base.replace(path: '/v1/lugares', queryParameters: {'q': texto}))
        .timeout(const Duration(seconds: 10));
    final datos = _json(r);
    if (datos is! List) {
      throw const ServicioMapaException('Respuesta inesperada del buscador');
    }
    return [for (final l in datos) Lugar.fromJson(l as Map<String, dynamic>)];
  }

  /// Nombre del lugar tocado en el mapa; si no hay, sus coordenadas.
  Future<Lugar> nombrar(LatLng punto) async {
    final respaldo = Lugar(
      '${punto.latitude.toStringAsFixed(4)}, ${punto.longitude.toStringAsFixed(4)}',
      punto,
    );
    try {
      final r = await _http
          .get(
            base.replace(
              path: '/v1/lugares/inverso',
              queryParameters: {
                'lat': '${punto.latitude}',
                'lon': '${punto.longitude}',
              },
            ),
          )
          .timeout(const Duration(seconds: 10));
      final lugar = Lugar.fromJson(_json(r) as Map<String, dynamic>);
      // Conserva el punto exacto que tocó el usuario.
      return Lugar(lugar.nombre, punto, detalle: lugar.detalle);
    } catch (_) {
      return respaldo;
    }
  }
}

/// Calcula rutas en auto con sus semáforos (`POST /v1/rutas`).
class Enrutador {
  Enrutador({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? apiUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;

  /// Rutas en auto entre las paradas, la más rápida primero. Solo hay
  /// alternativas cuando hay dos paradas (origen y destino).
  Future<List<RutaPropuesta>> calcular(List<Lugar> paradas) async {
    if (paradas.length < 2) {
      throw const ServicioMapaException('Faltan el origen o el destino');
    }
    final r = await _http
        .post(
          base.replace(path: '/v1/rutas'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'paradas': [for (final p in paradas) p.toJson()],
            'alternativas': true,
          }),
        )
        .timeout(const Duration(seconds: 20));
    final datos = _json(r);
    if (datos is! List) {
      throw const ServicioMapaException('Respuesta inesperada del enrutador');
    }
    return [
      for (final ruta in datos)
        RutaPropuesta.fromJson(ruta as Map<String, dynamic>, paradas),
    ];
  }
}

/// Error de búsqueda o de cálculo de ruta, con un mensaje para el usuario.
class ServicioMapaException implements Exception {
  const ServicioMapaException(this.mensaje);
  final String mensaje;
  @override
  String toString() => mensaje;
}

/// Decodifica la respuesta como UTF-8 (para tildes y ñ). Si el backend
/// respondió un error, lo convierte en un mensaje claro para el usuario.
dynamic _json(http.Response r) {
  final cuerpo = utf8.decode(r.bodyBytes);
  if (r.statusCode < 300) return jsonDecode(cuerpo);
  String? codigo;
  try {
    codigo = ((jsonDecode(cuerpo) as Map)['error'] as Map)['codigo'] as String?;
  } catch (_) {}
  throw ServicioMapaException(switch (codigo) {
    'sin_ruta' => 'No hay ruta en auto entre esos puntos',
    'servicio_no_disponible' => 'El servicio de mapas no está disponible',
    'solicitud_invalida' => 'Revisa el origen y el destino',
    _ => 'Servicio de mapas: error ${r.statusCode}',
  });
}
