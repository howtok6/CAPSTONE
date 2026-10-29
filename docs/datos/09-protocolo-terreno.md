# Protocolo de terreno: medición de tiempos semafóricos

Versión 2 · 22-oct-2026 (muestra ajustada a los límites comunales). Método definido en
`08-decision-tiempos-semaforicos.md`.

**Qué se obtiene:** ciclo, verde, amarillo y rojo de 13 cruces del eje Alameda → Providencia → Apoquindo, dentro de
las comunas de Santiago, Providencia y Las Condes, en tres franjas horarias (39 mediciones). **Esfuerzo:** 4 días
hábiles de unas 4 h en terreno, más ~6 h de extracción desde los videos.

## 1. Cruces de la muestra

Lista completa con coordenadas e identificador SUMO en `tsc-thesis/data/terreno/cruces_muestra.csv`.

El eje va de Matucana (límite de Santiago con Estación Central) hasta el término de Av. Apoquindo, junto a Camino El
Alba, y tiene ~86 puntos semaforizados (37 en Santiago, 23 en Providencia y 26 en Las Condes, incluidos pasos
peatonales). Ver `07-decision-escenario.md`.

| ID | Ruta | Cruce | Comuna | Tipo |
|---|---|---|---|---|
| C11 | A | Alameda × Matucana / Exposición | Santiago | principal |
| C12 | A | Alameda × Av. Brasil / Almirante Latorre | Santiago | principal |
| C01 | A | Alameda × Santa Rosa / Mac Iver | Santiago | principal |
| C02 | B | Alameda × Portugal | Santiago | principal |
| C03 | B | Providencia × General Bustamante | Providencia | principal |
| C04 | B | Providencia × Manuel Montt | Providencia | principal |
| C05 | C | Providencia × Pedro de Valdivia | Providencia | principal |
| C06 | C | Providencia × Ricardo Lyon | Providencia | secundario |
| C07 | C | Providencia × Tobalaba | Providencia (límite con Las Condes) | principal |
| C08 | C | Apoquindo × El Golf | Las Condes | principal |
| C09 | D | Apoquindo × San Pascual | Las Condes | secundario |
| C10 | D | Apoquindo × Manquehue | Las Condes | principal |
| C13 | D | Apoquindo × Tomás Moro / Chesterton | Las Condes | principal |

**Criterios:** los dos extremos del eje en Santiago y Las Condes, repartidos en las tres comunas (4 en Santiago, 5 en
Providencia y 4 en Las Condes), mezcla de avenidas principales y calles secundarias, y los cruces de tramos que hoy no
cubre ninguna red (C01, C02, C06, C07, C11, C12, C13). Se excluyó Plaza Baquedano por su geometría atípica.
**Reservas** si un cruce está en obras o con carabinero dirigiendo: Alameda × Ricardo Cumming, Providencia × Huelén,
Apoquindo × La Castellana y Apoquindo × Hernando de Magallanes.

**Rutas a pie** (distancia en línea recta): A ≈ 3,1 km · B ≈ 2,3 km · C ≈ 2,1 km · D ≈ 2,8 km. La Línea 1 del Metro
corre bajo todo el eje y sirve para moverse entre cruces o llegar al punto de partida.

## 2. Calendario

Martes a jueves, que son días de tránsito típico. Cada ruta se mide una vez en cada franja, rotando:

| Día | Punta mañana 07:30–09:00 | Valle 10:30–12:00 | Punta tarde 18:00–19:30 |
|---|---|---|---|
| 1 | Ruta A | Ruta B | Ruta C |
| 2 | Ruta B | Ruta C | Ruta D |
| 3 | Ruta C | Ruta D | Ruta A |
| 4 | Ruta D | Ruta A | Ruta B |

Ejemplo: martes 27, miércoles 28 y jueves 29 de octubre, y martes 3 de noviembre. Si falta tiempo, la **versión
mínima** es valle y punta tarde (8 salidas): punta tarde es el perfil donde se contrasta H1.

Evitar días con lluvia, feriados, marchas o eventos masivos en el eje; si ocurren, anotarlos y repetir la medición.

## 3. Equipo

- Teléfono con batería cargada y al menos 4 GB libres; batería externa.
- Opcional: trípode pequeño o soporte para apoyar el teléfono.
- Esta guía y la lista de cruces en el teléfono.

## 4. Procedimiento en cada cruce

1. **Ubicarse** en una esquina, en la vereda, desde donde se vean a la vez el semáforo vehicular que controla el eje y
   el que controla la calle transversal. Si no se ven ambos, grabar desde una posición que muestre el del eje y, en
   lo posible, el peatonal de la transversal.
2. **Decir en voz alta al iniciar** el cruce, la hora y la dirección a la que apunta la cámara («C04, 18:12, mirando
   al oriente»). Queda en el audio del video y evita confusiones al extraer.
3. **Grabar sin cortes al menos 3 ciclos completos**, unos 6 a 8 minutos. Si el ciclo es largo, seguir hasta ver
   tres veces el inicio del verde del eje.
4. **Anotar en el teléfono** lo que el video no muestra: flechas de viraje, fase peatonal exclusiva, botón peatonal,
   carabinero dirigiendo, semáforo en destello o apagado, obras.
5. **Llenar una fila en `mediciones.csv`** (se puede hacer al volver a casa):
   `medicion_id, cruce_id, fecha, hora_inicio, franja, observador, metodo, video_archivo, clima, notas`.
   Convención de `medicion_id`: `C04-PM-D1` (cruce, franja `AM`/`VA`/`PM`, día). Franja: `punta_am`, `valle`,
   `punta_pm`.

**Respaldo sin video:** cronómetro con vueltas (*laps*), marcando cada cambio de color del eje; vale solo para el grupo
del eje y se anota `metodo = cronometro`.

## 5. Extracción desde el video

1. Abrir el video en un reproductor que muestre el tiempo con décimas y permita avanzar cuadro a cuadro.
2. Por cada cambio de color, agregar una fila en `eventos.csv`: `medicion_id, grupo, color, t, notas`.
    - **grupo:** `eje` y `transversal`. Si los dos sentidos del eje tienen tiempos distintos, `eje_oriente` y
      `eje_poniente`. Para flechas de viraje, `giro_<calle>`. Para peatones, `peatonal_<calle>`, con el verde
      intermitente anotado como `amarillo`.
    - **color:** `verde`, `amarillo` o `rojo`, en el instante en que **enciende**.
    - **t:** segundos desde el inicio del video (`134.2`) o `mm:ss.s` (`2:14.2`).
3. Empezar en el primer verde del grupo y terminar en un verde (así cada ciclo queda cerrado).

Ejemplo de dos ciclos del eje:

```csv
medicion_id,grupo,color,t,notas
C04-PM-D1,eje,verde,12.4,
C04-PM-D1,eje,amarillo,58.1,
C04-PM-D1,eje,rojo,61.1,
C04-PM-D1,eje,verde,102.5,
C04-PM-D1,eje,amarillo,148.0,
C04-PM-D1,eje,rojo,151.0,
C04-PM-D1,eje,verde,192.6,
```

4. Procesar: `python scripts/procesar_terreno.py` genera `data/terreno/resumen_tiempos.csv` con ciclo, verde,
   amarillo y rojo (media y desviación) por medición y grupo. Avisa si algún grupo tiene menos de 3 ciclos completos y
   marca `ciclo_variable = si` cuando el ciclo varía más de 4 s.

## 6. Control de calidad

- Al menos 3 ciclos completos por grupo; si no, repetir la medición.
- En cada cruce, el ciclo del eje y el de la transversal deben coincidir (es el mismo controlador). Si difieren más de
  2 s, revisar la extracción.
- Amarillo muy distinto entre ciclos del mismo grupo → revisar la extracción.
- Si `ciclo_variable = si`, anotar el cruce como probablemente actuado o adaptativo; ese dato es útil en sí mismo.

## 7. Seguridad y privacidad

- Grabar siempre desde la vereda, nunca desde la calzada ni desde un vehículo en movimiento.
- Encuadrar los semáforos, no a las personas.
- **Los videos no se suben a git ni se publican** (rostros y patentes): quedan en
  `tsc-thesis/data/terreno/videos/`, excluida del repositorio. Solo se publican los CSV con tiempos extraídos.
