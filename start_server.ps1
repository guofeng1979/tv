$Host.UI.RawUI.WindowTitle = "Comic Server"
$PYTHON_DIR = Join-Path $PSScriptRoot "..\ComfyUI_windows_portable\python_embeded"
$PYTHON_EXE = Join-Path $PYTHON_DIR "python.exe"

$SERVER_SCRIPT = Get-ChildItem -Path $PSScriptRoot -Filter "*_server.py" | Select-Object -First 1 -ExpandProperty FullName
$HTML_FILE = Get-ChildItem -Path $PSScriptRoot -Filter "*.html" | Where-Object { $_.Name -notlike "*index*" } | Select-Object -First 1 -ExpandProperty FullName

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Static Comic Server Starting" -ForegroundColor Cyan
Write-Host "  Python: $PYTHON_EXE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "[ERROR] Python not found: $PYTHON_EXE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not $SERVER_SCRIPT) {
    Write-Host "[ERROR] Server script not found in: $PSScriptRoot" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Server script: $SERVER_SCRIPT" -ForegroundColor Green
Write-Host "HTML file: $HTML_FILE" -ForegroundColor Green
Write-Host ""

Start-Sleep -Milliseconds 500
if ($HTML_FILE) {
    Start-Process -FilePath $HTML_FILE
}

Write-Host "Starting server (this window must stay open)..." -ForegroundColor Yellow
Write-Host ""
& $PYTHON_EXE $SERVER_SCRIPT
