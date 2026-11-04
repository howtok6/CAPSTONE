// Dobles de prueba compartidos: GPS y mapa falsos.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mockup/mapa_low_poly.dart';
import 'package:mockup/ubicacion.dart';

/// GPS falso: concede o niega el permiso, recuerda la preferencia y entrega
/// las posiciones que se le pasen.
class GpsFalso implements FuenteUbicacion {
  GpsFalso({
    this.resultado = ResultadoPermiso.concedido,
    this.guardada = const PreferenciaUbicacion.exacta(),
  });
  ResultadoPermiso resultado;
  PreferenciaUbicacion? guardada;
  final pedidos = <PreferenciaUbicacion>[];
  final posiciones = StreamController<Posicion>.broadcast();

  @override
  Future<PreferenciaUbicacion?> preferenciaGuardada() async => guardada;
  @override
  Future<void> guardarPreferencia(PreferenciaUbicacion p) async => guardada = p;
  @override
  Future<ResultadoPermiso> permitir(PreferenciaUbicacion p) async {
    pedidos.add(p);
    return resultado;
  }

  @override
  Stream<Posicion> seguir(
    PreferenciaUbicacion p, {
    bool sistemaAproximado = false,
  }) => p.exacta
      ? posiciones.stream
      : posiciones.stream.map((x) => aproximar(x, p.rangoM));
  @override
  Future<void> abrirAjustes() async {}
}

/// Sin permiso de ubicación y sin preguntar (el usuario ya eligió no compartirla).
GpsFalso sinGps() =>
    GpsFalso(guardada: const PreferenciaUbicacion.desactivada());

/// MapLibre es una vista nativa: en las pruebas se reemplaza por un recuadro
/// que guarda los últimos datos recibidos y avisa los toques como gestos.
class MapaFalso {
  DatosMapa? ultimo;
  Widget construir(DatosMapa d) {
    ultimo = d;
    return Listener(
      key: const Key('mapa-falso'),
      onPointerDown: (_) => d.alInteractuar?.call(),
      child: const ColoredBox(color: Colors.black),
    );
  }
}
