// Package api expone el contrato HTTP /v1 que consume la app móvil.
package api

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
	"via/backend/internal/servicios"
)

// Dependencias del manejador HTTP.
type Dependencias struct {
	Geocodificador servicios.Geocodificador
	Rutas          *servicios.Rutas
	Navegacion     *servicios.Navegacion
	Viajes         *servicios.Viajes
	// Comprobaciones de salud de los servicios de los que depende, por nombre.
	Salud   map[string]func(context.Context) (any, error)
	Version string
}

type manejador struct{ Dependencias }

// Nuevo arma el enrutador HTTP con sus middlewares.
func Nuevo(d Dependencias) http.Handler {
	m := &manejador{d}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/salud", m.salud)
	mux.HandleFunc("GET /v1/lugares", m.buscarLugares)
	mux.HandleFunc("GET /v1/lugares/inverso", m.nombrarLugar)
	mux.HandleFunc("POST /v1/rutas", m.calcularRutas)
	mux.HandleFunc("GET /v1/semaforos", m.semaforos)
	mux.HandleFunc("GET /v1/semaforos/proximo", m.proximoSemaforo)
	mux.HandleFunc("GET /v1/semaforos/{id}", m.semaforo)
	mux.HandleFunc("GET /v1/trafico", m.trafico)
	mux.HandleFunc("GET /v1/simulacion/destinos", m.destinosSimulados)
	mux.HandleFunc("POST /v1/viajes", m.crearViaje)
	mux.HandleFunc("GET /v1/viajes/{id}", m.verViaje)
	mux.HandleFunc("POST /v1/viajes/{id}/ubicacion", m.registrarUbicacion)
	mux.HandleFunc("DELETE /v1/viajes/{id}", m.finalizarViaje)
	return encadenar(mux, cors, registrar, recuperar)
}

// --- salud -------------------------------------------------------------

type estadoServicio struct {
	OK      bool   `json:"ok"`
	Detalle any    `json:"detalle,omitempty"`
	Error   string `json:"error,omitempty"`
}

func (m *manejador) salud(w http.ResponseWriter, r *http.Request) {
	ctx, cancelar := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancelar()
	estado := "ok"
	servicios := map[string]estadoServicio{}
	for nombre, comprobar := range m.Salud {
		detalle, err := comprobar(ctx)
		if err != nil {
			estado = "degradado"
			servicios[nombre] = estadoServicio{Error: err.Error()}
			continue
		}
		servicios[nombre] = estadoServicio{OK: true, Detalle: detalle}
	}
	responder(w, http.StatusOK, map[string]any{"estado": estado, "version": m.Version, "servicios": servicios})
}

// --- lugares y rutas ---------------------------------------------------

func (m *manejador) buscarLugares(w http.ResponseWriter, r *http.Request) {
	lugares, err := m.Geocodificador.Buscar(r.Context(), r.URL.Query().Get("q"))
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, lugares)
}

func (m *manejador) nombrarLugar(w http.ResponseWriter, r *http.Request) {
	p, err := punto(r)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, m.Geocodificador.Nombrar(r.Context(), p))
}

type solicitudRutas struct {
	Paradas      []geo.Punto `json:"paradas"`
	Alternativas *bool       `json:"alternativas"`
}

func (m *manejador) calcularRutas(w http.ResponseWriter, r *http.Request) {
	var s solicitudRutas
	if err := leerJSON(r, &s); err != nil {
		fallar(w, r, err)
		return
	}
	alternativas := s.Alternativas == nil || *s.Alternativas
	rutas, err := m.Rutas.Calcular(r.Context(), s.Paradas, alternativas)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, rutas)
}

// --- semáforos y tráfico -----------------------------------------------

func (m *manejador) semaforos(w http.ResponseWriter, r *http.Request) {
	recuadro, err := recuadroOpcional(r)
	if err != nil {
		fallar(w, r, err)
		return
	}
	s, err := m.Navegacion.Semaforos(r.Context(), recuadro)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, s)
}

func (m *manejador) semaforo(w http.ResponseWriter, r *http.Request) {
	s, err := m.Navegacion.Semaforo(r.Context(), r.PathValue("id"))
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, s)
}

func (m *manejador) proximoSemaforo(w http.ResponseWriter, r *http.Request) {
	p, err := punto(r)
	if err != nil {
		fallar(w, r, err)
		return
	}
	rumbo, err := numero(r.URL.Query(), "rumbo")
	if err != nil || rumbo < 0 || rumbo >= 360 {
		fallar(w, r, fmt.Errorf("%w: rumbo debe estar en [0, 360)", dominio.ErrInvalido))
		return
	}
	prox, err := m.Navegacion.ProximoPorRumbo(r.Context(), p, rumbo)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, map[string]any{"proximo_semaforo": prox})
}

func (m *manejador) trafico(w http.ResponseWriter, r *http.Request) {
	recuadro, err := recuadroOpcional(r)
	if err != nil {
		fallar(w, r, err)
		return
	}
	incluirLibres := r.URL.Query().Get("incluir_libres") == "true"
	t, err := m.Navegacion.Trafico(r.Context(), recuadro, incluirLibres)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, t)
}

// --- viajes ------------------------------------------------------------

func (m *manejador) destinosSimulados(w http.ResponseWriter, r *http.Request) {
	d, err := m.Viajes.DestinosSimulados(r.Context())
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, d)
}

func (m *manejador) crearViaje(w http.ResponseWriter, r *http.Request) {
	var s servicios.SolicitudViaje
	if err := leerJSON(r, &s); err != nil {
		fallar(w, r, err)
		return
	}
	v, err := m.Viajes.Crear(r.Context(), s)
	if err != nil {
		fallar(w, r, err)
		return
	}
	w.Header().Set("Location", "/v1/viajes/"+v.ID)
	responder(w, http.StatusCreated, v)
}

func (m *manejador) verViaje(w http.ResponseWriter, r *http.Request) {
	v, err := m.Viajes.Obtener(r.Context(), r.PathValue("id"))
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, v)
}

func (m *manejador) registrarUbicacion(w http.ResponseWriter, r *http.Request) {
	var u dominio.Ubicacion
	if err := leerJSON(r, &u); err != nil {
		fallar(w, r, err)
		return
	}
	v, err := m.Viajes.RegistrarUbicacion(r.Context(), r.PathValue("id"), u)
	if err != nil {
		fallar(w, r, err)
		return
	}
	responder(w, http.StatusOK, v)
}

func (m *manejador) finalizarViaje(w http.ResponseWriter, r *http.Request) {
	if err := m.Viajes.Finalizar(r.Context(), r.PathValue("id")); err != nil {
		fallar(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// --- parámetros --------------------------------------------------------

func punto(r *http.Request) (geo.Punto, error) {
	q := r.URL.Query()
	lat, err := numero(q, "lat")
	if err != nil {
		return geo.Punto{}, err
	}
	lon, err := numero(q, "lon")
	if err != nil {
		return geo.Punto{}, err
	}
	p := geo.Punto{Lat: lat, Lon: lon}
	if !p.Valido() {
		return geo.Punto{}, fmt.Errorf("%w: lat y lon deben ser coordenadas válidas", dominio.ErrInvalido)
	}
	return p, nil
}

func recuadroOpcional(r *http.Request) (*geo.Recuadro, error) {
	b := strings.TrimSpace(r.URL.Query().Get("bbox"))
	if b == "" {
		return nil, nil
	}
	rec, err := geo.ParsearRecuadro(b)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", dominio.ErrInvalido, err)
	}
	return &rec, nil
}
