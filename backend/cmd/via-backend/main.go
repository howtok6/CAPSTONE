// Comando via-backend: el backend de la app móvil «Vía».
//
// Expone /v1 a la app y se comunica por HTTP con los demás servicios: la
// simulación (entorno de pruebas que provee el tráfico), OSRM y Nominatim.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"via/backend/internal/almacen"
	"via/backend/internal/api"
	"via/backend/internal/config"
	"via/backend/internal/proveedores/nominatim"
	"via/backend/internal/proveedores/osrm"
	"via/backend/internal/proveedores/simulacion"
	"via/backend/internal/servicios"
)

// version se fija al compilar: -ldflags "-X main.version=..."
var version = "dev"

func main() {
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stdout, nil)))
	cfg := config.Desde(nil)

	sim := simulacion.Nuevo(cfg.SimulacionURL, cfg.TiempoEspera)
	enrutador := osrm.Nuevo(cfg.OSRMURL, cfg.TiempoEspera, cfg.AgenteUsuario)
	geocodificador := nominatim.Nuevo(cfg.NominatimURL, cfg.TiempoEspera, cfg.AgenteUsuario)
	viajesGuardados := almacen.NuevaMemoria[*servicios.ViajeInterno](cfg.ViajeInactivo)

	nav := servicios.NuevaNavegacion(sim)
	manejador := api.Nuevo(api.Dependencias{
		Geocodificador: geocodificador,
		Rutas:          servicios.NuevasRutas(enrutador, nav),
		Navegacion:     nav,
		Viajes:         servicios.NuevosViajes(nav, enrutador, sim, viajesGuardados),
		Salud: map[string]func(context.Context) (any, error){
			"simulacion": func(ctx context.Context) (any, error) { return sim.Estado(ctx) },
		},
		Version: version,
	})

	srv := &http.Server{
		Addr:              cfg.Direccion,
		Handler:           manejador,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, detener := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer detener()

	go func() {
		t := time.NewTicker(10 * time.Minute)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				viajesGuardados.Purgar()
			}
		}
	}()

	go func() {
		slog.Info("backend escuchando", "direccion", cfg.Direccion, "simulacion", cfg.SimulacionURL,
			"osrm", cfg.OSRMURL, "nominatim", cfg.NominatimURL, "version", version)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("el servidor se detuvo", "error", err)
			detener()
		}
	}()

	<-ctx.Done()
	apagado, cancelar := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelar()
	if err := srv.Shutdown(apagado); err != nil {
		slog.Error("apagado forzado", "error", err)
	}
	slog.Info("backend detenido")
}
