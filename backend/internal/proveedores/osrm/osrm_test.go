package osrm

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

const rutaDosTramos = `{"code":"Ok","routes":[{"distance":2500,"duration":360,
 "geometry":{"coordinates":[[-70.65,-33.44],[-70.64,-33.44],[-70.63,-33.43]]},
 "legs":[
  {"steps":[{"name":"Alameda","distance":900,"maneuver":{"type":"depart"}},
            {"name":"Portugal","distance":100,"maneuver":{"type":"turn","modifier":"left"}},
            {"name":"","distance":0,"maneuver":{"type":"arrive"}}]},
  {"steps":[{"name":"Portugal","distance":0,"maneuver":{"type":"depart"}},
            {"name":"Providencia","distance":1500,"maneuver":{"type":"turn","modifier":"right"}},
            {"name":"","distance":0,"maneuver":{"type":"arrive"}}]}]}]}`

func TestRutasUneTramosYOrdenaCoordenadas(t *testing.T) {
	var pedido string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		pedido = r.URL.String()
		_, _ = w.Write([]byte(rutaDosTramos))
	}))
	defer srv.Close()
	c := Nuevo(srv.URL, time.Second, "prueba")
	paradas := []geo.Punto{{Lat: -33.44, Lon: -70.65}, {Lat: -33.44, Lon: -70.64}, {Lat: -33.43, Lon: -70.63}}
	rutas, err := c.Rutas(context.Background(), paradas, false)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(pedido, "/route/v1/driving/-70.650000,-33.440000;-70.640000,-33.440000;") ||
		!strings.Contains(pedido, "alternatives=false") {
		t.Errorf("pedido = %s", pedido)
	}
	r := rutas[0]
	if r.DistanciaKm != 2.5 || r.DuracionMin != 6 || r.Trazado[0] != [2]float64{-33.44, -70.65} {
		t.Errorf("ruta = %+v", r)
	}
	tipos := []string{}
	for _, p := range r.Pasos {
		tipos = append(tipos, p.Tipo)
	}
	if strings.Join(tipos, ",") != "depart,turn,parada,turn,arrive" {
		t.Errorf("pasos = %v", tipos)
	}
}

func TestSinRuta(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"code":"NoRoute","message":"Impossible route"}`))
	}))
	defer srv.Close()
	_, err := Nuevo(srv.URL, time.Second, "").Rutas(context.Background(),
		[]geo.Punto{{Lat: -33.4, Lon: -70.6}, {Lat: -33.5, Lon: -70.7}}, true)
	if !errors.Is(err, dominio.ErrSinRuta) {
		t.Fatalf("error = %v; se esperaba ErrSinRuta", err)
	}
}
