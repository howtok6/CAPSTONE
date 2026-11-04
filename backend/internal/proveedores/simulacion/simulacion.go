// Package simulacion es el cliente del servicio de simulación (simulacion/),
// el entorno de pruebas que hace de proveedor de tráfico: semáforos, estado por
// acceso, tráfico por calle y viajes simulados.
//
// En producción se reemplaza por otro proveedor con el mismo contrato.
package simulacion

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/proveedores/clientehttp"
)

const servicio = "simulación"

// Cliente del servicio de simulación.
type Cliente struct {
	base string
	http *clientehttp.Cliente
}

// Nuevo crea el cliente; base es, por ejemplo, http://127.0.0.1:8000.
func Nuevo(base string, espera time.Duration) *Cliente {
	return &Cliente{base: strings.TrimRight(base, "/"), http: clientehttp.Nuevo(espera, "")}
}

func (c *Cliente) obtener(ctx context.Context, ruta string, destino any) error {
	return c.http.Hacer(ctx, servicio, http.MethodGet, c.base+ruta, nil, destino)
}

// Estado del servicio: si está listo, tiempo simulado y vehículos en la red.
type Estado struct {
	Lista         bool    `json:"lista"`
	Escenario     string  `json:"escenario"`
	Controlador   string  `json:"controlador"`
	TiempoSim     float64 `json:"tiempo_sim"`
	Vehiculos     int     `json:"vehiculos"`
	ViajesActivos int     `json:"viajes_activos"`
}

// Estado consulta GET /estado.
func (c *Cliente) Estado(ctx context.Context) (Estado, error) {
	var e Estado
	err := c.obtener(ctx, "/estado", &e)
	return e, err
}

// Semaforos consulta GET /semaforos (estático).
func (c *Cliente) Semaforos(ctx context.Context) ([]dominio.Semaforo, error) {
	var s []dominio.Semaforo
	err := c.obtener(ctx, "/semaforos", &s)
	return s, err
}

// EstadoSemaforos consulta GET /semaforos/estado: semáforo -> acceso -> estado.
func (c *Cliente) EstadoSemaforos(ctx context.Context, ids []string) (map[string]map[string]dominio.EstadoAcceso, error) {
	ruta := "/semaforos/estado"
	if len(ids) > 0 {
		ruta += "?ids=" + url.QueryEscape(strings.Join(ids, ","))
	}
	var r struct {
		Semaforos map[string]map[string]dominio.EstadoAcceso `json:"semaforos"`
	}
	err := c.obtener(ctx, ruta, &r)
	return r.Semaforos, err
}

// Calles consulta GET /red/calles (estático).
func (c *Cliente) Calles(ctx context.Context) ([]dominio.Calle, error) {
	var s []dominio.Calle
	err := c.obtener(ctx, "/red/calles", &s)
	return s, err
}

// Trafico consulta GET /trafico.
func (c *Cliente) Trafico(ctx context.Context) ([]dominio.EstadoCalle, error) {
	var r struct {
		Calles []dominio.EstadoCalle `json:"calles"`
	}
	err := c.obtener(ctx, "/trafico", &r)
	return r.Calles, err
}

// Destinos consulta GET /destinos: recorridos de demostración.
func (c *Cliente) Destinos(ctx context.Context) ([]dominio.DestinoSimulado, error) {
	var d []dominio.DestinoSimulado
	err := c.obtener(ctx, "/destinos", &d)
	return d, err
}

// CrearViaje: POST /viajes con el índice del destino de demostración.
func (c *Cliente) CrearViaje(ctx context.Context, ruta int) (dominio.ViajeSimulado, error) {
	var v dominio.ViajeSimulado
	err := c.http.Hacer(ctx, servicio, http.MethodPost, c.base+"/viajes", map[string]int{"ruta": ruta}, &v)
	return v, err
}

// Viaje: GET /viajes/{id}.
func (c *Cliente) Viaje(ctx context.Context, id string) (dominio.ViajeSimulado, error) {
	var v dominio.ViajeSimulado
	err := c.obtener(ctx, "/viajes/"+url.PathEscape(id), &v)
	return v, err
}

// FinalizarViaje: DELETE /viajes/{id}.
func (c *Cliente) FinalizarViaje(ctx context.Context, id string) error {
	err := c.http.Hacer(ctx, servicio, http.MethodDelete, c.base+"/viajes/"+url.PathEscape(id), nil, nil)
	if err != nil {
		return fmt.Errorf("finalizar viaje simulado %s: %w", id, err)
	}
	return nil
}
