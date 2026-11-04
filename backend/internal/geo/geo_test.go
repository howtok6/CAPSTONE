package geo

import (
	"math"
	"testing"
)

func cerca(t *testing.T, nombre string, obtenido, esperado, tolerancia float64) {
	t.Helper()
	if math.Abs(obtenido-esperado) > tolerancia {
		t.Errorf("%s = %.3f; se esperaba %.3f ± %.3f", nombre, obtenido, esperado, tolerancia)
	}
}

func TestDistanciaYRumbo(t *testing.T) {
	a := Punto{Lat: -33.44, Lon: -70.65}
	norte := Punto{Lat: -33.43, Lon: -70.65}
	este := Punto{Lat: -33.44, Lon: -70.64}
	cerca(t, "distancia 0,01° de latitud", Distancia(a, norte), 1111.95, 1)
	cerca(t, "distancia 0,01° de longitud", Distancia(a, este), 928.0, 2)
	cerca(t, "rumbo al norte", Rumbo(a, norte), 0, 0.01)
	cerca(t, "rumbo al este", Rumbo(a, este), 90, 0.1)
	cerca(t, "rumbo al sur", Rumbo(norte, a), 180, 0.01)
}

func TestDiferenciaAngular(t *testing.T) {
	casos := []struct{ a, b, d float64 }{{10, 350, 20}, {0, 180, 180}, {90, 270, 180}, {45, 45, 0}, {359, 1, 2}}
	for _, c := range casos {
		cerca(t, "diferencia", DiferenciaAngular(c.a, c.b), c.d, 1e-9)
	}
}

func TestParsearRecuadro(t *testing.T) {
	r, err := ParsearRecuadro("-70.7,-33.5,-70.5,-33.4")
	if err != nil {
		t.Fatal(err)
	}
	if !r.Contiene(Punto{Lat: -33.45, Lon: -70.6}) || r.Contiene(Punto{Lat: -33.3, Lon: -70.6}) {
		t.Error("Contiene no respeta el recuadro")
	}
	for _, malo := range []string{"", "1,2,3", "a,b,c,d", "-70.5,-33.4,-70.7,-33.5"} {
		if _, err := ParsearRecuadro(malo); err == nil {
			t.Errorf("%q debería ser inválido", malo)
		}
	}
}

func TestProyectar(t *testing.T) {
	// Trazado en L: 1 km al este y luego 1 km al norte.
	o := Punto{Lat: -33.44, Lon: -70.65}
	e := Punto{Lat: -33.44, Lon: -70.65 + 0.010774}
	n := Punto{Lat: -33.44 + 0.008993, Lon: e.Lon}
	pl := NuevaPolilinea([]Punto{o, e, n})
	cerca(t, "largo", pl.Largo(), 2000, 5)

	// A mitad del primer tramo, 30 m al sur.
	p := Punto{Lat: -33.44 - 0.00027, Lon: -70.65 + 0.005387}
	pr := pl.Proyectar(p, 0)
	cerca(t, "recorrido", pr.RecorridoM, 500, 3)
	cerca(t, "separación", pr.SeparacionM, 30, 1)
	cerca(t, "rumbo del tramo", pr.RumboSegmento, 90, 0.5)

	// Desde 1200 m ya no puede volver al primer tramo.
	pr = pl.Proyectar(p, 1200)
	if pr.RecorridoM < 1000 {
		t.Errorf("con desde=1200 se proyectó en %.0f m", pr.RecorridoM)
	}
	if !o.Valido() || (Punto{}).Valido() || (Punto{Lat: 91}).Valido() {
		t.Error("Valido no distingue puntos imposibles")
	}
}
