// Pantalla principal de «Vía»: vista de conducción con semáforo, paneles de
// gasolina y gasto energético, y controles de recorrido.
//
// La pantalla funciona en tres modos según de dónde salen los datos:
// - Demo: semáforo, rutas y distancias simuladas dentro de la app.
// - En vivo: semáforo y destinos desde la simulación SUMO (lib/via_api.dart).
// - Ruta propuesta: ruta real de OpenStreetMap elegida por el usuario
//   (lib/rutas_osm.dart y lib/proponer_ruta.dart); se recorre en demo.

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'driving_scene.dart';
import 'overhead_scene.dart';
import 'proponer_ruta.dart';
import 'rutas_osm.dart';
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
  const MobilityPage({super.key, this.api, this.buscador, this.enrutador});

  /// Cliente de la API de simulación; null usa la URL configurada (API_URL).
  final ViaApi? api;

  /// Servicios de OpenStreetMap para proponer rutas; null usa los públicos.
  final BuscadorLugares? buscador;
  final Enrutador? enrutador;
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

  // --- Simulación en vivo (tsc-thesis/api) ---------------------------------
  late final ViaApi api = widget.api ?? ViaApi();
  List<Destino>? destinos; // null = API no disponible → modo demo
  EstadoViaje? viaje;
  bool consultando = false;
  bool get enVivo => viaje != null;
  ProximoSemaforo? get semaforoVivo => viaje?.semaforo;

  // --- Rutas propuestas por el usuario (OpenStreetMap) ----------------------
  // Usan valores del selector desde [primeraPropuesta] para no chocar con los
  // índices de la simulación. No existen en la red SUMO: se recorren en demo.
  static const primeraPropuesta = 100;
  final propuestas = <RutaPropuesta>[];
  RutaPropuesta? get propuesta =>
      route >= primeraPropuesta ? propuestas[route - primeraPropuesta] : null;

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

  /// Fase y segundos que muestra el semáforo: los de la simulación si hay un
  /// semáforo en vivo; si no, los del ciclo demo.
  int get fase =>
      semaforoVivo != null ? (_colores[semaforoVivo!.color] ?? 2) : phase;
  int get segundos =>
      semaforoVivo != null ? (semaforoVivo!.segundos ?? 0) : seconds;

  /// Color del panel del semáforo según la fase: verde, amarillo o rojo.
  Color get signalColor =>
      [const Color(0xFF6BD5A0), yellow, const Color(0xFFFF7773)][fase];

  /// Título del panel del semáforo: el cruce en vivo, o un mensaje según el
  /// estado del recorrido (entrando a la vía, llegada, reinicio).
  String get nombreSemaforo {
    if (viaje == null) return 'Av. Alameda';
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
      return enVivo
          ? 'Simulación en vivo'
          : ['Verde → amarillo', 'Amarillo → rojo', 'Rojo → verde'][phase];
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
  }

  /// Pide los destinos a la simulación. Si responde, el selector muestra sus
  /// destinos y los recorridos pueden ir en vivo; si falla, la app sigue en demo.
  Future<void> cargarDestinos() async {
    try {
      final lista = await api.destinos();
      if (mounted && lista.isNotEmpty) setState(() => destinos = lista);
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
      if (mounted && viaje?.id == actual.id) setState(() => viaje = nuevo);
    } catch (_) {
      // Se reintenta en el siguiente segundo.
    } finally {
      consultando = false;
    }
  }

  /// Acción del botón Iniciar / Finalizar recorrido.
  ///
  /// Al finalizar, retira el vehículo de la simulación sin esperar respuesta.
  /// Al iniciar, crea un viaje en vivo solo si la API está disponible y la ruta
  /// es de la simulación; las rutas demo y las propuestas se recorren en demo.
  Future<void> alternarRecorrido() async {
    if (navigating) {
      final actual = viaje;
      setState(() {
        navigating = false;
        viaje = null;
      });
      if (actual != null) {
        unawaited(api.finalizarViaje(actual.id).catchError((_) {}));
      }
      return;
    }
    setState(() => navigating = true);
    if (destinos == null || propuesta != null) return; // modo demo
    try {
      final nuevo = await api.crearViaje(route);
      if (mounted && navigating) setState(() => viaje = nuevo);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Sin conexión con la simulación: modo demo'),
        ),
      );
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
        ),
      ),
    );
    if (nueva == null || !mounted) return;
    setState(() {
      propuestas.add(nueva);
      route = primeraPropuesta + propuestas.length - 1;
    });
  }

  @override
  void dispose() {
    // Al salir, detiene el reloj y retira el vehículo si quedaba un viaje activo.
    timer.cancel();
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
              ? 'Vista desde arriba de la ciudad, con el auto y la ruta marcada.'
              : 'Auto amarillo al centro de una calle con casas y edificios a ambos lados.',
          child: CustomPaint(
            key: ValueKey(overhead ? 'overhead-scene' : 'rear-scene'),
            painter: overhead
                ? OverheadScenePainter(alternate: route == 1)
                : DrivingScenePainter(alternate: route == 1),
          ),
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
              const Spacer(),
              const Icon(Icons.location_on_outlined, color: subdued, size: 13),
              const SizedBox(width: 4),
              const Text(
                'Santiago',
                style: TextStyle(color: subdued, fontSize: 11),
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
      ],
    );
  }

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
              semaforoVivo != null && semaforoVivo!.segundos == null
                  ? '—'
                  : '${segundos}s',
              key: const Key('traffic-seconds'),
              style: TextStyle(
                color: signalColor,
                fontSize: 30,
                fontWeight: FontWeight.w700,
              ),
            ),
            const Text(
              'para cambiar',
              style: TextStyle(color: subdued, fontSize: 8),
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
                  onPressed: () => setState(() => overhead = fromAbove),
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
                ? (enVivo
                      ? 'Recorrido en curso · Simulación en vivo'
                      : 'Recorrido en curso · Demo')
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
