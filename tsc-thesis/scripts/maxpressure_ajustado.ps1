# Max-Pressure ajustado: elige la mejor configuracion del ajuste (valle y punta tarde), la deja en
# <escenario>/maxpressure_<perfil>.json (tambien para las perturbaciones de punta tarde) y vuelve a
# correr Max-Pressure con 10 replicas. Las filas con los valores por defecto quedan como
# "maxpressure_defecto" en los JSON de lineas base.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\maxpressure_ajustado.ps1 [-EsperarPid <pid>]
param([int]$EsperarPid = 0)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$esc = "las_condes_providencia"
$log = "logs\tanda_v2"
Add-Type -Name Energia3 -Namespace Tesis -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Tesis.Energia3]::SetThreadExecutionState([uint32]"0x80000001")
function Nota($t) { "{0:HH:mm:ss} {1}" -f (Get-Date), $t | Add-Content "$log\avance.txt" }
if ($EsperarPid) {
    Nota "maxpressure_ajustado: esperando a que termine el proceso $EsperarPid"
    Wait-Process -Id $EsperarPid -ErrorAction SilentlyContinue
}
python scripts\elegir_maxpressure.py --scenario $s --perfil eod_valle *> "$log\elegir_mp_valle.log"
python scripts\elegir_maxpressure.py --scenario $s --perfil eod_punta_tarde --tambien "eod_punta_tarde_cierre,eod_punta_tarde_alza" *> "$log\elegir_mp_pt.log"
$procs = @()
foreach ($p in "eod_valle", "eod_punta_tarde") {
    $procs += Start-Process -FilePath python -PassThru -WindowStyle Hidden `
        -ArgumentList @("-u", "scripts\run_baselines.py", "--scenario", $s, "--profile", $p, "--seeds", "10",
                        "--controllers", "maxpressure", "--out", "results\${esc}_${p}_baselines_maxpressure_ajustado.json") `
        -RedirectStandardOutput "$log\mp_ajustado_$p.log" -RedirectStandardError "$log\mp_ajustado_$p.err"
}
$procs | ForEach-Object { $null = $_.Handle }
Nota "maxpressure_ajustado: 2 procesos lanzados"
$procs | Wait-Process
python -c @"
import json
for p in ('eod_valle', 'eod_punta_tarde'):
    destino = f'results/$($esc)_{p}_baselines.json'
    filas = json.load(open(destino))
    for r in filas:
        if r['controller'] == 'maxpressure':
            r['controller'] = 'maxpressure_defecto'
    filas = [r for r in filas if r['controller'] != 'maxpressure'] + json.load(open(f'results/$($esc)_{p}_baselines_maxpressure_ajustado.json'))
    json.dump(filas, open(destino, 'w'), indent=2)
    print(p, sorted({r['controller'] for r in filas}))
"@ *> "$log\junta_mp.log"
Nota "TODO OK maxpressure_ajustado"
