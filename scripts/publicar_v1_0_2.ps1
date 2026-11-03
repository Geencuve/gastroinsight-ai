# Publica la versión 1.0.2: aplica el parche, prueba, construye el instalador, etiqueta y deja evidencias.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\publicar_v1_0_2.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
function Alto($mensaje) { Write-Host "`nDETENIDO: $mensaje" -ForegroundColor Red; exit 1 }

if (-not (Test-Path parche_v1_0_2.diff)) { Alto "falta parche_v1_0_2.diff en la carpeta del proyecto." }
if (git status --porcelain --untracked-files=no) { git status --short; Alto "hay cambios sin guardar; haz commit antes de aplicar el parche." }
if (git tag --list v1.0.2) { Alto "la etiqueta v1.0.2 ya existe." }
New-Item -ItemType Directory -Force evidencias\E04 | Out-Null

Write-Host "1/5 Verificando y aplicando el parche..." -ForegroundColor Cyan
git apply --check --ignore-whitespace parche_v1_0_2.diff
if ($LASTEXITCODE -ne 0) { Alto "el parche no se puede aplicar automáticamente; no se modificó nada." }
git apply --ignore-whitespace parche_v1_0_2.diff
if ($LASTEXITCODE -ne 0) { Alto "falló la aplicación del parche." }
git diff --stat | Out-File -Encoding utf8 evidencias\E04\cambios_del_parche.txt

Write-Host "2/5 Ejecutando todas las pruebas..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File scripts\ejecutar_pruebas.ps1 -Salida evidencias\E04\pruebas
if ($LASTEXITCODE -ne 0) { Alto "hay pruebas fallidas; revisa evidencias\E04\pruebas\pruebas.log. El parche quedó aplicado sin commit." }

Write-Host "3/5 Construyendo el instalador..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File desktop\actualizar_version.ps1 -Version 1.0.2
$setup = "dist\GastroInsightAI-Setup-1.0.2.exe"
if (-not (Test-Path $setup)) { Alto "no se generó $setup." }

Write-Host "4/5 Commit y etiqueta..." -ForegroundColor Cyan
git add -A
git commit -m "Versión 1.0.2: correlación excluye cámaras demo por defecto y denominación Testbed experimental"
if ($LASTEXITCODE -ne 0) { Alto "falló el commit." }
git tag -a v1.0.2 -m "Versión 1.0.2"
git push; git push origin v1.0.2

Write-Host "5/5 Evidencias..." -ForegroundColor Cyan
Copy-Item $setup evidencias\E04\
@(
    "Etiqueta: v1.0.2"
    "Commit: $(git rev-parse HEAD)"
    "Instalador: GastroInsightAI-Setup-1.0.2.exe ($([math]::Round((Get-Item $setup).Length / 1MB)) MB)"
    "SHA-256: $((Get-FileHash $setup -Algorithm SHA256).Hash)"
) | Tee-Object -FilePath evidencias\E04\commit_etiqueta_instalador.txt
Write-Host "`nVersión 1.0.2 publicada." -ForegroundColor Green
