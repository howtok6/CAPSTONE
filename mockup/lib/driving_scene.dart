import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Procedural block city seen from behind the vehicle. No external map assets.
class DrivingScenePainter extends CustomPainter {
  const DrivingScenePainter({required this.alternate});
  final bool alternate;
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final horizon = h * .26;
    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF161C29), Color(0xFF444447)],
        ).createShader(Offset.zero & size),
    );
    void poly(List<Offset> points, Color color) => canvas.drawPath(
      Path()..addPolygon(points, true),
      Paint()..color = color,
    );
    Offset p(double x, double depth, [double height = 0]) {
      final scale = 1 / (1 + depth * .55);
      return Offset(
        w / 2 + x * w * scale,
        horizon + (h - horizon) * scale - height * h * scale,
      );
    }

    // Distant silhouette and the roadway converge toward the same horizon.
    final random = math.Random(9);
    for (int i = 0; i < 24; i++) {
      final bh = 10 + random.nextDouble() * 40;
      canvas.drawRect(
        Rect.fromLTWH(i * w / 24, horizon - bh, w / 24 - 2, bh + 20),
        Paint()..color = const Color(0xFF30343E),
      );
    }
    poly([p(-2, 0), p(-2, 50), p(2, 50), p(2, 0)], const Color(0xFF36383D));
    poly([
      p(-.29, 0),
      p(-.29, 50),
      p(.29, 50),
      p(.29, 0),
    ], const Color(0xFF22252C));
    for (final side in [-1.0, 1.0]) {
      poly([
        p(side * .29, 0),
        p(side * .29, 50),
        p(side * .33, 50),
        p(side * .33, 0),
      ], const Color(0xFF66676A));
      canvas.drawLine(
        p(side * .275, 0),
        p(side * .275, 40),
        Paint()
          ..color = const Color(0xFFBEA75E)
          ..strokeWidth = 1.5,
      );
    }
    for (int i = 0; i < 18; i++) {
      final z = i * 1.0 + .3;
      poly([
        p(-.007, z),
        p(-.007, z + .45),
        p(.007, z + .45),
        p(.007, z),
      ], const Color(0xFF96968E));
    }
    // Render far buildings before near ones, including visible side and roof faces.
    for (int i = 10; i >= 0; i--) {
      for (final side in [-1.0, 1.0]) {
        final z = 1.0 + i * 1.5;
        final x = side * (.36 + (i % 3) * .025);
        final outer = x + side * (.23 + (i % 2) * .1);
        final height = i % 3 == 0 ? .18 : .33 + (i % 4) * .10;
        final a = p(x, z), b = p(outer, z), d = p(x, z + 1);
        final at = p(x, z, height),
            bt = p(outer, z, height),
            ct = p(outer, z + 1, height),
            dt = p(x, z + 1, height);
        poly([a, b, bt, at], const Color(0xFF484D58));
        poly([a, d, dt, at], const Color(0xFF363D48));
        poly([at, bt, ct, dt], const Color(0xFF626773));
        // Small lit windows on the street-facing wall.
        for (int floor = 1; floor <= (height / .07).floor(); floor++) {
          for (int col = 0; col < 3; col++) {
            final wz = z + .15 + col * .25;
            final wh = floor * .06;
            poly(
              [
                p(x, wz, wh),
                p(x, wz + .10, wh),
                p(x, wz + .10, wh + .024),
                p(x, wz, wh + .024),
              ],
              (floor + col + i) % 3 == 0
                  ? const Color(0xFFBBA46B)
                  : const Color(0xFF69717B),
            );
          }
        }
        if (i % 3 == 0) {
          final ridge = p((x + outer) / 2, z, height + .07);
          poly([at, bt, ridge], const Color(0xFF74716A));
          poly([
            ridge,
            bt,
            ct,
            p((x + outer) / 2, z + 1, height + .07),
          ], const Color(0xFF54565D));
        }
        // Sidewalk lamps.
        final base = p(side * .32, z + .9), top = p(side * .32, z + .9, .18);
        canvas.drawLine(
          base,
          top,
          Paint()
            ..color = const Color(0xFF858A90)
            ..strokeWidth = 2,
        );
        canvas.drawCircle(top, 2.5, Paint()..color = const Color(0xFFFFDF84));
      }
    }
    final route = Path()
      ..moveTo(w * .5, h * .78)
      ..lineTo(w * .5, h * .52);
    if (alternate) {
      route.lineTo(w * .58, h * .43);
    } else {
      route.lineTo(w * .5, h * .40);
    }
    canvas.drawPath(
      route,
      Paint()
        ..color = const Color(0x33F5CB45)
        ..strokeWidth = 18
        ..style = PaintingStyle.stroke,
    );
    canvas.drawPath(
      route,
      Paint()
        ..color = const Color(0xFFF5CB45)
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke,
    );
    final arrow = alternate
        ? Offset(w * .58, h * .43)
        : Offset(w * .5, h * .40);
    poly([
      arrow + const Offset(0, -7),
      arrow + const Offset(-6, 5),
      arrow + const Offset(6, 5),
    ], const Color(0xFFF5CB45));
    // Rear view of the car, scaled independently to remain legible on phones.
    canvas.save();
    canvas.translate(w / 2, h < 700 ? h * .67 : h * .72);
    final carScale = math.min(w / 350, 1.25);
    canvas.scale(carScale);
    canvas.drawOval(
      const Rect.fromLTWH(-66, 23, 132, 26),
      Paint()..color = const Color(0x88000000),
    );
    void round(Rect rect, double radius, Color color) => canvas.drawRRect(
      RRect.fromRectAndRadius(rect, Radius.circular(radius)),
      Paint()..color = color,
    );
    round(const Rect.fromLTWH(-57, -2, 15, 43), 5, const Color(0xFF0A0C10));
    round(const Rect.fromLTWH(42, -2, 15, 43), 5, const Color(0xFF0A0C10));
    poly([
      const Offset(-46, 1),
      const Offset(-33, -39),
      const Offset(-22, -46),
      const Offset(25, -46),
      const Offset(36, -36),
      const Offset(47, 1),
    ], const Color(0xFFDAB33C));
    poly([
      const Offset(-29, -34),
      const Offset(28, -34),
      const Offset(36, -12),
      const Offset(-36, -12),
    ], const Color(0xFF26313C));
    canvas.drawLine(
      const Offset(-23, -30),
      const Offset(24, -30),
      Paint()
        ..color = const Color(0xFF69727D)
        ..strokeWidth = 2,
    );
    round(const Rect.fromLTWH(-51, -7, 102, 43), 9, const Color(0xFFF5CB45));
    round(const Rect.fromLTWH(-46, 5, 23, 7), 2, const Color(0xFFFF6D5E));
    round(const Rect.fromLTWH(23, 5, 23, 7), 2, const Color(0xFFFF6D5E));
    round(const Rect.fromLTWH(-19, 17, 38, 12), 2, const Color(0xFFE7E8DC));
    round(const Rect.fromLTWH(-46, 31, 92, 6), 2, const Color(0xFF34363B));
    round(const Rect.fromLTWH(-61, -9, 12, 8), 3, const Color(0xFFE8BB3D));
    round(const Rect.fromLTWH(49, -9, 12, 8), 3, const Color(0xFFE8BB3D));
    canvas.restore();
  }

  @override
  bool shouldRepaint(DrivingScenePainter oldDelegate) =>
      oldDelegate.alternate != alternate;
}
