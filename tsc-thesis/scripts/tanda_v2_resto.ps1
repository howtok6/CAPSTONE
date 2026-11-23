# Tanda v2, resto (23-nov): termina la evaluacion IPPO, arma punta manana y reajusta Max-Pressure.
#   A) en paralelo: evaluacion IPPO (s0 punta tarde; s1 y s2 en valle y punta tarde; 10 replicas,
#      cada una a su propio JSON) + demanda y Webster de punta manana
#   B) junta las filas IPPO en los JSON de lineas base; lineas base de punta manana (4 procesos)
#      y ajuste de Max-Pressure en valle
#   C) ajuste de Max-Pressure en punta tarde
# Uso: powershell -ExecutionPolicy Bypass -File scripts\tanda_v2_resto.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$esc = "las_condes_providencia"
$log = "logs\tanda_v2"
New-Item -ItemType Directory -Force $log, "results\ippo_v2" | Out-Null
# Que Windows no suspenda el PC mientras corre la tanda (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
Add-Type -Name Energia -Namespace Tesis -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Tesis.Energia]::SetThreadExecutionState([uint32]"0x80000001")
function Nota($t) { "{0:HH:mm:ss} {1}" -f (Get-Date), $t | Add-Content "$log\avance.txt" }
function Lanzar($nombre, $argumentos) {
    $p = Start-Process -FilePath python -ArgumentList $argumentos -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$log\$nombre.log" -RedirectStandardError "$log\$nombre.err"
    $null = $p.Handle
    return $p
}
function Esperar($procs, $etapa) {
    $procs | Wait-Process
    $malos = @($procs | Where-Object { $_.ExitCode -ne 0 }).Count
    Nota "$etapa terminada ($malos con error)"
}

# --- A
$a = @()
$evals = @(@(0, "eod_punta_tarde"), @(1, "eod_valle"), @(1, "eod_punta_tarde"), @(2, "eod_valle"), @(2, "eod_punta_tarde"))
foreach ($e in $evals) {
    $sem, $perfil = $e
    $a += Lanzar "evalua_v2_s${sem}_$perfil" @("-u", "scripts\eval_rl.py", "--scenario", $s, "--profile", $perfil,
        "--model", "models\$esc\ppo_fase_wait_adam_eod_mixto_s$sem.zip", "--seeds", "10",
        "--name", "ippo_mixto_s$sem", "--merge-into", "results\ippo_v2\${perfil}_s$sem.json")
}
$a += Start-Process -FilePath powershell.exe -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command",
    ("python -u scripts\build_demand_area.py --scenario $s --escala 0.18 --speed-factor 0.7 --profiles eod_punta_manana " +
     "--train-replicas 3 --eval-replicas 10 > $log\demanda_pm.log 2>&1; " +
     "python -u scripts\build_webster.py --scenario $s --profile eod_punta_manana > $log\webster_pm.log 2>&1")
$a | ForEach-Object { $null = $_.Handle }
Nota "A: 5 evaluaciones IPPO + demanda/Webster de punta manana lanzadas"
Esperar $a "A"

# --- B
python -c @"
import json, glob, os
for perfil in ('eod_valle', 'eod_punta_tarde'):
    destino = f'results/$($esc)_{perfil}_baselines.json'
    filas = json.load(open(destino))
    for f in sorted(glob.glob(f'results/ippo_v2/{perfil}_s*.json')):
        nuevas = json.load(open(f))
        nombres = {r['controller'] for r in nuevas}
        filas = [r for r in filas if r['controller'] not in nombres] + nuevas
    json.dump(filas, open(destino, 'w'), indent=2)
    print(perfil, sorted({r['controller'] for r in filas}))
"@ *> "$log\junta_ippo.log"
Nota "B: filas IPPO agregadas a los JSON de lineas base"
$b = @()
$b += Start-Process -FilePath powershell.exe -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy",
    "Bypass", "-File", "scripts\baselines_paralelo.ps1", "-Perfil", "eod_punta_manana", "-Semillas", "10"
$b += Lanzar "ajuste_mp_valle" @("-u", "scripts\ajustar_baselines.py", "--scenario", $s, "--profile", "eod_valle",
    "--solo", "maxpressure", "--replicas", "2", "--workers", "3")
Esperar $b "B"

# --- C
$c = @(Lanzar "ajuste_mp_pt" @("-u", "scripts\ajustar_baselines.py", "--scenario", $s, "--profile", "eod_punta_tarde",
    "--solo", "maxpressure", "--replicas", "2", "--workers", "6"))
Esperar $c "C"
Nota "TODO OK resto"

