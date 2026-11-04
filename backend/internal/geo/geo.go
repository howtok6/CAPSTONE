// Package geo reúne la geometría que necesita el backend: distancias y rumbos
// sobre la Tierra, recuadros y la proyección de un punto sobre una polilínea.
//
// Las distancias de unos pocos kilómetros se calculan en un plano local
// equirectangular: en Santiago el error es de centímetros.
package geo

import (
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
)

const radioTierraM = 6371008.8

// Punto en WGS84.
type Punto struct {
	Lat float64 `json:"lat"`
	Lon float64 `json:"lon"`
}

// Valido indica si el punto tiene coordenadas posibles y no es el (0, 0) que
// envían algunos GPS antes de fijar posición.
func (p Punto) Valido() bool {
	if math.IsNaN(p.Lat) || math.IsNaN(p.Lon) {
		return false
	}
	return p.Lat >= -90 && p.Lat <= 90 && p.Lon >= -180 && p.Lon <= 180 && !(p.Lat == 0 && p.Lon == 0)
}

func rad(g float64) float64    { return g * math.Pi / 180 }
func grados(r float64) float64 { return r * 180 / math.Pi }

// Distancia en metros entre dos puntos (fórmula del semiverseno).
func Distancia(a, b Punto) float64 {
	dLat := rad(b.Lat - a.Lat)
	dLon := rad(b.Lon - a.Lon)
	h := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(rad(a.Lat))*math.Cos(rad(b.Lat))*math.Sin(dLon/2)*math.Sin(dLon/2)
	return 2 * radioTierraM * math.Asin(math.Min(1, math.Sqrt(h)))
}

// Rumbo inicial de a hacia b, en grados: 0 = norte, 90 = este.
func Rumbo(a, b Punto) float64 {
	y := math.Sin(rad(b.Lon-a.Lon)) * math.Cos(rad(b.Lat))
	x := math.Cos(rad(a.Lat))*math.Sin(rad(b.Lat)) -
		math.Sin(rad(a.Lat))*math.Cos(rad(b.Lat))*math.Cos(rad(b.Lon-a.Lon))
	return math.Mod(grados(math.Atan2(y, x))+360, 360)
}

// DiferenciaAngular entre dos rumbos, en [0, 180].
func DiferenciaAngular(a, b float64) float64 {
	d := math.Mod(math.Abs(a-b), 360)
	if d > 180 {
		d = 360 - d
	}
	return d
}

// plano local en metros alrededor de un punto de referencia.
type plano struct {
	ref  Punto
	cos0 float64
}

func nuevoPlano(ref Punto) plano { return plano{ref: ref, cos0: math.Cos(rad(ref.Lat))} }

func (p plano) xy(q Punto) (float64, float64) {
	return rad(q.Lon-p.ref.Lon) * radioTierraM * p.cos0, rad(q.Lat-p.ref.Lat) * radioTierraM
}

// Recuadro geográfico.
type Recuadro struct {
	MinLon, MinLat, MaxLon, MaxLat float64
}

// Contiene indica si el punto cae dentro del recuadro (bordes incluidos).
func (r Recuadro) Contiene(p Punto) bool {
	return p.Lon >= r.MinLon && p.Lon <= r.MaxLon && p.Lat >= r.MinLat && p.Lat <= r.MaxLat
}

// ParsearRecuadro lee "minLon,minLat,maxLon,maxLat", el orden de OSM.
func ParsearRecuadro(s string) (Recuadro, error) {
	partes := strings.Split(s, ",")
	if len(partes) != 4 {
		return Recuadro{}, errors.New("bbox debe ser minLon,minLat,maxLon,maxLat")
	}
	var v [4]float64
	for i, parte := range partes {
		f, err := strconv.ParseFloat(strings.TrimSpace(parte), 64)
		if err != nil {
			return Recuadro{}, fmt.Errorf("bbox: %q no es un número", parte)
		}
		v[i] = f
	}
	r := Recuadro{v[0], v[1], v[2], v[3]}
	if r.MinLon > r.MaxLon || r.MinLat > r.MaxLat {
		return Recuadro{}, errors.New("bbox: el mínimo supera al máximo")
	}
	return r, nil
}

// Polilinea es un trazado (por ejemplo una ruta) con sus distancias acumuladas.
type Polilinea struct {
	Puntos []Punto
	acum   []float64
}

// NuevaPolilinea precalcula la distancia acumulada hasta cada vértice.
func NuevaPolilinea(puntos []Punto) *Polilinea {
	acum := make([]float64, len(puntos))
	for i := 1; i < len(puntos); i++ {
		acum[i] = acum[i-1] + Distancia(puntos[i-1], puntos[i])
	}
	return &Polilinea{Puntos: puntos, acum: acum}
}

// Largo total en metros.
func (pl *Polilinea) Largo() float64 {
	if len(pl.acum) == 0 {
		return 0
	}
	return pl.acum[len(pl.acum)-1]
}

// Proyeccion de un punto sobre la polilínea.
type Proyeccion struct {
	RecorridoM    float64 // distancia a lo largo del trazado hasta el punto proyectado
	SeparacionM   float64 // distancia perpendicular del punto al trazado
	RumboSegmento float64 // rumbo del tramo donde cae la proyección
	Punto         Punto
}

// Proyectar devuelve el punto del trazado más cercano a p, buscando solo desde
// `desdeM` metros recorridos. Así, en una ruta que pasa dos veces cerca del
// mismo lugar, no se retrocede a la primera pasada.
func (pl *Polilinea) Proyectar(p Punto, desdeM float64) Proyeccion {
	mejor := Proyeccion{SeparacionM: math.Inf(1)}
	for i := 0; i+1 < len(pl.Puntos); i++ {
		if pl.acum[i+1] < desdeM {
			continue
		}
		a, b := pl.Puntos[i], pl.Puntos[i+1]
		pla := nuevoPlano(a)
		bx, by := pla.xy(b)
		px, py := pla.xy(p)
		largo2 := bx*bx + by*by
		// Dentro del tramo donde cae `desdeM`, no se puede proyectar antes de él.
		tMin := 0.0
		if tramo := pl.acum[i+1] - pl.acum[i]; desdeM > pl.acum[i] && tramo > 0 {
			tMin = math.Min(1, (desdeM-pl.acum[i])/tramo)
		}
		t := tMin
		if largo2 > 0 {
			t = math.Max(tMin, math.Min(1, (px*bx+py*by)/largo2))
		}
		dx, dy := px-t*bx, py-t*by
		sep := math.Hypot(dx, dy)
		if sep < mejor.SeparacionM {
			mejor = Proyeccion{
				RecorridoM:    pl.acum[i] + t*(pl.acum[i+1]-pl.acum[i]),
				SeparacionM:   sep,
				RumboSegmento: Rumbo(a, b),
				Punto:         Punto{Lat: a.Lat + t*(b.Lat-a.Lat), Lon: a.Lon + t*(b.Lon-a.Lon)},
			}
		}
	}
	if len(pl.Puntos) == 1 {
		return Proyeccion{SeparacionM: Distancia(p, pl.Puntos[0]), Punto: pl.Puntos[0]}
	}
	return mejor
}

// PuntoEn devuelve el punto del trazado a `recorridoM` metros del inicio.
func (pl *Polilinea) PuntoEn(recorridoM float64) Punto {
	if len(pl.Puntos) == 0 {
		return Punto{}
	}
	if recorridoM <= 0 {
		return pl.Puntos[0]
	}
	for i := 0; i+1 < len(pl.Puntos); i++ {
		if recorridoM <= pl.acum[i+1] {
			largo := pl.acum[i+1] - pl.acum[i]
			t := 0.0
			if largo > 0 {
				t = (recorridoM - pl.acum[i]) / largo
			}
			a, b := pl.Puntos[i], pl.Puntos[i+1]
			return Punto{Lat: a.Lat + t*(b.Lat-a.Lat), Lon: a.Lon + t*(b.Lon-a.Lon)}
		}
	}
	return pl.Puntos[len(pl.Puntos)-1]
}

// DesdeLatLon convierte pares [lat, lon] en puntos.
func DesdeLatLon(pares [][2]float64) []Punto {
	puntos := make([]Punto, len(pares))
	for i, p := range pares {
		puntos[i] = Punto{Lat: p[0], Lon: p[1]}
	}
	return puntos
}
