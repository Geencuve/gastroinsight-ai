# Genera un instalador actualizado de GastroInsight AI.
# Uso: powershell -ExecutionPolicy Bypass -File desktop\actualizar_version.ps1 -Version 1.0.1
param([Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$iss = "desktop\installer.iss"
(Get-Content $iss -Encoding UTF8) -replace '#define AppVersion ".*"', "#define AppVersion `"$Version`"" |
    Set-Content $iss -Encoding UTF8

$base = "templates\base.html"
(Get-Content $base -Encoding UTF8) -replace '<strong>GastroInsight AI</strong> · v[\d\.]+', "<strong>GastroInsight AI</strong> · v$Version" |
    Set-Content $base -Encoding UTF8

Write-Host "Version $Version aplicada. Ejecutando pruebas..." -ForegroundColor Cyan
.\venv\Scripts\python.exe manage.py test core.test_home core.test_legal core.test_first_run -v 0
if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron: no se genera el instalador." }

powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1
