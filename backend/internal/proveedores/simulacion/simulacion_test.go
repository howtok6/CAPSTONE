package simulacion

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

func TestContratoConLaSimulacion(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/semaforos/estado":
			if r.URL.Query().Get("ids") != "A,B" {
				t.Errorf("ids = %q", r.URL.Query().Get("ids"))
			}
			_, _ = w.Write([]byte(`{"tiempo_sim":400,"semaforos":{"A":{"A_e":{"color":"verde","segundos_para_cambio":12,"siguiente_color":"amarillo","exacto":true}}}}`))
		case "/viajes":
			_, _ = w.Write([]byte(`{"id":"v1","estado":"esperando","ruta":0,"destino":"Bustamante","distancia_total_m":1665}`))
		case "/viajes/v9":
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"detail":"viaje no encontrado"}`))
		default:
			w.WriteHeader(http.StatusTeapot)
		}
	}))
	defer srv.Close()
	c := Nuevo(srv.URL+"/", time.Second)
	ctx := context.Background()

	e, err := c.EstadoSemaforos(ctx, []string{"A", "B"})
	if err != nil || e["A"]["A_e"].Color != "verde" || *e["A"]["A_e"].SegundosParaCambio != 12 {
		t.Fatalf("estado = %+v, %v", e, err)
	}
	v, err := c.CrearViaje(ctx, 0)
	if err != nil || v.ID != "v1" || *v.DistanciaTotalM != 1665 {
		t.Fatalf("crear = %+v, %v", v, err)
	}
	if _, err := c.Viaje(ctx, "v9"); !errors.Is(err, dominio.ErrNoEncontrado) {
		t.Errorf("viaje inexistente: %v", err)
	}
	if _, err := c.Semaforos(ctx); !errors.Is(err, dominio.ErrProveedor) {
		t.Errorf("respuesta 418: %v", err)
	}
	srv.Close()
	if _, err := c.Estado(ctx); !errors.Is(err, dominio.ErrProveedor) {
		t.Errorf("servicio caído: %v", err)
	}
}

func TestViajeLibre(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var cuerpo struct {
			Origen        geo.Punto `json:"origen"`
			Destino       geo.Punto `json:"destino"`
			NombreDestino string    `json:"nombre_destino"`
		}
		if r.Method != http.MethodPost || r.URL.Path != "/viajes" || json.NewDecoder(r.Body).Decode(&cuerpo) != nil {
			w.WriteHeader(http.StatusTeapot)
			return
		}
		if cuerpo.Origen.Lat < -33.43 {
			w.WriteHeader(http.StatusUnprocessableEntity)
			_, _ = w.Write([]byte(`{"detail":"el origen queda fuera del área simulada (Las Condes y Providencia)"}`))
			return
		}
		if cuerpo.Destino.Lon != -70.5847 || cuerpo.NombreDestino != "Escuela Militar" {
			t.Errorf("cuerpo = %+v", cuerpo)
		}
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"id":"v2","estado":"esperando","ruta":null,"destino":"Escuela Militar","distancia_total_m":2706,
			"recorrido":{"distancia_km":2.7,"trazado":[[-33.4165,-70.6070],[-33.4138,-70.5847]],
			"semaforos":[{"id":"S1","nombre":"Av. Apoquindo × Tobalaba","lat":-33.416,"lon":-70.601,"distancia_desde_inicio_m":420}]}}`))
	}))
	defer srv.Close()
	c := Nuevo(srv.URL, time.Second)
	ctx := context.Background()

	v, err := c.CrearViajeLibre(ctx, geo.Punto{Lat: -33.4176, Lon: -70.6065}, geo.Punto{Lat: -33.4140, Lon: -70.5847}, "Escuela Militar")
	if err != nil || v.ID != "v2" || v.Recorrido == nil || len(v.Recorrido.Trazado) != 2 || v.Recorrido.Semaforos[0].ID != "S1" {
		t.Fatalf("crear libre = %+v, %v", v, err)
	}
	_, err = c.CrearViajeLibre(ctx, geo.Punto{Lat: -33.4378, Lon: -70.6504}, geo.Punto{Lat: -33.4140, Lon: -70.5847}, "")
	if !errors.Is(err, dominio.ErrInvalido) || !strings.Contains(err.Error(), "fuera del área") || strings.Contains(err.Error(), "detail") {
		t.Errorf("fuera del área: %v", err)
	}
}

func TestAjustes(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/ajustes" {
			w.WriteHeader(http.StatusTeapot)
			return
		}
		if r.Method == http.MethodGet {
			_, _ = w.Write([]byte(`{"velocidad":5.0,"perfil":"eod_punta_tarde","perfiles":["eod_punta_tarde","eod_valle"],"lista":true}`))
			return
		}
		var c dominio.CambioAjustes
		_ = json.NewDecoder(r.Body).Decode(&c)
		if c.Perfil != nil && *c.Perfil == "eod_punta_manana" {
			w.WriteHeader(http.StatusUnprocessableEntity)
			_, _ = w.Write([]byte(`{"detail":"perfil desconocido: eod_punta_manana (disponibles: eod_punta_tarde, eod_valle)"}`))
			return
		}
		if c.Velocidad == nil || *c.Velocidad != 3 {
			t.Errorf("cambio = %+v", c)
		}
		_, _ = w.Write([]byte(`{"velocidad":3.0,"perfil":"eod_punta_tarde","perfiles":["eod_punta_tarde","eod_valle"],"lista":true}`))
	}))
	defer srv.Close()
	c := Nuevo(srv.URL, time.Second)
	ctx := context.Background()

	a, err := c.Ajustes(ctx)
	if err != nil || a.Velocidad != 5 || a.Perfil != "eod_punta_tarde" || len(a.Perfiles) != 2 || !a.Lista {
		t.Fatalf("ajustes = %+v, %v", a, err)
	}
	tres := 3.0
	if a, err = c.CambiarAjustes(ctx, dominio.CambioAjustes{Velocidad: &tres}); err != nil || a.Velocidad != 3 {
		t.Fatalf("cambiar velocidad = %+v, %v", a, err)
	}
	manana := "eod_punta_manana"
	_, err = c.CambiarAjustes(ctx, dominio.CambioAjustes{Perfil: &manana})
	if !errors.Is(err, dominio.ErrInvalido) || !strings.Contains(err.Error(), "perfil desconocido") {
		t.Errorf("perfil desconocido: %v", err)
	}
}
