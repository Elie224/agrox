param(
    [string]$Message = "Update AgroX"
)

$ErrorActionPreference = "Stop"

function Run-Git {
    param([string[]]$GitArgs)
    Write-Host "> git $($GitArgs -join ' ')"
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Commande git echouee: git $($GitArgs -join ' ')"
    }
}

# Verifie que le dossier est bien un repo git.
if (-not (Test-Path ".git")) {
    Write-Error "Aucun repo git detecte dans ce dossier."
    exit 1
}

# Synchronise d'abord les refs distantes.
Run-Git @("fetch", "origin", "main")
Run-Git @("fetch", "hf", "main")

$local = (git rev-parse main).Trim()
$origin = (git rev-parse origin/main).Trim()
$hf = (git rev-parse hf/main).Trim()

if ($origin -ne $hf) {
    Write-Error "origin/main et hf/main divergent. Synchronisez d'abord les remotes avant de pousser."
    exit 1
}

if ($local -ne $origin) {
    Write-Host "La branche locale n'est pas alignee avec origin/main. Rebase auto..."
    Run-Git @("pull", "--rebase", "origin", "main")
}

Run-Git @("add", "-A")

$hasStaged = & git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Aucun changement a commit."
}
else {
    Run-Git @("commit", "-m", $Message)
}

Run-Git @("push", "origin", "main")
Run-Git @("push", "hf", "main")

Write-Host "Publie sur GitHub (origin) et Hugging Face (hf)."
