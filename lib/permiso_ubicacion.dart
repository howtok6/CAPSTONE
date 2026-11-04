// Hoja «¿Cómo quieres compartir tu ubicación?»: el usuario elige ubicación
// exacta o aproximada (y en ese caso el rango), o seguir sin ubicación.
//
// Aparece la primera vez que se abre la app y cada vez que se toca el
// indicador de ubicación del encabezado. Solo devuelve la elección: pedir el
// permiso al sistema lo hace la pantalla con [FuenteUbicacion.permitir].
import 'package:flutter/material.dart';

import 'main.dart' show subdued, yellow;
import 'ubicacion.dart';

/// Muestra la hoja y devuelve lo que eligió el usuario, o null si la cerró sin
/// elegir. [actual] deja marcada la opción vigente.
Future<PreferenciaUbicacion?> elegirUbicacion(
  BuildContext context, {
  PreferenciaUbicacion? actual,
}) => showModalBottomSheet<PreferenciaUbicacion>(
  context: context,
  isScrollControlled: true,
  backgroundColor: const Color(0xFF20242C),
  constraints: const BoxConstraints(maxWidth: 430),
  builder: (_) => HojaUbicacion(actual: actual),
);

class HojaUbicacion extends StatefulWidget {
  const HojaUbicacion({super.key, this.actual});
  final PreferenciaUbicacion? actual;
  @override
  State<HojaUbicacion> createState() => _HojaUbicacionState();
}

class _HojaUbicacionState extends State<HojaUbicacion> {
  late bool exacta = widget.actual?.modo != ModoUbicacion.aproximada;
  late int rango = widget.actual?.modo == ModoUbicacion.aproximada
      ? widget.actual!.rangoM
      : 500;

  PreferenciaUbicacion get eleccion => exacta
      ? const PreferenciaUbicacion.exacta()
      : PreferenciaUbicacion.aproximada(rango);

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      child: Column(
        key: const Key('location-sheet'),
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Row(
            children: [
              Icon(Icons.my_location_rounded, color: yellow, size: 22),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  '¿Cómo quieres compartir tu ubicación?',
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Vía la usa para mostrarte en el mapa, seguir tu ruta y decirte '
            'cuándo cambia el próximo semáforo. Solo se envía al backend '
            'mientras dura un recorrido.',
            style: TextStyle(fontSize: 12, color: subdued, height: 1.45),
          ),
          const SizedBox(height: 16),
          opcion(
            clave: 'location-exact',
            elegida: exacta,
            icono: Icons.gps_fixed_rounded,
            titulo: 'Ubicación exacta',
            detalle:
                'Tu posición real del GPS. El próximo semáforo y la '
                'distancia hasta él son precisos.',
            alElegir: () => setState(() => exacta = true),
          ),
          const SizedBox(height: 8),
          opcion(
            clave: 'location-approximate',
            elegida: !exacta,
            icono: Icons.blur_circular_rounded,
            titulo: 'Ubicación aproximada',
            detalle:
                'Solo la zona en que estás, dentro del rango que elijas. '
                'El próximo semáforo pasa a ser una estimación.',
            alElegir: () => setState(() => exacta = false),
            extra: exacta
                ? null
                : Wrap(
                    spacing: 6,
                    children: [
                      for (final m in PreferenciaUbicacion.rangos)
                        ChoiceChip(
                          key: Key('location-range-$m'),
                          label: Text(
                            PreferenciaUbicacion.textoRango(m),
                            style: TextStyle(
                              fontSize: 11,
                              color: rango == m
                                  ? const Color(0xFF161A21)
                                  : null,
                            ),
                          ),
                          selected: rango == m,
                          selectedColor: yellow,
                          visualDensity: VisualDensity.compact,
                          onSelected: (_) => setState(() => rango = m),
                        ),
                    ],
                  ),
          ),
          const SizedBox(height: 10),
          const Text(
            'Si el sistema te pregunta otra vez, elige la misma opción: la app '
            'usa siempre la más reservada de las dos.',
            style: TextStyle(fontSize: 10, color: subdued, height: 1.4),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              TextButton(
                key: const Key('location-skip'),
                onPressed: () => Navigator.pop(
                  context,
                  const PreferenciaUbicacion.desactivada(),
                ),
                child: const Text('Ahora no'),
              ),
              const Spacer(),
              FilledButton(
                key: const Key('location-continue'),
                onPressed: () => Navigator.pop(context, eleccion),
                style: FilledButton.styleFrom(
                  backgroundColor: yellow,
                  foregroundColor: const Color(0xFF161A21),
                ),
                child: const Text('Continuar'),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget opcion({
    required String clave,
    required bool elegida,
    required IconData icono,
    required String titulo,
    required String detalle,
    required VoidCallback alElegir,
    Widget? extra,
  }) => Semantics(
    selected: elegida,
    button: true,
    child: InkWell(
      key: Key(clave),
      onTap: alElegir,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: elegida ? yellow.withValues(alpha: .08) : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: elegida ? yellow : const Color(0xFF454A53),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icono, color: elegida ? yellow : subdued, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    detalle,
                    style: const TextStyle(
                      fontSize: 11,
                      color: subdued,
                      height: 1.4,
                    ),
                  ),
                  if (extra != null) ...[const SizedBox(height: 8), extra],
                ],
              ),
            ),
            Icon(
              elegida ? Icons.radio_button_checked : Icons.radio_button_off,
              size: 18,
              color: elegida ? yellow : subdued,
            ),
          ],
        ),
      ),
    ),
  );
}
