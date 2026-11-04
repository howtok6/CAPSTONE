// Package servicios contiene la lógica de negocio del backend. Depende solo de
// interfaces: la simulación, OSRM y Nominatim se inyectan y pueden reemplazarse
// (por ejemplo, la simulación por datos reales de semáforos).
package servicios

import (
	"context"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

// ProveedorTrafico entrega semáforos, su estado por acceso y el tráfico por calle.
// Hoy lo implementa el servicio de simulación.
type ProveedorTrafico interface {
	Semaforos(ctx context.Context) ([]dominio.Semaforo, error)
	EstadoSemaforos(ctx context.Context, ids []string) (map[string]map[string]dominio.EstadoAcceso, error)
	Calles(ctx context.Context) ([]dominio.Calle, error)
	Trafico(ctx context.Context) ([]dominio.EstadoCalle, error)
}

// SimuladorViajes crea viajes de demostración dentro de la simulación.
type SimuladorViajes interface {
	Destinos(ctx context.Context) ([]dominio.DestinoSimulado, error)
	CrearViaje(ctx context.Context, ruta int) (dominio.ViajeSimulado, error)
	Viaje(ctx context.Context, id string) (dominio.ViajeSimulado, error)
	FinalizarViaje(ctx context.Context, id string) error
}

// Enrutador calcula rutas en auto (OSRM).
type Enrutador interface {
	Rutas(ctx context.Context, paradas []geo.Punto, alternativas bool) ([]dominio.Ruta, error)
}

// Geocodificador busca lugares y nombra puntos (Nominatim).
type Geocodificador interface {
	Buscar(ctx context.Context, texto string) ([]dominio.Lugar, error)
	Nombrar(ctx context.Context, p geo.Punto) dominio.Lugar
}

// AlmacenViajes guarda los viajes activos (hoy en memoria).
type AlmacenViajes interface {
	Guardar(id string, v *ViajeInterno)
	Obtener(id string) (*ViajeInterno, bool)
	Eliminar(id string)
}
