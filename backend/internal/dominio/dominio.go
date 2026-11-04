// Package dominio define el modelo del backend: lugares, rutas, semáforos,
// tráfico y viajes, tal como se exponen a la app (JSON en español).
package dominio

import (
	"errors"
	"time"
)

// Errores de dominio; la capa HTTP los traduce a códigos de estado.
var (
	ErrNoEncontrado = errors.New("no encontrado")
	ErrInvalido     = errors.New("solicitud inválida")
	ErrConflicto    = errors.New("operación no permitida en el estado actual")
	ErrSinRuta      = errors.New("no hay ruta entre esos puntos")
	ErrProveedor    = errors.New("servicio externo no disponible")
)

// Lugar con nombre, resultado de buscar o de nombrar un punto.
type Lugar struct {
	Nombre  string  `json:"nombre"`
	Detalle string  `json:"detalle,omitempty"`
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
}

// Paso es una maniobra de la ruta: salir, girar, continuar, parada o llegar.
type Paso struct {
	Tipo        string  `json:"tipo"`                  // depart | turn | parada | arrive | roundabout | ...
	Modificador string  `json:"modificador,omitempty"` // left | slight right | straight | uturn | ...
	Calle       string  `json:"calle"`
	DistanciaM  float64 `json:"distancia_m"`
}

// SemaforoEnRuta es un semáforo por el que pasa una ruta.
type SemaforoEnRuta struct {
	ID                    string  `json:"id"`
	Nombre                string  `json:"nombre"`
	Lat                   float64 `json:"lat"`
	Lon                   float64 `json:"lon"`
	DistanciaDesdeInicioM float64 `json:"distancia_desde_inicio_m"`
	RumboLlegada          float64 `json:"-"`
}

// Ruta en auto entre dos o más paradas.
type Ruta struct {
	DistanciaKm float64          `json:"distancia_km"`
	DuracionMin float64          `json:"duracion_min"`
	Trazado     [][2]float64     `json:"trazado"` // [lat, lon]
	Pasos       []Paso           `json:"pasos"`
	Semaforos   []SemaforoEnRuta `json:"semaforos"`
}

// Acceso de un semáforo: una calle que llega a él y su sentido de llegada.
type Acceso struct {
	ID    string  `json:"id"`
	Calle string  `json:"calle"`
	Rumbo float64 `json:"rumbo"`
}

// Semaforo: datos estáticos de una intersección semaforizada.
type Semaforo struct {
	ID      string   `json:"id"`
	Nombre  string   `json:"nombre"`
	Calles  []string `json:"calles"`
	Lat     float64  `json:"lat"`
	Lon     float64  `json:"lon"`
	Accesos []Acceso `json:"accesos"`
}

// EstadoAcceso: lo que ve un conductor que llega por un acceso.
type EstadoAcceso struct {
	Color              string  `json:"color"` // verde | amarillo | rojo | apagado
	SegundosParaCambio *int    `json:"segundos_para_cambio"`
	SiguienteColor     *string `json:"siguiente_color"`
	Exacto             bool    `json:"exacto"` // false = estimación (controlador adaptativo)
}

// Calle de la red, con su geometría (estático).
type Calle struct {
	ID                string       `json:"id"`
	Nombre            string       `json:"nombre"`
	VelocidadLibreKmh float64      `json:"velocidad_libre_kmh"`
	Forma             [][2]float64 `json:"forma"` // [lat, lon]
}

// EstadoCalle: velocidad media y nivel de servicio de una calle en este momento.
type EstadoCalle struct {
	ID           string  `json:"id"`
	VelocidadKmh float64 `json:"velocidad_kmh"`
	Vehiculos    int     `json:"vehiculos"`
	Nivel        string  `json:"nivel"` // libre | fluido | moderado | congestionado
}

// Ubicacion informada por el GPS del celular.
type Ubicacion struct {
	Lat          float64   `json:"lat"`
	Lon          float64   `json:"lon"`
	Rumbo        *float64  `json:"rumbo,omitempty"` // grados; si falta, se estima con la ubicación anterior
	VelocidadKmh *float64  `json:"velocidad_kmh,omitempty"`
	PrecisionM   *float64  `json:"precision_m,omitempty"`
	Momento      time.Time `json:"momento"`
}

// ProximoSemaforo en el camino del usuario, con el estado de su acceso.
type ProximoSemaforo struct {
	ID         string   `json:"id"`
	Nombre     string   `json:"nombre"`
	Calles     []string `json:"calles"`
	DistanciaM int      `json:"distancia_m"`
	Acceso     string   `json:"acceso,omitempty"`
	EstadoAcceso
}

// Modos de viaje.
const (
	ModoGPS      = "gps"      // la app envía la ubicación real del celular
	ModoSimulado = "simulado" // un vehículo dentro de la simulación representa al usuario
)

// Viaje de un usuario, real (GPS) o simulado.
type Viaje struct {
	ID                 string           `json:"id"`
	Modo               string           `json:"modo"`
	Estado             string           `json:"estado"` // esperando | en_ruta | llego | finalizado | reiniciado
	Destino            string           `json:"destino,omitempty"`
	DistanciaTotalM    *int             `json:"distancia_total_m,omitempty"`
	DistanciaRestanteM *int             `json:"distancia_restante_m,omitempty"`
	SemaforosEnRuta    int              `json:"semaforos_en_ruta"`
	Ubicacion          *Ubicacion       `json:"ubicacion,omitempty"`
	ProximoSemaforo    *ProximoSemaforo `json:"proximo_semaforo"`
	CreadoEn           time.Time        `json:"creado_en"`
	ActualizadoEn      time.Time        `json:"actualizado_en"`
}

// DestinoSimulado es un recorrido de demostración que ofrece la simulación.
type DestinoSimulado struct {
	Ruta        int     `json:"ruta"`
	ID          string  `json:"id"`
	Nombre      string  `json:"nombre"`
	Origen      string  `json:"origen"`
	DistanciaKm float64 `json:"distancia_km"`
}

// ViajeSimulado es el viaje tal como lo entrega el proveedor de simulación.
type ViajeSimulado struct {
	ID                 string   `json:"id"`
	Estado             string   `json:"estado"`
	Ruta               int      `json:"ruta"`
	Destino            string   `json:"destino"`
	TiempoSim          float64  `json:"tiempo_sim"`
	DistanciaTotalM    *int     `json:"distancia_total_m"`
	DistanciaRestanteM *int     `json:"distancia_restante_m"`
	VelocidadKmh       *float64 `json:"velocidad_kmh"`
	Posicion           *struct {
		Lat float64 `json:"lat"`
		Lon float64 `json:"lon"`
	} `json:"posicion"`
	ProximoSemaforo *struct {
		ID         string   `json:"id"`
		Nombre     string   `json:"nombre"`
		Calles     []string `json:"calles"`
		DistanciaM float64  `json:"distancia_m"`
		EstadoAcceso
	} `json:"proximo_semaforo"`
}
