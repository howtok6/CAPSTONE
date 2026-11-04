<#
.SYNOPSIS
  Prueba de humo de la API v1 del backend de «Vía»: llama a cada endpoint que
  usa la app (y a los de diagnóstico), revisa el código HTTP y muestra un
  resumen. Sirve para comprobar que backend, simulación, OSRM y Nominatim
  responden antes de probar la app en el celular.

.EXAMPLE
  # Con el backend en http://127.0.0.1:8080 y la simulación corriendo:
  powershell -ExecutionPolicy Bypass -File backend\pruebas\probar-endpoints.ps1

.EXAMPLE
  # Otro backend, guardando cada respuesta en un archivo:
  .\probar-endpoints.ps1 -Base http://192.168.1.50:8080 -Salida respuestas.json

.NOTES
  Funciona en Windows PowerShell 5.1 y PowerShell 7. Termina con código 1 si
  algún endpoint no respondió lo esperado. Los viajes que crea los termina al
  final, así que no deja vehículos en la simulación.
#>
param(
  [string]$Base = 'http://127.0.0.1:8080',
  [string]$Salida = '',
  [switch]$SinExternos  # omite la prueba de las teselas de OpenFreeMap
)

$ErrorActionPreference = 'Stop'
$Base = $Base.TrimEnd('/')
$script:resultados = New-Object System.Collections.ArrayList
$script:respuestas = [ordered]@{}

function Probar {
  param(
    [string]$Nombre,
    [string]$Metodo,
    [string]$Ruta,
    $Cuerpo = $null,
    [int[]]$Esperado = @(200),
    [string]$Url = ''
  )
  $uri = if ($Url) { $Url } else { "$Base$Ruta" }
  $p = @{ Uri = $uri; Method = $Metodo; UseBasicParsing = $true; TimeoutSec = 30 }
  if ($null -ne $Cuerpo) {
    $json = $Cuerpo | ConvertTo-Json -Depth 10 -Compress
    $p.Body = [Text.Encoding]::UTF8.GetBytes($json)
    $p.ContentType = 'application/json; charset=utf-8'
  }
  $reloj = [Diagnostics.Stopwatch]::StartNew()
  $codigo = 0; $texto = ''
  try {
    $r = Invoke-WebRequest @p
    $codigo = [int]$r.StatusCode
    $texto = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
  } catch {
    $resp = $_.Exception.Response
    if ($null -ne $resp) { $codigo = [int]$resp.StatusCode }
    $texto = if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  }
  $reloj.Stop()
  $ok = $Esperado -contains $codigo
  $etiqueta = if ($Url) { "$Metodo $Url" } else { "$Metodo $Ruta" }
  [void]$script:resultados.Add([pscustomobject]@{
    Resultado = $(if ($ok) { 'OK' } else { 'FALLA' })
    HTTP      = $codigo
    Esperado  = ($Esperado -join '/')
    Segundos  = [math]::Round($reloj.Elapsed.TotalSeconds, 2)
    Prueba    = $Nombre
    Llamada   = $(if ($etiqueta.Length -gt 90) { $etiqueta.Substring(0, 87) + '...' } else { $etiqueta })
  })
  $color = if ($ok) { 'Green' } else { 'Red' }
  Write-Host ("{0,-6} {1,3}  {2}" -f $(if ($ok) { 'OK' } else { 'FALLA' }), $codigo, $Nombre) -ForegroundColor $color
  if (-not $ok) { Write-Host "       $etiqueta`n       $texto" -ForegroundColor DarkGray }
  $datos = $null
  $inicio = "$texto".TrimStart()
  if ($inicio.StartsWith('{') -or $inicio.StartsWith('[')) {
    try { $datos = $texto | ConvertFrom-Json } catch { }
  }
  $script:respuestas[$Nombre] = [ordered]@{ llamada = $etiqueta; http = $codigo; cuerpo = $Cuerpo; respuesta = $datos }
  return $datos
}

Write-Host "Probando $Base`n"

# --- Estado -----------------------------------------------------------------
$salud = Probar 'Salud del backend y la simulación' GET '/v1/salud'
if ($salud -and $salud.estado -ne 'ok') {
  Write-Host "       Atención: estado '$($salud.estado)'. Sin simulación fallarán semáforos, tráfico y viajes." -ForegroundColor Yellow
}

# --- Lugares (Nominatim, vía backend) --------------------------------------
$q = [uri]::EscapeDataString('Costanera Center')
$null = Probar 'Buscar lugares' GET "/v1/lugares?q=$q"
$null = Probar 'Nombrar un punto del mapa' GET '/v1/lugares/inverso?lat=-33.4372&lon=-70.6275'

# --- Rutas (OSRM, vía backend) ---------------------------------------------
$paradas = @(@{ lat = -33.4378; lon = -70.6504 }, @{ lat = -33.4372; lon = -70.6275 })
$rutas = Probar 'Calcular rutas con semáforos' POST '/v1/rutas' @{ paradas = $paradas; alternativas = $true }
$trazado = if ($rutas) { @($rutas)[0].trazado } else { $null }
$null = Probar 'Ruta con una parada intermedia' POST '/v1/rutas' @{
  paradas = @($paradas[0], @{ lat = -33.4400; lon = -70.6400 }, $paradas[1]); alternativas = $false }

# --- Semáforos y tráfico (simulación, vía backend) -------------------------
$semaforos = Probar 'Semáforos de la red' GET '/v1/semaforos'
$null = Probar 'Semáforos en un recuadro' GET '/v1/semaforos?bbox=-70.66,-33.45,-70.62,-33.43'
$idSemaforo = if ($semaforos) { @($semaforos)[0].id } else { 'GS_inexistente' }
$null = Probar 'Un semáforo por id' GET "/v1/semaforos/$([uri]::EscapeDataString($idSemaforo))"
$null = Probar 'Próximo semáforo sin viaje' GET '/v1/semaforos/proximo?lat=-33.44406&lon=-70.6524&rumbo=92.5'
$null = Probar 'Tráfico por calle' GET '/v1/trafico'
$null = Probar 'Tráfico en un recuadro, con calles libres' GET '/v1/trafico?bbox=-70.66,-33.45,-70.62,-33.43&incluir_libres=true'
$null = Probar 'Destinos de demostración' GET '/v1/simulacion/destinos'

# --- Viaje GPS (lo que hace la app con una ruta propuesta) ------------------
if (-not $trazado) { $trazado = @(@(-33.4378, -70.6504), @(-33.4372, -70.6275)) }
$gps = Probar 'Crear viaje GPS con la ruta elegida' POST '/v1/viajes' @{
  modo = 'gps'; nombre_destino = 'Cerro Santa Lucía'; trazado = $trazado } -Esperado 201
if ($gps) {
  $id = $gps.id
  $p0 = @($trazado)[0]
  $null = Probar 'Enviar ubicación exacta' POST "/v1/viajes/$id/ubicacion" @{
    lat = $p0[0]; lon = $p0[1]; rumbo = 90; velocidad_kmh = 30; precision_m = 6 }
  $null = Probar 'Enviar ubicación aproximada (rango 500 m)' POST "/v1/viajes/$id/ubicacion" @{
    lat = $p0[0]; lon = $p0[1]; precision_m = 500 }
  $null = Probar 'Consultar el viaje GPS' GET "/v1/viajes/$id"
  $null = Probar 'Terminar el viaje GPS' DELETE "/v1/viajes/$id" -Esperado 204
  $null = Probar 'Ubicación en un viaje terminado (error)' POST "/v1/viajes/$id/ubicacion" @{
    lat = $p0[0]; lon = $p0[1] } -Esperado 409
}

# --- Viaje simulado (demo sin moverse) --------------------------------------
$sim = Probar 'Crear viaje simulado' POST '/v1/viajes' @{ modo = 'simulado'; destino = 0 } -Esperado 201
if ($sim) {
  Start-Sleep -Seconds 2
  $null = Probar 'Consultar el viaje simulado' GET "/v1/viajes/$($sim.id)"
  $null = Probar 'Terminar el viaje simulado' DELETE "/v1/viajes/$($sim.id)" -Esperado 204
}

# --- Errores esperados -------------------------------------------------------
$null = Probar 'Viaje inexistente (error)' GET '/v1/viajes/v_no_existe' -Esperado 404
$null = Probar 'Rumbo fuera de rango (error)' GET '/v1/semaforos/proximo?lat=-33.44&lon=-70.65&rumbo=400' -Esperado 400
$null = Probar 'Ruta con una sola parada (error)' POST '/v1/rutas' @{ paradas = @($paradas[0]) } -Esperado 400

# --- Servicio externo que la app usa directo (teselas del mapa) -------------
if (-not $SinExternos) {
  $null = Probar 'Teselas OpenFreeMap (TileJSON)' GET '' -Url 'https://tiles.openfreemap.org/planet'
  $null = Probar 'Fuentes del mapa (glifos)' GET '' -Url 'https://tiles.openfreemap.org/fonts/Noto%20Sans%20Bold/0-255.pbf'
}

# --- Resumen -----------------------------------------------------------------
$fallas = @($script:resultados | Where-Object Resultado -eq 'FALLA').Count
Write-Host ''
$script:resultados | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
Write-Host ("{0} pruebas, {1} fallas" -f $script:resultados.Count, $fallas) -ForegroundColor $(if ($fallas) { 'Red' } else { 'Green' })
if ($Salida) {
  $script:respuestas | ConvertTo-Json -Depth 12 | Out-File -FilePath $Salida -Encoding utf8
  Write-Host "Respuestas guardadas en $Salida"
}
if ($fallas) { exit 1 }
