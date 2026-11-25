# Simular recorridos A → B y ajustes de simulación — 24 y 25 de noviembre de 2026

Desarrollo hecho por Benjamín Quiroz con Claude (asistente de IA) para la demo de la app «Vía». Cubre la
simulación, el backend y la app. Este documento resume qué se hizo, por qué, cómo usarlo y qué quedó pendiente.

## 1. Objetivo

En la presentación no podremos movernos de un lugar a otro, así que el modo GPS no sirve para mostrar la app. Hacía
falta poder elegir **cualquier recorrido** dentro de Las Condes y Providencia y verlo funcionando: un auto que avanza,
frena en los rojos y muestra los semáforos en vivo. Antes solo existían 3 recorridos fijos de demostración.

## 2. Qué se agregó

| Función | Qué hace | Dónde se ve |
|---|---|---|
| **Simular recorrido A → B** | Al proponer una ruta (★), el interruptor «Simular recorrido» hace que la recorra un auto de SUMO en vez del GPS del celular. El mapa dibuja el camino que calcula la simulación. | App, bajo el selector de recorrido |
| **Ajustes de simulación** | Antes de un recorrido simulado se elige la **velocidad** (1x, 3x, 5x) y el **horario** (Valle, Punta mañana, Punta tarde). Durante el recorrido quedan bloqueados (candado). | App, fila «Ajustes de simulación» |
| **Botón de recentrar** | Va siempre justo encima del panel de recorrido; antes tenía una altura fija y tapaba las opciones nuevas. | App |
| **Marco de teléfono** | En Chrome de escritorio, Proponer ruta, Ajustes y la hoja de ubicación se abren dentro del marco con forma de teléfono, no a lo ancho de la ventana. | App (solo en pantallas anchas) |

Los 3 recorridos de demostración y el modo GPS **no cambian**.

## 3. Cómo usarlo en la app

1. Con la simulación y el backend corriendo, tocar «Proponer ruta» y elegir **A y B dentro de Las Condes o
   Providencia** (el origen por defecto, Plaza de Armas, queda fuera del área). Ejemplo: Costanera Center → Escuela
   Militar.
2. Confirmar la ruta, activar **«Simular recorrido»** y, si se quiere, ajustar velocidad y horario.
3. «Iniciar recorrido». Debajo aparece «Recorrido en curso · Simulación en vivo».

Si un punto queda fuera del área, la app lo explica («No se puede simular: el origen queda fuera del área
simulada…») y no inicia el recorrido.

## 4. Cómo funciona por dentro

### Simulación (`simulacion/via_sim/`)

- `POST /viajes` acepta, además de `{"ruta": 0}`, un viaje libre:
  `{"origen": {"lat", "lon"}, "destino": {"lat", "lon"}, "nombre_destino": "…"}`.
  Valida que ambos puntos estén dentro de las comunas (`tsc-thesis/scenarios/las_condes_providencia/comunas.geojson`),
  a menos de 150 m de una calle para autos y a más de 200 m entre sí. Calcula la ruta más rápida con
  `findRoute` de SUMO, pone el vehículo y responde también `recorrido` (trazado, semáforos y distancia).
- `GET /ajustes` y `POST /ajustes`: la **velocidad** cambia al instante; el **perfil** de demanda (`eod_valle`,
  `eod_punta_tarde`) reinicia la simulación con su demanda y su plan Webster. Mientras se reinicia, `lista` es
  false y los viajes en curso quedan `reiniciado`. Medido: el reinicio toma 3 a 6 segundos.
- No se modificó nada de `tsc-thesis/`.

### Backend (`backend/`)

- `POST /v1/viajes` en modo `simulado` acepta `paradas` (usa la primera y la última) y `nombre_destino`. La
  respuesta de creación trae `recorrido`; las consultas siguientes no lo repiten.
- `GET /v1/simulacion/ajustes` y `POST /v1/simulacion/ajustes` pasan a la simulación la velocidad y el perfil. Se
  usó POST (no PUT) porque el CORS del backend solo permite GET, POST y DELETE.
- Los rechazos de la simulación (punto fuera del área, perfil desconocido) llegan a la app como `400
  solicitud_invalida` con el mensaje original.

### App (`frontend/lib/`, rama `dev-benja`)

- `via_api.dart`: `crearViajeSimuladoLibre`, `ajustes` y `cambiarAjustes`.
- `main.dart`: interruptor «Simular recorrido», fila y panel «Ajustes de simulación», botón de recentrar anclado al
  panel y `MarcoTelefono` alrededor de toda la app.

## 5. Decisiones

- **Punta mañana usa los datos de punta tarde.** La demanda de la mañana no es creíble (sale más congestionada que
  la tarde, al revés que en la realidad) y no está validada con TomTom. Es la misma decisión del doc 14, sección 9,
  y de la tabla de tiempos de la app (`--manana-como-tarde`). El panel lo indica: «Usa los datos de punta tarde».
  Pasar entre punta mañana y punta tarde no reinicia la simulación.
- **Velocidades 1x, 3x y 5x, fijas durante el recorrido**, para no alterar un recorrido en curso.
- **Las paradas intermedias se ignoran** en un recorrido simulado: el auto va directo de A a B (la app avisa).
- **La ruta la calcula SUMO**, no OSRM, porque es la que recorre el auto. Puede diferir un poco de la ruta ★
  propuesta; el mapa muestra la de SUMO.
- **Los ajustes afectan a toda la simulación** (es una sola para todos), incluidos los semáforos que ve el modo GPS.

## 6. Limitaciones conocidas y pendientes

- **Taco bloqueado en punta tarde.** Hacia el minuto 30 simulado se forma un bloqueo en Av. Tobalaba. Como la tesis
  desactiva el teletransporte de SUMO (`--time-to-teleport -1` en `tsc-thesis/src/tsc/sumo_env.py`), un auto que
  cae ahí queda detenido para siempre. Reproducido con Guillermo Acuña → Martín de Zamora. En valle casi no pasa.
  **Pendiente (sin implementar):** que solo el auto de la app calcule la ruta con los tacos actuales y, si queda
  detenido mucho rato, se adelante al tramo libre siguiente. No afectaría los resultados de la tesis.
- **`sumo-data` sin versión fija.** `simulacion/requirements.txt` fija `eclipse-sumo==1.27.1` pero no `sumo-data`;
  en Mac se instala la 1.28 y SUMO no arranca (falta `libproj`). Arreglo: agregar `sumo-data==1.27.1`.
- **Docker.** `comunas.geojson` no se copia a la imagen de la simulación; ahí solo se exige que el punto esté cerca
  de una calle de la red (que cubre el área más 400 m).
- **Fin de la hora simulada.** Al llegar a 3600 s la simulación vuelve a empezar y los viajes quedan
  «Simulación reiniciada» (unos 11 minutos reales a 5x).

## 7. Cómo correrlo en Mac

Requisitos: Python 3.12, Go 1.25 o superior y Flutter (`brew install python@3.12 go` y
`brew install --cask flutter`).

**Terminal 1 — simulación**

```bash
cd simulacion
python3.12 -m venv .venv && source .venv/bin/activate   # solo la primera vez
pip install -r requirements.txt                          # solo la primera vez
pip install --force-reinstall --no-deps "sumo-data==1.27.1"   # solo la primera vez, en Mac
python run.py
```

**Terminal 2 — backend**

```bash
cd backend
go run ./cmd/via-backend
```

**Terminal 3 — app** (rama `dev-benja`)

```bash
cd frontend
flutter run -d chrome
```

`http://127.0.0.1:8080/v1/salud` debe responder `ok`. Con `python run.py --velocidad 3 --perfil eod_valle` se puede
arrancar directamente en otros ajustes; desde la app se cambian después.

## 8. Ramas y commits

**`simular-ruta-ab`** (desde `escenario-las-condes-providencia`):

1. Simulación: viajes con origen y destino libres dentro del área
2. Backend: viajes simulados entre dos puntos elegidos
3. Simulación: ajustes de velocidad y horario en vivo
4. Backend: ajustes de velocidad y horario de la simulación
5. Este documento

Pendiente: Pull Request hacia `escenario-las-condes-providencia` cuando Gabriel lo revise.

**`dev-benja`** (app):

1. App: «Simular recorrido» para las rutas propuestas
2. App: panel «Ajustes de simulación» (velocidad y horario)
3. App: el botón de recentrar va siempre encima del panel de recorrido
4. App: Proponer ruta y los paneles se abren dentro del marco de teléfono
5. README de la app: sección sobre estas funciones

## 9. Pruebas

| Parte | Comando | Resultado |
|---|---|---|
| Simulación | `cd simulacion && python -m pytest tests` | 8 pruebas, pasan (incluye viaje libre en el área y ajustes) |
| Backend | `cd backend && go test ./...` | Pasan (incluye viaje libre y `/v1/simulacion/ajustes`) |
| App | `cd frontend && flutter test` | 35 pruebas, pasan (incluye Simular recorrido, Ajustes, botón de recentrar y marco de teléfono) |

Además se probó de punta a punta con la simulación y el backend reales: viaje libre Costanera Center → Escuela
Militar (2,7 km, 9 semáforos), rechazo de un punto fuera del área y cambio de punta tarde a valle.
