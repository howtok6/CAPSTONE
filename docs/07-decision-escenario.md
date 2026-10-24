# Decisión de escenario: de corredor a nivel comunal

Registrada el 22-oct-2026. Estado: **decidida por el autor; pendiente de validación con el profesor guía.**

## Decisión

El proyecto pasa de un corredor único de 8–12 intersecciones (anteproyecto, sección 5.2) a **nivel comunal**.
El **MVP** se acota a las comunas que atraviesa el eje principal oriente–poniente:
**Apoquindo → Providencia → Alameda**.

**Límites del MVP (decididos el 22-oct): los de las comunas de Santiago, Providencia y Las Condes.** Calculados
cruzando el eje con los límites administrativos de OpenStreetMap (`boundary=administrative`, `admin_level=8`):

| Tramo | Comuna | Desde | Hasta |
|---|---|---|---|
| Alameda (Av. Libertador Bernardo O'Higgins) | Santiago | Matucana / Exposición (−70,679), límite con Estación Central | Plaza Baquedano (−70,635) |
| Av. Providencia | Providencia | Plaza Baquedano (−70,635) | Av. Tobalaba (−70,6015), límite con Las Condes |
| Av. Apoquindo | Las Condes | Av. Tobalaba (−70,6015) | término de la avenida junto a Camino El Alba (−70,545) |

El eje mide ~13,5 km (suma de tramos en línea recta) y tiene **~86 puntos semaforizados**: 37 en Santiago, 23 en
Providencia y 26 en Las Condes (nodos de semáforo de OSM a menos de 45 m agrupados en un punto; incluye pasos
peatonales semaforizados, así que el número de intersecciones es menor).

## Historia

| Fecha | Escenario | Motivo |
|---|---|---|
| 23-ago-2026 | Apoquindo (11 semáforos sobre el eje) | Separación de cuadras realista (98–531 m) y un solo eje a coordinar. Providencia se descartó por cuadras de 14–44 m. |
| 16-sep a 14-oct-2026 | Alameda-Providencia (36 semáforos) | Pasó a ser el escenario principal sin registro escrito de la decisión. |
| 22-oct-2026 | Nivel comunal; MVP en el eje Apoquindo → Providencia → Alameda | Decisión de alcance del autor. |
| 22-oct-2026 | Límites del MVP = límites comunales de Santiago, Providencia y Las Condes | Decisión del autor; extremos calculados con los límites de OSM. |

## Red del eje completo (construida el 24-oct-2026)

`scenarios/eje_comunal` cubre todo el MVP, de Matucana al término de Av. Apoquindo. Se reconstruye con:

```
python scripts/download_axis_osm.py --out scenarios/eje_comunal --buffer 150
python scripts/build_santiago.py --osm=<recuadros> --out scenarios/eje_comunal --tls-join-dist 30 --keep-geo-boundary=<franja_poly.txt>
python scripts/fix_tls.py --scenario scenarios/eje_comunal
python scripts/list_axis_tls.py --scenario scenarios/eje_comunal
python scripts/diagnose_net.py --scenario scenarios/eje_comunal
```

- **Franja:** 150 m a cada lado del eje (provisional; ver decisión abierta 5), cortada en Matucana. Polígono en
  `franja.geojson`.
- **Tamaño:** 1 130 arcos, 86 programas de semáforo: **64 sobre el eje** (27 en la Alameda, 19 en Av. Providencia,
  19 en Av. Apoquindo; uno compartido en Baquedano) y 22 solo en transversales. Listas en `tls_eje.json`.
- **Correcciones automáticas:** semáforos a menos de 30 m se unen (las dos calzadas de la Alameda en un mismo
  cruce); dos semáforos con un solo verde y virajes permisivos reciben una fase de viraje protegido
  (`fix_tls.py`, `tls_fixes.add.xml`), entre ellos Providencia × Condell.
- **Diagnóstico:** APTA. Sin problemas estructurales; en 1 200 s de prueba, 0 teletransportes, 0 colisiones, 0 atascos.
- **Fuente:** API principal de OSM en siete recuadros (Overpass no respondió). Los recuadros no se versionan.

## Cobertura de las redes anteriores

| Red | Longitud (oeste → este) | Extensión | Semáforos | Calles principales |
|---|---|---|---|---|
| `alameda_providencia` | −70,651 a −70,611 | 3,8 × 2,1 km | 36 | Av. Providencia, Salvador, Bellavista, Manuel Montt — **no incluye la Alameda** |
| `providencia` | −70,637 a −70,592 | 4,2 × 2,8 km | 72 | Andrés Bello, Los Leones, Av. Providencia, El Bosque |
| `apoquindo` | −70,598 a −70,560 | 3,5 × 1,9 km | 42 | Av. Apoquindo, Los Militares, Martín de Zamora |

**La Alameda no está en ninguna red (verificado el 22-oct).** Pese a su nombre, `alameda_providencia` no tiene ninguna
arista llamada Alameda ni Libertador Bernardo O'Higgins: su extremo poniente está en Plaza Baquedano (Vicuña Mackenna,
Bellavista) y su primer semáforo sobre el eje es Providencia × General Bustamante. En OpenStreetMap hay 29 nodos de
semáforo sobre la Alameda entre Baquedano y Dieciocho (−70,635 a −70,659), que corresponden a unos 13 cruces (cada
calzada tiene su propio nodo).

**Brecha en Providencia:** entre −70,611 y −70,598 hay ~1,2 km del eje sin cubrir en las redes principales (Av.
Providencia, entre Pedro de Valdivia y Tobalaba, aprox.). Solo la red `providencia` lo cubre, y su diagnóstico la
desaconseja (5 semáforos de fase única, 3 arcos críticos).

**Semáforos sobre el eje en las redes actuales:** 30 (18 en Av. Providencia y 12 en Av. Apoquindo hasta Alonso de
Córdova). Fuera de las redes quedan toda la Alameda y Av. Apoquindo al oriente de Alonso de Córdova.

Como referencia de escala, las tres redes actuales suman ~150 semáforos (incluidas transversales), contra 8–12 del
anteproyecto.

## Decisiones abiertas

1. **Cómo construir la red del eje completo.**
    - *Opción A:* regenerar una sola red desde OSM con un recorte ajustado al eje (franja de algunas cuadras a cada lado). Evita costuras, pero obliga a repetir la depuración en netedit.
    - *Opción B:* unir las redes existentes con `netconvert` y depurar las costuras. Reutiliza el trabajo hecho, pero las uniones entre redes importadas por separado suelen dejar arcos duplicados o desconectados.
    - Recomendación: opción A, reutilizando las correcciones de fases ya hechas (Providencia/Condell y otras).
    - **Resuelto el 24-oct:** se aplicó la opción A (ver «Red del eje completo»).
2. **Cuántos semáforos controla el agente.** Recomendación: solo los del eje; las transversales en tiempo fijo como demanda de contexto. Aun así, el eje solo ya tiene 64 semáforos en la red construida (5 a 8 veces lo previsto en el anteproyecto), así que conviene evaluar si se agrupan cruces muy cercanos en un agente o si el MVP entrena por tramo comunal antes de unir el eje.
3. **Qué significa «nivel comunal» después del MVP:** ¿todas las intersecciones semaforizadas de las tres comunas, o el eje más sus transversales principales? Define el alcance de la tesis completa.
4. ~~Límite poniente del MVP en la Alameda~~ — **resuelto el 22-oct:** límites comunales (tabla de arriba).
5. **Ancho de la franja de red** a cada lado del eje: cuántas cuadras de transversales se incluyen como demanda de
   contexto (recomendación: hasta el primer cruce semaforizado de cada transversal).
6. **Validación con el profesor guía,** porque el cambio modifica el escenario del anteproyecto formal (sección 5.2, «corredor de 8–12 intersecciones»).

## Impacto en el resto del proyecto

- **Demanda:** los perfiles actuales se generaron para `alameda_providencia`; habrá que regenerarlos para la red del eje.
- **Plan Webster:** recalcular para la nueva red.
- **Resultados existentes:** los de `alameda_providencia` y `apoquindo` siguen sirviendo como pruebas de sanidad por tramo.
- **Riesgo de cómputo:** mayor que el previsto en el anteproyecto; la decisión 2 es la principal mitigación.
