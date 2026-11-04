// Package osrm calcula rutas en auto con un servidor OSRM.
package osrm

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
	"via/backend/internal/proveedores/clientehttp"
)

const servicio = "OSRM"

// Cliente de OSRM.
type Cliente struct {
	base string
	http *clientehttp.Cliente
}

// Nuevo crea el cliente; base es, por ejemplo, https://router.project-osrm.org.
func Nuevo(base string, espera time.Duration, agente string) *Cliente {
	return &Cliente{base: strings.TrimRight(base, "/"), http: clientehttp.Nuevo(espera, agente)}
}

type respuesta struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Routes  []struct {
		Distance float64 `json:"distance"`
		Duration float64 `json:"duration"`
		Geometry struct {
			Coordinates [][2]float64 `json:"coordinates"` // [lon, lat]
		} `json:"geometry"`
		Legs []struct {
			Steps []struct {
				Name     string  `json:"name"`
				Distance float64 `json:"distance"`
				Maneuver struct {
					Type     string `json:"type"`
					Modifier string `json:"modifier"`
				} `json:"maneuver"`
			} `json:"steps"`
		} `json:"legs"`
	} `json:"routes"`
}

// Rutas en auto entre las paradas, la más rápida primero. OSRM solo entrega
// alternativas cuando hay dos paradas.
func (c *Cliente) Rutas(ctx context.Context, paradas []geo.Punto, alternativas bool) ([]dominio.Ruta, error) {
	if len(paradas) < 2 {
		return nil, fmt.Errorf("%w: se necesitan al menos origen y destino", dominio.ErrInvalido)
	}
	coords := make([]string, len(paradas))
	for i, p := range paradas {
		coords[i] = fmt.Sprintf("%.6f,%.6f", p.Lon, p.Lat)
	}
	q := url.Values{
		"overview":     {"full"},
		"geometries":   {"geojson"},
		"steps":        {"true"},
		"alternatives": {fmt.Sprint(alternativas)},
	}
	u := c.base + "/route/v1/driving/" + strings.Join(coords, ";") + "?" + q.Encode()

	var r respuesta
	err := c.http.Hacer(ctx, servicio, http.MethodGet, u, nil, &r)
	if err != nil {
		// OSRM responde 400 con un JSON que explica el error (p. ej. NoRoute).
		var e *clientehttp.ErrorHTTP
		explicado := errors.As(err, &e) && e.Estado == http.StatusBadRequest &&
			json.Unmarshal([]byte(e.Cuerpo), &r) == nil && r.Code != ""
		if !explicado {
			return nil, err
		}
	}
	switch r.Code {
	case "Ok":
	case "NoRoute", "NoSegment":
		return nil, dominio.ErrSinRuta
	default:
		return nil, fmt.Errorf("%w: OSRM %s %s", dominio.ErrProveedor, r.Code, r.Message)
	}

	rutas := make([]dominio.Ruta, 0, len(r.Routes))
	for _, ruta := range r.Routes {
		trazado := make([][2]float64, len(ruta.Geometry.Coordinates))
		for i, c := range ruta.Geometry.Coordinates {
			trazado[i] = [2]float64{c[1], c[0]}
		}
		// Une los pasos de todos los tramos: omite la salida repetida de cada
		// tramo y marca como «parada» las llegadas intermedias.
		var pasos []dominio.Paso
		for t, tramo := range ruta.Legs {
			for _, s := range tramo.Steps {
				tipo := s.Maneuver.Type
				if tipo == "depart" && t > 0 {
					continue
				}
				if tipo == "arrive" && t < len(ruta.Legs)-1 {
					tipo = "parada"
				}
				pasos = append(pasos, dominio.Paso{
					Tipo: tipo, Modificador: s.Maneuver.Modifier, Calle: s.Name, DistanciaM: s.Distance,
				})
			}
		}
		rutas = append(rutas, dominio.Ruta{
			DistanciaKm: ruta.Distance / 1000,
			DuracionMin: ruta.Duration / 60,
			Trazado:     trazado,
			Pasos:       pasos,
		})
	}
	return rutas, nil
}
