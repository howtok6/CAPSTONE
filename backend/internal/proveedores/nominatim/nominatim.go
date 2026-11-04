// Package nominatim busca lugares por nombre y nombra puntos del mapa con un
// servidor Nominatim, respetando su política de uso: como máximo una consulta
// por segundo, User-Agent identificable y resultados guardados en caché.
package nominatim

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
	"via/backend/internal/proveedores/clientehttp"
)

const servicio = "Nominatim"

// RecuadroSantiago limita las búsquedas al Gran Santiago (minLon,minLat,maxLon,maxLat).
const RecuadroSantiago = "-70.85,-33.65,-70.45,-33.30"

// Cliente de Nominatim con límite de frecuencia y caché.
type Cliente struct {
	base      string
	http      *clientehttp.Cliente
	Intervalo time.Duration // separación mínima entre consultas (1 s por política)
	Vigencia  time.Duration // cuánto vale una respuesta en caché
	MaxCache  int

	turno  sync.Mutex // serializa las consultas al servidor
	ultima time.Time
	mu     sync.Mutex
	cache  map[string]entrada
	reloj  func() time.Time
	dormir func(time.Duration)
}

type entrada struct {
	valor  any
	expira time.Time
}

// Nuevo crea el cliente; base es, por ejemplo, https://nominatim.openstreetmap.org.
func Nuevo(base string, espera time.Duration, agente string) *Cliente {
	return &Cliente{
		base:      strings.TrimRight(base, "/"),
		http:      clientehttp.Nuevo(espera, agente),
		Intervalo: time.Second,
		Vigencia:  24 * time.Hour,
		MaxCache:  1000,
		cache:     map[string]entrada{},
		reloj:     time.Now,
		dormir:    time.Sleep,
	}
}

type resultado struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Lat         string `json:"lat"`
	Lon         string `json:"lon"`
}

func (r resultado) lugar() (dominio.Lugar, bool) {
	lat, err1 := strconv.ParseFloat(r.Lat, 64)
	lon, err2 := strconv.ParseFloat(r.Lon, 64)
	if err1 != nil || err2 != nil {
		return dominio.Lugar{}, false
	}
	nombre := r.Name
	if nombre == "" {
		nombre = strings.TrimSpace(strings.Split(r.DisplayName, ",")[0])
	}
	return dominio.Lugar{Nombre: nombre, Detalle: r.DisplayName, Lat: lat, Lon: lon}, true
}

// Buscar devuelve hasta 5 lugares del Gran Santiago que coinciden con el texto.
func (c *Cliente) Buscar(ctx context.Context, texto string) ([]dominio.Lugar, error) {
	texto = strings.TrimSpace(texto)
	if texto == "" {
		return nil, fmt.Errorf("%w: el texto de búsqueda está vacío", dominio.ErrInvalido)
	}
	clave := "buscar:" + strings.ToLower(texto)
	if v, ok := c.leerCache(clave); ok {
		return v.([]dominio.Lugar), nil
	}
	q := url.Values{
		"q": {texto}, "format": {"jsonv2"}, "limit": {"5"}, "countrycodes": {"cl"},
		"viewbox": {RecuadroSantiago}, "bounded": {"1"}, "accept-language": {"es"},
	}
	var datos []resultado
	if err := c.consultar(ctx, "/search?"+q.Encode(), &datos); err != nil {
		return nil, err
	}
	lugares := make([]dominio.Lugar, 0, len(datos))
	for _, d := range datos {
		if l, ok := d.lugar(); ok {
			lugares = append(lugares, l)
		}
	}
	c.guardarCache(clave, lugares)
	return lugares, nil
}

// Nombrar devuelve el nombre del lugar en un punto. Conserva el punto exacto;
// si el servidor no responde o no hay nada, el nombre son las coordenadas.
func (c *Cliente) Nombrar(ctx context.Context, p geo.Punto) dominio.Lugar {
	respaldo := dominio.Lugar{Nombre: fmt.Sprintf("%.4f, %.4f", p.Lat, p.Lon), Lat: p.Lat, Lon: p.Lon}
	clave := fmt.Sprintf("nombrar:%.5f,%.5f", p.Lat, p.Lon)
	if v, ok := c.leerCache(clave); ok {
		return v.(dominio.Lugar)
	}
	q := url.Values{
		"lat": {strconv.FormatFloat(p.Lat, 'f', 6, 64)}, "lon": {strconv.FormatFloat(p.Lon, 'f', 6, 64)},
		"format": {"jsonv2"}, "zoom": {"17"}, "accept-language": {"es"},
	}
	var d resultado
	if err := c.consultar(ctx, "/reverse?"+q.Encode(), &d); err != nil {
		return respaldo
	}
	l, ok := d.lugar()
	if !ok {
		return respaldo
	}
	l.Lat, l.Lon = p.Lat, p.Lon
	c.guardarCache(clave, l)
	return l
}

// consultar espera su turno para no superar una consulta por intervalo.
func (c *Cliente) consultar(ctx context.Context, ruta string, destino any) error {
	c.turno.Lock()
	if espera := c.Intervalo - c.reloj().Sub(c.ultima); !c.ultima.IsZero() && espera > 0 {
		c.dormir(espera)
	}
	c.ultima = c.reloj()
	c.turno.Unlock()
	return c.http.Hacer(ctx, servicio, http.MethodGet, c.base+ruta, nil, destino)
}

func (c *Cliente) leerCache(clave string) (any, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.cache[clave]
	if !ok || c.reloj().After(e.expira) {
		return nil, false
	}
	return e.valor, true
}

func (c *Cliente) guardarCache(clave string, valor any) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.cache) >= c.MaxCache {
		c.cache = map[string]entrada{} // simple: se vacía al llenarse
	}
	c.cache[clave] = entrada{valor: valor, expira: c.reloj().Add(c.Vigencia)}
}
