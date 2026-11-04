package nominatim

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"via/backend/internal/geo"
)

func TestBuscarUsaCacheYRespetaElIntervalo(t *testing.T) {
	var llamadas atomic.Int32
	var agente string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		llamadas.Add(1)
		agente = r.Header.Get("User-Agent")
		if r.URL.Query().Get("bounded") != "1" || r.URL.Query().Get("viewbox") != RecuadroSantiago {
			t.Errorf("la búsqueda no se limitó a Santiago: %s", r.URL.RawQuery)
		}
		_, _ = w.Write([]byte(`[{"name":"Plaza de Armas","display_name":"Plaza de Armas, Santiago","lat":"-33.4378","lon":"-70.6504"},
			{"name":"","display_name":"Sin coordenadas","lat":"x","lon":"y"}]`))
	}))
	defer srv.Close()
	c := Nuevo(srv.URL, time.Second, "via-prueba")
	c.Intervalo = 80 * time.Millisecond
	ctx := context.Background()

	inicio := time.Now()
	l, err := c.Buscar(ctx, "Plaza de Armas")
	if err != nil || len(l) != 1 || l[0].Nombre != "Plaza de Armas" || l[0].Lat != -33.4378 {
		t.Fatalf("buscar = %+v, %v", l, err)
	}
	if _, err := c.Buscar(ctx, "plaza de armas "); err != nil { // misma búsqueda: caché
		t.Fatal(err)
	}
	if llamadas.Load() != 1 {
		t.Errorf("llamadas = %d; la segunda búsqueda debía salir de la caché", llamadas.Load())
	}
	if _, err := c.Buscar(ctx, "Providencia"); err != nil {
		t.Fatal(err)
	}
	if time.Since(inicio) < 80*time.Millisecond {
		t.Error("dos consultas al servidor no respetaron el intervalo mínimo")
	}
	if agente != "via-prueba" {
		t.Errorf("User-Agent = %q", agente)
	}
	if _, err := c.Buscar(ctx, "  "); err == nil {
		t.Error("una búsqueda vacía debe ser inválida")
	}
}

func TestNombrarConRespaldo(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()
	c := Nuevo(srv.URL, time.Second, "")
	l := c.Nombrar(context.Background(), geo.Punto{Lat: -33.44, Lon: -70.65})
	if l.Nombre != "-33.4400, -70.6500" || l.Lat != -33.44 {
		t.Errorf("respaldo = %+v", l)
	}
}
