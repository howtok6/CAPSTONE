package historico

import (
	"math"
	"testing"
	"time"

	"via/backend/internal/geo"
)

// Una calle de ~930 m hacia el oriente y su calzada contraria, con datos solo en punta tarde.
func tablaDePrueba(t *testing.T) *Tabla {
	t.Helper()
	ida := [][2]float64{{-33.4400, -70.6500}, {-33.4400, -70.6400}}
	vuelta := [][2]float64{{-33.4401, -70.6400}, {-33.4401, -70.6500}}
	tabla, err := Nueva(Archivo{
		Franjas: []FranjaJSON{{ID: "punta_tarde", Nombre: "Punta tarde"}},
		Calles: []CalleJSON{
			{ID: "ida", LargoM: 930, LibreKmh: 50, Forma: ida,
				Vel: map[string]map[string]float64{"punta_tarde": {Actual: 10, Adaptativo: 20}}},
			{ID: "vuelta", LargoM: 930, LibreKmh: 50, Forma: vuelta,
				Vel: map[string]map[string]float64{"punta_tarde": {Actual: 40}}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	return tabla
}

func hora(t *testing.T, texto string) time.Time {
	t.Helper()
	m, err := time.Parse(time.RFC3339, texto)
	if err != nil {
		t.Fatal(err)
	}
	return m
}

func TestFranjaSegunLaHora(t *testing.T) {
	tabla := tablaDePrueba(t)
	casos := []struct {
		momento string
		franja  string
		ok      bool
	}{
		{"2026-11-11T18:15:00-03:00", "punta_tarde", true}, // miércoles en punta tarde
		{"2026-11-11T12:00:00-03:00", "", false},           // valle: la tabla de prueba no lo trae
		{"2026-11-11T03:00:00-03:00", "", false},           // madrugada: sin datos
		{"2026-11-14T18:15:00-03:00", "", false},           // sábado: sería valle, que no está
		{"2026-11-11T21:15:00Z", "punta_tarde", true},      // misma hora, expresada en UTC
	}
	for _, c := range casos {
		id, _, ok := tabla.Franja(hora(t, c.momento))
		if id != c.franja || ok != c.ok {
			t.Errorf("%s: franja %q ok=%v; se esperaba %q ok=%v", c.momento, id, ok, c.franja, c.ok)
		}
	}
}

func TestEstimarUsaLaCalzadaDelSentidoDelViaje(t *testing.T) {
	tabla := tablaDePrueba(t)
	momento := hora(t, "2026-11-11T18:15:00-03:00")
	haciaOriente := []geo.Punto{{Lat: -33.44003, Lon: -70.6490}, {Lat: -33.44003, Lon: -70.6410}}
	e, ok := tabla.Estimar(haciaOriente, momento)
	if !ok {
		t.Fatal("debía haber estimación en punta tarde")
	}
	if e.CubiertoM < 0.95*e.TotalM {
		t.Fatalf("cubierto %.0f de %.0f m", e.CubiertoM, e.TotalM)
	}
	// 10 km/h actual y 20 km/h adaptativo: el adaptativo demora la mitad
	esperado := e.TotalM / (10 / 3.6)
	if math.Abs(e.SegActual-esperado) > 0.05*esperado {
		t.Errorf("actual %.0f s; se esperaban ~%.0f", e.SegActual, esperado)
	}
	if math.Abs(e.SegAdaptativo-e.SegActual/2) > 0.05*e.SegActual {
		t.Errorf("adaptativo %.0f s; se esperaba la mitad de %.0f", e.SegAdaptativo, e.SegActual)
	}

	// En sentido contrario calza con la otra calzada (40 km/h), que no tiene dato adaptativo
	haciaPoniente := []geo.Punto{{Lat: -33.44008, Lon: -70.6410}, {Lat: -33.44008, Lon: -70.6490}}
	v, _ := tabla.Estimar(haciaPoniente, momento)
	if math.Abs(v.SegActual-v.TotalM/(40/3.6)) > 0.05*v.SegActual || v.SegAdaptativo != v.SegActual {
		t.Errorf("sentido contrario: actual %.0f s, adaptativo %.0f s", v.SegActual, v.SegAdaptativo)
	}
}

func TestEstimarFueraDeLaRedNoCubreNada(t *testing.T) {
	tabla := tablaDePrueba(t)
	lejos := []geo.Punto{{Lat: -33.50, Lon: -70.70}, {Lat: -33.50, Lon: -70.69}}
	e, ok := tabla.Estimar(lejos, hora(t, "2026-11-11T18:15:00-03:00"))
	if !ok || e.CubiertoM != 0 || e.TotalM < 900 {
		t.Errorf("ok=%v cubierto=%.0f total=%.0f", ok, e.CubiertoM, e.TotalM)
	}
	// Una calle que cruza la red en perpendicular tampoco calza
	cruce := []geo.Punto{{Lat: -33.4410, Lon: -70.6450}, {Lat: -33.4390, Lon: -70.6450}}
	if e, _ := tabla.Estimar(cruce, hora(t, "2026-11-11T18:15:00-03:00")); e.CubiertoM != 0 {
		t.Errorf("el cruce perpendicular cubrió %.0f m", e.CubiertoM)
	}
}
