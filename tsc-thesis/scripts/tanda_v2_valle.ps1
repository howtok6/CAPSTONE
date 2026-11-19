# Valle sobre la red depurada con la configuracion validada con TomTom (18 y 19-nov):
# escala 0,18 y speedFactor 0,7. Demanda (3 train + 10 eval) -> Webster -> lineas base (10 replicas).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\tanda_v2_valle.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$log = "logs\tanda_v2"
New-Item -ItemType Directory -Force $log | Out-Null
function Paso($nombre, $argumentos) {
    "{0:HH:mm:ss} inicio {1}" -f (Get-Date), $nombre | Add-Content "$log\avance.txt"
    $p = Start-Process -FilePath python -ArgumentList $argumentos -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput "$log\$nombre.log" -RedirectStandardError "$log\$nombre.err"
    "{0:HH:mm:ss} fin {1} (codigo {2})" -f (Get-Date), $nombre, $p.ExitCode | Add-Content "$log\avance.txt"
    if ($p.ExitCode -ne 0) { throw "fallo $nombre" }
}
Paso "demanda_valle" @("-u", "scripts\build_demand_area.py", "--scenario", $s, "--escala", "0.18", "--speed-factor", "0.7",
                       "--profiles", "eod_valle", "--train-replicas", "3", "--eval-replicas", "10")
Paso "webster_valle" @("-u", "scripts\build_webster.py", "--scenario", $s, "--profile", "eod_valle")
& powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\baselines_paralelo.ps1" -Perfil eod_valle -Semillas 10
if ($LASTEXITCODE -ne 0) { throw "fallaron las lineas base" }
"{0:HH:mm:ss} TODO OK valle" -f (Get-Date) | Add-Content "$log\avance.txt"
