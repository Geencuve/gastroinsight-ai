# Ejecuta todas las pruebas con cobertura y deja las evidencias en la carpeta indicada.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\ejecutar_pruebas.ps1 -Salida evidencias\E03
param([string]$Salida = "evidencias\E03")
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force $Salida | Out-Null
Write-Host "Ejecutando todas las pruebas con cobertura (unos minutos)..." -ForegroundColor Cyan
cmd /c "venv\Scripts\coverage.exe run manage.py test --verbosity 2 > $Salida\pruebas.log 2>&1"
$codigo = $LASTEXITCODE
venv\Scripts\coverage.exe report | Out-File -Encoding utf8 "$Salida\cobertura.txt"
venv\Scripts\coverage.exe html -d "$Salida\cobertura_html" -q
venv\Scripts\coverage.exe json -o "$Salida\cobertura.json" -q
venv\Scripts\python.exe scripts\resumen_pruebas.py $Salida
if ($codigo -ne 0) { Write-Host "`nHAY PRUEBAS FALLIDAS: revisa $Salida\pruebas.log" -ForegroundColor Red; exit 1 }
Write-Host "`nTodas las pruebas aprobadas." -ForegroundColor Green
