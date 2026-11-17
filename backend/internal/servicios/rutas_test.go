package servicios

import (
	"context"
	"strings"
	"testing"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

// Dos rutas: la del eje es la más rápida a flujo libre; la alternativa va por fuera.
type enrutadorDosRutas struct{}

func (enrutadorDosRutas) Rutas(context.Context, []geo.Punto, bool) ([]dominio.Ruta, error) {
	return []dominio.Ruta{
		{DistanciaKm: 3, DuracionMin: 6, Trazado: [][2]float64{{-33.44, -70.65}, {-33.44, -70.62}}},
		{DistanciaKm: 4, DuracionMin: 8, Trazado: [][2]float64{{-33.45, -70.65}, {-33.45, -70.62}}},
	}, nil
}

// En punta, el eje está congestionado (25 min; 15 con control adaptativo) y de la
// alternativa no hay datos (8 min del enrutador por el índice 2 = 16 min).
type estimadorFalso struct{ hayDatos bool }

func (e estimadorFalso) Estimar(trazado []geo.Punto, _ time.Time) (dominio.TramoEstimado, bool) {
	if !e.hayDatos {
		return dominio.TramoEstimado{}, false
	}
	t := dominio.TramoEstimado{Franja: "punta_tarde", FranjaNombre: "Punta tarde", TotalM: 3000, IndiceCongestion: 2}
	if trazado[0].Lat > -33.445 {
		t.CubiertoM, t.SegActual, t.SegAdaptativo = 3000, 1500, 900
	}
	return t, true
}

var paradasDePrueba = []geo.Punto{{Lat: -33.44, Lon: -70.65}, {Lat: -33.44, Lon: -70.62}}

func TestRecomiendaLaRutaMasRapidaALaHoraPedida(t *testing.T) {
	r := NuevasRutas(enrutadorDosRutas{}, NuevaNavegacion(nuevoTraficoFalso())).ConEstimador(estimadorFalso{true})
	rutas, err := r.CalcularEn(context.Background(), paradasDePrueba, true, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if len(rutas) != 2 || rutas[0].DistanciaKm != 4 {
		t.Fatalf("la alternativa debía quedar primera: %+v", rutas)
	}
	mejor, eje := rutas[0], rutas[1]
	if !mejor.Recomendada || eje.Recomendada {
		t.Errorf("recomendada: %v y %v", mejor.Recomendada, eje.Recomendada)
	}
	if mejor.Estimacion.DuracionMin != 16 || mejor.Estimacion.Cobertura != 0 {
		t.Errorf("alternativa: %+v", *mejor.Estimacion)
	}
	e := eje.Estimacion
	if e.DuracionMin != 25 || e.DuracionAdaptativoMin != 15 || e.AhorroAdaptativoMin != 10 || e.Cobertura != 1 {
		t.Errorf("eje: %+v", *e)
	}
	for _, parte := range []string{"punta tarde", "16 min", "9 min menos", "pocos datos"} {
		if !strings.Contains(mejor.Motivo, parte) {
			t.Errorf("al motivo le falta %q: %s", parte, mejor.Motivo)
		}
	}
	// El enrutador no se toca: la duración a flujo libre sigue en la ruta
	if mejor.DuracionMin != 8 || eje.DuracionMin != 6 {
		t.Errorf("duración del enrutador alterada: %v y %v", mejor.DuracionMin, eje.DuracionMin)
	}
}

func TestSinDatosParaLaHoraQuedanComoLasEntregaElEnrutador(t *testing.T) {
	nav := NuevaNavegacion(nuevoTraficoFalso())
	for nombre, r := range map[string]*Rutas{
		"sin tabla":          NuevasRutas(enrutadorDosRutas{}, nav),
		"tabla sin esa hora": NuevasRutas(enrutadorDosRutas{}, nav).ConEstimador(estimadorFalso{false}),
	} {
		rutas, err := r.Calcular(context.Background(), paradasDePrueba, true)
		if err != nil {
			t.Fatal(err)
		}
		if rutas[0].DistanciaKm != 3 || rutas[0].Estimacion != nil || rutas[0].Recomendada || rutas[0].Motivo != "" {
			t.Errorf("%s: %+v", nombre, rutas[0])
		}
	}
}
