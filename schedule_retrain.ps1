param(
  [string]$TaskName = "AgriRetrainHebdo",
  [string]$Day = "MON",
  [string]$Time = "02:00"
)

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "retrain_from_feedback.py"

if (-not (Test-Path $pythonExe)) {
  Write-Error "Python venv introuvable: $pythonExe"
  exit 1
}

if (-not (Test-Path $scriptPath)) {
  Write-Error "Script introuvable: $scriptPath"
  exit 1
}

$taskCmd = "`"$pythonExe`" `"$scriptPath`""

schtasks /Create /F /SC WEEKLY /D $Day /TN $TaskName /TR $taskCmd /ST $Time | Out-Null
Write-Output "Tache planifiee creee: $TaskName ($Day a $Time)"
