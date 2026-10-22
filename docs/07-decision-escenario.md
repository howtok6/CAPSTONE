# Decisión de escenario: de corredor a nivel comunal

Registrada el 22-oct-2026. Estado: **decidida por el autor; pendiente de validación con el profesor guía.**

## Decisión

El proyecto pasa de un corredor único de 8–12 intersecciones (anteproyecto, sección 5.2) a **nivel comunal**.
El **MVP** se acota a las comunas que atraviesa el eje principal oriente–poniente:
**Apoquindo → Providencia → Alameda**.

Según las coordenadas de las redes existentes, el eje cruza **Las Condes** (Apoquindo), **Providencia** (Av.
Providencia) y **Santiago** (Alameda). Esta lista se deriva de la geografía de las redes y conviene confirmarla al fijar
los límites exactos.

## Historia

| Fecha | Escenario | Motivo |
|---|---|---|
| 23-ago-2026 | Apoquindo (11 semáforos sobre el eje) | Separación de cuadras realista (98–531 m) y un solo eje a coordinar. Providencia se descartó por cuadras de 14–44 m. |
| 16-sep a 14-oct-2026 | Alameda-Providencia (36 semáforos) | Pasó a ser el escenario principal sin registro escrito de la decisión. |
| 22-oct-2026 | Nivel comunal; MVP en el eje Apoquindo → Providencia → Alameda | Decisión de alcance del autor. |

## Cobertura actual de las redes

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

**Semáforos sobre el eje en las redes actuales:** 30 (18 en Av. Providencia y 12 en Av. Apoquindo), más los ~13 de
la Alameda que solo están en OSM.

El eje completo mide ~8,5 km. Como referencia de escala, las tres redes suman ~150 semáforos, contra 8–12 del
anteproyecto.

## Decisiones abiertas

1. **Cómo construir la red del eje completo.**
    - *Opción A:* regenerar una sola red desde OSM con un recorte ajustado al eje (franja de algunas cuadras a cada lado). Evita costuras, pero obliga a repetir la depuración en netedit.
    - *Opción B:* unir las redes existentes con `netconvert` y depurar las costuras. Reutiliza el trabajo hecho, pero las uniones entre redes importadas por separado suelen dejar arcos duplicados o desconectados.
    - Recomendación: opción A, reutilizando las correcciones de fases ya hechas (Providencia/Condell y otras).
2. **Cuántos semáforos controla el agente.** Recomendación: solo los del eje; las transversales en tiempo fijo como demanda de contexto. Controlar ~150 agentes multiplica el costo de entrenamiento y aleja el resultado de un despliegue realista por fases.
3. **Qué significa «nivel comunal» después del MVP:** ¿todas las intersecciones semaforizadas de las tres comunas, o el eje más sus transversales principales? Define el alcance de la tesis completa.
4. **Límite poniente del MVP en la Alameda:** hasta dónde se extiende el eje al poniente de Plaza Baquedano (por
   ejemplo, hasta Santa Rosa o hasta Dieciocho). Define cuántos cruces de la Alameda entran a la red.
5. **Validación con el profesor guía,** porque el cambio modifica el escenario del anteproyecto formal (sección 5.2, «corredor de 8–12 intersecciones»).

## Impacto en el resto del proyecto

- **Demanda:** los perfiles actuales se generaron para `alameda_providencia`; habrá que regenerarlos para la red del eje.
- **Plan Webster:** recalcular para la nueva red.
- **Resultados existentes:** los de `alameda_providencia` y `apoquindo` siguen sirviendo como pruebas de sanidad por tramo.
- **Riesgo de cómputo:** mayor que el previsto en el anteproyecto; la decisión 2 es la principal mitigación.
