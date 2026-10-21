param([int]$Port = 8501, [string]$DataDir = '')  # -DataDir: folder of real GBB Excel exports (sets GBB_DATA_DIR)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$appPath = Join-Path $projectRoot 'app.py'
$runtimePath = Join-Path $projectRoot '.runtime'
$pidPath = Join-Path $runtimePath 'streamlit.pid'
if (!(Test-Path -LiteralPath $appPath)) { throw 'app.py is missing.' }
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
if (Test-Path -LiteralPath $pidPath) {
    $recordedPid = [int](Get-Content -LiteralPath $pidPath)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $recordedPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -like '*streamlit*' -and $existing.CommandLine.Contains($appPath)) {
        Write-Output "SignalDesk is already running (PID $recordedPid)."
        exit 0
    }
}
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port $Port is already occupied. Use -Port with a free port." }
if ($DataDir) {  # several folders may be given, separated by ";" (the first is searched first)
    foreach ($dir in ($DataDir -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
        if (!(Test-Path -LiteralPath $dir -PathType Container)) { throw "Data folder not found: $dir" }
    }
    $env:GBB_DATA_DIR = $DataDir
}
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $pythonPath = $localPython }
$arguments = '-m streamlit run "' + $appPath + '" --server.address=127.0.0.1 --server.port=' + $Port + ' --server.headless=true --browser.gatherUsageStats=false'
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'streamlit.stdout.log') -RedirectStandardError (Join-Path $runtimePath 'streamlit.stderr.log')
Set-Content -LiteralPath $pidPath -Value $process.Id
Write-Output "SignalDesk starting at http://127.0.0.1:$Port (PID $($process.Id)). Logs: $runtimePath"
