# Lineas base de un perfil con un proceso por controlador (run_baselines.py es secuencial:
# 4 controladores x 10 replicas x ~15 min en punta tarde = ~10 h; en paralelo, ~2,5 h).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\baselines_paralelo.ps1 -Perfil eod_punta_tarde
param([string]$Perfil = "eod_punta_tarde", [int]$Semillas = 10,
      [string]$Escenario = "scenarios\las_condes_providencia")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$esc = Split-Path $Escenario -Leaf
$log = "logs\tanda_v2"
New-Item -ItemType Directory -Force $log | Out-Null
$procs = @()
foreach ($c in "fixed", "webster", "greedy", "maxpressure") {
    $out = "results\${esc}_${Perfil}_baselines_$c.json"
    $procs += Start-Process -FilePath python -PassThru -WindowStyle Hidden `
        -ArgumentList @("-u", "scripts\run_baselines.py", "--scenario", $Escenario, "--profile", $Perfil,
                        "--seeds", "$Semillas", "--controllers", $c, "--out", $out) `
        -RedirectStandardOutput "$log\baselines_${Perfil}_$c.log" -RedirectStandardError "$log\baselines_${Perfil}_$c.err"
}
$procs | ForEach-Object { $null = $_.Handle }  # sin esto ExitCode queda vacio al terminar
"{0:HH:mm:ss} lineas base {1}: 4 procesos lanzados" -f (Get-Date), $Perfil | Add-Content "$log\avance.txt"
$procs | Wait-Process
$malos = @($procs | Where-Object { $_.ExitCode -ne 0 })
if ($malos.Count) {
    "{0:HH:mm:ss} lineas base {1}: fallaron {2}" -f (Get-Date), $Perfil, $malos.Count | Add-Content "$log\avance.txt"
    exit 1
}
python -c "import json,glob,sys; p=sys.argv[1]; f=sorted(glob.glob(f'results/{p}_baselines_*.json')); r=[x for a in f for x in json.load(open(a))]; json.dump(r, open(f'results/{p}_baselines.json','w'), indent=2); print(len(r), 'corridas')" "${esc}_${Perfil}"
"{0:HH:mm:ss} lineas base {1}: OK -> results\{2}_{1}_baselines.json" -f (Get-Date), $Perfil, $esc | Add-Content "$log\avance.txt"
