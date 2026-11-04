// Package config lee la configuración del backend desde variables de entorno.
package config

import (
	"os"
	"time"
)

// Config del backend. Todas las URLs apuntan a servicios del proyecto o externos.
type Config struct {
	Direccion     string        // VIA_DIRECCION, p. ej. ":8080"
	SimulacionURL string        // VIA_SIMULACION_URL: servicio de simulación (entorno de pruebas)
	OSRMURL       string        // VIA_OSRM_URL: enrutamiento
	NominatimURL  string        // VIA_NOMINATIM_URL: búsqueda de lugares
	AgenteUsuario string        // VIA_AGENTE: User-Agent para servicios de OSM
	TiempoEspera  time.Duration // VIA_TIEMPO_ESPERA: límite por llamada a un servicio
	ViajeInactivo time.Duration // VIA_VIAJE_INACTIVO: se olvida un viaje sin actividad tras este plazo
}

// Desde lee la configuración con valores por defecto para desarrollo local.
func Desde(getenv func(string) string) Config {
	if getenv == nil {
		getenv = os.Getenv
	}
	valor := func(clave, porDefecto string) string {
		if v := getenv(clave); v != "" {
			return v
		}
		return porDefecto
	}
	duracion := func(clave string, porDefecto time.Duration) time.Duration {
		if d, err := time.ParseDuration(getenv(clave)); err == nil && d > 0 {
			return d
		}
		return porDefecto
	}
	return Config{
		Direccion:     valor("VIA_DIRECCION", ":8080"),
		SimulacionURL: valor("VIA_SIMULACION_URL", "http://127.0.0.1:8000"),
		OSRMURL:       valor("VIA_OSRM_URL", "https://router.project-osrm.org"),
		NominatimURL:  valor("VIA_NOMINATIM_URL", "https://nominatim.openstreetmap.org"),
		AgenteUsuario: valor("VIA_AGENTE", "via-capstone-backend/0.1 (proyecto academico DUOC UC)"),
		TiempoEspera:  duracion("VIA_TIEMPO_ESPERA", 10*time.Second),
		ViajeInactivo: duracion("VIA_VIAJE_INACTIVO", 2*time.Hour),
	}
}
