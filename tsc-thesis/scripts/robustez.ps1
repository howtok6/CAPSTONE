# Robustez (OE6): corre las cuatro lineas base y los tres modelos IPPO v2 en las dos perturbaciones
# que prepara robustez.py (cierre de pista y alza subita del 30 %), 5 replicas pareadas con punta tarde.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\robustez.ps1 [-EsperarPid <pid>]
param([int]$EsperarPid = 0, [string]$Perfil = "eod_punta_tarde", [int]$Semillas = 5)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$esc = "las_condes_providencia"
$log = "logs\tanda_v2"
Add-Type -Name Energia2 -Namespace Tesis -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Tesis.Energia2]::SetThreadExecutionState([uint32]"0x80000001")
function Nota($t) { "{0:HH:mm:ss} {1}" -f (Get-Date), $t | Add-Content "$log\avance.txt" }
if ($EsperarPid) {
    Nota "robustez: esperando a que termine el proceso $EsperarPid"
    Wait-Process -Id $EsperarPid -ErrorAction SilentlyContinue
}
$cierre = (Resolve-Path "$s\robustez_cierre.add.xml").Path
foreach ($caso in "cierre", "alza") {
    $p = "${Perfil}_$caso"
    $env:TSC_SUMO_EXTRA = if ($caso -eq "cierre") { "-a $cierre" } else { "" }
    $procs = @()
    $procs += Start-Process -FilePath powershell.exe -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile",
        "-ExecutionPolicy", "Bypass", "-File", "scripts\baselines_paralelo.ps1", "-Perfil", $p, "-Semillas", "$Semillas"
    foreach ($sem in 0, 1, 2) {
        $procs += Start-Process -FilePath python -PassThru -WindowStyle Hidden `
            -ArgumentList @("-u", "scripts\eval_rl.py", "--scenario", $s, "--profile", $p, "--seeds", "$Semillas",
                            "--model", "models\$esc\ppo_fase_wait_adam_eod_mixto_s$sem.zip", "--name", "ippo_mixto_s$sem",
                            "--merge-into", "results\ippo_v2\${p}_s$sem.json") `
            -RedirectStandardOutput "$log\evalua_${p}_s$sem.log" -RedirectStandardError "$log\evalua_${p}_s$sem.err"
    }
    $procs | ForEach-Object { $null = $_.Handle }
    Nota "robustez ${caso}: 4 lineas base + 3 IPPO lanzados (TSC_SUMO_EXTRA='$env:TSC_SUMO_EXTRA')"
    $procs | Wait-Process
    Nota "robustez ${caso}: terminado ($(@($procs | Where-Object { $_.ExitCode -ne 0 }).Count) con error)"
}
$env:TSC_SUMO_EXTRA = ""
python -c @"
import json, glob
for caso in ('cierre', 'alza'):
    p = '$Perfil' + '_' + caso
    destino = f'results/$($esc)_{p}_baselines.json'
    filas = json.load(open(destino))
    for f in sorted(glob.glob(f'results/ippo_v2/{p}_s*.json')):
        nuevas = json.load(open(f))
        nombres = {r['controller'] for r in nuevas}
        filas = [r for r in filas if r['controller'] not in nombres] + nuevas
    json.dump(filas, open(destino, 'w'), indent=2)
    print(p, len(filas))
"@ *> "$log\junta_robustez.log"
Nota "TODO OK robustez"
