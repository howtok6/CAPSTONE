// Package historico estima cuánto demora un trazado según la franja horaria,
// con la tabla de velocidades por calle que exporta la simulación
// (tsc-thesis/scripts/exportar_tiempos_app.py -> backend/datos/tiempos_area.json,
// Las Condes + Providencia; tiempos_eje.json es la tabla anterior del eje).
//
// La tabla trae, por calle y franja, la velocidad media con el control actual
// (Webster) y con el control adaptativo (agente IPPO). Son resultados de
// simulación con demanda EOD calibrada, no mediciones en la calle, y solo
// cubren las calles de la red simulada. En la tabla del área la punta mañana
// repite los valores de la punta tarde (la mañana no se pudo validar).
package historico

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"time"

	"via/backend/internal/dominio"
	"via/backend/internal/geo"
)

const (
	celdaGrados  = 0.001 // ~100 m: tamaño de la grilla de búsqueda
	pasoM        = 15.0  // el trazado se recorre en pasos de este largo
	maxDistM     = 20.0  // distancia máxima entre el trazado y la calle que lo explica
	maxDesvioGra = 35.0  // diferencia máxima de rumbo: descarta la calzada contraria y los cruces
	// Control con que se estima la situación de hoy y el escenario de la tesis.
	Actual     = "actual"
	Adaptativo = "adaptativo"
)

// Archivo es el formato de tiempos_eje.json.
type Archivo struct {
	Generado string       `json:"generado"`
	Fuente   string       `json:"fuente"`
	Franjas  []FranjaJSON `json:"franjas"`
	Calles   []CalleJSON  `json:"calles"`
}

// FranjaJSON: franja horaria de la tabla.
type FranjaJSON struct {
	ID     string `json:"id"`
	Nombre string `json:"nombre"`
}

// CalleJSON: una calle de la red con su velocidad por franja y control (km/h).
type CalleJSON struct {
	ID       string                        `json:"id"`
	LargoM   float64                       `json:"largo_m"`
	LibreKmh float64                       `json:"libre_kmh"`
	Forma    [][2]float64                  `json:"forma"` // [lat, lon]
	Vel      map[string]map[string]float64 `json:"vel"`   // franja -> control -> km/h
}

type segmento struct {
	ax, ay, bx, by float64 // metros en el plano local
	rumbo          float64
	calle          int
}

// Tabla de velocidades cargada en memoria, con una grilla para ubicar calles.
type Tabla struct {
	Generado string
	Fuente   string
	nombres  map[string]string // franja -> nombre para mostrar
	vel      []map[string]map[string]float64
	segs     []segmento
	grilla   map[[2]int][]int
	ref      geo.Punto
	cos0     float64
	indice   map[string]float64 // franja -> velocidad libre / velocidad simulada, mediana de las calles
	zona     *time.Location
}

// Cargar lee la tabla desde un archivo JSON.
func Cargar(ruta string) (*Tabla, error) {
	datos, err := os.ReadFile(ruta)
	if err != nil {
		return nil, err
	}
	var a Archivo
	if err := json.Unmarshal(datos, &a); err != nil {
		return nil, fmt.Errorf("tabla de tiempos %s: %w", ruta, err)
	}
	return Nueva(a)
}

// Nueva arma la tabla a partir de su contenido.
func Nueva(a Archivo) (*Tabla, error) {
	if len(a.Calles) == 0 {
		return nil, fmt.Errorf("la tabla de tiempos no tiene calles")
	}
	zona, err := time.LoadLocation("America/Santiago")
	if err != nil {
		zona = time.FixedZone("CLT", -3*3600)
	}
	t := &Tabla{Generado: a.Generado, Fuente: a.Fuente, nombres: map[string]string{},
		grilla: map[[2]int][]int{}, indice: map[string]float64{}, zona: zona}
	for _, f := range a.Franjas {
		t.nombres[f.ID] = f.Nombre
	}
	for _, c := range a.Calles {
		if len(c.Forma) > 0 {
			t.ref = geo.Punto{Lat: c.Forma[0][0], Lon: c.Forma[0][1]}
			break
		}
	}
	t.cos0 = math.Cos(t.ref.Lat * math.Pi / 180)
	razones := map[string][]float64{}
	for i, c := range a.Calles {
		t.vel = append(t.vel, c.Vel)
		pts := geo.DesdeLatLon(c.Forma)
		for j := 0; j+1 < len(pts); j++ {
			ax, ay := t.xy(pts[j])
			bx, by := t.xy(pts[j+1])
			if ax == bx && ay == by {
				continue
			}
			k := len(t.segs)
			t.segs = append(t.segs, segmento{ax, ay, bx, by, geo.Rumbo(pts[j], pts[j+1]), i})
			for _, celda := range celdasEntre(pts[j], pts[j+1]) {
				t.grilla[celda] = append(t.grilla[celda], k)
			}
		}
		for franja, porControl := range c.Vel {
			if v := porControl[Actual]; v > 0 && c.LibreKmh > 0 {
				razones[franja] = append(razones[franja], c.LibreKmh/v)
			}
		}
	}
	// Índice de congestión de la franja: cuántas veces más lento que a velocidad libre
	// se recorre una calle típica. Se usa la mediana y no la media para que las pocas
	// calles bloqueadas de la simulación (sobre todo en punta mañana) no lo dominen.
	for franja, r := range razones {
		sort.Float64s(r)
		t.indice[franja] = math.Max(1, r[len(r)/2])
	}
	return t, nil
}

func (t *Tabla) xy(p geo.Punto) (float64, float64) {
	return (p.Lon - t.ref.Lon) * 111320 * t.cos0, (p.Lat - t.ref.Lat) * 110540
}

func celda(p geo.Punto) [2]int {
	return [2]int{int(math.Floor(p.Lat / celdaGrados)), int(math.Floor(p.Lon / celdaGrados))}
}

// celdasEntre: celdas que toca el segmento, con una de margen.
func celdasEntre(a, b geo.Punto) [][2]int {
	ca, cb := celda(a), celda(b)
	var out [][2]int
	for i := min(ca[0], cb[0]) - 1; i <= max(ca[0], cb[0])+1; i++ {
		for j := min(ca[1], cb[1]) - 1; j <= max(ca[1], cb[1])+1; j++ {
			out = append(out, [2]int{i, j})
		}
	}
	return out
}

// Franja horaria de un momento: su id y su nombre. ok es falso cuando no hay
// datos para esa hora (noche y madrugada), y entonces no se estima nada.
//
// Días hábiles: punta mañana 07:00-09:00, punta tarde 17:30-20:00 y valle el
// resto entre las 06:00 y las 22:00. Fines de semana: valle de 09:00 a 21:00.
// Las puntas vienen de las ventanas de la EOD; el resto es un supuesto.
func (t *Tabla) Franja(momento time.Time) (id, nombre string, ok bool) {
	m := momento.In(t.zona)
	minuto := m.Hour()*60 + m.Minute()
	finDeSemana := m.Weekday() == time.Saturday || m.Weekday() == time.Sunday
	switch {
	case finDeSemana && minuto >= 9*60 && minuto < 21*60:
		id = "valle"
	case finDeSemana:
		return "", "", false
	case minuto >= 7*60 && minuto < 9*60:
		id = "punta_manana"
	case minuto >= 17*60+30 && minuto < 20*60:
		id = "punta_tarde"
	case minuto >= 6*60 && minuto < 22*60:
		id = "valle"
	default:
		return "", "", false
	}
	if _, hay := t.indice[id]; !hay {
		return "", "", false
	}
	nombre = t.nombres[id]
	if nombre == "" {
		nombre = id
	}
	return id, nombre, true
}

// Estimar recorre el trazado y suma el tiempo de los tramos que calzan con una
// calle de la tabla. ok es falso si no hay datos para esa hora.
func (t *Tabla) Estimar(trazado []geo.Punto, momento time.Time) (dominio.TramoEstimado, bool) {
	franja, nombre, ok := t.Franja(momento)
	if !ok {
		return dominio.TramoEstimado{}, false
	}
	e := dominio.TramoEstimado{Franja: franja, FranjaNombre: nombre, IndiceCongestion: t.indice[franja]}
	for i := 0; i+1 < len(trazado); i++ {
		a, b := trazado[i], trazado[i+1]
		largo := geo.Distancia(a, b)
		if largo <= 0 {
			continue
		}
		rumbo := geo.Rumbo(a, b)
		pasos := int(math.Ceil(largo / pasoM))
		paso := largo / float64(pasos)
		for k := 0; k < pasos; k++ {
			f := (float64(k) + 0.5) / float64(pasos)
			medio := geo.Punto{Lat: a.Lat + f*(b.Lat-a.Lat), Lon: a.Lon + f*(b.Lon-a.Lon)}
			e.TotalM += paso
			c, hay := t.calleEn(medio, rumbo)
			if !hay {
				continue
			}
			vel := t.vel[c][franja]
			actual := vel[Actual]
			if actual <= 0 {
				continue
			}
			adaptativo := vel[Adaptativo]
			if adaptativo <= 0 {
				adaptativo = actual
			}
			e.CubiertoM += paso
			e.SegActual += paso / (actual / 3.6)
			e.SegAdaptativo += paso / (adaptativo / 3.6)
		}
	}
	return e, true
}

// calleEn: calle más cercana al punto que va en el mismo sentido.
func (t *Tabla) calleEn(p geo.Punto, rumbo float64) (int, bool) {
	px, py := t.xy(p)
	mejor, calle := maxDistM, -1
	for _, k := range t.grilla[celda(p)] {
		s := t.segs[k]
		if geo.DiferenciaAngular(s.rumbo, rumbo) > maxDesvioGra {
			continue
		}
		dx, dy := s.bx-s.ax, s.by-s.ay
		u := ((px-s.ax)*dx + (py-s.ay)*dy) / (dx*dx + dy*dy)
		u = math.Max(0, math.Min(1, u))
		if d := math.Hypot(px-(s.ax+u*dx), py-(s.ay+u*dy)); d < mejor {
			mejor, calle = d, s.calle
		}
	}
	return calle, calle >= 0
}
