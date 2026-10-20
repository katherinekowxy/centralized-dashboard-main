$ErrorActionPreference = 'Stop'
$appPath = Join-Path $PSScriptRoot 'app.py'
$pidPath = Join-Path $PSScriptRoot '.runtime\streamlit.pid'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Output 'No tracked SignalDesk process.'; exit 0 }
$recordedPid = [int](Get-Content -LiteralPath $pidPath)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $recordedPid" -ErrorAction SilentlyContinue
if ($process) {
    if ($process.CommandLine -notlike '*streamlit*' -or !$process.CommandLine.Contains($appPath)) { throw 'PID belongs to another process; leaving it running.' }
    Stop-Process -Id $recordedPid
    Write-Output "Stopped SignalDesk (PID $recordedPid)."
}
Remove-Item -LiteralPath $pidPath
