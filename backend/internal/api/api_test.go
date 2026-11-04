package api

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"via/backend/internal/almacen"
	"via/backend/internal/dominio"
	"via/backend/internal/geo"
	"via/backend/internal/servicios"
)

const lat0 = -33.44

type trafico struct{ caido bool }

func (t trafico) Semaforos(context.Context) ([]dominio.Semaforo, error) {
	if t.caido {
		return nil, dominio.ErrProveedor
	}
	return []dominio.Semaforo{{ID: "A", Nombre: "Avenida × A", Lat: lat0, Lon: -70.655,
		Accesos: []dominio.Acceso{{ID: "A_e", Calle: "Avenida", Rumbo: 90}}}}, nil
}
func (t trafico) EstadoSemaforos(context.Context, []string) (map[string]map[string]dominio.EstadoAcceso, error) {
	s := 7
	return map[string]map[string]dominio.EstadoAcceso{"A": {"A_e": {Color: "rojo", SegundosParaCambio: &s, Exacto: true}}}, nil
}
func (t trafico) Calles(context.Context) ([]dominio.Calle, error) {
	return []dominio.Calle{{ID: "e1", Nombre: "Avenida", VelocidadLibreKmh: 50, Forma: [][2]float64{{lat0, -70.66}, {lat0, -70.65}}}}, nil
}
func (t trafico) Trafico(context.Context) ([]dominio.EstadoCalle, error) {
	return []dominio.EstadoCalle{{ID: "e1", VelocidadKmh: 20, Vehiculos: 4, Nivel: "moderado"}}, nil
}

type sim struct{}

func (sim) Destinos(context.Context) ([]dominio.DestinoSimulado, error) {
	return []dominio.DestinoSimulado{{Ruta: 0, Nombre: "Bustamante", DistanciaKm: 1.7}}, nil
}
func (sim) CrearViaje(context.Context, int) (dominio.ViajeSimulado, error) {
	return dominio.ViajeSimulado{ID: "s1", Estado: "esperando"}, nil
}
func (sim) Viaje(context.Context, string) (dominio.ViajeSimulado, error) {
	return dominio.ViajeSimulado{ID: "s1", Estado: "en_ruta"}, nil
}
func (sim) FinalizarViaje(context.Context, string) error { return nil }

type enrutador struct{}

func (enrutador) Rutas(_ context.Context, p []geo.Punto, _ bool) ([]dominio.Ruta, error) {
	if p[0].Lat < -34 {
		return nil, dominio.ErrSinRuta
	}
	return []dominio.Ruta{{DistanciaKm: 1.9, DuracionMin: 4, Trazado: [][2]float64{{lat0, -70.66}, {lat0, -70.64}}}}, nil
}

type geocod struct{}

func (geocod) Buscar(_ context.Context, q string) ([]dominio.Lugar, error) {
	if strings.TrimSpace(q) == "" {
		return nil, dominio.ErrInvalido
	}
	return []dominio.Lugar{{Nombre: "Plaza de Armas", Lat: -33.4378, Lon: -70.6504}}, nil
}
func (geocod) Nombrar(_ context.Context, p geo.Punto) dominio.Lugar {
	return dominio.Lugar{Nombre: "Alameda", Lat: p.Lat, Lon: p.Lon}
}

func servidor(t *testing.T, tr trafico) *httptest.Server {
	t.Helper()
	nav := servicios.NuevaNavegacion(tr)
	h := Nuevo(Dependencias{
		Geocodificador: geocod{},
		Rutas:          servicios.NuevasRutas(enrutador{}, nav),
		Navegacion:     nav,
		Viajes:         servicios.NuevosViajes(nav, enrutador{}, sim{}, almacen.NuevaMemoria[*servicios.ViajeInterno](time.Hour)),
		Salud: map[string]func(context.Context) (any, error){
			"simulacion": func(context.Context) (any, error) {
				if tr.caido {
					return nil, errors.New("sin conexión")
				}
				return map[string]bool{"lista": true}, nil
			},
		},
		Version: "prueba",
	})
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return srv
}

func pedir(t *testing.T, srv *httptest.Server, metodo, ruta, cuerpo string) (int, map[string]any, []any) {
	t.Helper()
	var lector io.Reader
	if cuerpo != "" {
		lector = strings.NewReader(cuerpo)
	}
	req, _ := http.NewRequest(metodo, srv.URL+ruta, lector)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	datos, _ := io.ReadAll(resp.Body)
	var obj map[string]any
	var lista []any
	if len(datos) > 0 && datos[0] == '[' {
		_ = json.Unmarshal(datos, &lista)
	} else if len(datos) > 0 {
		_ = json.Unmarshal(datos, &obj)
	}
	return resp.StatusCode, obj, lista
}

func codigoError(obj map[string]any) string {
	e, _ := obj["error"].(map[string]any)
	c, _ := e["codigo"].(string)
	return c
}

func TestFlujoDeViajeGPS(t *testing.T) {
	srv := servidor(t, trafico{})
	estado, v, _ := pedir(t, srv, "POST", "/v1/viajes",
		`{"modo":"gps","nombre_destino":"Fin","trazado":[[-33.44,-70.66],[-33.44,-70.64]]}`)
	if estado != http.StatusCreated || v["semaforos_en_ruta"].(float64) != 1 {
		t.Fatalf("crear: %d %v", estado, v)
	}
	id := v["id"].(string)

	estado, v, _ = pedir(t, srv, "POST", "/v1/viajes/"+id+"/ubicacion", `{"lat":-33.44,"lon":-70.658,"rumbo":90}`)
	prox, _ := v["proximo_semaforo"].(map[string]any)
	if estado != http.StatusOK || prox["id"] != "A" || prox["color"] != "rojo" || prox["segundos_para_cambio"].(float64) != 7 {
		t.Fatalf("ubicación: %d %v", estado, v)
	}
	if estado, _, _ = pedir(t, srv, "GET", "/v1/viajes/"+id, ""); estado != http.StatusOK {
		t.Fatalf("ver: %d", estado)
	}
	if estado, _, _ = pedir(t, srv, "DELETE", "/v1/viajes/"+id, ""); estado != http.StatusNoContent {
		t.Fatalf("finalizar: %d", estado)
	}
	estado, v, _ = pedir(t, srv, "POST", "/v1/viajes/"+id+"/ubicacion", `{"lat":-33.44,"lon":-70.65}`)
	if estado != http.StatusConflict || codigoError(v) != "conflicto" {
		t.Fatalf("ubicación tras finalizar: %d %v", estado, v)
	}
}

func TestErroresYValidaciones(t *testing.T) {
	srv := servidor(t, trafico{})
	casos := []struct {
		metodo, ruta, cuerpo string
		estado               int
		codigo               string
	}{
		{"POST", "/v1/viajes", `{"modo":"tren"}`, 400, "solicitud_invalida"},
		{"POST", "/v1/viajes", `no es json`, 400, "solicitud_invalida"},
		{"POST", "/v1/rutas", `{"paradas":[{"lat":-33.44,"lon":-70.65}]}`, 400, "solicitud_invalida"},
		{"POST", "/v1/rutas", `{"paradas":[{"lat":-35,"lon":-70.65},{"lat":-33.44,"lon":-70.64}]}`, 422, "sin_ruta"},
		{"GET", "/v1/viajes/nada", "", 404, "no_encontrado"},
		{"GET", "/v1/semaforos/nada", "", 404, "no_encontrado"},
		{"GET", "/v1/semaforos?bbox=1,2,3", "", 400, "solicitud_invalida"},
		{"GET", "/v1/semaforos/proximo?lat=-33.44&lon=-70.658", "", 400, "solicitud_invalida"},
		{"GET", "/v1/lugares/inverso?lat=abc&lon=-70.6", "", 400, "solicitud_invalida"},
		{"GET", "/v1/lugares?q=", "", 400, "solicitud_invalida"},
	}
	for _, c := range casos {
		estado, obj, _ := pedir(t, srv, c.metodo, c.ruta, c.cuerpo)
		if estado != c.estado || codigoError(obj) != c.codigo {
			t.Errorf("%s %s: %d %v; se esperaba %d %s", c.metodo, c.ruta, estado, obj, c.estado, c.codigo)
		}
	}
}

func TestConsultas(t *testing.T) {
	srv := servidor(t, trafico{})
	if estado, _, l := pedir(t, srv, "GET", "/v1/lugares?q=plaza", ""); estado != 200 || len(l) != 1 {
		t.Errorf("lugares: %d %v", estado, l)
	}
	estado, _, l := pedir(t, srv, "POST", "/v1/rutas", `{"paradas":[{"lat":-33.44,"lon":-70.66},{"lat":-33.44,"lon":-70.64}]}`)
	if estado != 200 || len(l) != 1 || len(l[0].(map[string]any)["semaforos"].([]any)) != 1 {
		t.Errorf("rutas: %d %v", estado, l)
	}
	estado, _, l = pedir(t, srv, "GET", "/v1/semaforos?bbox=-70.7,-33.5,-70.6,-33.4", "")
	acceso := l[0].(map[string]any)["accesos"].([]any)[0].(map[string]any)
	if estado != 200 || acceso["color"] != "rojo" || acceso["rumbo"].(float64) != 90 {
		t.Errorf("semáforos: %d %v", estado, l)
	}
	estado, obj, _ := pedir(t, srv, "GET", "/v1/semaforos/proximo?lat=-33.44&lon=-70.658&rumbo=90", "")
	if estado != 200 || obj["proximo_semaforo"].(map[string]any)["id"] != "A" {
		t.Errorf("próximo: %d %v", estado, obj)
	}
	estado, _, l = pedir(t, srv, "GET", "/v1/trafico", "")
	if estado != 200 || len(l) != 1 || l[0].(map[string]any)["nivel"] != "moderado" {
		t.Errorf("tráfico: %d %v", estado, l)
	}
	if estado, _, l = pedir(t, srv, "GET", "/v1/simulacion/destinos", ""); estado != 200 || len(l) != 1 {
		t.Errorf("destinos: %d %v", estado, l)
	}
	estado, obj, _ = pedir(t, srv, "POST", "/v1/viajes", `{"modo":"simulado","destino":0}`)
	if estado != 201 || obj["modo"] != "simulado" {
		t.Errorf("viaje simulado: %d %v", estado, obj)
	}
}

func TestSaludYServicioCaido(t *testing.T) {
	srv := servidor(t, trafico{caido: true})
	estado, obj, _ := pedir(t, srv, "GET", "/v1/salud", "")
	if estado != 200 || obj["estado"] != "degradado" {
		t.Errorf("salud: %d %v", estado, obj)
	}
	estado, obj, _ = pedir(t, srv, "GET", "/v1/semaforos", "")
	if estado != 503 || codigoError(obj) != "servicio_no_disponible" {
		t.Errorf("semáforos sin simulación: %d %v", estado, obj)
	}
	// Las rutas siguen funcionando, solo sin semáforos.
	estado, _, l := pedir(t, srv, "POST", "/v1/rutas", `{"paradas":[{"lat":-33.44,"lon":-70.66},{"lat":-33.44,"lon":-70.64}]}`)
	if estado != 200 || len(l[0].(map[string]any)["semaforos"].([]any)) != 0 {
		t.Errorf("rutas sin simulación: %d %v", estado, l)
	}
}

func TestCORS(t *testing.T) {
	srv := servidor(t, trafico{})
	req, _ := http.NewRequest("OPTIONS", srv.URL+"/v1/viajes", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent || resp.Header.Get("Access-Control-Allow-Origin") != "*" {
		t.Errorf("preflight: %d %v", resp.StatusCode, resp.Header)
	}
}
