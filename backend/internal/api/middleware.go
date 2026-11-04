package api

import (
	"log/slog"
	"net/http"
	"time"
)

type intermedio func(http.Handler) http.Handler

// encadenar aplica los middlewares; el primero queda por fuera.
func encadenar(h http.Handler, m ...intermedio) http.Handler {
	for i := len(m) - 1; i >= 0; i-- {
		h = m[i](h)
	}
	return h
}

// cors permite que la app web (Flutter en Chrome) llame al backend en desarrollo.
func cors(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Access-Control-Allow-Origin", "*")
		h.Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		h.Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		siguiente.ServeHTTP(w, r)
	})
}

type grabadora struct {
	http.ResponseWriter
	estado int
}

func (g *grabadora) WriteHeader(estado int) {
	g.estado = estado
	g.ResponseWriter.WriteHeader(estado)
}

// registrar deja una línea por solicitud: método, ruta, estado y duración.
func registrar(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		inicio := time.Now()
		g := &grabadora{ResponseWriter: w, estado: http.StatusOK}
		siguiente.ServeHTTP(g, r)
		slog.Info("http", "metodo", r.Method, "ruta", r.URL.Path, "estado", g.estado,
			"ms", time.Since(inicio).Milliseconds())
	})
}

// recuperar convierte un pánico en un 500 sin tumbar el servidor.
func recuperar(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if p := recover(); p != nil {
				slog.Error("pánico atendiendo solicitud", "ruta", r.URL.Path, "panico", p)
				var cuerpo ErrorAPI
				cuerpo.Error.Codigo, cuerpo.Error.Mensaje = "error_interno", "error interno"
				responder(w, http.StatusInternalServerError, cuerpo)
			}
		}()
		siguiente.ServeHTTP(w, r)
	})
}
