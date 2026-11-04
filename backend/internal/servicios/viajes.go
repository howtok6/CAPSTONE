package servicios

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"sync"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

const (
	// Más lejos que esto del trazado, el usuario se considera fuera de la ruta.
	fueraDeRutaM = 60.0
	// A menos de esto del final de la ruta, el viaje se da por terminado.
	llegadaM = 30.0
	// Desplazamiento mínimo para estimar el rumbo entre dos ubicaciones.
	movimientoMinimoM = 5.0
)

// ViajeInterno: lo que el backend guarda de un viaje, además de lo que publica.
type ViajeInterno struct {
	Publico      dominio.Viaje
	IDSimulacion string
	Trazado      *geo.Polilinea
	EnRuta       []dominio.SemaforoEnRuta
	RecorridoM   float64
	Rumbo        *float64
}

// SolicitudViaje: lo que envía la app para iniciar un viaje.
type SolicitudViaje struct {
	Modo          string       `json:"modo"`           // gps | simulado
	Destino       *int         `json:"destino"`        // simulado: índice de GET /v1/simulacion/destinos
	NombreDestino string       `json:"nombre_destino"` // gps: texto para mostrar
	Paradas       []geo.Punto  `json:"paradas"`        // gps: el backend calcula la ruta
	Trazado       [][2]float64 `json:"trazado"`        // gps: ruta ya elegida en POST /v1/rutas
}

// Viajes administra los viajes de los usuarios.
type Viajes struct {
	nav       *Navegacion
	enrutador Enrutador
	sim       SimuladorViajes
	almacen   AlmacenViajes
	reloj     func() time.Time
	mu        sync.Mutex // serializa los cambios de un viaje
}

// NuevosViajes crea el servicio.
func NuevosViajes(nav *Navegacion, e Enrutador, sim SimuladorViajes, a AlmacenViajes) *Viajes {
	return &Viajes{nav: nav, enrutador: e, sim: sim, almacen: a, reloj: time.Now}
}

func nuevoID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "v_" + hex.EncodeToString(b)
}

func entero(f float64) *int {
	v := int(math.Round(f))
	return &v
}

// DestinosSimulados: recorridos de demostración disponibles.
func (v *Viajes) DestinosSimulados(ctx context.Context) ([]dominio.DestinoSimulado, error) {
	return v.sim.Destinos(ctx)
}

// Crear inicia un viaje GPS o simulado.
func (v *Viajes) Crear(ctx context.Context, s SolicitudViaje) (dominio.Viaje, error) {
	switch s.Modo {
	case dominio.ModoSimulado:
		return v.crearSimulado(ctx, s)
	case dominio.ModoGPS, "":
		return v.crearGPS(ctx, s)
	default:
		return dominio.Viaje{}, fmt.Errorf("%w: modo debe ser «gps» o «simulado»", dominio.ErrInvalido)
	}
}

func (v *Viajes) crearSimulado(ctx context.Context, s SolicitudViaje) (dominio.Viaje, error) {
	if s.Destino == nil {
		return dominio.Viaje{}, fmt.Errorf("%w: falta destino (ver GET /v1/simulacion/destinos)", dominio.ErrInvalido)
	}
	vs, err := v.sim.CrearViaje(ctx, *s.Destino)
	if err != nil {
		return dominio.Viaje{}, err
	}
	ahora := v.reloj()
	vi := &ViajeInterno{IDSimulacion: vs.ID}
	vi.Publico = dominio.Viaje{ID: nuevoID(), Modo: dominio.ModoSimulado, CreadoEn: ahora}
	desdeSimulado(&vi.Publico, vs, ahora)
	v.almacen.Guardar(vi.Publico.ID, vi)
	return vi.Publico, nil
}

func (v *Viajes) crearGPS(ctx context.Context, s SolicitudViaje) (dominio.Viaje, error) {
	var trazado []geo.Punto
	switch {
	case len(s.Trazado) >= 2:
		trazado = geo.DesdeLatLon(s.Trazado)
	case len(s.Paradas) >= 2:
		rutas, err := NuevasRutas(v.enrutador, v.nav).Calcular(ctx, s.Paradas, false)
		if err != nil {
			return dominio.Viaje{}, err
		}
		trazado = geo.DesdeLatLon(rutas[0].Trazado)
	case len(s.Trazado) == 1 || len(s.Paradas) == 1:
		return dominio.Viaje{}, fmt.Errorf("%w: una ruta necesita al menos dos puntos", dominio.ErrInvalido)
	}
	for _, p := range trazado {
		if !p.Valido() {
			return dominio.Viaje{}, fmt.Errorf("%w: el trazado tiene coordenadas inválidas", dominio.ErrInvalido)
		}
	}

	ahora := v.reloj()
	vi := &ViajeInterno{}
	vi.Publico = dominio.Viaje{
		ID: nuevoID(), Modo: dominio.ModoGPS, Estado: "en_ruta", Destino: s.NombreDestino,
		CreadoEn: ahora, ActualizadoEn: ahora,
	}
	if trazado != nil {
		vi.Trazado = geo.NuevaPolilinea(trazado)
		vi.Publico.DistanciaTotalM = entero(vi.Trazado.Largo())
		vi.Publico.DistanciaRestanteM = entero(vi.Trazado.Largo())
		en, err := v.nav.SemaforosEnRuta(ctx, vi.Trazado)
		if err != nil {
			slog.Warn("viaje sin semáforos: proveedor de tráfico no disponible", "error", err)
		}
		vi.EnRuta = en
		vi.Publico.SemaforosEnRuta = len(en)
	}
	v.almacen.Guardar(vi.Publico.ID, vi)
	return vi.Publico, nil
}

// Obtener devuelve el viaje con su estado actualizado: el semáforo cambia
// aunque el usuario no se mueva.
func (v *Viajes) Obtener(ctx context.Context, id string) (dominio.Viaje, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	vi, ok := v.almacen.Obtener(id)
	if !ok {
		return dominio.Viaje{}, fmt.Errorf("viaje %q: %w", id, dominio.ErrNoEncontrado)
	}
	if vi.Publico.Estado == "finalizado" {
		return vi.Publico, nil
	}
	if vi.Publico.Modo == dominio.ModoSimulado {
		vs, err := v.sim.Viaje(ctx, vi.IDSimulacion)
		switch {
		case errors.Is(err, dominio.ErrNoEncontrado):
			vi.Publico.Estado = "reiniciado" // la simulación se reinició y perdió el vehículo
			vi.Publico.ProximoSemaforo = nil
		case err != nil:
			return dominio.Viaje{}, err
		default:
			desdeSimulado(&vi.Publico, vs, v.reloj())
		}
	} else if vi.Publico.Ubicacion != nil {
		v.calcularProximo(ctx, vi)
	}
	v.almacen.Guardar(id, vi)
	return vi.Publico, nil
}

// RegistrarUbicacion recibe la ubicación del GPS y recalcula el próximo semáforo.
func (v *Viajes) RegistrarUbicacion(ctx context.Context, id string, u dominio.Ubicacion) (dominio.Viaje, error) {
	p := geo.Punto{Lat: u.Lat, Lon: u.Lon}
	if !p.Valido() {
		return dominio.Viaje{}, fmt.Errorf("%w: lat y lon deben ser coordenadas válidas", dominio.ErrInvalido)
	}
	if u.Rumbo != nil && (*u.Rumbo < 0 || *u.Rumbo >= 360) {
		return dominio.Viaje{}, fmt.Errorf("%w: rumbo debe estar en [0, 360)", dominio.ErrInvalido)
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	vi, ok := v.almacen.Obtener(id)
	if !ok {
		return dominio.Viaje{}, fmt.Errorf("viaje %q: %w", id, dominio.ErrNoEncontrado)
	}
	if vi.Publico.Modo != dominio.ModoGPS {
		return dominio.Viaje{}, fmt.Errorf("%w: un viaje simulado no recibe ubicaciones", dominio.ErrConflicto)
	}
	if vi.Publico.Estado == "finalizado" {
		return dominio.Viaje{}, fmt.Errorf("%w: el viaje ya terminó", dominio.ErrConflicto)
	}

	if u.Momento.IsZero() {
		u.Momento = v.reloj()
	}
	// Rumbo: el del GPS si viene; si no, el del desplazamiento desde la ubicación anterior.
	if u.Rumbo != nil {
		r := *u.Rumbo
		vi.Rumbo = &r
	} else if ant := vi.Publico.Ubicacion; ant != nil {
		q := geo.Punto{Lat: ant.Lat, Lon: ant.Lon}
		if geo.Distancia(q, p) >= movimientoMinimoM {
			r := math.Round(geo.Rumbo(q, p)*10) / 10
			vi.Rumbo = &r
		}
	}
	ub := u
	vi.Publico.Ubicacion = &ub
	vi.Publico.ActualizadoEn = v.reloj()

	if vi.Trazado != nil {
		pr := vi.Trazado.Proyectar(p, math.Max(0, vi.RecorridoM-100))
		if pr.SeparacionM <= fueraDeRutaM {
			vi.RecorridoM = pr.RecorridoM
			restante := math.Max(0, vi.Trazado.Largo()-vi.RecorridoM)
			vi.Publico.DistanciaRestanteM = entero(restante)
			if restante <= llegadaM {
				vi.Publico.Estado = "llego"
			}
		}
	}
	v.calcularProximo(ctx, vi)
	v.almacen.Guardar(id, vi)
	return vi.Publico, nil
}

// calcularProximo usa la ruta si el usuario va sobre ella; si no, su rumbo.
func (v *Viajes) calcularProximo(ctx context.Context, vi *ViajeInterno) {
	u := vi.Publico.Ubicacion
	p := geo.Punto{Lat: u.Lat, Lon: u.Lon}
	var (
		prox *dominio.ProximoSemaforo
		err  error
	)
	enRuta := false
	if vi.Trazado != nil {
		pr := vi.Trazado.Proyectar(p, math.Max(0, vi.RecorridoM-100))
		enRuta = pr.SeparacionM <= fueraDeRutaM
	}
	switch {
	case vi.Publico.Estado == "llego":
		prox = nil
	case enRuta:
		prox, err = v.nav.ProximoEnRuta(ctx, vi.EnRuta, vi.RecorridoM)
	case vi.Rumbo != nil:
		prox, err = v.nav.ProximoPorRumbo(ctx, p, *vi.Rumbo)
	}
	if err != nil {
		slog.Warn("no se pudo calcular el próximo semáforo", "viaje", vi.Publico.ID, "error", err)
		return // se conserva el último conocido
	}
	vi.Publico.ProximoSemaforo = prox
}

// Finalizar termina el viaje; en uno simulado retira el vehículo de la simulación.
func (v *Viajes) Finalizar(ctx context.Context, id string) error {
	v.mu.Lock()
	defer v.mu.Unlock()
	vi, ok := v.almacen.Obtener(id)
	if !ok {
		return fmt.Errorf("viaje %q: %w", id, dominio.ErrNoEncontrado)
	}
	if vi.Publico.Modo == dominio.ModoSimulado && vi.Publico.Estado != "finalizado" {
		if err := v.sim.FinalizarViaje(ctx, vi.IDSimulacion); err != nil && !errors.Is(err, dominio.ErrNoEncontrado) {
			return err
		}
	}
	vi.Publico.Estado = "finalizado"
	vi.Publico.ProximoSemaforo = nil
	vi.Publico.ActualizadoEn = v.reloj()
	v.almacen.Guardar(id, vi)
	return nil
}

// desdeSimulado copia el estado de un viaje de la simulación al formato del backend.
func desdeSimulado(d *dominio.Viaje, s dominio.ViajeSimulado, ahora time.Time) {
	d.Estado = s.Estado
	d.Destino = s.Destino
	d.DistanciaTotalM = s.DistanciaTotalM
	d.DistanciaRestanteM = s.DistanciaRestanteM
	d.ActualizadoEn = ahora
	if s.Posicion != nil {
		d.Ubicacion = &dominio.Ubicacion{Lat: s.Posicion.Lat, Lon: s.Posicion.Lon, VelocidadKmh: s.VelocidadKmh, Momento: ahora}
	}
	d.ProximoSemaforo = nil
	if ps := s.ProximoSemaforo; ps != nil {
		d.ProximoSemaforo = &dominio.ProximoSemaforo{
			ID: ps.ID, Nombre: ps.Nombre, Calles: ps.Calles,
			DistanciaM: int(math.Round(ps.DistanciaM)), EstadoAcceso: ps.EstadoAcceso,
		}
	}
}
