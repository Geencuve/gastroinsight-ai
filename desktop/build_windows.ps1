# Construye GastroInsight AI para Windows: ejecutable (PyInstaller) + instalador (Inno Setup).
# Uso: powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"

Write-Host "1/5 Dependencias de escritorio..." -ForegroundColor Cyan
python -m pip install -q -r requirements-desktop.txt

Write-Host "2/5 Modelos de IA e icono..." -ForegroundColor Cyan
if (-not (Test-Path ai_vision\ml_models\emotion-ferplus-8.onnx)) { python scripts\download_models.py }
python desktop\make_icon.py

Write-Host "3/5 Archivos estaticos..." -ForegroundColor Cyan
python manage.py collectstatic --noinput --clear -v 0

Write-Host "4/5 Empaquetando con PyInstaller (puede tardar 10-15 minutos)..." -ForegroundColor Cyan
pyinstaller desktop\gastroinsight.spec --noconfirm --clean --distpath dist --workpath build

Write-Host "5/5 Creando el instalador..." -ForegroundColor Cyan
function Find-Iscc {
    foreach ($p in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) { if (Test-Path $p) { return $p } }
    return $null
}
$iscc = Find-Iscc
if (-not $iscc) {
    winget install --id JRSoftware.InnoSetup -e --accept-source-agreements --accept-package-agreements
    $iscc = Find-Iscc
}
if (-not $iscc) { throw "No se encontro Inno Setup. Instalalo desde jrsoftware.org y vuelve a ejecutar." }
& $iscc desktop\installer.iss

$setup = Get-ChildItem dist\GastroInsightAI-Setup-*.exe | Select-Object -First 1
Write-Host ""
Write-Host "Listo: $($setup.FullName) ($([math]::Round($setup.Length / 1MB)) MB)" -ForegroundColor Green
