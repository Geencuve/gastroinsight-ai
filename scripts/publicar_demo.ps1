# Publica GastroInsight AI con un enlace HTTPS temporal (Cloudflare Tunnel).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\publicar_demo.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force logs | Out-Null

function Find-Cloudflared {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe",
                     "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

$cloudflared = Find-Cloudflared
if (-not $cloudflared) {
    Write-Host "Instalando cloudflared (una sola vez)..." -ForegroundColor Cyan
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    $cloudflared = Find-Cloudflared
    if (-not $cloudflared) { throw "No se encontró cloudflared. Cierra y abre la terminal, y vuelve a ejecutar el script." }
}

# Configuración solo para esta publicación (no modifica el .env)
$env:DEBUG = "False"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1,.trycloudflare.com"
$env:CSRF_TRUSTED_ORIGINS = "https://*.trycloudflare.com"
$env:SERVE_MEDIA = "True"
$env:PYTHONIOENCODING = "utf-8"

$server = Start-Process -FilePath ".\venv\Scripts\python.exe" `
    -ArgumentList "manage.py", "runserver", "127.0.0.1:8000", "--insecure", "--noreload" `
    -PassThru -NoNewWindow -RedirectStandardOutput "logs\servidor_publico.log" -RedirectStandardError "logs\servidor_publico_err.log"
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Servidor local listo. Abriendo el túnel..." -ForegroundColor Green
Write-Host "Busca abajo la línea con https://...trycloudflare.com y compártela." -ForegroundColor Green
Write-Host "Para terminar la publicación presiona Ctrl + C." -ForegroundColor Yellow
Write-Host ""
try {
    & $cloudflared tunnel --url http://127.0.0.1:8000
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
    Write-Host "Publicación terminada: el enlace ya no funciona." -ForegroundColor Yellow
}
