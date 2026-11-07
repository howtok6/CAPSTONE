# Pilotos por comuna

Se usa la misma tabla de mediciones para las **32 comunas de la provincia de
Santiago**, con **seis puntos de referencia por comuna: 192 en total**.
Cambiar de comuna no realiza consultas al proveedor. Cada clic en
**Consultar velocidades y tiempos** realiza seis consultas de flujo para la
comuna seleccionada. No se consultan las 32 comunas de una sola vez.

| Comuna | Ejes de referencia | Pantalla |
| --- | --- | --- |
| Cerrillos | PEDRO AGUIRRE CERDA | [Abrir](http://127.0.0.1:8000/cerrillos) |
| Cerro Navia | JOSE JOAQUIN PEREZ / NEPTUNO | [Abrir](http://127.0.0.1:8000/cerro-navia) |
| Conchalí | DORSAL / INDEPENDENCIA | [Abrir](http://127.0.0.1:8000/conchali) |
| El Bosque | GRAN AVENIDA | [Abrir](http://127.0.0.1:8000/el-bosque) |
| Estación Central | ALAMEDA | [Abrir](http://127.0.0.1:8000/estacion-central) |
| Huechuraba | RECOLETA / PEDRO FONTOVA | [Abrir](http://127.0.0.1:8000/huechuraba) |
| Independencia | INDEPENDENCIA | [Abrir](http://127.0.0.1:8000/independencia) |
| La Cisterna | GRAN AVENIDA | [Abrir](http://127.0.0.1:8000/la-cisterna) |
| La Florida | VICUÑA MACKENNA | [Abrir](http://127.0.0.1:8000/la-florida) |
| La Granja | SANTA ROSA | [Abrir](http://127.0.0.1:8000/la-granja) |
| La Pintana | SANTA ROSA | [Abrir](http://127.0.0.1:8000/la-pintana) |
| La Reina | LARRAIN | [Abrir](http://127.0.0.1:8000/la-reina) |
| Las Condes | Apoquindo / Apoquindo / Manquehue / Manquehue | [Abrir](http://127.0.0.1:8000/las-condes) |
| Lo Barnechea | La Dehesa / Alcalde Delano | [Abrir](http://127.0.0.1:8000/lo-barnechea) |
| Lo Espejo | LO ESPEJO / AV. CENTRAL | [Abrir](http://127.0.0.1:8000/lo-espejo) |
| Lo Prado | SAN PABLO | [Abrir](http://127.0.0.1:8000/lo-prado) |
| Macul | QUILIN | [Abrir](http://127.0.0.1:8000/macul) |
| Maipú | LOS PAJARITOS / PAJARITOS | [Abrir](http://127.0.0.1:8000/maipu) |
| Ñuñoa | Irarrázaval | [Abrir](http://127.0.0.1:8000/nunoa) |
| Pedro Aguirre Cerda | DEPARTAMENTAL | [Abrir](http://127.0.0.1:8000/pedro-aguirre-cerda) |
| Peñalolén | GRECIA | [Abrir](http://127.0.0.1:8000/penalolen) |
| Providencia | Providencia | [Abrir](http://127.0.0.1:8000/providencia) |
| Pudahuel | SAN PABLO | [Abrir](http://127.0.0.1:8000/pudahuel) |
| Quilicura | MANUEL ANTONIO MATTA / LO CRUZAT | [Abrir](http://127.0.0.1:8000/quilicura) |
| Quinta Normal | CARRASCAL | [Abrir](http://127.0.0.1:8000/quinta-normal) |
| Recoleta | RECOLETA | [Abrir](http://127.0.0.1:8000/recoleta) |
| Renca | MIRAFLORES / DOMINGO SANTA MARIA | [Abrir](http://127.0.0.1:8000/renca) |
| San Joaquín | LAS INDUSTRIAS | [Abrir](http://127.0.0.1:8000/san-joaquin) |
| San Miguel | GRAN AVENIDA | [Abrir](http://127.0.0.1:8000/san-miguel) |
| San Ramón | SANTA ROSA | [Abrir](http://127.0.0.1:8000/san-ramon) |
| Santiago | ALAMEDA B. O'HIGGINS | [Abrir](http://127.0.0.1:8000/santiago) |
| Vitacura | Vitacura | [Abrir](http://127.0.0.1:8000/vitacura) |

También puedes abrir <http://127.0.0.1:8000/comunas> y elegir la comuna en el selector.
La URL cambia al elegirla, de modo que puedes guardar o compartir el enlace local.
La selección borra la captura anterior de la pantalla: cada tabla y descarga
corresponden exclusivamente a la comuna seleccionada. Mientras se obtiene una
captura, se bloquea el selector para evitar mezclar resultados.

## Fuentes y alcance

Los códigos y coordenadas de referencia provienen del [inventario oficial UOCT RM,
revisión del 15 de mayo de 2023](https://www.transporteinforma.cl/content/uploads/2023/10/Intersecciones-de-Semaforos-conectados-a-Sistema-UOCT-RM.pdf).
Cada punto conserva la página de origen del PDF en `source_page`, contando desde 1.
Las etiquetas de calles se normalizaron para su lectura. Ese inventario no confirma
el funcionamiento actual de los semáforos ni contiene aforos o programaciones.

El alcance se contrastó con la [lista oficial de la provincia de Santiago](https://dprmetropolitana.dpr.gob.cl/conozca-la-region/).
Los cinco pilotos anteriores se conservan. Las 27 comunas agregadas tienen seis
registros cada una, con dos accesos identificados y coordenadas de seis decimales
legibles en el PDF (`-33,ddd,ddd` y `-70,ddd,ddd`). Los formatos ambiguos,
coordenadas fuera de la ventana urbana de selección y etiquetas peatonales se
omiten; no se reparan posiciones dudosas. También se excluyó `J121811` por una
longitud incompatible con el resto del eje Matta en Quilicura.

En cada piloto nuevo se seleccionaron puntos separados al menos 80 metros en
uno o dos ejes. La selección es exploratoria, no una muestra estadística de la
comuna. La comuna es la indicada por UOCT; no se verificó contra un polígono
administrativo. Algunos cruces están en límites comunales. La ubicación y el
sentido de la vía que devuelve TomTom siguen pendientes de validación en mapa.

Cada archivo `app/data/{identificador_con_guiones_bajos}.json` contiene los puntos,
ventana y dos rutas. Los nuevos también conservan `source_commune`,
`source_latitude_raw` y `source_longitude_raw`. El [registro de importación](INVENTARIO_COMUNAS.json)
contiene la huella SHA-256 del PDF, filtros, exclusiones y códigos seleccionados.
Para reproducir los 27 archivos nuevos desde una copia local del PDF oficial:

```bash
python -m pip install -e '.[inventory]'
python -m scripts.import_uoct --pdf tmp/pdfs/uoct-rm-2023.pdf
```

El importador no descarga datos ni consulta TomTom; solo regenera los 27 pilotos
nuevos y su registro de procedencia. No modifica los cinco archivos originales.
`tmp/` está excluido de Git. La API no requiere pypdf para funcionar.

Las ventanas de incidentes son rectángulos de estudio alrededor de los puntos.
No son polígonos administrativos ni cubren toda la comuna. La captura consulta
el tramo más cercano al punto; hay que validar la vía y el sentido en el mapa,
especialmente en pasos a desnivel y vías paralelas.

La tabla muestra velocidad actual, velocidad de flujo libre, tiempos actuales y
de referencia, demora, confianza y estado de cierre. No hay aceleración, conteos
de vehículos, estados de las luces ni planes semafóricos. No se activa un sondeo
continuo ni se guarda un histórico automáticamente.

## API

El catálogo `GET /api/studies` devuelve comunas y enlaces disponibles sin consumir
cuota de TomTom. Para cada identificador de la tabla anterior:

```text
GET /api/studies/{study_id}
GET /api/studies/{study_id}/points.geojson
GET /api/studies/{study_id}/snapshot?include_incidents=false
GET /api/studies/{study_id}/snapshot.csv
```

Configuración y GeoJSON no consultan TomTom. Una captura solo de flujo y una
descarga CSV desde la API realizan seis consultas cada una. Si consultas
`snapshot` sin parámetros, se incluye una consulta adicional de incidentes.
`include_routes=true` agrega dos recorridos entre los extremos del piloto, en
ambos sentidos. El motor elige el recorrido: no se obliga a seguir un eje específico.

La API devuelve 404 para comunas no configuradas. No acepta rutas de archivos
como identificadores. Una falta de datos se informa explícitamente y no se
transforma en velocidad cero.

Los botones CSV y JSON de la pantalla reutilizan la captura visible y no hacen
nuevas consultas. El CSV identifica la comuna y el punto de cada observación.

## Terminal

```bash
cd santiago-traffic-api
source .venv/bin/activate
python -m app.capture_study --study providencia --without-incidents
python -m app.capture_study --study nunoa --format csv
python -m app.capture_study --study lo-barnechea --format json
python -m app.capture_study --study vitacura --include-routes
```

Cada comando produce una muestra nueva. Los comandos imprimen resultados, sin
guardar archivos ni iniciar procesos en segundo plano. El comando anterior
`python -m app.capture_las_condes` sigue disponible y usa Las Condes por defecto.

Consulta `DATOS_LAS_CONDES.md` para la interpretación de los campos y los datos
adicionales necesarios para estudiar semáforos. Los derechos de conservación y
reutilización del proveedor deben verificarse antes de construir un histórico.
