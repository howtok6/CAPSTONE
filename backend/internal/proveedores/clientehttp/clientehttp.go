// Package clientehttp es el cliente JSON común para hablar con los demás
// servicios del proyecto (simulación) y con servicios externos (OSRM, Nominatim).
package clientehttp

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"via/backend/internal/dominio"
)

// Cliente HTTP con tiempo de espera y User-Agent fijos.
type Cliente struct {
	HTTP   *http.Client
	Agente string
}

// Nuevo crea un cliente con el tiempo de espera dado por llamada.
func Nuevo(espera time.Duration, agente string) *Cliente {
	return &Cliente{HTTP: &http.Client{Timeout: espera}, Agente: agente}
}

// ErrorHTTP: el servicio respondió con un código de error.
type ErrorHTTP struct {
	Servicio string
	Estado   int
	Cuerpo   string
}

func (e *ErrorHTTP) Error() string {
	return fmt.Sprintf("%s respondió %d: %s", e.Servicio, e.Estado, recortar(e.Cuerpo, 200))
}

// Unwrap traduce el código HTTP a un error de dominio.
func (e *ErrorHTTP) Unwrap() error {
	switch e.Estado {
	case http.StatusNotFound:
		return dominio.ErrNoEncontrado
	case http.StatusConflict:
		return dominio.ErrConflicto
	case http.StatusBadRequest, http.StatusUnprocessableEntity:
		return dominio.ErrInvalido
	default:
		return dominio.ErrProveedor
	}
}

// Hacer envía una solicitud y, si `destino` no es nil, decodifica la respuesta JSON.
func (c *Cliente) Hacer(ctx context.Context, servicio, metodo, url string, cuerpo, destino any) error {
	var lector io.Reader
	if cuerpo != nil {
		datos, err := json.Marshal(cuerpo)
		if err != nil {
			return err
		}
		lector = bytes.NewReader(datos)
	}
	req, err := http.NewRequestWithContext(ctx, metodo, url, lector)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	if cuerpo != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.Agente != "" {
		req.Header.Set("User-Agent", c.Agente)
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("%w: %s: %v", dominio.ErrProveedor, servicio, err)
	}
	defer resp.Body.Close()
	datos, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	if err != nil {
		return fmt.Errorf("%w: %s: %v", dominio.ErrProveedor, servicio, err)
	}
	if resp.StatusCode >= 300 {
		return &ErrorHTTP{Servicio: servicio, Estado: resp.StatusCode, Cuerpo: string(datos)}
	}
	if destino == nil || len(datos) == 0 {
		return nil
	}
	if err := json.Unmarshal(datos, destino); err != nil {
		return fmt.Errorf("%w: %s: respuesta inválida: %v", dominio.ErrProveedor, servicio, err)
	}
	return nil
}

// EstadoHTTP devuelve el código de un ErrorHTTP, o 0 si el error es otro.
func EstadoHTTP(err error) int {
	var e *ErrorHTTP
	if errors.As(err, &e) {
		return e.Estado
	}
	return 0
}

func recortar(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
