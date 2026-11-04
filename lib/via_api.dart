// Cliente del backend Go de «Vía» (backend/ en la rama master): viajes,
// semáforos y ubicación. La app habla solo con el backend; él consulta la
// simulación, OSRM y Nominatim.
//
// La URL base se fija al compilar:
//   flutter run --dart-define=API_URL=http://192.168.1.50:8080
// Por defecto usa http://127.0.0.1:8080, que funciona en un celular conectado
// por USB tras `adb reverse tcp:8080 tcp:8080`.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import 'ubicacion.dart';

const apiUrl = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://127.0.0.1:8080',
);

/// Recorrido de demostración de la simulación (`GET /v1/simulacion/destinos`).
class Destino {
  const Destino(this.ruta, this.nombre, this.distanciaKm);
  final int ruta;
  final String nombre;
  final double distanciaKm;

  factory Destino.fromJson(Map<String, dynamic> j) => Destino(
    j['ruta'] as int,
    j['nombre'] as String,
    (j['distancia_km'] as num).toDouble(),
  );
}

/// Próximo semáforo en el camino del usuario, según el backend.
///
/// [segundos] es null cuando no se puede predecir el cambio. [exacto] indica
/// si la cuenta regresiva es exacta (plan fijo) o una estimación (controlador
/// adaptativo).
class ProximoSemaforo {
  const ProximoSemaforo({
    this.id = '',
    required this.nombre,
    required this.distanciaM,
    required this.color,
    required this.segundos,
    required this.siguiente,
    required this.exacto,
  });
  final String id;
  final String nombre;
  final int distanciaM;
  final String color; // verde | amarillo | rojo | apagado | desconocido
  final int? segundos;
  final String? siguiente;
  final bool exacto;

  factory ProximoSemaforo.fromJson(Map<String, dynamic> j) => ProximoSemaforo(
    id: j['id'] as String? ?? '',
    nombre: j['nombre'] as String,
    distanciaM: (j['distancia_m'] as num).round(),
    color: j['color'] as String,
    segundos: (j['segundos_para_cambio'] as num?)?.round(),
    siguiente: j['siguiente_color'] as String?,
    exacto: j['exacto'] as bool? ?? false,
  );
}

/// Estado de un viaje (respuesta de `POST /v1/viajes`, `GET /v1/viajes/{id}`
/// y `POST /v1/viajes/{id}/ubicacion`).
class EstadoViaje {
  const EstadoViaje({
    required this.id,
    required this.estado,
    required this.destino,
    this.modo = 'simulado',
    this.semaforo,
    this.distanciaRestanteM,
    this.tieneUbicacion = false,
    this.posicion,
  });
  final String id;
  final String estado; // esperando | en_ruta | llego | finalizado | reiniciado
  final String destino;
  final String modo; // gps (ubicación real del celular) | simulado
  final ProximoSemaforo? semaforo;
  final int? distanciaRestanteM;

  /// En un viaje GPS, si el backend ya recibió alguna ubicación.
  final bool tieneUbicacion;

  /// Última ubicación conocida del viaje: la que envió el celular (GPS) o la
  /// del vehículo dentro de la simulación (simulado).
  final LatLng? posicion;

  bool get esGps => modo == 'gps';

  /// true mientras el vehículo no ha llegado ni se ha retirado; solo entonces
  /// tiene sentido seguir consultando.
  bool get activo => estado == 'esperando' || estado == 'en_ruta';

  factory EstadoViaje.fromJson(Map<String, dynamic> j) {
    final s = j['proximo_semaforo'];
    final u = j['ubicacion'];
    return EstadoViaje(
      id: j['id'] as String,
      estado: j['estado'] as String,
      destino: j['destino'] as String? ?? '',
      modo: j['modo'] as String? ?? 'simulado',
      tieneUbicacion: u != null,
      posicion: u is Map && u['lat'] != null && u['lon'] != null
          ? LatLng((u['lat'] as num).toDouble(), (u['lon'] as num).toDouble())
          : null,
      semaforo: s == null
          ? null
          : ProximoSemaforo.fromJson(s as Map<String, dynamic>),
      distanciaRestanteM: (j['distancia_restante_m'] as num?)?.round(),
    );
  }
}

/// Cliente HTTP del backend. Cada método lanza una excepción si el backend no
/// responde o devuelve error; quien llama decide si pasar a demo.
class ViaApi {
  ViaApi({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? apiUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;
  static const _espera = Duration(seconds: 4);

  /// Recorridos de demostración de la simulación, con su distancia.
  Future<List<Destino>> destinos() async {
    final r = await _http
        .get(base.resolve('/v1/simulacion/destinos'))
        .timeout(_espera);
    _revisar(r);
    return (_json(r) as List)
        .map((d) => Destino.fromJson(d as Map<String, dynamic>))
        .toList();
  }

  /// Viaje simulado: un vehículo de la simulación va hacia el destino [ruta].
  /// Admite una espera más larga porque el vehículo debe entrar a la red.
  Future<EstadoViaje> crearViaje(int ruta) =>
      _crear({'modo': 'simulado', 'destino': ruta});

  /// Viaje GPS por la ruta elegida: la app enviará la ubicación del celular.
  /// [trazado] son pares [lat, lon], tal como vienen de `/v1/rutas`.
  Future<EstadoViaje> crearViajeGps({
    required List<List<double>> trazado,
    String destino = '',
  }) => _crear({'modo': 'gps', 'trazado': trazado, 'nombre_destino': destino});

  Future<EstadoViaje> _crear(Map<String, Object> cuerpo) async {
    final r = await _http
        .post(
          base.resolve('/v1/viajes'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(cuerpo),
        )
        .timeout(const Duration(seconds: 15));
    _revisar(r);
    return EstadoViaje.fromJson(_json(r) as Map<String, dynamic>);
  }

  /// Envía la ubicación del GPS; devuelve el viaje con su próximo semáforo.
  Future<EstadoViaje> enviarUbicacion(String id, Posicion p) async {
    final r = await _http
        .post(
          base.resolve('/v1/viajes/$id/ubicacion'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(p.toJson()),
        )
        .timeout(_espera);
    _revisar(r);
    return EstadoViaje.fromJson(_json(r) as Map<String, dynamic>);
  }

  /// Estado actual del viaje [id], con su próximo semáforo.
  Future<EstadoViaje> viaje(String id) async {
    final r = await _http.get(base.resolve('/v1/viajes/$id')).timeout(_espera);
    _revisar(r);
    return EstadoViaje.fromJson(_json(r) as Map<String, dynamic>);
  }

  /// Termina el viaje [id]; en uno simulado, retira el vehículo.
  Future<void> finalizarViaje(String id) async {
    await _http.delete(base.resolve('/v1/viajes/$id')).timeout(_espera);
  }

  // Siempre como UTF-8: sin esto, package:http decodificaría como latin-1 si
  // falta el charset, y los nombres con tildes o «×» saldrían mal.
  static dynamic _json(http.Response r) => jsonDecode(utf8.decode(r.bodyBytes));

  /// Lanza [ViaApiException] si la respuesta no es exitosa (código 300 o más).
  void _revisar(http.Response r) {
    if (r.statusCode >= 300) {
      throw ViaApiException(r.statusCode, utf8.decode(r.bodyBytes));
    }
  }
}

/// Error HTTP del backend, con el código y el detalle que devolvió
/// (`{"error": {"codigo", "mensaje"}}`).
class ViaApiException implements Exception {
  ViaApiException(this.status, this.detalle);
  final int status;
  final String detalle;
  @override
  String toString() => 'API $status: $detalle';
}
