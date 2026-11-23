# Max-Pressure ajustado: elige la mejor configuracion del ajuste (valle y punta tarde), la deja en
# <escenario>/maxpressure_<perfil>.json (tambien para las perturbaciones de punta tarde) y vuelve a
# correr Max-Pressure con 10 replicas, repartidas en procesos (punta tarde: 5 x 2 replicas;
# valle: 2 x 5). Las filas con los valores por defecto quedan como "maxpressure_defecto".
# Uso: powershell -ExecutionPolicy Bypass -File scripts\maxpressure_ajustado.ps1 [-EsperarPid <pid>]
param([int]$EsperarPid = 0)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$s = "scenarios\las_condes_providencia"
$esc = "las_condes_providencia"
$log = "logs\tanda_v2"
New-Item -ItemType Directory -Force "results\mp_ajustado" | Out-Null
Add-Type -Name Energia3 -Namespace Tesis -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Tesis.Energia3]::SetThreadExecutionState([uint32]"0x80000001")
function Nota($t) { "{0:HH:mm:ss} {1}" -f (Get-Date), $t | Add-Content "$log\avance.txt" }
if ($EsperarPid) {
    Nota "maxpressure_ajustado: esperando a que termine el proceso $EsperarPid"
    Wait-Process -Id $EsperarPid -ErrorAction SilentlyContinue
}
python scripts\elegir_maxpressure.py --scenario $s --perfil eod_valle *> "$log\elegir_mp_valle.log"
python scripts\elegir_maxpressure.py --scenario $s --perfil eod_punta_tarde --tambien "eod_punta_tarde_cierre,eod_punta_tarde_alza" *> "$log\elegir_mp_pt.log"
$trozos = @(@("eod_punta_tarde", 0, 2), @("eod_punta_tarde", 2, 2), @("eod_punta_tarde", 4, 2), @("eod_punta_tarde", 6, 2),
            @("eod_punta_tarde", 8, 2), @("eod_valle", 0, 5), @("eod_valle", 5, 5))
$procs = @()
foreach ($t in $trozos) {
    $p, $ini, $n = $t
    $procs += Start-Process -FilePath python -PassThru -WindowStyle Hidden `
        -ArgumentList @("-u", "scripts\run_baselines.py", "--scenario", $s, "--profile", $p, "--seeds", "$n",
                        "--semilla-inicial", "$ini", "--controllers", "maxpressure",
                        "--out", "results\mp_ajustado\${p}_$ini.json") `
        -RedirectStandardOutput "$log\mp_ajustado_${p}_$ini.log" -RedirectStandardError "$log\mp_ajustado_${p}_$ini.err"
}
$procs | ForEach-Object { $null = $_.Handle }
Nota "maxpressure_ajustado: $($procs.Count) procesos lanzados"
$procs | Wait-Process
Nota "maxpressure_ajustado: corridas terminadas ($(@($procs | Where-Object { $_.ExitCode -ne 0 }).Count) con error)"
python -c @"
import json, glob
for p in ('eod_valle', 'eod_punta_tarde'):
    destino = f'results/$($esc)_{p}_baselines.json'
    filas = json.load(open(destino))
    for r in filas:
        if r['controller'] == 'maxpressure':
            r['controller'] = 'maxpressure_defecto'
    nuevas = [r for f in sorted(glob.glob(f'results/mp_ajustado/{p}_*.json')) for r in json.load(open(f))]
    filas = [r for r in filas if r['controller'] != 'maxpressure'] + nuevas
    json.dump(filas, open(destino, 'w'), indent=2)
    print(p, len(nuevas), sorted({r['controller'] for r in filas}))
"@ *> "$log\junta_mp.log"
Nota "TODO OK maxpressure_ajustado"
