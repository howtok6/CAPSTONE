import 'package:flutter/material.dart';

/// Conceptual city plan sharing the vehicle and route with the rear view.
class OverheadScenePainter extends CustomPainter {
  const OverheadScenePainter({required this.alternate});
  final bool alternate;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final center = w / 2;
    final roadWidth = w * .24;
    final crossing = h * .45;
    final carY = h < 700 ? h * .67 : h * .72;
    const asphalt = Color(0xFF20262E);
    const yellow = Color(0xFFF5CB45);

    void rect(Rect bounds, Color color, [double radius = 0]) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(bounds, Radius.circular(radius)),
        Paint()..color = color,
      );
    }

    rect(Offset.zero & size, const Color(0xFF343C43));
    // Pavements, main avenue and two intersecting streets.
    rect(
      Rect.fromLTWH(center - roadWidth / 2 - 8, 0, roadWidth + 16, h),
      const Color(0xFF737771),
    );
    rect(Rect.fromLTWH(center - roadWidth / 2, 0, roadWidth, h), asphalt);
    for (final y in [crossing, crossing - h * .27]) {
      rect(Rect.fromLTWH(0, y - 31, w, 62), const Color(0xFF737771));
      rect(Rect.fromLTWH(0, y - 24, w, 48), asphalt);
      for (double x = 8; x < w; x += 24) {
        if ((x - center).abs() > roadWidth / 2) {
          rect(Rect.fromLTWH(x, y - 1, 11, 2), const Color(0xFF92968C));
        }
      }
    }
    for (double y = 0; y < h; y += 26) {
      if ((y - crossing).abs() > 34 && (y - crossing + h * .27).abs() > 34) {
        rect(Rect.fromLTWH(center - 1, y, 2, 12), const Color(0xFFA2A395));
      }
    }

    // Roof blocks and small planted courtyards on both sides of the avenue.
    final blockWidth = (w - roadWidth) / 2 - 27;
    for (int row = 0; row < 9; row++) {
      final y = 28 + row * h / 8;
      if ((y + 26 - crossing).abs() < 65 ||
          (y + 26 - crossing + h * .27).abs() < 65) {
        continue;
      }
      for (final right in [false, true]) {
        final x = right ? center + roadWidth / 2 + 17 : 10.0;
        if (row % 4 == 2) {
          rect(Rect.fromLTWH(x, y, blockWidth, 65), const Color(0xFF3C4C42), 7);
          for (int tree = 0; tree < 3; tree++) {
            final point = Offset(
              x + 15 + tree * (blockWidth - 30) / 2,
              y + 24 + (tree % 2) * 20,
            );
            canvas.drawCircle(
              point + const Offset(3, 3),
              9,
              Paint()..color = const Color(0xFF293A32),
            );
            canvas.drawCircle(
              point,
              8,
              Paint()..color = const Color(0xFF637663),
            );
          }
        } else {
          final bounds = Rect.fromLTWH(x, y, blockWidth, row.isEven ? 58 : 70);
          rect(bounds.shift(const Offset(5, 6)), const Color(0xFF242C33), 3);
          rect(bounds, const Color(0xFF555F6A), 3);
          rect(bounds.deflate(5), const Color(0xFF68727A), 2);
          rect(
            Rect.fromLTWH(x + 12, y + 12, blockWidth * .35, 16),
            const Color(0xFF444F5A),
            2,
          );
          canvas.drawLine(
            Offset(x + 7, y + 36),
            Offset(x + blockWidth - 7, y + 36),
            Paint()
              ..color = const Color(0xFF899087)
              ..strokeWidth = 2,
          );
        }
      }
    }

    // The selected destination changes the route in either camera view.
    final destination = alternate
        ? Offset(w * .86, crossing)
        : Offset(center, h * .30);
    final route = Path()
      ..moveTo(center, carY)
      ..lineTo(center, crossing);
    route.lineTo(destination.dx, destination.dy);
    canvas.drawPath(
      route,
      Paint()
        ..color = yellow.withValues(alpha: .16)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 18
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawPath(
      route,
      Paint()
        ..color = yellow
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawCircle(destination, 8, Paint()..color = yellow);
    canvas.drawCircle(destination, 3, Paint()..color = asphalt);

    // Car roof, front windscreen, rear glass, wheels and lights.
    canvas.save();
    canvas.translate(center, carY);
    canvas.drawOval(
      const Rect.fromLTWH(-23, -34, 50, 80),
      Paint()..color = const Color(0x66000000),
    );
    for (final x in [-22.0, 16.0]) {
      rect(Rect.fromLTWH(x, -23, 6, 14), const Color(0xFF10141A), 2);
      rect(Rect.fromLTWH(x, 18, 6, 14), const Color(0xFF10141A), 2);
    }
    rect(const Rect.fromLTWH(-19, -36, 38, 74), yellow, 10);
    rect(const Rect.fromLTWH(-15, -21, 30, 16), const Color(0xFF273746), 4);
    rect(const Rect.fromLTWH(-14, -2, 28, 21), const Color(0xFFD9B43E), 3);
    rect(const Rect.fromLTWH(-14, 22, 28, 9), const Color(0xFF273746), 3);
    for (final x in [-14.0, 8.0]) {
      rect(Rect.fromLTWH(x, -33, 6, 3), const Color(0xFFFFF2C2), 1);
      rect(Rect.fromLTWH(x, 33, 6, 3), const Color(0xFFFF7064), 1);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(OverheadScenePainter oldDelegate) =>
      alternate != oldDelegate.alternate;
}
