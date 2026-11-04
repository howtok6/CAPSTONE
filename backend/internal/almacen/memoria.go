// Package almacen guarda los viajes activos. Por ahora en memoria; la interfaz
// que usa el servicio permite reemplazarlo por una base de datos.
package almacen

import (
	"sync"
	"time"
)

// Memoria es un almacén genérico en memoria con expiración por inactividad.
type Memoria[T any] struct {
	mu       sync.RWMutex
	items    map[string]registro[T]
	inactivo time.Duration
	reloj    func() time.Time
}

type registro[T any] struct {
	valor T
	toque time.Time
}

// NuevaMemoria crea el almacén; un elemento sin escrituras durante `inactivo` se descarta.
func NuevaMemoria[T any](inactivo time.Duration) *Memoria[T] {
	return &Memoria[T]{items: map[string]registro[T]{}, inactivo: inactivo, reloj: time.Now}
}

// Guardar crea o reemplaza un elemento.
func (m *Memoria[T]) Guardar(id string, v T) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.items[id] = registro[T]{valor: v, toque: m.reloj()}
}

// Obtener devuelve el elemento si existe y no expiró.
func (m *Memoria[T]) Obtener(id string) (T, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	r, ok := m.items[id]
	if !ok || m.reloj().Sub(r.toque) > m.inactivo {
		var cero T
		return cero, false
	}
	return r.valor, true
}

// Eliminar borra el elemento.
func (m *Memoria[T]) Eliminar(id string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.items, id)
}

// Purgar descarta los elementos inactivos y devuelve cuántos quedaron.
func (m *Memoria[T]) Purgar() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	ahora := m.reloj()
	for id, r := range m.items {
		if ahora.Sub(r.toque) > m.inactivo {
			delete(m.items, id)
		}
	}
	return len(m.items)
}
