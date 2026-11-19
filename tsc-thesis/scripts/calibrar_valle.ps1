# Valle contra la captura TomTom del 19-nov 15:04: demanda a dos escalas con speedFactor 0,7 y comparacion.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$cap = "data\tomtom\las_condes_providencia\flujo_20261119_1504.json"
$log = "logs\validacion"
$procs = @()
foreach ($e in "0.18", "0.25") {
    $t = "e" + $e.Replace("0.", "0") + "_sf07"
    $dir = "$s\demand\calib_$t"
    $cmd = "python -u scripts\build_demand_area.py --scenario $s --escala $e --speed-factor 0.7 --profiles eod_valle --eval-replicas 1 --carpeta $dir > $log\demanda_valle_$t.log 2>&1; " +
           "python -u scripts\comparar_tomtom.py --scenario $s --captura $cap --rutas $dir\eval\routes_eod_valle_s00.rou.xml --speed-factor 0.7 --etiqueta red2_$t > $log\comparar_valle_$t.log 2>&1"
    $procs += Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile", "-Command", $cmd -WindowStyle Hidden -PassThru
}
$procs | Wait-Process
python scripts\resumen_validacion.py --captura flujo_20261119_1504 > $log\resumen_valle.log 2>&1
