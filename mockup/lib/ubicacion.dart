// Ubicación del celular para los viajes GPS.
//
// [FuenteUbicacion] separa la app del plugin de GPS: en la app se usa
// [FuenteGps] (geolocator) y en las pruebas una fuente falsa.
import 'dart:async';

import 'package:geolocator/geolocator.dart';

/// Una lectura del GPS, en el formato que recibe el backend.
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
  final double? precisionM;

  Map<String, dynamic> toJson() => {
    'lat': lat,
    'lon': lon,
    'rumbo': ?rumbo,
    'velocidad_kmh': ?velocidadKmh,
    'precision_m': ?precisionM,
  };
}

/// Origen de las ubicaciones del usuario.
abstract class FuenteUbicacion {
  /// Pide permiso y verifica que el GPS esté encendido. false si no se puede.
  Future<bool> permitir();

  /// Ubicaciones a medida que el usuario se mueve.
  Stream<Posicion> seguir();
}

/// GPS del celular con geolocator.
class FuenteGps implements FuenteUbicacion {
  /// Bajo esta velocidad el rumbo del GPS no es confiable: se omite y el
  /// backend lo estima con la ubicación anterior.
  static const velocidadMinimaRumboMs = 1.5;

  @override
  Future<bool> permitir() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return false;
      var permiso = await Geolocator.checkPermission();
      if (permiso == LocationPermission.denied) {
        permiso = await Geolocator.requestPermission();
      }
      return permiso == LocationPermission.whileInUse ||
          permiso == LocationPermission.always;
    } catch (_) {
      return false; // sin plugin (pruebas, escritorio) o sin servicio
    }
  }

  @override
  Stream<Posicion> seguir() =>
      Geolocator.getPositionStream(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 5,
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
}
