# Demanda del eje comunal derivada de la EOD 2012

Registrada el 11-nov-2026. Estado: **generada y en uso para la tanda de entrenamiento del 11-nov**; pendiente de
validación del profesor guía. Reemplaza, sin borrarla, la demanda aleatoria de `build_demand_profiles.py`.

## Qué cambia

| | Demanda sintética (hasta el 7-nov) | Demanda EOD (desde el 11-nov) |
|---|---|---|
| Origen y destino | Al azar, con peso por tercio poniente/oriente de la red | Viajes en auto de la EOD 2012 proyectados sobre el eje |
| Sentido | Uno solo por perfil en todo el eje | Distinto por tramo, el que resulta de la encuesta |
| Nivel | Período de `randomTrips` elegido a mano | Flujo máximo de punta mañana del censo vehicular (4 600 veh/h) |
| Perfiles | `valle`, `punta_manana`, `punta_tarde`, `sobresaturado` | Los mismos con prefijo `eod_` |
| Script | `scripts/build_demand_profiles.py` | `scripts/build_demand_eod.py` |

Los resultados con demanda sintética (`results/eje_comunal_<perfil>_baselines.json`) no se tocan; los nuevos quedan en
`results/eje_comunal_eod_<perfil>_baselines.json`.

## Datos

Microdatos de la Encuesta Origen Destino de Santiago 2012 (SECTRA): `viajes.csv`, `personas.csv` y
`ViajesDifusion.csv` en `tsc-thesis/data/eod2012/` (fuera de git, ~25 MB). Se descargaron de la copia pública
`github.com/zorzalerrante/aves` (commit `a63dc02`), carpeta `data/external/EOD_STGO`. El factor de expansión es el
del viaje por el de la persona, día laboral normal; con él el total da 18 461 134 viajes, la cifra oficial.

Vehículos: auto chofer = 1 por viaje; taxi = 1; colectivo = 1/3. Buses, motos y bicicletas quedan fuera.

## Modelo

Cada extremo del viaje se proyecta sobre el eje (posición `s` desde Matucana y distancia lateral `d`). La red es una
franja de 150 m a cada lado, así que el viaje se convierte en uno de tres componentes:

| Componente | Cuándo | Por dónde va en la red |
|---|---|---|
| **eje** | Ambos extremos dentro de la franja, o con probabilidad `exp(-d/lambda)` según la distancia de los extremos externos | Recorre el eje entre las posiciones de sus extremos |
| **local** | Un extremo dentro de la franja y el viaje no recorre el eje | Entra o sale por una transversal cercana a ese extremo |
| **cruce** | Ningún extremo interno y origen y destino a lados opuestos, con probabilidad `exp(-(d_o+d_d)/2000)` | Cruza por una transversal cercana al punto donde la recta origen-destino corta el eje |

Ventanas de la encuesta: valle 10:00–12:00; punta mañana 07:00–09:00; punta tarde 17:30–19:30. Las puntas se llevan
a su hora más cargada (factor 1,30 y 1,13). Sobresaturado es 130 % de la punta más cargada, que resulta ser la mañana.

## Parámetros

| Parámetro | Valor | Cómo se fijó |
|---|---|---|
| `lambda` | 445 m | Resuelto para que el máximo de punta mañana entre Santa Rosa y M. Montt sea 4 600 veh/h (censo) |
| Crecimiento del parque | 1,49 | Viajes en auto EMS 2024 / EOD 2012; no se ajusta |
| `lambda_cruce` | 2 000 m | Supuesto |
| `beta` (local y cruce) | 0,05 | **No sale de datos.** Nivel con que la red atiende la punta tarde dejando menos de 5 % de vehículos sin entrar, con el controlador voraz |
| `escala` | 1,0 | El nivel del censo se usa sin retoque |

## Resultado de la calibración

Vehículos por hora (media de las 21 realizaciones de cada perfil): valle 7 297; punta tarde 11 650; punta mañana
15 812; sobresaturado 20 521. La demanda sintética tenía 1 800, 5 000, 4 236 y 6 546.

Flujo a lo largo del eje en el centro de cada zona (veh/h, hacia oriente / hacia poniente):

| Zona | Punta mañana | Punta tarde | Valle |
|---|---|---|---|
| S1 Ruta 5–Santa Rosa | 1 337 / 1 267 | 876 / 2 485 | 113 / 262 |
| S2 Santa Rosa–Baquedano | 1 561 / 1 478 | 699 / 1 476 | 664 / 504 |
| P1 Baquedano–M. Montt | 2 545 / 2 096 | 1 296 / 1 231 | 969 / 1 337 |
| P2 M. Montt–P. de Valdivia | 1 979 / 1 898 | 1 346 / 1 106 | 1 144 / 1 131 |
| P3 P. de Valdivia–Tobalaba | 1 581 / 1 409 | 1 568 / 1 255 | 354 / 666 |
| L1 Tobalaba–Alcántara | 1 712 / 2 063 | 1 799 / 1 076 | 701 / 417 |
| L2 Alcántara–Manquehue | 1 529 / 2 410 | 1 866 / 542 | 431 / 641 |
| L3 Manquehue–Los Dominicos | 1 181 / 1 002 | 879 / 488 | 187 / 105 |

Lecturas:

- **No hay un sentido único por perfil.** En punta mañana, Alameda y Providencia van equilibradas y Apoquindo carga
  hacia el poniente (55–61 %). En punta tarde, Alameda carga hacia el poniente (68–74 %) y Apoquindo hacia el oriente
  (63–77 %). La demanda sintética suponía mañana hacia el oriente y tarde hacia el poniente en todo el eje.
- **Comprobación fuera del ajuste.** El sentido cargado de Apoquindo en punta mañana da 2 063–2 410 veh/h; el censo
  lo estimaba por capacidad en 1 800–2 700. Ese dato no se usó para calibrar.
- **Onda verde de Webster.** Para los perfiles `eod_` no se define sentido (`--offsets auto` no los reconoce y deja
  «ninguno»), coherente con lo anterior.

Prueba con el controlador voraz, una realización por perfil, 1 h:

| Perfil | Vehículos | Sin entrar al final | Demora de los que terminan | Índice de congestión |
|---|---|---|---|---|
| Valle | 7 394 | 0 | 77 s | 1,59 |
| Punta tarde | 11 646 | 530 (4,6 %) | 92 s | 1,82 |
| Punta mañana | 15 668 | 971 (6,2 %) | 143 s | 2,11 |

El índice (tiempo de viaje sobre tiempo a flujo libre) queda bajo el de la muestra de Waze del 16-sep (2,3 a 4,5 en
el eje en punta tarde), que es una sola medición y no es fuente de calibración.

## Limitaciones

- **Datos de 2012.** La estructura espacial es anterior a las líneas 3 y 6 del Metro y al traslado de oficinas hacia
  Las Condes; el crecimiento de 1,49 es parejo para toda la ciudad.
- **Transversales subrepresentadas.** Con `beta` = 0,05 entran por las transversales unas 30 a 45 veh/h por calle en
  las puntas, muy por debajo de lo real. Con `beta` = 0,12 la punta tarde deja 9 % de vehículos sin entrar. Esto
  favorece a cualquier controlador que dé verde al eje y debe decirse al interpretar los resultados.
- **La red modelada tiene menos capacidad que la real.** Con el flujo del censo, la punta mañana ya queda saturada
  con el controlador voraz. Causas probables: pistas y fases estimadas desde OpenStreetMap.
- **`lambda` depende de un solo dato** (el máximo del censo) y de la forma exponencial supuesta.
- **Destino no es ruta.** La encuesta no dice por qué calles pasa el viaje; el reparto entre eje, local y cruce es un
  modelo, no una medición.
- **Menos vehículos que los esperados.** Entre 7 y 11 % de los viajes se descartan porque ningún arco del tipo
  buscado es alcanzable desde el origen.

## Cómo se reproduce

```
python scripts/build_demand_eod.py --scenario scenarios/eje_comunal --solo-calibrar --probar
python scripts/build_demand_eod.py --scenario scenarios/eje_comunal --train-replicas 10 --eval-replicas 10
python scripts/tanda_eod.py --pasos 2000000 --replicas 10
```

La calibración queda en `scenarios/eje_comunal/demand/eod_calibracion.json`. `tanda_eod.py` entrena tres agentes
(`eod_punta_tarde` con semillas 0 y 1, y `eod_mixto`, que rota los cuatro perfiles), calcula los planes de Webster,
corre las líneas base y evalúa todo con 10 réplicas por perfil. Avance en `logs/tanda_eod/estado.json`.

## Pendiente

- Repetir los barridos de `ajustar_baselines.py` con la demanda EOD: Max-Pressure sigue con la configuración ajustada
  sobre la demanda sintética.
- Subir `beta` cuando la red admita más tráfico transversal (revisión de pistas y fases en los cruces principales).
- Contrastar los flujos por zona con los detectores de la UOCT si llega la respuesta de transparencia.

## Resultados de la tanda del 11-nov

Tres agentes IPPO (observación por fase, recompensa `wait`, 2 M de muestras): dos entrenados solo con
`eod_punta_tarde` (semillas 0 y 1) y uno con `eod_mixto` (los cuatro perfiles rotando, semilla 0). Evaluación con 10
demandas por perfil no vistas al entrenar, pareadas entre controladores, 1 h simulada. La tanda corrió de 01:33 a
07:06; la tabla se regenera con `python scripts/resumen_tanda_eod.py`.

Demora media por vehículo incluyendo a los que no terminan (s, ± IC 95 %):

| Controlador | Valle | Punta tarde | Punta mañana | Sobresaturado |
|---|---|---|---|---|
| Tiempo fijo | 228,4 ± 6,4 | 422,7 ± 15,0 | 582,4 ± 11,0 | 735,0 ± 12,6 |
| Webster | 153,1 ± 10,2 | 286,0 ± 22,8 | 512,6 ± 12,1 | 641,6 ± 15,1 |
| Max-Pressure | 109,1 ± 10,0 | 260,0 ± 34,0 | 427,1 ± 14,8 | 561,4 ± 15,5 |
| Voraz | **77,2 ± 2,4** | 206,6 ± 27,1 | 415,5 ± 11,7 | 546,0 ± 14,1 |
| IPPO punta tarde, semilla 0 | 109,7 ± 6,8 | 108,6 ± 4,0 | 419,7 ± 10,9 | 603,6 ± 20,0 |
| IPPO punta tarde, semilla 1 | 88,2 ± 3,9 | **106,9 ± 4,7** | **403,8 ± 16,2** | 555,9 ± 10,6 |
| IPPO mixto, semilla 0 | 77,9 ± 6,0 | 125,9 ± 23,6 | 420,9 ± 13,7 | **535,3 ± 15,0** |

Diferencia de cada agente con el mejor clásico de cada perfil, que en los cuatro es el voraz:

| Agente | Valle | Punta tarde | Punta mañana | Sobresaturado |
|---|---|---|---|---|
| IPPO punta tarde, semilla 0 | +42,1 % | −47,4 % | +1,0 % | +10,5 % |
| IPPO punta tarde, semilla 1 | +14,3 % | −48,3 % | −2,8 % | +1,8 % |
| IPPO mixto, semilla 0 | +1,0 % | −39,1 % | +1,3 % | −2,0 % |

Lectura:

- **La ventaja del agente se concentra en punta tarde.** Ahí baja la demora cerca de la mitad frente al voraz. En
  punta mañana y sobresaturado las diferencias de ±3 % caen dentro del intervalo de confianza: es un empate.
- **H2 no se sostiene con esta demanda.** Con la demanda sintética la ventaja crecía con la congestión; aquí los dos
  perfiles más congestionados son justamente donde no hay ventaja. En ambos quedan sin entrar entre 6 y 16 % de los
  vehículos con cualquier controlador: la red está limitada por capacidad y el control tiene poco margen. Es una
  explicación posible, no comprobada.
- **Entrenar solo en punta tarde generaliza mal.** En valle los dos agentes quedan peor que el voraz, y la semilla 0
  también en sobresaturado. Las dos semillas coinciden en punta tarde y difieren en los demás perfiles.
- **El entrenamiento mixto empata o gana en los cuatro perfiles**, a cambio de menos ventaja y más dispersión en
  punta tarde. Es una sola semilla: falta repetirlo antes de concluir.
- **El voraz supera a Max-Pressure en todos los perfiles.** Max-Pressure no se reajustó para esta demanda; su demora
  entre los que terminan es la menor, pero deja más vehículos sin entrar.

Estas cifras heredan las limitaciones de arriba, en particular las transversales al 5 %. No contrastan todavía las
hipótesis de la tesis.
