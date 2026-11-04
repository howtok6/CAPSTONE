package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"

	"via/backend/internal/dominio"
)

const maxCuerpo = 1 << 20 // 1 MiB

// ErrorAPI es el cuerpo de toda respuesta de error.
type ErrorAPI struct {
	Error struct {
		Codigo  string `json:"codigo"`
		Mensaje string `json:"mensaje"`
	} `json:"error"`
}

func responder(w http.ResponseWriter, estado int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(estado)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

// fallar traduce un error de dominio a su código HTTP.
func fallar(w http.ResponseWriter, r *http.Request, err error) {
	estado, codigo, mensaje := http.StatusInternalServerError, "error_interno", "error interno"
	switch {
	case errors.Is(err, dominio.ErrInvalido):
		estado, codigo, mensaje = http.StatusBadRequest, "solicitud_invalida", err.Error()
	case errors.Is(err, dominio.ErrNoEncontrado):
		estado, codigo, mensaje = http.StatusNotFound, "no_encontrado", err.Error()
	case errors.Is(err, dominio.ErrConflicto):
		estado, codigo, mensaje = http.StatusConflict, "conflicto", err.Error()
	case errors.Is(err, dominio.ErrSinRuta):
		estado, codigo, mensaje = http.StatusUnprocessableEntity, "sin_ruta", err.Error()
	case errors.Is(err, context.DeadlineExceeded):
		estado, codigo, mensaje = http.StatusGatewayTimeout, "tiempo_agotado", "un servicio tardó demasiado en responder"
	case errors.Is(err, dominio.ErrProveedor):
		estado, codigo, mensaje = http.StatusServiceUnavailable, "servicio_no_disponible", err.Error()
	}
	if estado >= 500 {
		slog.Error("solicitud fallida", "metodo", r.Method, "ruta", r.URL.Path, "error", err)
	}
	var cuerpo ErrorAPI
	cuerpo.Error.Codigo, cuerpo.Error.Mensaje = codigo, mensaje
	responder(w, estado, cuerpo)
}

func leerJSON(r *http.Request, destino any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, maxCuerpo))
	if err := dec.Decode(destino); err != nil {
		if errors.Is(err, io.EOF) {
			return fmt.Errorf("%w: falta el cuerpo JSON", dominio.ErrInvalido)
		}
		return fmt.Errorf("%w: JSON inválido: %v", dominio.ErrInvalido, err)
	}
	if dec.More() {
		return fmt.Errorf("%w: el cuerpo tiene contenido después del JSON", dominio.ErrInvalido)
	}
	return nil
}

func numero(q url.Values, clave string) (float64, error) {
	v := q.Get(clave)
	if v == "" {
		return 0, fmt.Errorf("%w: falta el parámetro %q", dominio.ErrInvalido, clave)
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return 0, fmt.Errorf("%w: %q debe ser un número", dominio.ErrInvalido, clave)
	}
	return f, nil
}
