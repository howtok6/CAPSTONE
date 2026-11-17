package api

import (
	"errors"
	"testing"
	"time"

	"via/backend/internal/dominio"
)

func TestMomentoDeSalida(t *testing.T) {
	ahora := time.Date(2026, 11, 11, 20, 45, 0, 0, time.FixedZone("CLT", -3*3600))

	if m, err := momentoDeSalida("", ahora); err != nil || !m.Equal(ahora) {
		t.Errorf("vacía: %v %v", m, err)
	}
	m, err := momentoDeSalida("18:15", ahora)
	if err != nil {
		t.Fatal(err)
	}
	if m.Hour() != 18 || m.Minute() != 15 || m.Day() != 11 || m.Month() != time.November {
		t.Errorf("HH:MM debía ser hoy a las 18:15 de Santiago: %v", m)
	}
	m, err = momentoDeSalida(" 2026-11-12T07:30:00-03:00 ", ahora)
	if err != nil || m.Day() != 12 || m.Hour() != 7 {
		t.Errorf("RFC 3339: %v %v", m, err)
	}
	for _, mala := range []string{"mañana", "25:00", "7"} {
		if _, err := momentoDeSalida(mala, ahora); !errors.Is(err, dominio.ErrInvalido) {
			t.Errorf("%q debía ser inválida: %v", mala, err)
		}
	}
}
