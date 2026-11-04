import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'main.dart' show subdued, surface, yellow;
import 'rutas_osm.dart';

/// Pantalla donde el usuario arma su propia ruta: elige origen, paradas y
/// destino (buscando o tocando el mapa), compara las alternativas de OSRM y
/// devuelve la elegida con `Navigator.pop`.
class ProponerRutaPage extends StatefulWidget {
  const ProponerRutaPage({super.key, this.buscador, this.enrutador});

  final BuscadorLugares? buscador;
  final Enrutador? enrutador;
  @override
  State<ProponerRutaPage> createState() => _ProponerRutaPageState();
}

class _ProponerRutaPageState extends State<ProponerRutaPage> {
  static const maxParadas = 5; // origen + 3 intermedias + destino
  late final buscador = widget.buscador ?? BuscadorLugares();
  late final enrutador = widget.enrutador ?? Enrutador();
  final mapa = MapController();
  final texto = TextEditingController();
  final paradas = <Lugar?>[plazaDeArmas, null];
  int editando = 1;
  List<Lugar> resultados = const [];
  List<RutaPropuesta> alternativas = const [];
  int elegida = 0;
  bool cargando = false;
  String? aviso;
  int _version = 0; // descarta respuestas de consultas ya reemplazadas

  String etiqueta(int i) => i == 0
      ? 'origen'
      : i == paradas.length - 1
      ? 'destino'
      : 'parada $i';

  static String km(double valor) =>
      valor.toStringAsFixed(1).replaceAll('.', ',');

  @override
  void dispose() {
    texto.dispose();
    mapa.dispose();
    super.dispose();
  }

  void cambiarParadas(VoidCallback cambio) => setState(() {
    cambio();
    _version++;
    alternativas = const [];
    resultados = const [];
    aviso = null;
  });

  void fijar(Lugar lugar) {
    cambiarParadas(() {
      paradas[editando] = lugar;
      texto.clear();
      final pendiente = paradas.indexOf(null);
      if (pendiente >= 0) editando = pendiente;
    });
    mapa.move(lugar.punto, 15);
    if (!paradas.contains(null)) calcular();
  }

  Future<void> buscar() async {
    final consulta = texto.text.trim();
    if (consulta.isEmpty) return;
    final version = ++_version;
    setState(() => cargando = true);
    try {
      final lista = await buscador.buscar(consulta);
      if (!mounted || version != _version) return;
      setState(() {
        resultados = lista;
        aviso = lista.isEmpty
            ? 'Sin resultados para «$consulta» en Santiago'
            : null;
      });
    } catch (_) {
      if (mounted) {
        setState(() => aviso = 'No se pudo buscar: revisa la conexión');
      }
    } finally {
      if (mounted) setState(() => cargando = false);
    }
  }

  Future<void> tocarMapa(LatLng punto) async {
    final version = ++_version;
    setState(() => cargando = true);
    final lugar = await buscador.nombrar(punto);
    if (!mounted) return;
    setState(() => cargando = false);
    if (version == _version) fijar(lugar);
  }

  Future<void> calcular() async {
    final version = ++_version;
    setState(() => cargando = true);
    try {
      final rutas = await enrutador.calcular(paradas.cast<Lugar>());
      if (!mounted || version != _version) return;
      setState(() {
        alternativas = rutas;
        elegida = 0;
      });
      mapa.fitCamera(
        CameraFit.coordinates(
          coordinates: [for (final r in rutas) ...r.trazado],
          padding: const EdgeInsets.all(40),
        ),
      );
    } on ServicioMapaException catch (e) {
      if (mounted) setState(() => aviso = e.mensaje);
    } catch (_) {
      if (mounted) {
        setState(() => aviso = 'Sin conexión con el servicio de rutas');
      }
    } finally {
      if (mounted) setState(() => cargando = false);
    }
  }

  void agregarParada() => cambiarParadas(() {
    paradas.insert(paradas.length - 1, null);
    editando = paradas.length - 2;
  });

  void quitarParada(int i) {
    cambiarParadas(() {
      paradas.removeAt(i);
      editando = paradas.contains(null)
          ? paradas.indexOf(null)
          : paradas.length - 1;
    });
    if (!paradas.contains(null)) calcular();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Proponer ruta', style: TextStyle(fontSize: 16)),
      backgroundColor: const Color(0xFF11151D),
    ),
    body: Column(
      children: [
        listaParadas(),
        campoBusqueda(),
        if (resultados.isNotEmpty) listaResultados(),
        Expanded(
          child: Stack(
            children: [
              mapaOsm(),
              if (cargando)
                const LinearProgressIndicator(minHeight: 2, color: yellow),
            ],
          ),
        ),
        panelInferior(),
      ],
    ),
  );

  Widget listaParadas() => Container(
    margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
    padding: const EdgeInsets.symmetric(vertical: 4),
    decoration: BoxDecoration(
      color: surface,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF454A53)),
    ),
    child: Column(
      children: [
        for (var i = 0; i < paradas.length; i++)
          InkWell(
            key: Key('stop-$i'),
            onTap: () => setState(() => editando = i),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              child: Row(
                children: [
                  marcador(i, editando == i),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      paradas[i]?.nombre ?? 'Elige el ${etiqueta(i)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: paradas[i] == null ? subdued : Colors.white,
                        fontWeight: editando == i ? FontWeight.w700 : null,
                      ),
                    ),
                  ),
                  if (i > 0 && i < paradas.length - 1)
                    IconButton(
                      key: Key('remove-stop-$i'),
                      tooltip: 'Quitar parada',
                      visualDensity: VisualDensity.compact,
                      iconSize: 16,
                      onPressed: () => quitarParada(i),
                      icon: const Icon(Icons.close, color: subdued),
                    ),
                ],
              ),
            ),
          ),
      ],
    ),
  );

  Widget marcador(int i, bool activo) {
    final extremo = i == 0 || i == paradas.length - 1;
    return Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: activo ? yellow : const Color(0xFF2B3039),
        border: Border.all(color: extremo ? yellow : subdued, width: 1.5),
      ),
      child: Text(
        i == 0 ? 'A' : (i == paradas.length - 1 ? 'B' : '$i'),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: activo ? const Color(0xFF161A21) : Colors.white,
        ),
      ),
    );
  }

  Widget campoBusqueda() => Padding(
    padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
    child: TextField(
      key: const Key('place-search'),
      controller: texto,
      textInputAction: TextInputAction.search,
      onSubmitted: (_) => buscar(),
      style: const TextStyle(fontSize: 13),
      decoration: InputDecoration(
        isDense: true,
        hintText: 'Buscar ${etiqueta(editando)} en Santiago',
        hintStyle: const TextStyle(fontSize: 12, color: subdued),
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF454A53)),
        ),
        suffixIcon: IconButton(
          key: const Key('place-search-button'),
          tooltip: 'Buscar',
          onPressed: buscar,
          icon: const Icon(Icons.search, size: 18, color: yellow),
        ),
      ),
    ),
  );

  Widget listaResultados() => ConstrainedBox(
    constraints: const BoxConstraints(maxHeight: 180),
    child: ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      children: [
        for (final lugar in resultados)
          ListTile(
            dense: true,
            leading: const Icon(Icons.place_outlined, color: yellow, size: 18),
            title: Text(lugar.nombre, style: const TextStyle(fontSize: 12)),
            subtitle: Text(
              lugar.detalle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: subdued),
            ),
            onTap: () => fijar(lugar),
          ),
      ],
    ),
  );

  Widget mapaOsm() => FlutterMap(
    mapController: mapa,
    options: MapOptions(
      initialCenter: plazaDeArmas.punto,
      initialZoom: 13,
      onTap: (_, punto) => tocarMapa(punto),
    ),
    children: [
      TileLayer(
        urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        userAgentPackageName: 'com.example.mockup',
        tileBuilder: darkModeTileBuilder,
      ),
      PolylineLayer(
        polylines: [
          // La elegida se dibuja al final para que quede encima.
          for (var i = 0; i < alternativas.length; i++)
            if (i != elegida)
              Polyline(
                points: alternativas[i].trazado,
                strokeWidth: 4,
                color: const Color(0xAA8A909B),
              ),
          if (alternativas.isNotEmpty)
            Polyline(
              points: alternativas[elegida].trazado,
              strokeWidth: 6,
              color: yellow,
              borderStrokeWidth: 2,
              borderColor: const Color(0xFF161A21),
            ),
        ],
      ),
      MarkerLayer(
        markers: [
          for (var i = 0; i < paradas.length; i++)
            if (paradas[i] != null)
              Marker(
                point: paradas[i]!.punto,
                width: 26,
                height: 26,
                child: marcador(i, true),
              ),
        ],
      ),
      const RichAttributionWidget(
        attributions: [TextSourceAttribution('OpenStreetMap contributors')],
      ),
    ],
  );

  Widget panelInferior() => Container(
    padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
    color: const Color(0xFF11151D),
    child: SafeArea(
      top: false,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (aviso != null || alternativas.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                aviso ??
                    'Busca o toca el mapa para fijar el ${etiqueta(editando)}',
                key: const Key('route-hint'),
                style: TextStyle(
                  fontSize: 11,
                  color: aviso != null ? const Color(0xFFFF7773) : subdued,
                ),
              ),
            ),
          if (alternativas.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (var i = 0; i < alternativas.length; i++)
                    ChoiceChip(
                      key: Key('alternative-$i'),
                      selected: elegida == i,
                      onSelected: (_) => setState(() => elegida = i),
                      selectedColor: yellow,
                      labelStyle: TextStyle(
                        fontSize: 11,
                        color: elegida == i ? const Color(0xFF161A21) : null,
                      ),
                      label: Text(
                        '${i == 0 ? 'Más rápida' : 'Alternativa $i'} · '
                        '${km(alternativas[i].distanciaKm)} km · '
                        '${alternativas[i].duracionMin.round()} min',
                      ),
                    ),
                ],
              ),
            ),
          Row(
            children: [
              OutlinedButton.icon(
                key: const Key('add-stop'),
                onPressed: paradas.length < maxParadas ? agregarParada : null,
                icon: const Icon(Icons.add_location_alt_outlined, size: 16),
                label: const Text('Parada', style: TextStyle(fontSize: 12)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  key: const Key('confirm-route'),
                  onPressed: alternativas.isEmpty
                      ? null
                      : () => Navigator.pop(context, alternativas[elegida]),
                  style: FilledButton.styleFrom(
                    backgroundColor: yellow,
                    foregroundColor: const Color(0xFF161A21),
                  ),
                  icon: const Icon(Icons.check, size: 17),
                  label: const Text(
                    'Proponer ruta',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
