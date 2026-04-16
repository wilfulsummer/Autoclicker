$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$dotnetCandidates = @(
    "C:\Program Files\dotnet\dotnet.exe",
    (Join-Path $env:LOCALAPPDATA "Microsoft\dotnet\dotnet.exe")
)
$pythonExe = (& python -c "import sys; print(sys.executable)")
$dotnet = $dotnetCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
$engineProject = Join-Path $projectRoot "engine\AutoClicker.Engine\AutoClicker.Engine.csproj"
$enginePublishDir = Join-Path $projectRoot "engine\publish"
$publishedEngineExe = Join-Path $enginePublishDir "AutoClicker.Engine.exe"
$publishedEngineDll = Join-Path $enginePublishDir "AutoClicker.Engine.dll"
$dotnetCliHome = Join-Path $projectRoot ".dotnet_cli"
$dotnetUserProfile = Join-Path $dotnetCliHome ".dotnet"
$localAppDataRoot = Join-Path $projectRoot ".appdata"
$appDataRoot = Join-Path $localAppDataRoot "Roaming"
$nugetConfig = Join-Path $projectRoot ".nuget\NuGet.Config"
$nugetPackages = Join-Path $projectRoot ".nuget\packages"

if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
    throw "Python executable was not found. Install Python so PyInstaller can build the desktop release."
}

if (-not $dotnet) {
    throw ".NET SDK/runtime host was not found. Install .NET 8 SDK so the native engine can be published for release builds."
}

New-Item -ItemType Directory -Force -Path $dotnetCliHome | Out-Null
New-Item -ItemType Directory -Force -Path $dotnetUserProfile | Out-Null
New-Item -ItemType Directory -Force -Path $localAppDataRoot | Out-Null
New-Item -ItemType Directory -Force -Path $appDataRoot | Out-Null
New-Item -ItemType Directory -Force -Path $nugetPackages | Out-Null
$env:DOTNET_CLI_HOME = $dotnetCliHome
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_MULTILEVEL_LOOKUP = "1"
$env:DOTNET_CLI_FIRST_TIME_USE = "0"
$env:DOTNET_NOLOGO = "1"
$env:HOME = $dotnetUserProfile
$env:USERPROFILE = $dotnetUserProfile
$env:LOCALAPPDATA = $localAppDataRoot
$env:APPDATA = $appDataRoot
$env:NUGET_PACKAGES = $nugetPackages

if (Test-Path $enginePublishDir) {
    Remove-Item -LiteralPath $enginePublishDir -Recurse -Force
}

& $dotnet publish $engineProject `
    -c Release `
    -r win-x64 `
    --self-contained true `
    /p:PublishSingleFile=true `
    /p:IncludeNativeLibrariesForSelfExtract=true `
    --configfile $nugetConfig `
    -o $enginePublishDir

if (-not (Test-Path $publishedEngineExe) -and -not (Test-Path $publishedEngineDll)) {
    throw "Native engine publish failed. Expected output was not created in $enginePublishDir."
}

& $pythonExe -m PyInstaller `
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
    --add-data "engine\publish;engine\publish" `
    app.pyw

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $projectRoot\dist\AutoClicker.exe"
