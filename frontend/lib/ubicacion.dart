// Ubicación del celular: permiso, precisión elegida por el usuario y lecturas.
//
// El usuario decide cómo comparte su ubicación ([PreferenciaUbicacion]):
// - exacta: la lectura del GPS tal cual, para seguir la ruta y el próximo
//   semáforo con precisión;
// - aproximada: solo la zona, dentro de un rango (250 m, 500 m o 1 km). La app
//   ajusta cada lectura al centro de una cuadrícula de ese tamaño antes de
//   mostrarla o enviarla al backend, así la posición real nunca sale del celular;
// - desactivada: no se pide permiso y los recorridos van en demo.
//
// El sistema operativo también puede dar solo una ubicación aproximada (en
// Android 12 o más el diálogo de permiso ofrece «Precisa» o «Aproximada»).
// Se aplica siempre la más restrictiva de las dos.
//
// [FuenteUbicacion] separa la app del plugin de GPS: en la app se usa
// [FuenteGps] (geolocator) y en las pruebas una fuente falsa.
import 'dart:async';
import 'dart:math' as math;

import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Una lectura de ubicación, en el formato que recibe el backend.
class Posicion {
  const Posicion(
    this.lat,
    this.lon, {
    this.rumbo,
    this.velocidadKmh,
    this.precisionM,
  });
  final double lat;
  final double lon;

  /// Grados desde el norte; null si el GPS no lo sabe (p. ej. detenido).
  final double? rumbo;
  final double? velocidadKmh;

  /// Radio de incertidumbre, en metros. En modo aproximado es el rango elegido.
  final double? precisionM;

  LatLng get punto => LatLng(lat, lon);

  Map<String, dynamic> toJson() => {
    'lat': lat,
    'lon': lon,
    'rumbo': ?rumbo,
    'velocidad_kmh': ?velocidadKmh,
    'precision_m': ?precisionM,
  };
}

enum ModoUbicacion { exacta, aproximada, desactivada }

/// Cómo quiere el usuario compartir su ubicación.
class PreferenciaUbicacion {
  const PreferenciaUbicacion._(this.modo, this.rangoM);
  const PreferenciaUbicacion.exacta() : this._(ModoUbicacion.exacta, 0);
  const PreferenciaUbicacion.aproximada([int rangoM = 500])
    : this._(ModoUbicacion.aproximada, rangoM);
  const PreferenciaUbicacion.desactivada()
    : this._(ModoUbicacion.desactivada, 0);

  final ModoUbicacion modo;

  /// Radio de la zona, en metros; solo en modo aproximado.
  final int rangoM;

  /// Rangos que puede elegir el usuario en modo aproximado.
  static const rangos = [250, 500, 1000];

  bool get activa => modo != ModoUbicacion.desactivada;
  bool get exacta => modo == ModoUbicacion.exacta;

  /// Texto corto para el encabezado: «Exacta», «≈ 500 m», «≈ 1 km».
  String get etiqueta => switch (modo) {
    ModoUbicacion.exacta => 'Exacta',
    ModoUbicacion.aproximada => '≈ ${textoRango(rangoM)}',
    ModoUbicacion.desactivada => 'Sin ubicación',
  };

  static String textoRango(int m) =>
      m >= 1000 ? '${(m / 1000).toStringAsFixed(m % 1000 == 0 ? 0 : 1)} km' : '$m m';

  /// Formato para guardar: «exacta», «aproximada:500» o «desactivada».
  String codificar() =>
      modo == ModoUbicacion.aproximada ? 'aproximada:$rangoM' : modo.name;

  static PreferenciaUbicacion? decodificar(String? texto) {
    if (texto == null) return null;
    if (texto == 'exacta') return const PreferenciaUbicacion.exacta();
    if (texto == 'desactivada') return const PreferenciaUbicacion.desactivada();
    if (texto.startsWith('aproximada:')) {
      final m = int.tryParse(texto.substring(11));
      if (m != null && m > 0) return PreferenciaUbicacion.aproximada(m);
    }
    return null;
  }

  @override
  bool operator ==(Object other) =>
      other is PreferenciaUbicacion &&
      other.modo == modo &&
      other.rangoM == rangoM;

  @override
  int get hashCode => Object.hash(modo, rangoM);
}

/// Resultado de pedir el permiso de ubicación.
enum ResultadoPermiso {
  /// Concedido con la precisión pedida.
  concedido,

  /// Concedido, pero el sistema solo entrega ubicación aproximada.
  soloAproximado,

  /// El usuario lo negó; se puede volver a pedir.
  denegado,

  /// Negado de forma permanente: solo se cambia en los ajustes del sistema.
  denegadoSiempre,

  /// La ubicación del celular está apagada.
  servicioApagado,
}

extension ResultadoPermisoX on ResultadoPermiso {
  bool get concedido =>
      this == ResultadoPermiso.concedido ||
      this == ResultadoPermiso.soloAproximado;
}

/// Rango con que se trata la ubicación cuando el sistema solo la da
/// aproximada. Android la entrega con una incertidumbre de hasta ~2 km.
const rangoSistemaAproximadoM = 2000;

/// Lleva [p] al centro de la celda de una cuadrícula de [rangoM] metros.
///
/// La cuadrícula es fija (no depende de la lectura anterior), así que mientras
/// el usuario se mueve dentro de una misma celda la posición no cambia y no
/// revela el recorrido fino. El rumbo y la velocidad se conservan: no dicen
/// dónde está el usuario y el backend los necesita para el próximo semáforo.
Posicion aproximar(Posicion p, int rangoM) {
  const metrosPorGrado = 111320.0;
  final pasoLat = rangoM / metrosPorGrado;
  final lat = ((p.lat / pasoLat).floor() + 0.5) * pasoLat;
  final pasoLon =
      rangoM / (metrosPorGrado * math.cos(lat * math.pi / 180).abs().clamp(0.01, 1));
  final lon = ((p.lon / pasoLon).floor() + 0.5) * pasoLon;
  return Posicion(
    lat,
    lon,
    rumbo: p.rumbo,
    velocidadKmh: p.velocidadKmh,
    precisionM: math.max(rangoM.toDouble(), p.precisionM ?? 0),
  );
}

/// Origen de las ubicaciones del usuario.
abstract class FuenteUbicacion {
  /// La preferencia guardada; null si el usuario nunca la eligió.
  Future<PreferenciaUbicacion?> preferenciaGuardada();

  /// Guarda la preferencia para las próximas aperturas de la app.
  Future<void> guardarPreferencia(PreferenciaUbicacion preferencia);

  /// Pide permiso al sistema según la [preferencia] y verifica que la
  /// ubicación del celular esté encendida.
  Future<ResultadoPermiso> permitir(PreferenciaUbicacion preferencia);

  /// Ubicaciones a medida que el usuario se mueve, ya ajustadas al rango de la
  /// [preferencia] (o al del sistema, si este solo concedió aproximada).
  Stream<Posicion> seguir(
    PreferenciaUbicacion preferencia, {
    bool sistemaAproximado = false,
  });

  /// Abre los ajustes de la app en el sistema (para un permiso negado siempre).
  Future<void> abrirAjustes();
}

/// GPS del celular con geolocator; la preferencia se guarda con
/// shared_preferences.
class FuenteGps implements FuenteUbicacion {
  /// Bajo esta velocidad el rumbo del GPS no es confiable: se omite y el
  /// backend lo estima con la ubicación anterior.
  static const velocidadMinimaRumboMs = 1.5;
  static const _clave = 'via.ubicacion';

  /// Clave del Info.plist de iOS para pedir precisión total por una vez.
  static const propositoIos = 'Navegacion';

  @override
  Future<PreferenciaUbicacion?> preferenciaGuardada() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return PreferenciaUbicacion.decodificar(prefs.getString(_clave));
    } catch (_) {
      return null; // sin plugin (pruebas, escritorio)
    }
  }

  @override
  Future<void> guardarPreferencia(PreferenciaUbicacion preferencia) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_clave, preferencia.codificar());
    } catch (_) {}
  }

  @override
  Future<ResultadoPermiso> permitir(PreferenciaUbicacion preferencia) async {
    if (!preferencia.activa) return ResultadoPermiso.denegado;
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        return ResultadoPermiso.servicioApagado;
      }
      var permiso = await Geolocator.checkPermission();
      if (permiso == LocationPermission.denied) {
        permiso = await Geolocator.requestPermission();
      }
      if (permiso == LocationPermission.deniedForever) {
        return ResultadoPermiso.denegadoSiempre;
      }
      if (permiso != LocationPermission.whileInUse &&
          permiso != LocationPermission.always) {
        return ResultadoPermiso.denegado;
      }
      var precision = LocationAccuracyStatus.precise;
      try {
        precision = await Geolocator.getLocationAccuracy();
      } catch (_) {
        // Web y algunas plataformas no informan la precisión concedida.
      }
      if (precision == LocationAccuracyStatus.reduced && preferencia.exacta) {
        // En iOS se puede pedir precisión total para esta sesión; en Android
        // la respuesta no cambia y el usuario debe cambiarla en los ajustes.
        try {
          precision = await Geolocator.requestTemporaryFullAccuracy(
            purposeKey: propositoIos,
          );
        } catch (_) {}
      }
      return precision == LocationAccuracyStatus.reduced
          ? ResultadoPermiso.soloAproximado
          : ResultadoPermiso.concedido;
    } catch (_) {
      return ResultadoPermiso.denegado; // sin plugin (pruebas, escritorio)
    }
  }

  @override
  Stream<Posicion> seguir(
    PreferenciaUbicacion preferencia, {
    bool sistemaAproximado = false,
  }) {
    final rango = sistemaAproximado
        ? math.max(preferencia.rangoM, rangoSistemaAproximadoM)
        : preferencia.rangoM;
    final exacta = preferencia.exacta && !sistemaAproximado;
    final lecturas = Geolocator.getPositionStream(
      locationSettings: LocationSettings(
        // En modo aproximado basta una precisión baja: ahorra batería.
        accuracy: exacta ? LocationAccuracy.high : LocationAccuracy.low,
        distanceFilter: exacta ? 5 : math.max(25, rango ~/ 4),
      ),
    ).map(
      (p) => Posicion(
        p.latitude,
        p.longitude,
        rumbo: p.speed >= velocidadMinimaRumboMs && p.heading >= 0
            ? p.heading % 360
            : null,
        velocidadKmh: p.speed >= 0 ? p.speed * 3.6 : null,
        precisionM: p.accuracy > 0 ? p.accuracy : null,
      ),
    );
    if (exacta) return lecturas;
    // Solo se emite cuando cambia la celda: dentro de ella no hay nada nuevo.
    return lecturas
        .map((p) => aproximar(p, rango))
        .distinct((a, b) => a.lat == b.lat && a.lon == b.lon);
  }

  @override
  Future<void> abrirAjustes() async {
    try {
      await Geolocator.openAppSettings();
    } catch (_) {}
  }
}
