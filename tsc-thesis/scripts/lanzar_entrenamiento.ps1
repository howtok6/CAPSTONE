# Lanza corridas de entrenamiento desacopladas: siguen aunque se cierre la terminal
# o la app, a prioridad baja para no estorbar el uso normal del equipo.
#
#   .\scripts\lanzar_entrenamiento.ps1 -Corridas "fase:0","fase:1","estandar:0" -Pasos 2000000
#
# Cada corrida es "<observacion>:<semilla>". Salida en logs\<modelo>.log; curva en
# models\<escenario>\<modelo>_log\progress.csv; checkpoints en <modelo>_ckpt\.
param(
    [string[]]$Corridas = @("fase:0"),
    [int]$Pasos = 2000000,
    [string]$Escenario = "scenarios/eje_comunal",
    [string]$Perfil = "punta_tarde",
    [string]$Optimizador = "adam",
    [string]$Recompensa = "wait",
    [string]$Extra = ""
)

$raiz = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
New-Item -ItemType Directory -Force (Join-Path $raiz "logs") | Out-Null
$inicio = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly `
    -Property @{ ShowWindow = [uint16]0; PriorityClass = [uint32]16384 }   # BelowNormal

foreach ($c in $Corridas) {
    $obs, $semilla = $c.Split(":")
    $nombre = "ppo_${obs}_${Recompensa}_${Optimizador}_${Perfil}_s$semilla"
    $log = Join-Path $raiz "logs\$nombre.log"
    $orden = "scripts/train_rl.py --scenario $Escenario --profile $Perfil --obs $obs --seed $semilla " +
             "--steps $Pasos --reward $Recompensa --optimizer $Optimizador $Extra"
    $linea = "cmd /c `"`"$python`" -u $orden > `"$log`" 2>&1`""
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $linea; CurrentDirectory = $raiz; ProcessStartupInformation = $inicio
    }
    Write-Output "$nombre -> PID $($r.ProcessId) (codigo $($r.ReturnValue))"
}
