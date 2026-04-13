param(
    [int]$Port = 5001,
    [switch]$KillExisting
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python introuvable dans .venv. Chemin attendu: $pythonExe"
    exit 1
}

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    if ($KillExisting) {
        foreach ($pid in $pids) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction Stop
                Write-Host "Processus $pid arrete sur le port $Port"
            }
            catch {
                Write-Warning "Impossible d'arreter le processus ${pid}: $($_.Exception.Message)"
            }
        }
    }
    else {
        Write-Host "Port $Port deja occupe (PID: $($pids -join ', ')). Relancez avec -KillExisting pour liberer le port."
        exit 1
    }
}

$env:PORT = "$Port"
Write-Host "Demarrage AgroX sur le port $Port"
& $pythonExe (Join-Path $root "app.py")
