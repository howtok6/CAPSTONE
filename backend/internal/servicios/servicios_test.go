package servicios

import (
	"context"
	"errors"
	"math"
	"testing"
	"time"

	"via/backend/internal/almacen"
	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

// Red de prueba: una avenida recta hacia el oriente sobre la latitud -33.44.
//
//	A (lon -70.655): semáforo de la avenida, accesos oriente (90°) y poniente (270°)
//	B (lon -70.645): semáforo de la avenida, solo acceso oriente
//	C (lon -70.650, 25 m al norte): semáforo de una transversal (0° y 180°)
//	D (lon -70.650, 200 m al norte): lejos de la avenida
const lat0 = -33.44

func ptrInt(v int) *int         { return &v }
func texto(v string) *string    { return &v }
func pto(lon float64) geo.Punto { return geo.Punto{Lat: lat0, Lon: lon} }

type traficoFalso struct {
	semaforos []dominio.Semaforo
	estados   map[string]map[string]dominio.EstadoAcceso
	consultas int
	fallar    bool
}

func nuevoTraficoFalso() *traficoFalso {
	return &traficoFalso{
		semaforos: []dominio.Semaforo{
			{ID: "A", Nombre: "Avenida × A", Lat: lat0, Lon: -70.655, Accesos: []dominio.Acceso{
				{ID: "A_e", Calle: "Avenida", Rumbo: 90}, {ID: "A_w", Calle: "Avenida", Rumbo: 270}}},
			{ID: "B", Nombre: "Avenida × B", Lat: lat0, Lon: -70.645, Accesos: []dominio.Acceso{
				{ID: "B_e", Calle: "Avenida", Rumbo: 90}}},
			{ID: "C", Nombre: "Transversal", Lat: lat0 + 0.000225, Lon: -70.650, Accesos: []dominio.Acceso{
				{ID: "C_n", Calle: "Transversal", Rumbo: 0}, {ID: "C_s", Calle: "Transversal", Rumbo: 180}}},
			{ID: "D", Nombre: "Lejano", Lat: lat0 + 0.0018, Lon: -70.650, Accesos: []dominio.Acceso{
				{ID: "D_e", Calle: "Otra", Rumbo: 90}}},
		},
		estados: map[string]map[string]dominio.EstadoAcceso{
			"A": {"A_e": {Color: "verde", SegundosParaCambio: ptrInt(12), SiguienteColor: texto("amarillo"), Exacto: true},
				"A_w": {Color: "rojo", SegundosParaCambio: ptrInt(12), SiguienteColor: texto("verde"), Exacto: true}},
			"B": {"B_e": {Color: "rojo", SegundosParaCambio: ptrInt(30), SiguienteColor: texto("verde"), Exacto: true}},
		},
	}
}

func (t *traficoFalso) Semaforos(context.Context) ([]dominio.Semaforo, error) {
	t.consultas++
	if t.fallar {
		return nil, dominio.ErrProveedor
	}
	return t.semaforos, nil
}
func (t *traficoFalso) EstadoSemaforos(_ context.Context, ids []string) (map[string]map[string]dominio.EstadoAcceso, error) {
	if t.fallar {
		return nil, dominio.ErrProveedor
	}
	return t.estados, nil
}
func (t *traficoFalso) Calles(context.Context) ([]dominio.Calle, error) {
	return []dominio.Calle{
		{ID: "e1", Nombre: "Avenida", VelocidadLibreKmh: 50, Forma: [][2]float64{{lat0, -70.66}, {lat0, -70.65}}},
		{ID: "e2", Nombre: "Pasaje", VelocidadLibreKmh: 30, Forma: [][2]float64{{-33.50, -70.70}, {-33.50, -70.69}}},
	}, nil
}
func (t *traficoFalso) Trafico(context.Context) ([]dominio.EstadoCalle, error) {
	return []dominio.EstadoCalle{
		{ID: "e1", VelocidadKmh: 12, Vehiculos: 9, Nivel: "congestionado"},
		{ID: "e2", VelocidadKmh: 30, Vehiculos: 0, Nivel: "libre"},
	}, nil
}

type simFalso struct {
	finalizados []string
}

func (s *simFalso) Destinos(context.Context) ([]dominio.DestinoSimulado, error) {
	return []dominio.DestinoSimulado{{Ruta: 0, ID: "bustamante", Nombre: "Av. General Bustamante", DistanciaKm: 1.7}}, nil
}
func (s *simFalso) CrearViaje(_ context.Context, ruta int) (dominio.ViajeSimulado, error) {
	if ruta != 0 {
		return dominio.ViajeSimulado{}, dominio.ErrInvalido
	}
	return dominio.ViajeSimulado{ID: "v1", Estado: "esperando", Destino: "Av. General Bustamante", DistanciaTotalM: ptrInt(1665)}, nil
}
func (s *simFalso) Viaje(_ context.Context, id string) (dominio.ViajeSimulado, error) {
	if id != "v1" {
		return dominio.ViajeSimulado{}, dominio.ErrNoEncontrado
	}
	v := dominio.ViajeSimulado{ID: "v1", Estado: "en_ruta", Destino: "Av. General Bustamante",
		DistanciaTotalM: ptrInt(1665), DistanciaRestanteM: ptrInt(1268)}
	v.ProximoSemaforo = &struct {
		ID         string   `json:"id"`
		Nombre     string   `json:"nombre"`
		Calles     []string `json:"calles"`
		DistanciaM float64  `json:"distancia_m"`
		dominio.EstadoAcceso
	}{ID: "GS_1", Nombre: "Alameda × Av. Portugal", DistanciaM: 447.4,
		EstadoAcceso: dominio.EstadoAcceso{Color: "rojo", SegundosParaCambio: ptrInt(11), Exacto: true}}
	return v, nil
}
func (s *simFalso) FinalizarViaje(_ context.Context, id string) error {
	s.finalizados = append(s.finalizados, id)
	return nil
}

type enrutadorFalso struct{}

func (enrutadorFalso) Rutas(_ context.Context, paradas []geo.Punto, _ bool) ([]dominio.Ruta, error) {
	return []dominio.Ruta{{DistanciaKm: 1.86, DuracionMin: 3, Trazado: [][2]float64{
		{paradas[0].Lat, paradas[0].Lon}, {paradas[len(paradas)-1].Lat, paradas[len(paradas)-1].Lon}}}}, nil
}

func preparar() (*traficoFalso, *simFalso, *Navegacion, *Viajes) {
	t, s := nuevoTraficoFalso(), &simFalso{}
	nav := NuevaNavegacion(t)
	v := NuevosViajes(nav, enrutadorFalso{}, s, almacen.NuevaMemoria[*ViajeInterno](time.Hour))
	return t, s, nav, v
}

var avenida = [][2]float64{{lat0, -70.660}, {lat0, -70.640}}

func TestSemaforosEnRutaDescartaTransversalesYLejanos(t *testing.T) {
	_, _, nav, _ := preparar()
	en, err := nav.SemaforosEnRuta(context.Background(), geo.NuevaPolilinea(geo.DesdeLatLon(avenida)))
	if err != nil {
		t.Fatal(err)
	}
	if len(en) != 2 || en[0].ID != "A" || en[1].ID != "B" {
		t.Fatalf("semáforos en ruta = %+v; se esperaban A y B", en)
	}
	if math.Abs(en[0].DistanciaDesdeInicioM-464) > 5 || math.Abs(en[1].DistanciaDesdeInicioM-1392) > 8 {
		t.Errorf("distancias = %.0f y %.0f m", en[0].DistanciaDesdeInicioM, en[1].DistanciaDesdeInicioM)
	}
}

func TestViajeGPSSigueLaRuta(t *testing.T) {
	_, _, _, viajes := preparar()
	ctx := context.Background()
	v, err := viajes.Crear(ctx, SolicitudViaje{Modo: "gps", Trazado: avenida, NombreDestino: "Fin"})
	if err != nil {
		t.Fatal(err)
	}
	if v.SemaforosEnRuta != 2 || v.Estado != "en_ruta" || *v.DistanciaTotalM < 1800 {
		t.Fatalf("viaje creado = %+v", v)
	}

	// Antes de A, yendo al oriente: el próximo es A con el acceso oriente en verde.
	v, err = viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.658})
	if err != nil {
		t.Fatal(err)
	}
	p := v.ProximoSemaforo
	if p == nil || p.ID != "A" || p.Acceso != "A_e" || p.Color != "verde" || *p.SegundosParaCambio != 12 {
		t.Fatalf("próximo = %+v", p)
	}
	if math.Abs(float64(p.DistanciaM)-278) > 5 {
		t.Errorf("distancia a A = %d m", p.DistanciaM)
	}

	// Pasado A: el próximo es B.
	v, _ = viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.652})
	if v.ProximoSemaforo == nil || v.ProximoSemaforo.ID != "B" || v.ProximoSemaforo.Color != "rojo" {
		t.Fatalf("pasado A, próximo = %+v", v.ProximoSemaforo)
	}
	if v.Ubicacion.Rumbo != nil {
		t.Error("el rumbo enviado por la app no debe inventarse")
	}

	// Llegando al final.
	v, _ = viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.6401})
	if v.Estado != "llego" || v.ProximoSemaforo != nil || *v.DistanciaRestanteM > 30 {
		t.Fatalf("al llegar: estado %s, próximo %+v, restante %d", v.Estado, v.ProximoSemaforo, *v.DistanciaRestanteM)
	}

	if err := viajes.Finalizar(ctx, v.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.65}); !errors.Is(err, dominio.ErrConflicto) {
		t.Errorf("ubicación en viaje finalizado: %v", err)
	}
}

func TestViajeGPSSinRutaUsaElRumboEstimado(t *testing.T) {
	_, _, _, viajes := preparar()
	ctx := context.Background()
	v, err := viajes.Crear(ctx, SolicitudViaje{Modo: "gps"})
	if err != nil {
		t.Fatal(err)
	}
	v, _ = viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.660})
	if v.ProximoSemaforo != nil {
		t.Fatal("sin rumbo no se puede saber el próximo semáforo")
	}
	v, _ = viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.659})
	if v.ProximoSemaforo == nil || v.ProximoSemaforo.ID != "A" || v.ProximoSemaforo.Acceso != "A_e" {
		t.Fatalf("con rumbo estimado al oriente, próximo = %+v", v.ProximoSemaforo)
	}
}

func TestProximoPorRumbo(t *testing.T) {
	_, _, nav, _ := preparar()
	ctx := context.Background()
	p, err := nav.ProximoPorRumbo(ctx, pto(-70.658), 90)
	if err != nil || p == nil || p.ID != "A" {
		t.Fatalf("al oriente = %+v, %v", p, err)
	}
	p, _ = nav.ProximoPorRumbo(ctx, pto(-70.658), 270)
	if p != nil {
		t.Fatalf("al poniente no hay semáforos, se obtuvo %+v", p)
	}
	p, _ = nav.ProximoPorRumbo(ctx, pto(-70.652), 270) // de vuelta hacia A por el acceso poniente
	if p == nil || p.ID != "A" || p.Acceso != "A_w" || p.Color != "rojo" {
		t.Fatalf("hacia A por el poniente = %+v", p)
	}
}

func TestViajeSimulado(t *testing.T) {
	_, sim, _, viajes := preparar()
	ctx := context.Background()
	if _, err := viajes.Crear(ctx, SolicitudViaje{Modo: "simulado"}); !errors.Is(err, dominio.ErrInvalido) {
		t.Errorf("sin destino: %v", err)
	}
	v, err := viajes.Crear(ctx, SolicitudViaje{Modo: "simulado", Destino: ptrInt(0)})
	if err != nil || v.Estado != "esperando" {
		t.Fatalf("crear = %+v, %v", v, err)
	}
	v, err = viajes.Obtener(ctx, v.ID)
	if err != nil || v.ProximoSemaforo == nil || v.ProximoSemaforo.DistanciaM != 447 || *v.ProximoSemaforo.SegundosParaCambio != 11 {
		t.Fatalf("obtener = %+v, %v", v.ProximoSemaforo, err)
	}
	if _, err := viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: lat0, Lon: -70.65}); !errors.Is(err, dominio.ErrConflicto) {
		t.Errorf("ubicación en viaje simulado: %v", err)
	}
	if err := viajes.Finalizar(ctx, v.ID); err != nil || len(sim.finalizados) != 1 || sim.finalizados[0] != "v1" {
		t.Fatalf("finalizar: %v, %v", err, sim.finalizados)
	}
}

func TestValidaciones(t *testing.T) {
	_, _, _, viajes := preparar()
	ctx := context.Background()
	if _, err := viajes.Crear(ctx, SolicitudViaje{Modo: "bicicleta"}); !errors.Is(err, dominio.ErrInvalido) {
		t.Errorf("modo inválido: %v", err)
	}
	if _, err := viajes.Crear(ctx, SolicitudViaje{Modo: "gps", Trazado: [][2]float64{{1, 2}}}); !errors.Is(err, dominio.ErrInvalido) {
		t.Errorf("trazado de un punto: %v", err)
	}
	v, _ := viajes.Crear(ctx, SolicitudViaje{Modo: "gps"})
	if _, err := viajes.RegistrarUbicacion(ctx, v.ID, dominio.Ubicacion{Lat: 0, Lon: 0}); !errors.Is(err, dominio.ErrInvalido) {
		t.Errorf("ubicación (0,0): %v", err)
	}
	if _, err := viajes.Obtener(ctx, "nada"); !errors.Is(err, dominio.ErrNoEncontrado) {
		t.Errorf("viaje inexistente: %v", err)
	}
}

func TestCacheYRespaldoDeDatosEstaticos(t *testing.T) {
	tr, _, nav, _ := preparar()
	ctx := context.Background()
	_, _ = nav.Semaforos(ctx, nil)
	_, _ = nav.Semaforos(ctx, nil)
	if tr.consultas != 1 {
		t.Errorf("los semáforos se pidieron %d veces; se esperaba 1 (caché)", tr.consultas)
	}
	trafico, err := nav.Trafico(ctx, nil, false)
	if err != nil || len(trafico) != 1 || trafico[0].ID != "e1" || trafico[0].Nivel != "congestionado" {
		t.Fatalf("tráfico sin calles libres = %+v, %v", trafico, err)
	}
	r := geo.Recuadro{MinLon: -70.75, MinLat: -33.55, MaxLon: -70.68, MaxLat: -33.45}
	trafico, _ = nav.Trafico(ctx, &r, true)
	if len(trafico) != 1 || trafico[0].ID != "e2" {
		t.Fatalf("tráfico en recuadro = %+v", trafico)
	}
}
