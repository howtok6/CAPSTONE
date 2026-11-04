// Cliente de la API de simulación en vivo (tsc-thesis/api).
//
// La URL base se fija al compilar:
//   flutter run --dart-define=API_URL=http://192.168.1.50:8000
// Por defecto usa http://127.0.0.1:8000, que funciona en un celular conectado
// por USB tras `adb reverse tcp:8000 tcp:8000`.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

const apiUrl = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://127.0.0.1:8000',
);

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

class ProximoSemaforo {
  const ProximoSemaforo({
    required this.nombre,
    required this.distanciaM,
    required this.color,
    required this.segundos,
    required this.siguiente,
    required this.exacto,
  });
  final String nombre;
  final int distanciaM;
  final String color; // verde | amarillo | rojo | apagado
  final int? segundos;
  final String? siguiente;
  final bool exacto;

  factory ProximoSemaforo.fromJson(Map<String, dynamic> j) => ProximoSemaforo(
    nombre: j['nombre'] as String,
    distanciaM: (j['distancia_m'] as num).round(),
    color: j['color'] as String,
    segundos: (j['segundos_para_cambio'] as num?)?.round(),
    siguiente: j['siguiente_color'] as String?,
    exacto: j['exacto'] as bool? ?? false,
  );
}

class EstadoViaje {
  const EstadoViaje({
    required this.id,
    required this.estado,
    required this.destino,
    this.semaforo,
    this.distanciaRestanteM,
  });
  final String id;
  final String estado; // esperando | en_ruta | llego | finalizado | reiniciado
  final String destino;
  final ProximoSemaforo? semaforo;
  final int? distanciaRestanteM;

  bool get activo => estado == 'esperando' || estado == 'en_ruta';

  factory EstadoViaje.fromJson(Map<String, dynamic> j) {
    final s = j['proximo_semaforo'];
    return EstadoViaje(
      id: j['id'] as String,
      estado: j['estado'] as String,
      destino: j['destino'] as String,
      semaforo: s == null
          ? null
          : ProximoSemaforo.fromJson(s as Map<String, dynamic>),
      distanciaRestanteM: (j['distancia_restante_m'] as num?)?.round(),
    );
  }
}

class ViaApi {
  ViaApi({String? baseUrl, http.Client? client})
    : base = Uri.parse(baseUrl ?? apiUrl),
      _http = client ?? http.Client();

  final Uri base;
  final http.Client _http;
  static const _espera = Duration(seconds: 4);

  Future<List<Destino>> destinos() async {
    final r = await _http.get(base.resolve('/destinos')).timeout(_espera);
    _revisar(r);
    return (_json(r) as List)
        .map((d) => Destino.fromJson(d as Map<String, dynamic>))
        .toList();
  }

  Future<EstadoViaje> crearViaje(int ruta) async {
    final r = await _http
        .post(
          base.resolve('/viajes'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'ruta': ruta}),
        )
        .timeout(const Duration(seconds: 12));
    _revisar(r);
    return EstadoViaje.fromJson(_json(r) as Map<String, dynamic>);
  }

  Future<EstadoViaje> viaje(String id) async {
    final r = await _http.get(base.resolve('/viajes/$id')).timeout(_espera);
    _revisar(r);
    return EstadoViaje.fromJson(_json(r) as Map<String, dynamic>);
  }

  Future<void> finalizarViaje(String id) async {
    await _http.delete(base.resolve('/viajes/$id')).timeout(_espera);
  }

  // FastAPI responde `application/json` sin charset; sin esto, package:http
  // decodificaría como latin-1 y los nombres con tildes o «×» saldrían mal.
  static dynamic _json(http.Response r) => jsonDecode(utf8.decode(r.bodyBytes));

  void _revisar(http.Response r) {
    if (r.statusCode >= 300) {
      throw ViaApiException(r.statusCode, utf8.decode(r.bodyBytes));
    }
  }
}

class ViaApiException implements Exception {
  ViaApiException(this.status, this.detalle);
  final int status;
  final String detalle;
  @override
  String toString() => 'API $status: $detalle';
}
