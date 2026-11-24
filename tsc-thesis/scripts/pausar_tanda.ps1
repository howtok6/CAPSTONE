# Pausa (suspende) o reanuda los procesos de Python de la tanda sin perder su estado en memoria.
#   powershell -ExecutionPolicy Bypass -File scripts\pausar_tanda.ps1            # pausa
#   powershell -ExecutionPolicy Bypass -File scripts\pausar_tanda.ps1 -Reanudar  # reanuda
# Solo toca procesos python.exe que corran scripts\<nombre>.py de la tesis o sean trabajadores de
# multiprocessing (spawn_main) de esos; no toca los servidores MCP. Los orquestadores .ps1 no se
# suspenden: quedan esperando a que sus procesos terminen. La pausa vive en memoria: si el PC se
# apaga o reinicia, se pierden las corridas en curso (los resultados ya guardados quedan).
param([switch]$Reanudar)
Set-Location (Split-Path $PSScriptRoot -Parent)
Add-Type -Namespace Tesis -Name Ntdll -MemberDefinition @'
[DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr h);
[DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr h);
'@
$registro = "logs\tanda_v2\pausados.txt"
$todos = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
# Solo scripts de la tesis (scripts\<nombre>.py); "Python313\Scripts\" de los servidores MCP no calza
$tanda = @($todos | Where-Object { $_.CommandLine -cmatch 'scripts\\[a-z_0-9]+\.py' })
$ids = @($tanda.ProcessId)
$tanda += @($todos | Where-Object { $_.CommandLine -match 'spawn_main' -and $ids -contains $_.ParentProcessId })
foreach ($p in $tanda) {
    $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    $r = if ($Reanudar) { [Tesis.Ntdll]::NtResumeProcess($proc.Handle) } else { [Tesis.Ntdll]::NtSuspendProcess($proc.Handle) }
    $cmd = ($p.CommandLine -replace '.*scripts\\', '' -replace '.*spawn_main.*', '(trabajador)')
    "{0,6} {1} {2}" -f $p.ProcessId, $(if ($r -eq 0) { "ok" } else { "error $r" }), $cmd.Substring(0, [Math]::Min(90, $cmd.Length))
}
"{0:HH:mm:ss} {1}: {2} procesos" -f (Get-Date), $(if ($Reanudar) { "reanudados" } else { "pausados" }), $tanda.Count |
    Tee-Object -Variable linea | Add-Content "logs\tanda_v2\avance.txt"
$linea
