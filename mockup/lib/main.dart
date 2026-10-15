import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'driving_scene.dart';
import 'overhead_scene.dart';

const yellow = Color(0xFFF5CB45);
const surface = Color(0xF01C2027);
const subdued = Color(0xFFB1B6C0);
void main() => runApp(const MyApp());

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

class MobilityPage extends StatefulWidget {
  const MobilityPage({super.key});
  @override
  State<MobilityPage> createState() => _MobilityPageState();
}

class _MobilityPageState extends State<MobilityPage> {
  int octane = 95, route = 0, phase = 0, seconds = 24;
  double efficiency = 7.5;
  bool navigating = false;
  bool overhead = false;
  String? expandedPanel;
  late final Timer timer;
  double get distance => route == 0 ? 4.8 : 6.2;
  double get liters => distance * efficiency / 100;
  Color get signalColor =>
      [const Color(0xFF6BD5A0), yellow, const Color(0xFFFF7773)][phase];

  @override
  void initState() {
    super.initState();
    timer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => setState(() {
        if (seconds > 1) {
          seconds--;
        } else {
          phase = (phase + 1) % 3;
          seconds = [30, 5, 25][phase];
        }
      }),
    );
  }

  @override
  void dispose() {
    timer.cancel();
    super.dispose();
  }

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
          // Short browser windows fit the whole portrait canvas without scrolling.
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
                child: const Text(
                  'DEMO',
                  style: TextStyle(
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
                route == 0
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
                  color: phase == [2, 1, 0][i]
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
              const Text(
                'Av. Alameda',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 3),
              Text(
                ['Verde → amarillo', 'Amarillo → rojo', 'Rojo → verde'][phase],
                style: TextStyle(color: signalColor, fontSize: 10),
              ),
            ],
          ),
        ),
        const SizedBox(width: 6),
        Column(
          children: [
            Text(
              '${seconds}s',
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
                  items: const [
                    DropdownMenuItem(
                      value: 0,
                      child: Text('Bustamante · 4,8 km'),
                    ),
                    DropdownMenuItem(
                      value: 1,
                      child: Text('Forestal · 6,2 km'),
                    ),
                  ],
                  onChanged: (value) => setState(() {
                    route = value!;
                    navigating = false;
                  }),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            navigating
                ? 'Recorrido en curso · Demo'
                : 'Desde Plaza de Armas · ${(distance * 2.5).round()} min',
            style: const TextStyle(fontSize: 10, color: subdued),
          ),
        ),
        const SizedBox(height: 9),
        SizedBox(
          width: double.infinity,
          height: 42,
          child: FilledButton.icon(
            onPressed: () => setState(() => navigating = !navigating),
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
