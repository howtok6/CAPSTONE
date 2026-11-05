// Pantalla principal de «Vía»: vista de conducción con semáforo, paneles de
// gasolina y gasto energético, y controles de recorrido.
//
// El fondo es un mapa 3D low poly navegable (lib/mapa_low_poly.dart): se mueve,
// acerca, gira e inclina con los dedos, dibuja la ruta elegida con sus
// semáforos y sigue al usuario (o al vehículo simulado) durante el recorrido.
// «Conducción» lleva la cámara detrás del usuario mirando hacia donde avanza;
// «Desde arriba», cenital con el norte arriba. Al mover el mapa la cámara deja
// de seguir; el botón de recentrar la devuelve.
//
// Al abrir la app por primera vez se pregunta cómo compartir la ubicación:
// exacta o aproximada dentro de un rango (lib/permiso_ubicacion.dart). La
// elección se guarda y se cambia tocando el indicador del encabezado.
//
// La pantalla funciona en tres modos según de dónde salen los datos. Todo lo
// que no es demo viene del backend Go (lib/via_api.dart y lib/rutas_osm.dart):
// - Demo: semáforo, rutas y distancias simuladas dentro de la app.
// - Viaje simulado: un vehículo de la simulación recorre un destino de
//   demostración y el panel muestra sus semáforos.
// - Viaje GPS: el usuario elige una ruta real (lib/proponer_ruta.dart) y la app
//   envía la ubicación del celular (lib/ubicacion.dart); el backend responde
//   el próximo semáforo. Sin permiso de ubicación se recorre en demo.

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import 'mapa_low_poly.dart';
import 'permiso_ubicacion.dart';
import 'proponer_ruta.dart';
import 'rutas_osm.dart';
import 'ubicacion.dart';
import 'via_api.dart';

/// Paleta compartida: amarillo de acento, fondo de tarjetas y texto secundario.
const yellow = Color(0xFFF5CB45);
const surface = Color(0xF01C2027);
const subdued = Color(0xFFB1B6C0);

/// Punto de entrada de la app.
void main() => runApp(const MyApp());

/// Raíz de la app: tema oscuro Material 3 con acento amarillo y la pantalla
/// de conducción como inicio.
class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Vía · Conducción',
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0C0E12),
      colorScheme: ColorScheme.fromSeed(
        seedColor: yellow,
        brightness: Brightness.dark,
        primary: yellow,
        surface: surface,
      ),
      fontFamily: 'Segoe UI',
    ),
    home: const MobilityPage(),
  );
}

/// Pantalla de conducción. Los clientes se pueden inyectar para las pruebas;
/// si son null se usan los servicios reales.
class MobilityPage extends StatefulWidget {
  const MobilityPage({
    super.key,
    this.api,
    this.buscador,
    this.enrutador,
    this.ubicacion,
    this.constructorMapa,
  });

  /// Cliente del backend; null usa la URL configurada (API_URL).
  final ViaApi? api;

  /// Búsqueda de lugares y rutas (también vía backend); null usa API_URL.
  final BuscadorLugares? buscador;
  final Enrutador? enrutador;

  /// Fuente de ubicación para los viajes GPS; null usa el GPS del celular.
  final FuenteUbicacion? ubicacion;

  /// Mapa de la pantalla principal y de «Proponer ruta»; null usa el mapa 3D
  /// low poly (MapLibre).
  final ConstructorMapa? constructorMapa;
  @override
  State<MobilityPage> createState() => _MobilityPageState();
}

class _MobilityPageState extends State<MobilityPage> {
  // --- Estado de la interfaz y del modo demo -------------------------------
  // octane: octanaje elegido. route: valor del selector de recorrido.
  // phase/seconds: ciclo local del semáforo (0 verde, 1 amarillo, 2 rojo).
  // efficiency: consumo de referencia del vehículo, en L/100 km.
  // expandedPanel: id de la tarjeta desplegada ('fuel', 'energy' o null).
  int octane = 95, route = 0, phase = 0, seconds = 24;
  double efficiency = 7.5;
  bool navigating = false;
  bool overhead = false;
  String? expandedPanel;
  late final Timer timer;

  // --- Viajes en vivo (backend) -------------------------------------------
  late final ViaApi api = widget.api ?? ViaApi();
  List<Destino>?
  destinos; // null = simulación no disponible → sin destinos demo
  EstadoViaje? viaje;
  bool consultando = false;

  // --- Ubicación del usuario ---------------------------------------------------
  // La ubicación se sigue mientras la app está abierta (para el mapa) y solo se
  // envía al backend durante un viaje GPS.
  late final FuenteUbicacion gps = widget.ubicacion ?? FuenteGps();
  PreferenciaUbicacion? preferencia; // null = el usuario aún no elige
  ResultadoPermiso? permiso; // respuesta del sistema al último pedido
  StreamSubscription<Posicion>? _ubicaciones;
  Posicion? miUbicacion; // ya ajustada al rango si es aproximada
  bool _enviandoUbicacion = false;
  Posicion? _ubicacionPendiente; // la última que llegó mientras se enviaba otra
  int _intentoViaje = 0; // identifica el último «Iniciar recorrido» en vivo
  bool get enVivo => viaje != null;

  // --- Mapa -------------------------------------------------------------------
  final mapa = ControlMapa();

  /// La cámara sigue al usuario hasta que este mueve el mapa con los dedos.
  bool siguiendo = true;
  ProximoSemaforo? get semaforoVivo => viaje?.semaforo;

  // --- Rutas propuestas por el usuario (OpenStreetMap, vía backend) ---------
  // Usan valores del selector desde [primeraPropuesta] para no chocar con los
  // índices de la simulación. Se recorren con el GPS del celular.
  static const primeraPropuesta = 100;
  final propuestas = <RutaPropuesta>[];
  RutaPropuesta? get propuesta =>
      route >= primeraPropuesta ? propuestas[route - primeraPropuesta] : null;

  /// Destino de la simulación elegido en el selector, si lo hay.
  Destino? get destinoSimulado =>
      propuesta == null && destinos != null && route < destinos!.length
      ? destinos![route]
      : null;

  /// La ruta que se dibuja en el mapa: la propuesta elegida o el recorrido del
  /// destino de la simulación (el mismo camino que hará el vehículo simulado).
  RutaPropuesta? get rutaEnMapa => propuesta ?? destinoSimulado?.comoRuta;

  /// Distancia del recorrido elegido, en km. Prioridad: ruta propuesta,
  /// destino de la simulación y, si no hay API, los valores fijos del demo.
  double get distance =>
      propuesta?.distanciaKm ??
      (destinos != null && route < destinos!.length
          ? destinos![route].distanciaKm
          : (route == 0 ? 4.8 : 6.2));

  /// Combustible estimado: distancia × consumo (L/100 km) ÷ 100.
  double get liters => distance * efficiency / 100;
  // Traducción entre los colores que envía la API y el índice de fase local.
  static const _colores = {'verde': 0, 'amarillo': 1, 'rojo': 2};
  static const _nombresColor = ['Verde', 'Amarillo', 'Rojo'];

  /// Fase que muestra el semáforo (0 verde, 1 amarillo, 2 rojo): la de la
  /// simulación en vivo o la del ciclo demo. Es -1 cuando en vivo no hay dato
  /// (aún no hay semáforo en la ruta, o está apagado): todas las luces apagadas.
  /// En vivo nunca se cae al ciclo demo, para no mostrar un color inventado.
  int get fase => enVivo ? (_colores[semaforoVivo?.color] ?? -1) : phase;

  /// Segundos para el cambio tal como se muestran: «—» si en vivo no hay dato,
  /// y «≈» delante cuando la simulación solo puede estimarlos (`exacto` false,
  /// con un controlador adaptativo).
  String get textoSegundos {
    if (!enVivo) return '${seconds}s';
    final s = semaforoVivo;
    if (s == null || s.segundos == null || fase < 0) return '—';
    return '${s.exacto ? '' : '≈'}${s.segundos}s';
  }

  /// Color del panel del semáforo según la fase: verde, amarillo, rojo o gris
  /// cuando no hay dato.
  Color get signalColor => fase < 0
      ? subdued
      : [const Color(0xFF6BD5A0), yellow, const Color(0xFFFF7773)][fase];

  /// Título del panel del semáforo: el cruce en vivo, o un mensaje según el
  /// estado del recorrido (entrando a la vía, llegada, reinicio).
  String get nombreSemaforo {
    if (viaje == null) return 'Av. Alameda';
    if (viaje!.esGps && !viaje!.tieneUbicacion) return 'Buscando tu ubicación…';
    if (viaje!.estado == 'esperando') return 'Entrando a la vía…';
    if (viaje!.estado == 'llego') return 'Llegaste a ${viaje!.destino}';
    if (viaje!.estado == 'reiniciado') return 'Simulación reiniciada';
    final s = semaforoVivo;
    return s == null ? 'Sin semáforos en la ruta' : s.nombre;
  }

  /// Línea secundaria del panel: el cambio de color que viene y, en vivo, la
  /// distancia hasta el cruce.
  String get cambioSemaforo {
    final s = semaforoVivo;
    if (s == null) {
      if (!enVivo) {
        return ['Verde → amarillo', 'Amarillo → rojo', 'Rojo → verde'][phase];
      }
      return viaje!.esGps ? 'Siguiendo tu ubicación' : 'Simulación en vivo';
    }
    if (fase < 0) {
      final motivo = s.color == 'apagado'
          ? 'Semáforo apagado'
          : 'Sin datos del semáforo';
      return '$motivo · a ${s.distanciaM} m';
    }
    final siguiente = _colores[s.siguiente];
    final cambio = siguiente == null
        ? _nombresColor[fase]
        : '${_nombresColor[fase]} → ${_nombresColor[siguiente].toLowerCase()}';
    return '$cambio · a ${s.distanciaM} m';
  }

  @override
  void initState() {
    super.initState();
    // Un solo reloj de 1 s: en vivo consulta el viaje; en demo avanza el ciclo
    // del semáforo (verde 30 s, amarillo 5 s, rojo 25 s).
    timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (enVivo) {
        actualizarViaje();
        return;
      }
      setState(() {
        if (seconds > 1) {
          seconds--;
        } else {
          phase = (phase + 1) % 3;
          seconds = [30, 5, 25][phase];
        }
      });
    });
    cargarDestinos();
    WidgetsBinding.instance.addPostFrameCallback((_) => prepararUbicacion());
  }

  /// Al abrir: si el usuario nunca eligió cómo compartir su ubicación, se le
  /// pregunta; si ya eligió, se activa sin volver a preguntar.
  Future<void> prepararUbicacion() async {
    final guardada = await gps.preferenciaGuardada();
    if (!mounted) return;
    if (guardada == null) {
      await cambiarUbicacion();
      return;
    }
    setState(() => preferencia = guardada);
    if (guardada.activa) await activarUbicacion(avisar: false);
  }

  /// Muestra la hoja de ubicación, guarda lo elegido y vuelve a pedir el
  /// permiso con la nueva precisión. Devuelve si quedó activa.
  Future<bool> cambiarUbicacion({bool avisar = true}) async {
    final eleccion = await elegirUbicacion(context, actual: preferencia);
    if (eleccion == null || !mounted) return ubicacionActiva;
    await gps.guardarPreferencia(eleccion);
    if (!mounted) return false;
    _detenerUbicacion();
    setState(() {
      preferencia = eleccion;
      permiso = null;
      miUbicacion = null;
    });
    if (!eleccion.activa) {
      // Sin ubicación, un viaje GPS en curso ya no puede seguirse.
      if (navigating && viaje?.esGps == true) await alternarRecorrido();
      return false;
    }
    return activarUbicacion(avisar: avisar);
  }

  bool get ubicacionActiva => _ubicaciones != null;

  /// Pide el permiso según la preferencia y empieza a seguir la ubicación.
  /// Con [avisar], explica al usuario por qué no se pudo.
  Future<bool> activarUbicacion({bool avisar = true}) async {
    final pref = preferencia;
    if (pref == null || !pref.activa) return false;
    if (_ubicaciones != null) return true;
    final r = await gps.permitir(pref);
    if (!mounted) return false;
    setState(() => permiso = r);
    if (!r.concedido) {
      if (avisar) avisarPermiso(r);
      return false;
    }
    final soloAproximado = r == ResultadoPermiso.soloAproximado;
    if (soloAproximado && avisar) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'El sistema solo permite ubicación aproximada: el próximo '
            'semáforo será una estimación',
          ),
        ),
      );
    }
    _ubicaciones = gps
        .seguir(pref, sistemaAproximado: soloAproximado)
        .listen(
          alMoverse,
          onError: (_) {
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Se perdió la señal del GPS')),
            );
          },
        );
    return true;
  }

  void _detenerUbicacion() {
    final s = _ubicaciones;
    _ubicaciones = null;
    _ubicacionPendiente = null;
    unawaited(s?.cancel());
  }

  /// Explica por qué no hay ubicación y, si hace falta, lleva a los ajustes.
  void avisarPermiso(ResultadoPermiso r, {String? texto}) {
    final mensaje =
        texto ??
        switch (r) {
          ResultadoPermiso.servicioApagado =>
            'La ubicación del celular está apagada',
          ResultadoPermiso.denegadoSiempre =>
            'Vía no tiene permiso de ubicación',
          _ => 'Sin permiso de ubicación: el mapa no te mostrará',
        };
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(mensaje),
        action: r == ResultadoPermiso.denegadoSiempre
            ? SnackBarAction(label: 'Ajustes', onPressed: gps.abrirAjustes)
            : null,
      ),
    );
  }

  /// Nueva ubicación del usuario: se dibuja, se envía si hay un viaje GPS y,
  /// si la cámara lo está siguiendo, la mueve.
  void alMoverse(Posicion p) {
    if (!mounted) return;
    setState(() => miUbicacion = p);
    if (viaje?.esGps == true) unawaited(enviarUbicacion(p));
    if (siguiendo && (navigating || rutaEnMapa == null)) seguirConCamara();
  }

  /// Lo que sigue la cámara: el vehículo en un viaje simulado; si no, el
  /// usuario.
  LatLng? get objetivoCamara => enVivo && !viaje!.esGps
      ? viaje!.posicion
      : miUbicacion?.punto;

  void seguirConCamara() {
    final objetivo = objetivoCamara;
    if (objetivo == null) return;
    mapa.seguir(
      objetivo,
      rumbo: enVivo && !viaje!.esGps ? null : miUbicacion?.rumbo,
      conduccion: !overhead,
    );
  }

  /// El usuario tocó el mapa: la cámara deja de seguirlo.
  void dejarDeSeguir() {
    if (siguiendo) setState(() => siguiendo = false);
  }

  /// Botón de recentrar (y cambios de ruta o de vista): durante un recorrido,
  /// o sin ruta elegida, la cámara sigue al usuario (si aún no se sabe dónde
  /// está, muestra la ruta y lo sigue en cuanto llega su ubicación); con una
  /// ruta elegida y sin recorrido, la encuadra completa.
  void recentrar() {
    final objetivo = objetivoCamara;
    final ruta = rutaEnMapa;
    final seguir = navigating || ruta == null;
    setState(() => siguiendo = seguir);
    if (seguir && objetivo != null) {
      seguirConCamara();
    } else if (ruta != null) {
      mapa.encuadrar(
        ruta.trazado,
        inclinacion: overhead ? 0.0 : MapaLowPoly.inclinacion,
      );
    } else {
      mapa.mover(
        plazaDeArmas.punto,
        15,
        inclinacion: overhead ? 0.0 : MapaLowPoly.inclinacion,
      );
    }
  }

  /// Pide los destinos a la simulación. Si responde, el selector muestra sus
  /// destinos y los recorridos pueden ir en vivo; si falla, la app sigue en demo.
  Future<void> cargarDestinos() async {
    try {
      final lista = await api.destinos();
      if (mounted && lista.isNotEmpty) {
        setState(() => destinos = lista);
        recentrar(); // muestra el recorrido de demostración elegido
      }
    } catch (_) {
      // Sin API: la app sigue en modo demo.
    }
  }

  /// Consulta el estado del viaje en vivo; la llama el reloj cada segundo.
  /// [consultando] evita pedidos superpuestos si la API tarda más de 1 s, y se
  /// descarta la respuesta si entretanto el viaje terminó o cambió.
  Future<void> actualizarViaje() async {
    final actual = viaje;
    if (actual == null || consultando || !actual.activo) return;
    consultando = true;
    try {
      final nuevo = await api.viaje(actual.id);
      if (mounted && viaje?.id == actual.id) {
        setState(() => viaje = nuevo);
        if (siguiendo && !nuevo.esGps) seguirConCamara();
      }
    } catch (_) {
      // Se reintenta en el siguiente segundo.
    } finally {
      consultando = false;
    }
  }

  /// Acción del botón Iniciar / Finalizar recorrido.
  ///
  /// Al finalizar, deja de seguir el GPS y termina el viaje sin esperar
  /// respuesta. Al iniciar: una ruta propuesta va como viaje GPS; un destino de
  /// la simulación, como viaje simulado; sin backend, en demo.
  Future<void> alternarRecorrido() async {
    if (navigating) {
      final actual = viaje;
      _ubicacionPendiente = null;
      setState(() {
        navigating = false;
        viaje = null;
      });
      if (actual != null) {
        unawaited(api.finalizarViaje(actual.id).catchError((_) {}));
      }
      recentrar();
      return;
    }
    setState(() => navigating = true);
    recentrar();
    final ruta = propuesta;
    if (ruta != null) return iniciarViajeGps(ruta);
    if (destinos == null) return; // modo demo
    // Crear el viaje puede tardar varios segundos. Si mientras tanto se finaliza
    // el recorrido, o se inicia otro, este viaje ya no corresponde: se retira de
    // la simulación en vez de dejar el vehículo abierto.
    final intento = ++_intentoViaje;
    bool vigente() => mounted && navigating && intento == _intentoViaje;
    try {
      final nuevo = await api.crearViaje(route);
      if (vigente()) {
        setState(() => viaje = nuevo);
      } else {
        unawaited(api.finalizarViaje(nuevo.id).catchError((_) {}));
      }
    } catch (_) {
      if (!mounted || !vigente()) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Sin conexión con la simulación: modo demo'),
        ),
      );
    }
  }

  /// Viaje GPS por la ruta propuesta: pide permiso de ubicación, crea el viaje
  /// en el backend y le envía cada ubicación. Sin permiso o sin backend, el
  /// recorrido sigue en demo.
  Future<void> iniciarViajeGps(RutaPropuesta ruta) async {
    final intento = ++_intentoViaje;
    bool vigente() => mounted && navigating && intento == _intentoViaje;
    void aviso(String texto) {
      if (!vigente()) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(texto)));
    }

    // Si el usuario no ha elegido cómo compartir su ubicación, se le pregunta.
    if (preferencia == null || !preferencia!.activa) {
      await cambiarUbicacion(avisar: false);
      if (!vigente()) return;
    }
    if (!await activarUbicacion(avisar: false)) {
      if (!vigente()) return;
      avisarPermiso(
        permiso ?? ResultadoPermiso.denegado,
        texto: 'Activa la ubicación para seguir la ruta en vivo: modo demo',
      );
      return;
    }
    if (!vigente()) return;
    try {
      final nuevo = await api.crearViajeGps(
        trazado: ruta.trazadoLatLon,
        destino: ruta.paradas.last.nombre,
      );
      if (!vigente()) {
        unawaited(api.finalizarViaje(nuevo.id).catchError((_) {}));
        return;
      }
      setState(() => viaje = nuevo);
      // La última ubicación conocida va de inmediato, sin esperar a moverse.
      final ultima = miUbicacion;
      if (ultima != null) unawaited(enviarUbicacion(ultima));
      recentrar();
    } catch (_) {
      aviso('Sin conexión con el backend: modo demo');
    }
  }

  /// Envía una ubicación al backend. Si hay otra en camino, guarda solo la
  /// última y la envía al terminar, para no acumular pedidos atrasados.
  Future<void> enviarUbicacion(Posicion p) async {
    final actual = viaje;
    if (actual == null || !actual.activo) return;
    if (_enviandoUbicacion) {
      _ubicacionPendiente = p;
      return;
    }
    _enviandoUbicacion = true;
    try {
      final nuevo = await api.enviarUbicacion(actual.id, p);
      if (mounted && viaje?.id == actual.id) setState(() => viaje = nuevo);
    } catch (_) {
      // Se reintenta con la próxima ubicación.
    } finally {
      _enviandoUbicacion = false;
      final siguiente = _ubicacionPendiente;
      _ubicacionPendiente = null;
      if (siguiente != null) unawaited(enviarUbicacion(siguiente));
    }
  }

  /// Abre la pantalla «Proponer ruta». Si hay un recorrido en curso lo termina
  /// primero. La ruta que devuelve se agrega al selector y queda elegida.
  Future<void> proponerRuta() async {
    if (navigating) await alternarRecorrido();
    if (!mounted) return;
    final nueva = await Navigator.push<RutaPropuesta>(
      context,
      MaterialPageRoute(
        builder: (_) => ProponerRutaPage(
          buscador: widget.buscador,
          enrutador: widget.enrutador,
          constructorMapa: widget.constructorMapa,
          origen: miUbicacion == null
              ? null
              : Lugar(
                  'Mi ubicación',
                  miUbicacion!.punto,
                  detalle: preferencia?.exacta == true
                      ? ''
                      : 'aproximada, ${preferencia?.etiqueta ?? ''}',
                ),
          posicion: marcadorUsuario,
        ),
      ),
    );
    if (nueva == null || !mounted) return;
    setState(() {
      propuestas.add(nueva);
      route = primeraPropuesta + propuestas.length - 1;
    });
    recentrar(); // muestra la ruta nueva completa
  }

  @override
  void dispose() {
    // Al salir, detiene el reloj y retira el vehículo si quedaba un viaje activo.
    timer.cancel();
    _detenerUbicacion();
    final actual = viaje;
    if (actual != null && actual.activo) {
      unawaited(api.finalizarViaje(actual.id).catchError((_) {}));
    }
    super.dispose();
  }

  /// Encuadra la vista como un teléfono: hasta 430 px de ancho y un alto mínimo
  /// de 640 px. En pantallas anchas (Chrome de escritorio) se centra con bordes
  /// redondeados.
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: LayoutBuilder(
        builder: (context, viewport) {
          final framed = viewport.maxWidth > 500;
          final availableHeight = math.max(
            1.0,
            viewport.maxHeight - (framed ? 32 : 0),
          );
          final height = math.min(availableHeight, 900.0);
          final width = math.min(viewport.maxWidth, 430.0);
          // En ventanas bajas, FittedBox escala toda la vista para que no haya scroll.
          return Center(
            child: FittedBox(
              fit: BoxFit.contain,
              child: SizedBox(
                width: width,
                height: math.max(height, 640.0),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(framed ? 28 : 0),
                  child: drivingView(width, math.max(height, 640.0)),
                ),
              ),
            ),
          );
        },
      ),
    ),
  );

  /// Vista completa, en capas de abajo hacia arriba: escena de la ciudad
  /// (conducción o desde arriba), degradado para que se lea el texto, encabezado,
  /// semáforo, indicación de la ruta, selector de cámara, paneles laterales y
  /// controles de recorrido.
  Widget drivingView(double width, double height) {
    final panelWidth = (width * .36).clamp(112.0, 150.0);
    final sideTop = (height * .34).clamp(246.0, 300.0);
    return Stack(
      key: const Key('driving-view'),
      fit: StackFit.expand,
      children: [
        Semantics(
          label: overhead
              ? 'Mapa de la ciudad visto desde arriba, con tu ruta.'
              : 'Mapa de la ciudad en 3D, siguiendo tu ruta.',
          child: mapaPrincipal(),
        ),
        const IgnorePointer(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xE611151D),
                  Color(0x0011151D),
                  Color(0x0011151D),
                  Color(0xF011151D),
                ],
                stops: [0, .28, .70, 1],
              ),
            ),
          ),
        ),
        Positioned(
          top: 16,
          left: 18,
          right: 18,
          child: Row(
            children: [
              const Icon(Icons.alt_route_rounded, color: yellow, size: 24),
              const SizedBox(width: 6),
              const Text(
                'vía',
                style: TextStyle(
                  fontSize: 25,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -1,
                ),
              ),
              Expanded(
                child: Align(
                  alignment: Alignment.centerRight,
                  child: indicadorUbicacion(),
                ),
              ),
              const SizedBox(width: 9),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                decoration: BoxDecoration(
                  color: yellow.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  enVivo ? 'EN VIVO' : 'DEMO',
                  key: const Key('mode-chip'),
                  style: const TextStyle(
                    fontSize: 8,
                    color: yellow,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ],
          ),
        ),
        Positioned(top: 62, left: 16, right: 16, child: trafficLight()),
        Positioned(
          top: 157,
          left: 16,
          right: 16,
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xC9181D25),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                enVivo
                    ? '↑  Hacia ${viaje!.destino}'
                    : propuesta != null
                    ? propuesta!.pasos.first.indicacion
                    : route == 0
                    ? '↑  Continúa por Av. Alameda'
                    : '↗  Hacia Parque Forestal',
                style: const TextStyle(color: yellow, fontSize: 11),
              ),
            ),
          ),
        ),
        Positioned(top: 196, left: 40, right: 40, child: viewSelector()),
        Positioned(
          top: sideTop,
          left: 10,
          width: panelWidth,
          child: fuelPanel(),
        ),
        Positioned(
          top: sideTop,
          right: 10,
          width: panelWidth,
          child: energyPanel(),
        ),
        Positioned(bottom: 16, left: 14, right: 14, child: routeControls()),
        Positioned(bottom: 156, right: 14, child: botonRecentrar()),
      ],
    );
  }

  /// Marcador del usuario en el mapa, con la zona si la ubicación es
  /// aproximada o imprecisa.
  MarcadorPosicion? get marcadorUsuario => miUbicacion == null
      ? null
      : MarcadorPosicion(
          miUbicacion!.punto,
          radioM: miUbicacion!.precisionM ?? 0,
        );

  static const _hexFase = ['#6BD5A0', '#F5CB45', '#FF7773'];

  /// Mapa navegable de fondo: la ruta elegida (propuesta o de la simulación)
  /// con sus paradas y semáforos (el próximo con su color actual) y el usuario
  /// o el vehículo simulado.
  Widget mapaPrincipal() {
    final ruta = rutaEnMapa;
    final proximo = semaforoVivo;
    SemaforoMapa? destacado;
    final semaforos = <SemaforoMapa>[
      for (final s in ruta?.semaforos ?? const <SemaforoEnRuta>[])
        if (s.punto != null) SemaforoMapa(s.id, s.punto!),
    ];
    if (proximo != null && proximo.id.isNotEmpty) {
      for (final s in semaforos) {
        if (s.id == proximo.id) destacado = s;
      }
    }
    final vehiculo = enVivo && !viaje!.esGps ? viaje!.posicion : null;
    final datos = DatosMapa(
      control: mapa,
      centro:
          miUbicacion?.punto ?? ruta?.paradas.first.punto ?? plazaDeArmas.punto,
      paradas: [
        if (ruta != null)
          for (var i = 0; i < ruta.paradas.length; i++)
            ParadaMapa(
              ruta.paradas[i].punto,
              i == 0 ? 'A' : (i == ruta.paradas.length - 1 ? 'B' : '$i'),
              extremo: i == 0 || i == ruta.paradas.length - 1,
            ),
      ],
      trazados: [?ruta?.trazado],
      elegida: 0,
      paleta: ProponerRutaPageEstado.ultimaPaleta,
      alTocar: (_) {},
      semaforos: semaforos,
      posicion: vehiculo != null
          ? MarcadorPosicion(vehiculo, vehiculo: true)
          : marcadorUsuario,
      proximo: destacado,
      colorProximo: fase < 0 ? '#8A909B' : _hexFase[fase],
      alInteractuar: dejarDeSeguir,
      zoom: 16,
      inclinacion: overhead ? 0 : MapaLowPoly.inclinacionConduccion,
      margenInferior: 160, // sobre el panel de recorrido
    );
    return KeyedSubtree(
      key: const Key('main-map'),
      child: (widget.constructorMapa ?? MapaLowPoly.new)(datos),
    );
  }

  /// Indicador del encabezado: cómo se comparte la ubicación. Tocarlo abre la
  /// hoja para cambiarlo.
  Widget indicadorUbicacion() {
    final pref = preferencia;
    final (icono, texto) = switch ((pref, permiso)) {
      (null, _) => (Icons.location_searching_rounded, 'Ubicación'),
      (final p?, _) when !p.activa => (Icons.location_off_outlined, 'Sin ubicación'),
      (_, final r?) when !r.concedido => (Icons.location_disabled_outlined, 'Sin permiso'),
      (_, ResultadoPermiso.soloAproximado) => (
        Icons.blur_circular_rounded,
        '≈ ${PreferenciaUbicacion.textoRango(math.max(pref!.rangoM, rangoSistemaAproximadoM))}',
      ),
      (final p?, _) => (
        p.exacta ? Icons.gps_fixed_rounded : Icons.blur_circular_rounded,
        p.etiqueta,
      ),
    };
    return Semantics(
      button: true,
      label: 'Ubicación: $texto. Toca para cambiarla.',
      child: InkWell(
        key: const Key('location-chip'),
        borderRadius: BorderRadius.circular(8),
        onTap: () => cambiarUbicacion(),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icono, color: subdued, size: 13),
              const SizedBox(width: 4),
              Flexible(
                child: Text(
                  texto,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: subdued, fontSize: 11),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Vuelve a centrar la cámara (ver [recentrar]). Relleno mientras sigue al
  /// usuario, de contorno cuando el usuario movió el mapa.
  Widget botonRecentrar() => Material(
    color: surface,
    shape: const CircleBorder(side: BorderSide(color: Color(0xFF454A53))),
    child: IconButton(
      key: const Key('recenter'),
      tooltip: 'Recentrar el mapa',
      onPressed: recentrar,
      icon: Icon(
        siguiendo ? Icons.my_location_rounded : Icons.location_searching_rounded,
        color: yellow,
        size: 20,
      ),
    ),
  );

  /// Estilo común de las tarjetas: fondo oscuro, borde y sombra suave.
  BoxDecoration cardDecoration({Color border = const Color(0xFF454A53)}) =>
      BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: border),
        boxShadow: const [
          BoxShadow(
            color: Color(0x33000000),
            blurRadius: 18,
            offset: Offset(0, 6),
          ),
        ],
      );

  /// Panel «Próximo semáforo»: luces, nombre del cruce, cambio que viene y
  /// segundos que faltan.
  Widget trafficLight() => Container(
    key: const Key('traffic-panel'),
    padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
    decoration: cardDecoration(border: signalColor.withValues(alpha: .35)),
    child: Row(
      children: [
        Container(
          padding: const EdgeInsets.all(5),
          decoration: BoxDecoration(
            color: const Color(0xFF0E1117),
            borderRadius: BorderRadius.circular(9),
          ),
          child: Column(
            children: List.generate(
              3,
              (i) => Container(
                width: 9,
                height: 9,
                margin: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: fase == [2, 1, 0][i]
                      ? signalColor
                      : const Color(0xFF343943),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'PRÓXIMO SEMÁFORO',
                style: TextStyle(
                  color: subdued,
                  fontSize: 8,
                  letterSpacing: .8,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                nombreSemaforo,
                key: const Key('traffic-name'),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                cambioSemaforo,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: signalColor, fontSize: 10),
              ),
            ],
          ),
        ),
        const SizedBox(width: 6),
        Column(
          children: [
            Text(
              textoSegundos,
              key: const Key('traffic-seconds'),
              style: TextStyle(
                color: signalColor,
                fontSize: 30,
                fontWeight: FontWeight.w700,
              ),
            ),
            Text(
              semaforoVivo?.exacto == false ? 'estimado' : 'para cambiar',
              style: const TextStyle(color: subdued, fontSize: 8),
            ),
          ],
        ),
      ],
    ),
  );

  /// Selector de cámara entre «Conducción» (vista trasera) y «Desde arriba».
  Widget viewSelector() => Container(
    key: const Key('view-selector'),
    padding: const EdgeInsets.all(3),
    decoration: cardDecoration(),
    child: Row(
      children: [
        for (final fromAbove in [false, true])
          Expanded(
            child: Semantics(
              selected: overhead == fromAbove,
              child: SizedBox(
                height: 36,
                child: TextButton.icon(
                  key: Key(fromAbove ? 'view-above' : 'view-driving'),
                  onPressed: () {
                    setState(() => overhead = fromAbove);
                    recentrar();
                  },
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    foregroundColor: overhead == fromAbove
                        ? const Color(0xFF161A21)
                        : subdued,
                    backgroundColor: overhead == fromAbove
                        ? yellow
                        : Colors.transparent,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  icon: Icon(
                    fromAbove
                        ? Icons.map_outlined
                        : Icons.directions_car_outlined,
                    size: 15,
                  ),
                  label: Text(
                    fromAbove ? 'Desde arriba' : 'Conducción',
                    style: const TextStyle(fontSize: 10),
                  ),
                ),
              ),
            ),
          ),
      ],
    ),
  );

  /// Tarjeta desplegable reutilizable. Solo una puede estar abierta a la vez:
  /// [expandedPanel] guarda el [id] de la abierta y tocarla la abre o la cierra.
  Widget expandablePanel({
    required String id,
    required IconData icon,
    required String title,
    required String value,
    required Widget details,
  }) {
    final expanded = expandedPanel == id;
    return Container(
      key: Key('$id-panel'),
      decoration: cardDecoration(),
      child: AnimatedSize(
        duration: const Duration(milliseconds: 180),
        alignment: Alignment.topCenter,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              button: true,
              expanded: expanded,
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  key: Key('$id-toggle'),
                  borderRadius: BorderRadius.circular(16),
                  onTap: () =>
                      setState(() => expandedPanel = expanded ? null : id),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 12,
                    ),
                    child: Row(
                      children: [
                        Icon(icon, size: 18, color: yellow),
                        const SizedBox(width: 7),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              FittedBox(
                                fit: BoxFit.scaleDown,
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  title,
                                  style: const TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 4),
                              FittedBox(
                                fit: BoxFit.scaleDown,
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  value,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    color: yellow,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 3),
                        Icon(
                          expanded ? Icons.expand_less : Icons.expand_more,
                          size: 14,
                          color: subdued,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            if (expanded)
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                child: details,
              ),
          ],
        ),
      ),
    );
  }

  /// Panel de gasolina: elige 93, 95 o 97 octanos. Es informativo; el octanaje
  /// no cambia el consumo calculado.
  Widget fuelPanel() => expandablePanel(
    id: 'fuel',
    icon: Icons.local_gas_station_outlined,
    title: 'Gasolina',
    value: '$octane oct.',
    details: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final value in [93, 95, 97])
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: SizedBox(
              height: 36,
              child: OutlinedButton(
                key: Key('octane-$value'),
                onPressed: () => setState(() {
                  octane = value;
                  expandedPanel = null;
                }),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  foregroundColor: octane == value ? yellow : subdued,
                  backgroundColor: octane == value
                      ? yellow.withValues(alpha: .12)
                      : Colors.transparent,
                  side: BorderSide(
                    color: octane == value ? yellow : const Color(0xFF454A53),
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: Semantics(
                  selected: octane == value,
                  label: 'Gasolina $value octanos',
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('$value', style: const TextStyle(fontSize: 14)),
                      Icon(
                        octane == value
                            ? Icons.check_circle
                            : Icons.circle_outlined,
                        size: 12,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    ),
  );

  /// Panel de gasto energético: litros estimados, distancia, equivalente en kWh
  /// (8,9 kWh/L, supuesto ilustrativo) y consumo de referencia ajustable.
  Widget energyPanel() => expandablePanel(
    id: 'energy',
    icon: Icons.bolt_rounded,
    title: 'Gasto energético',
    value: '${liters.toStringAsFixed(2)} L',
    details: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(height: 8, color: Color(0xFF454A53)),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            '${distance.toStringAsFixed(1)} km de ruta',
            style: const TextStyle(fontSize: 9, color: subdued),
          ),
        ),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            '≈ ${(liters * 8.9).toStringAsFixed(2)} kWh',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ),
        const Text(
          'Equivalente',
          style: TextStyle(fontSize: 8, color: subdued),
        ),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            '${efficiency.toStringAsFixed(1)} L/100 km',
            style: const TextStyle(fontSize: 9, color: subdued),
          ),
        ),
        const SizedBox(height: 7),
        SizedBox(
          width: double.infinity,
          height: 33,
          child: OutlinedButton(
            key: const Key('adjust-consumption'),
            style: OutlinedButton.styleFrom(
              padding: EdgeInsets.zero,
              side: const BorderSide(color: Color(0xFF454A53)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onPressed: adjustConsumption,
            child: const Text('Ajustar', style: TextStyle(fontSize: 10)),
          ),
        ),
      ],
    ),
  );

  /// Hoja inferior para ajustar el consumo del vehículo (4 a 14 L/100 km).
  /// `updateSheet` redibuja la hoja y `setState` actualiza la pantalla de fondo.
  Future<void> adjustConsumption() async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF20242C),
      constraints: const BoxConstraints(maxWidth: 430),
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, updateSheet) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Consumo de tu vehículo',
                  style: TextStyle(fontSize: 19, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                Text(
                  '${efficiency.toStringAsFixed(1)} L / 100 km',
                  style: const TextStyle(color: yellow, fontSize: 24),
                ),
                Slider(
                  key: const Key('efficiency-slider'),
                  value: efficiency,
                  min: 4,
                  max: 14,
                  divisions: 20,
                  label: '${efficiency.toStringAsFixed(1)} L/100 km',
                  onChanged: (value) {
                    setState(() => efficiency = value);
                    updateSheet(() {});
                  },
                ),
                const Text(
                  'Estimación por distancia y consumo. El octanaje no cambia el rendimiento. Equivalencia ilustrativa: 8,9 kWh/L.',
                  style: TextStyle(fontSize: 12, color: subdued, height: 1.5),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () => Navigator.pop(sheetContext),
                    child: const Text('Listo'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Controles inferiores: selector de recorrido (destinos demo o de la
  /// simulación, más las rutas propuestas marcadas con ★), botón para proponer
  /// una ruta, tiempo estimado y botón Iniciar / Finalizar.
  Widget routeControls() => Container(
    key: const Key('route-controls'),
    padding: const EdgeInsets.all(12),
    decoration: cardDecoration(),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            const Icon(Icons.near_me_outlined, color: yellow, size: 19),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  key: const Key('route-selector'),
                  value: route,
                  isExpanded: true,
                  isDense: true,
                  dropdownColor: const Color(0xFF20242C),
                  style: const TextStyle(fontSize: 12, color: Colors.white),
                  items: [
                    if (destinos != null)
                      for (final d in destinos!)
                        DropdownMenuItem(
                          value: d.ruta,
                          child: Text(
                            '${d.nombre} · ${d.distanciaKm.toStringAsFixed(1).replaceAll('.', ',')} km',
                          ),
                        )
                    else ...const [
                      DropdownMenuItem(
                        value: 0,
                        child: Text('Bustamante · 4,8 km'),
                      ),
                      DropdownMenuItem(
                        value: 1,
                        child: Text('Forestal · 6,2 km'),
                      ),
                    ],
                    for (var i = 0; i < propuestas.length; i++)
                      DropdownMenuItem(
                        value: primeraPropuesta + i,
                        child: Text(
                          '★ ${propuestas[i].nombre} · ${propuestas[i].distanciaKm.toStringAsFixed(1).replaceAll('.', ',')} km',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) {
                    if (navigating) alternarRecorrido();
                    setState(() => route = value!);
                    recentrar();
                  },
                ),
              ),
            ),
            IconButton(
              key: const Key('propose-route'),
              tooltip: 'Proponer ruta',
              onPressed: proponerRuta,
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints.tightFor(width: 32, height: 28),
              icon: const Icon(Icons.add_road_rounded, color: yellow, size: 19),
            ),
          ],
        ),
        const SizedBox(height: 7),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            navigating
                ? (!enVivo
                      ? 'Recorrido en curso · Demo'
                      : viaje!.esGps
                      ? 'Recorrido en curso · GPS en vivo'
                      : 'Recorrido en curso · Simulación en vivo')
                : propuesta != null
                ? 'Desde ${propuesta!.paradas.first.nombre} · ${propuesta!.duracionMin.round()} min'
                : 'Desde Plaza de Armas · ${(distance * 2.5).round()} min',
            style: const TextStyle(fontSize: 10, color: subdued),
          ),
        ),
        const SizedBox(height: 9),
        SizedBox(
          width: double.infinity,
          height: 42,
          child: FilledButton.icon(
            onPressed: alternarRecorrido,
            style: FilledButton.styleFrom(
              backgroundColor: yellow,
              foregroundColor: const Color(0xFF161A21),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            icon: Icon(
              navigating
                  ? Icons.stop_circle_outlined
                  : Icons.navigation_outlined,
              size: 17,
            ),
            label: Text(
              navigating ? 'Finalizar recorrido' : 'Iniciar recorrido',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
        ),
      ],
    ),
  );
}
