package servicios

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"sync"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

const (
	// Un semáforo está «en la ruta» si queda a menos de esto del trazado.
	toleranciaRutaM = 35.0
	// Un acceso corresponde al sentido de llegada si su rumbo difiere menos de esto.
	toleranciaAccesoGrados = 60.0
	// Sin ruta: se buscan semáforos hacia adelante, dentro de este alcance y cono.
	alcanceSinRutaM  = 500.0
	conoSinRutaGrado = 40.0
	// Tramo antes del semáforo con que se mide el rumbo de llegada por la ruta.
	tramoLlegadaM = 30.0
)

// Navegacion responde qué semáforos hay en una ruta, cuál es el próximo para
// un usuario y el estado del tráfico. Guarda en caché los datos estáticos.
type Navegacion struct {
	trafico  ProveedorTrafico
	vigencia time.Duration
	reloj    func() time.Time

	mu        sync.Mutex
	semaforos []dominio.Semaforo
	porID     map[string]dominio.Semaforo
	calles    []dominio.Calle
	cargaS    time.Time
	cargaC    time.Time
}

// NuevaNavegacion crea el servicio sobre un proveedor de tráfico.
func NuevaNavegacion(t ProveedorTrafico) *Navegacion {
	return &Navegacion{trafico: t, vigencia: 10 * time.Minute, reloj: time.Now}
}

func (n *Navegacion) estaticos(ctx context.Context) ([]dominio.Semaforo, map[string]dominio.Semaforo, error) {
	n.mu.Lock()
	defer n.mu.Unlock()
	if n.semaforos != nil && n.reloj().Sub(n.cargaS) < n.vigencia {
		return n.semaforos, n.porID, nil
	}
	s, err := n.trafico.Semaforos(ctx)
	if err != nil {
		if n.semaforos != nil {
			return n.semaforos, n.porID, nil // mejor datos viejos que ninguno
		}
		return nil, nil, err
	}
	n.semaforos, n.porID, n.cargaS = s, make(map[string]dominio.Semaforo, len(s)), n.reloj()
	for _, x := range s {
		n.porID[x.ID] = x
	}
	return n.semaforos, n.porID, nil
}

func (n *Navegacion) callesEstaticas(ctx context.Context) ([]dominio.Calle, error) {
	n.mu.Lock()
	defer n.mu.Unlock()
	if n.calles != nil && n.reloj().Sub(n.cargaC) < n.vigencia {
		return n.calles, nil
	}
	c, err := n.trafico.Calles(ctx)
	if err != nil {
		if n.calles != nil {
			return n.calles, nil
		}
		return nil, err
	}
	n.calles, n.cargaC = c, n.reloj()
	return c, nil
}

// AccesoConEstado: un acceso del semáforo con su color actual.
type AccesoConEstado struct {
	dominio.Acceso
	*dominio.EstadoAcceso
}

// SemaforoConEstado: un semáforo con el estado de cada acceso.
type SemaforoConEstado struct {
	ID      string            `json:"id"`
	Nombre  string            `json:"nombre"`
	Calles  []string          `json:"calles"`
	Lat     float64           `json:"lat"`
	Lon     float64           `json:"lon"`
	Accesos []AccesoConEstado `json:"accesos"`
}

// Semaforos con su estado actual; si hay recuadro, solo los que caen dentro.
func (n *Navegacion) Semaforos(ctx context.Context, recuadro *geo.Recuadro) ([]SemaforoConEstado, error) {
	todos, _, err := n.estaticos(ctx)
	if err != nil {
		return nil, err
	}
	var elegidos []dominio.Semaforo
	var ids []string
	for _, s := range todos {
		if recuadro == nil || recuadro.Contiene(geo.Punto{Lat: s.Lat, Lon: s.Lon}) {
			elegidos = append(elegidos, s)
			ids = append(ids, s.ID)
		}
	}
	if len(elegidos) == 0 {
		return []SemaforoConEstado{}, nil
	}
	var estados map[string]map[string]dominio.EstadoAcceso
	if recuadro == nil {
		estados, err = n.trafico.EstadoSemaforos(ctx, nil)
	} else {
		estados, err = n.trafico.EstadoSemaforos(ctx, ids)
	}
	if err != nil {
		return nil, err
	}
	salida := make([]SemaforoConEstado, len(elegidos))
	for i, s := range elegidos {
		salida[i] = conEstado(s, estados[s.ID])
	}
	return salida, nil
}

// Semaforo con su estado actual.
func (n *Navegacion) Semaforo(ctx context.Context, id string) (SemaforoConEstado, error) {
	_, porID, err := n.estaticos(ctx)
	if err != nil {
		return SemaforoConEstado{}, err
	}
	s, ok := porID[id]
	if !ok {
		return SemaforoConEstado{}, fmt.Errorf("semáforo %q: %w", id, dominio.ErrNoEncontrado)
	}
	estados, err := n.trafico.EstadoSemaforos(ctx, []string{id})
	if err != nil {
		return SemaforoConEstado{}, err
	}
	return conEstado(s, estados[id]), nil
}

func conEstado(s dominio.Semaforo, estados map[string]dominio.EstadoAcceso) SemaforoConEstado {
	accesos := make([]AccesoConEstado, len(s.Accesos))
	for i, a := range s.Accesos {
		accesos[i] = AccesoConEstado{Acceso: a}
		if e, ok := estados[a.ID]; ok {
			accesos[i].EstadoAcceso = &e
		}
	}
	return SemaforoConEstado{ID: s.ID, Nombre: s.Nombre, Calles: s.Calles, Lat: s.Lat, Lon: s.Lon, Accesos: accesos}
}

// tieneAcceso indica si se puede llegar al semáforo con ese rumbo.
func tieneAcceso(s dominio.Semaforo, rumbo float64) bool {
	for _, a := range s.Accesos {
		if geo.DiferenciaAngular(a.Rumbo, rumbo) <= toleranciaAccesoGrados {
			return true
		}
	}
	return false
}

// SemaforosEnRuta: los semáforos por los que pasa el trazado, en orden.
// Descarta los que quedan cerca pero en una calle transversal: el rumbo de la
// ruta al llegar debe coincidir con alguno de sus accesos.
func (n *Navegacion) SemaforosEnRuta(ctx context.Context, pl *geo.Polilinea) ([]dominio.SemaforoEnRuta, error) {
	todos, _, err := n.estaticos(ctx)
	if err != nil {
		return nil, err
	}
	var en []dominio.SemaforoEnRuta
	for _, s := range todos {
		pr := pl.Proyectar(geo.Punto{Lat: s.Lat, Lon: s.Lon}, 0)
		if pr.SeparacionM > toleranciaRutaM {
			continue
		}
		rumbo := pr.RumboSegmento
		if pr.RecorridoM > 5 {
			rumbo = geo.Rumbo(pl.PuntoEn(math.Max(0, pr.RecorridoM-tramoLlegadaM)), pr.Punto)
		}
		if !tieneAcceso(s, rumbo) {
			continue
		}
		en = append(en, dominio.SemaforoEnRuta{
			ID: s.ID, Nombre: s.Nombre, Lat: s.Lat, Lon: s.Lon,
			DistanciaDesdeInicioM: math.Round(pr.RecorridoM), RumboLlegada: rumbo,
		})
	}
	sort.Slice(en, func(i, j int) bool { return en[i].DistanciaDesdeInicioM < en[j].DistanciaDesdeInicioM })
	return en, nil
}

// ProximoEnRuta: el primer semáforo de la ruta que aún no se cruza.
func (n *Navegacion) ProximoEnRuta(ctx context.Context, enRuta []dominio.SemaforoEnRuta, recorridoM float64) (*dominio.ProximoSemaforo, error) {
	for _, s := range enRuta {
		if s.DistanciaDesdeInicioM >= recorridoM-5 {
			_, porID, err := n.estaticos(ctx)
			if err != nil {
				return nil, err
			}
			return n.completar(ctx, porID[s.ID], math.Max(0, s.DistanciaDesdeInicioM-recorridoM), s.RumboLlegada)
		}
	}
	return nil, nil
}

// ProximoPorRumbo: sin ruta, el semáforo más cercano hacia donde avanza el usuario.
func (n *Navegacion) ProximoPorRumbo(ctx context.Context, p geo.Punto, rumbo float64) (*dominio.ProximoSemaforo, error) {
	todos, _, err := n.estaticos(ctx)
	if err != nil {
		return nil, err
	}
	var mejor *dominio.Semaforo
	mejorD := math.Inf(1)
	for i := range todos {
		s := &todos[i]
		q := geo.Punto{Lat: s.Lat, Lon: s.Lon}
		d := geo.Distancia(p, q)
		if d > alcanceSinRutaM || d >= mejorD {
			continue
		}
		if d > 15 && geo.DiferenciaAngular(geo.Rumbo(p, q), rumbo) > conoSinRutaGrado {
			continue
		}
		if !tieneAcceso(*s, rumbo) {
			continue
		}
		mejor, mejorD = s, d
	}
	if mejor == nil {
		return nil, nil
	}
	return n.completar(ctx, *mejor, mejorD, rumbo)
}

// completar agrega el estado del acceso por el que llega el usuario.
func (n *Navegacion) completar(ctx context.Context, s dominio.Semaforo, distanciaM, rumbo float64) (*dominio.ProximoSemaforo, error) {
	p := &dominio.ProximoSemaforo{
		ID: s.ID, Nombre: s.Nombre, Calles: s.Calles, DistanciaM: int(math.Round(distanciaM)),
		EstadoAcceso: dominio.EstadoAcceso{Color: "desconocido"},
	}
	var acceso *dominio.Acceso
	mejor := toleranciaAccesoGrados + 10
	for i, a := range s.Accesos {
		if d := geo.DiferenciaAngular(a.Rumbo, rumbo); d <= mejor {
			acceso, mejor = &s.Accesos[i], d
		}
	}
	if acceso == nil {
		return p, nil
	}
	p.Acceso = acceso.ID
	estados, err := n.trafico.EstadoSemaforos(ctx, []string{s.ID})
	if err != nil {
		slog.Warn("sin estado del semáforo", "id", s.ID, "error", err)
		return p, nil
	}
	if e, ok := estados[s.ID][acceso.ID]; ok {
		p.EstadoAcceso = e
	}
	return p, nil
}

// CalleConEstado: una calle con su geometría y su tráfico actual.
type CalleConEstado struct {
	ID                string       `json:"id"`
	Nombre            string       `json:"nombre"`
	Nivel             string       `json:"nivel"`
	VelocidadKmh      float64      `json:"velocidad_kmh"`
	VelocidadLibreKmh float64      `json:"velocidad_libre_kmh"`
	Vehiculos         int          `json:"vehiculos"`
	Forma             [][2]float64 `json:"forma"`
}

// Trafico por calle; por defecto omite las calles sin vehículos («libre»).
func (n *Navegacion) Trafico(ctx context.Context, recuadro *geo.Recuadro, incluirLibres bool) ([]CalleConEstado, error) {
	calles, err := n.callesEstaticas(ctx)
	if err != nil {
		return nil, err
	}
	estados, err := n.trafico.Trafico(ctx)
	if err != nil {
		return nil, err
	}
	porID := make(map[string]dominio.EstadoCalle, len(estados))
	for _, e := range estados {
		porID[e.ID] = e
	}
	salida := []CalleConEstado{}
	for _, c := range calles {
		e, ok := porID[c.ID]
		if !ok || (!incluirLibres && e.Nivel == "libre") {
			continue
		}
		if recuadro != nil && !tocaRecuadro(c.Forma, *recuadro) {
			continue
		}
		salida = append(salida, CalleConEstado{
			ID: c.ID, Nombre: c.Nombre, Nivel: e.Nivel, VelocidadKmh: e.VelocidadKmh,
			VelocidadLibreKmh: c.VelocidadLibreKmh, Vehiculos: e.Vehiculos, Forma: c.Forma,
		})
	}
	return salida, nil
}

func tocaRecuadro(forma [][2]float64, r geo.Recuadro) bool {
	for _, p := range forma {
		if r.Contiene(geo.Punto{Lat: p[0], Lon: p[1]}) {
			return true
		}
	}
	return false
}
