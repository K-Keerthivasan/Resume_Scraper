param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Setting up Resume Scraper for Windows..."

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $PythonCommand -m venv .venv
    if (($LASTEXITCODE -ne 0) -and (-not (Test-Path ".venv\Scripts\python.exe"))) {
        throw "Could not create .venv. Install Python 3.10+ and rerun this script."
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Python created the virtual environment, but pip bootstrap failed. Continuing because this project currently has no required packages."
    }
}

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"

$RequirementsHasPackages = (Test-Path "requirements.txt") -and ((Get-Item "requirements.txt").Length -gt 0)
$PipAvailable = $false

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $VenvPython -m pip --version > $null 2> $null
$ErrorActionPreference = $PreviousErrorActionPreference
if ($LASTEXITCODE -eq 0) {
    $PipAvailable = $true
}

if ($PipAvailable) {
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Could not upgrade pip in .venv."
    }
}

if ($RequirementsHasPackages -and $PipAvailable) {
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install packages from requirements.txt."
    }
} elseif ($RequirementsHasPackages) {
    throw "requirements.txt has packages, but pip is not available in .venv. Reinstall Python with pip/ensurepip support."
} else {
    Write-Host "No Python packages to install."
}

New-Item -ItemType Directory -Force -Path "job_data" | Out-Null

Write-Host ""
Write-Host "Windows setup complete."
Write-Host "Start the collector with:"
Write-Host "  .\start_windows.ps1"
