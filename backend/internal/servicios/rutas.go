package servicios

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"strings"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

// MaxParadas: origen, hasta tres paradas intermedias y destino.
const MaxParadas = 5

// Rutas calcula rutas en auto, les agrega los semáforos por los que pasan y,
// si hay tabla de tiempos, estima cuánto demoran a la hora pedida y recomienda una.
type Rutas struct {
	enrutador Enrutador
	nav       *Navegacion
	estimador EstimadorRutas
}

// NuevasRutas crea el servicio.
func NuevasRutas(e Enrutador, nav *Navegacion) *Rutas { return &Rutas{enrutador: e, nav: nav} }

// ConEstimador activa las recomendaciones según la hora.
func (r *Rutas) ConEstimador(est EstimadorRutas) *Rutas {
	r.estimador = est
	return r
}

// Calcular rutas entre las paradas para salir ahora.
func (r *Rutas) Calcular(ctx context.Context, paradas []geo.Punto, alternativas bool) ([]dominio.Ruta, error) {
	return r.CalcularEn(ctx, paradas, alternativas, time.Now())
}

// CalcularEn calcula rutas entre las paradas para salir en `momento`. Con tabla
// de tiempos y datos para esa hora, las ordena por duración estimada y marca la
// recomendada; si no, quedan como las entrega el enrutador (la más rápida a
// flujo libre primero).
func (r *Rutas) CalcularEn(ctx context.Context, paradas []geo.Punto, alternativas bool,
	momento time.Time) ([]dominio.Ruta, error) {
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
	r.recomendar(rutas, momento)
	return rutas, nil
}

// recomendar estima cada ruta, las ordena de menor a mayor duración y marca la primera.
func (r *Rutas) recomendar(rutas []dominio.Ruta, momento time.Time) {
	if r.estimador == nil || len(rutas) == 0 {
		return
	}
	estimaciones := make([]*dominio.EstimacionRuta, len(rutas))
	for i := range rutas {
		tramo, ok := r.estimador.Estimar(geo.DesdeLatLon(rutas[i].Trazado), momento)
		if !ok || tramo.TotalM <= 0 {
			return // sin datos para esa hora: no se recomienda nada
		}
		estimaciones[i] = estimar(rutas[i], tramo)
	}
	for i := range rutas {
		rutas[i].Estimacion = estimaciones[i]
	}
	sort.SliceStable(rutas, func(i, j int) bool {
		return rutas[i].Estimacion.DuracionMin < rutas[j].Estimacion.DuracionMin
	})
	rutas[0].Recomendada = true
	rutas[0].Motivo = motivo(rutas)
}

// estimar combina lo que la tabla sabe del trazado con la duración del enrutador.
//
// Dentro del eje simulado se usa el tiempo de la simulación. Fuera no hay datos:
// se toma la duración del enrutador (flujo libre), repartida por distancia, por el
// índice de congestión de la franja (calle típica del eje). Así una ruta no parece más
// rápida solo por salirse de la zona con datos. El control adaptativo solo cambia
// el tramo dentro del eje.
func estimar(ruta dominio.Ruta, tramo dominio.TramoEstimado) *dominio.EstimacionRuta {
	cobertura := math.Min(1, tramo.CubiertoM/tramo.TotalM)
	indice := math.Max(1, tramo.IndiceCongestion)
	fuera := ruta.DuracionMin * 60 * (1 - cobertura) * indice
	actual := (tramo.SegActual + fuera) / 60
	adaptativo := (tramo.SegAdaptativo + fuera) / 60
	return &dominio.EstimacionRuta{
		Franja:                tramo.Franja,
		FranjaNombre:          tramo.FranjaNombre,
		DuracionMin:           redondear(actual, 1),
		DuracionAdaptativoMin: redondear(adaptativo, 1),
		AhorroAdaptativoMin:   redondear(actual-adaptativo, 1),
		Cobertura:             redondear(cobertura, 2),
		Fuente:                "simulacion",
	}
}

// motivo explica en una frase por qué se recomienda la primera ruta.
func motivo(rutas []dominio.Ruta) string {
	mejor := rutas[0].Estimacion
	texto := fmt.Sprintf("La más rápida en %s: %.0f min", strings.ToLower(mejor.FranjaNombre), mejor.DuracionMin)
	if len(rutas) > 1 {
		if dif := rutas[1].Estimacion.DuracionMin - mejor.DuracionMin; dif >= 1 {
			texto += fmt.Sprintf(", %.0f min menos que la siguiente", dif)
		} else {
			texto += "; la siguiente demora casi lo mismo"
		}
	}
	texto += "."
	if mejor.Cobertura < 0.2 {
		texto += " Estimación con pocos datos: casi toda la ruta va fuera del eje simulado."
	}
	return texto
}

func redondear(x float64, decimales int) float64 {
	f := math.Pow(10, float64(decimales))
	return math.Round(x*f) / f
}
