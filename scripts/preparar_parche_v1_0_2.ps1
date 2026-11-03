# Genera parche_v1_0_2.diff a partir de los cambios de la versión 1.0.2 y verifica que se aplica limpio.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\preparar_parche_v1_0_2.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
function Alto($mensaje) { Write-Host "`nDETENIDO: $mensaje" -ForegroundColor Red; exit 1 }

# 0. Preparación: ignorar el .diff, ajustar el script de publicación y guardar lo pendiente
if (-not (Select-String -Path .gitignore -Pattern 'parche_\*\.diff' -Quiet)) { Add-Content .gitignore 'parche_*.diff' }
$pub = "scripts\publicar_v1_0_2.ps1"
(Get-Content $pub -Encoding UTF8) -replace 'git status --porcelain\)', 'git status --porcelain --untracked-files=no)' |
    Set-Content $pub -Encoding UTF8
git add .gitignore $pub scripts\cambios_v1_0_2.py scripts\preparar_parche_v1_0_2.ps1 requirements.lock requirements.txt
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m "chore: scripts de preparación y publicación de la versión 1.0.2" }
if (git status --porcelain --untracked-files=no) { git status --short; Alto "hay cambios sin guardar distintos de los esperados." }

# 1. Aplicar los cambios
Write-Host "1/4 Aplicando los cambios de la versión 1.0.2..." -ForegroundColor Cyan
venv\Scripts\python.exe scripts\cambios_v1_0_2.py
if ($LASTEXITCODE -ne 0) { git checkout -- .; Alto "un cambio no se pudo aplicar; se revirtió todo." }

# 2. Pruebas afectadas
Write-Host "2/4 Pruebas afectadas..." -ForegroundColor Cyan
venv\Scripts\python.exe manage.py test analytics.test_correlation core.test_legal core.test_home core.test_first_run core.test_guide -v 1
if ($LASTEXITCODE -ne 0) { Alto "fallaron pruebas; los cambios quedaron aplicados para revisarlos (git diff). Envíame la salida." }

# 3. Generar el parche y volver al estado anterior
Write-Host "3/4 Generando parche_v1_0_2.diff..." -ForegroundColor Cyan
git diff --output=parche_v1_0_2.diff
git diff --stat
New-Item -ItemType Directory -Force evidencias\E04 | Out-Null
Copy-Item parche_v1_0_2.diff evidencias\E04\ -Force
git checkout -- .

# 4. Verificar que el parche se aplica limpio
Write-Host "4/4 Verificando el parche..." -ForegroundColor Cyan
git apply --check --ignore-whitespace parche_v1_0_2.diff
if ($LASTEXITCODE -ne 0) { Alto "el parche generado no se aplica limpio." }
Write-Host "`nParche listo: parche_v1_0_2.diff (copia en evidencias\E04). Ahora ejecuta scripts\publicar_v1_0_2.ps1" -ForegroundColor Green
