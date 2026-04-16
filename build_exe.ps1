$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$engineDir = Join-Path $projectRoot "engine\AutoClicker.Engine\bin\Release\net8.0-windows"
$engineExe = Join-Path $engineDir "AutoClicker.Engine.exe"
$engineDll = Join-Path $engineDir "AutoClicker.Engine.dll"

if (-not (Test-Path $engineExe) -and -not (Test-Path $engineDll)) {
    throw "Native engine build output was not found in $engineDir. Build the engine first, or keep using the Python-only path."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name AutoClicker `
    --collect-submodules pynput `
    --add-data "app_settings.json;." `
    --add-data "clicker_settings.json;." `
    --add-data "settings_presets.json;." `
    --add-data "theme_presets.json;." `
    --add-data "theme_settings.json;." `
    --add-data "engine\AutoClicker.Engine\bin\Release\net8.0-windows;engine\AutoClicker.Engine\bin\Release\net8.0-windows" `
    app.pyw

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $projectRoot\dist\AutoClicker.exe"
