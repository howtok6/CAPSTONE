package simulacion

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"via/backend/internal/dominio"
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
