import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockup/main.dart';

void main() {
  for (final size in [
    const Size(320, 568),
    const Size(360, 640),
    const Size(390, 844),
    const Size(1440, 1000),
  ]) {
    testWidgets('All driving controls stay inside the phone view at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MyApp());
      final scene = tester.getRect(find.byKey(const Key('driving-view')));
      for (final key in [
        'traffic-panel',
        'fuel-panel',
        'energy-panel',
        'route-controls',
        'view-selector',
      ]) {
        final rect = tester.getRect(find.byKey(Key(key)));
        expect(
          scene.contains(rect.topLeft),
          isTrue,
          reason: '$key must be inside scene',
        );
        expect(
          scene.contains(rect.bottomRight),
          isTrue,
          reason: '$key must be inside scene',
        );
      }
      final fuel = tester.getRect(find.byKey(const Key('fuel-panel')));
      final energy = tester.getRect(find.byKey(const Key('energy-panel')));
      final signal = tester.getRect(find.byKey(const Key('traffic-panel')));
      final controls = tester.getRect(find.byKey(const Key('route-controls')));
      expect(fuel.right, lessThan(energy.left));
      expect(signal.bottom, lessThan(fuel.top));
      expect(fuel.bottom, lessThan(controls.top));
      expect(energy.bottom, lessThan(controls.top));
      expect(scene.width, lessThanOrEqualTo(430));
      expect(find.byType(SingleChildScrollView), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    });
  }

  testWidgets('Mobile fuel, route, consumption and traffic controls work', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const MyApp());
    expect(find.text('0.36 L'), findsOneWidget);
    expect(find.byKey(const Key('octane-97')), findsNothing);
    await tester.tap(find.byKey(const Key('fuel-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('octane-97')));
    await tester.pumpAndSettle();
    expect(find.text('97 oct.'), findsOneWidget);
    expect(find.byKey(const Key('octane-97')), findsNothing);
    expect(find.text('0.36 L'), findsOneWidget);
    await tester.tap(find.byKey(const Key('route-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Forestal · 6,2 km').last);
    await tester.pumpAndSettle();
    expect(find.text('0.47 L'), findsOneWidget);
    await tester.tap(find.byKey(const Key('energy-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('adjust-consumption')));
    await tester.pumpAndSettle();
    await tester.drag(
      find.byKey(const Key('efficiency-slider')),
      const Offset(60, 0),
    );
    await tester.pump();
    await tester.tap(find.text('Listo'));
    await tester.pumpAndSettle();
    expect(find.text('0.47 L'), findsNothing);
    await tester.tap(find.text('Iniciar recorrido'));
    await tester.pump();
    expect(find.text('Recorrido en curso · Demo'), findsOneWidget);
    await tester.tap(find.text('Finalizar recorrido'));
    await tester.pump();
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'Camera switching preserves route and expandable controls on small phones',
    (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MyApp());
      expect(find.byKey(const Key('rear-scene')), findsOneWidget);
      await tester.tap(find.byKey(const Key('view-above')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('overhead-scene')), findsOneWidget);
      await tester.tap(find.byKey(const Key('fuel-toggle')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('octane-93')), findsOneWidget);
      final controls = tester.getRect(find.byKey(const Key('route-controls')));
      expect(
        tester.getRect(find.byKey(const Key('fuel-panel'))).bottom,
        lessThan(controls.top),
      );
      await tester.tap(find.byKey(const Key('energy-toggle')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('octane-93')), findsNothing);
      expect(find.text('Equivalente'), findsOneWidget);
      expect(
        tester.getRect(find.byKey(const Key('energy-panel'))).bottom,
        lessThan(controls.top),
      );
      await tester.tap(find.byKey(const Key('view-driving')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('rear-scene')), findsOneWidget);
      expect(find.text('0.36 L'), findsOneWidget);
      await tester.tap(find.byKey(const Key('energy-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Equivalente'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets('Traffic light cycles through all colors', (tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('24s'), findsOneWidget);
    await tester.pump(const Duration(seconds: 24));
    expect(find.text('Amarillo → rojo'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    expect(find.text('Rojo → verde'), findsOneWidget);
    await tester.pump(const Duration(seconds: 25));
    expect(find.text('Verde → amarillo'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
