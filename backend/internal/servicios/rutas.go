package servicios

import (
	"context"
	"fmt"
	"log/slog"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

// MaxParadas: origen, hasta tres paradas intermedias y destino.
const MaxParadas = 5

// Rutas calcula rutas en auto y les agrega los semáforos por los que pasan.
type Rutas struct {
	enrutador Enrutador
	nav       *Navegacion
}

// NuevasRutas crea el servicio.
func NuevasRutas(e Enrutador, nav *Navegacion) *Rutas { return &Rutas{enrutador: e, nav: nav} }

// Calcular rutas entre las paradas, la más rápida primero.
func (r *Rutas) Calcular(ctx context.Context, paradas []geo.Punto, alternativas bool) ([]dominio.Ruta, error) {
	if len(paradas) < 2 || len(paradas) > MaxParadas {
		return nil, fmt.Errorf("%w: se necesitan entre 2 y %d paradas", dominio.ErrInvalido, MaxParadas)
	}
	for i, p := range paradas {
		if !p.Valido() {
			return nil, fmt.Errorf("%w: la parada %d no tiene coordenadas válidas", dominio.ErrInvalido, i+1)
		}
	}
	rutas, err := r.enrutador.Rutas(ctx, paradas, alternativas)
	if err != nil {
		return nil, err
	}
	for i := range rutas {
		en, err := r.nav.SemaforosEnRuta(ctx, geo.NuevaPolilinea(geo.DesdeLatLon(rutas[i].Trazado)))
		if err != nil {
			// Sin proveedor de tráfico la ruta sigue sirviendo, solo sin semáforos.
			slog.Warn("ruta sin semáforos: proveedor de tráfico no disponible", "error", err)
			en = nil
		}
		if en == nil {
			en = []dominio.SemaforoEnRuta{}
		}
		rutas[i].Semaforos = en
	}
	return rutas, nil
}
