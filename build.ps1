$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$distDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'dist'))
$stagingDirectory = [System.IO.Path]::GetFullPath((Join-Path $distDirectory '.staging'))
$releaseDirectory = Join-Path $distDirectory $timestamp
$stagingArchive = Join-Path $distDirectory ".staging-$timestamp.zip"
if (-not $stagingDirectory.StartsWith($distDirectory + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'The temporary build directory must stay inside dist'
}
if (Test-Path -LiteralPath $stagingDirectory) {
    Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingDirectory | Out-Null
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'tools\build_webview2.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'WebView2 bridge build failed' }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
    $previousPythonUserBase = $env:PYTHONUSERBASE
    $env:PYTHONUSERBASE = Join-Path $PSScriptRoot '.venv\packaging-userbase'
    try {
        & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath $stagingDirectory StarSaviorHelper.spec
        if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
    }
    finally {
        if ($null -eq $previousPythonUserBase) {
            Remove-Item Env:PYTHONUSERBASE -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONUSERBASE = $previousPythonUserBase
        }
    }
    Compress-Archive -Path (Join-Path $stagingDirectory 'starsaviorhelper') -DestinationPath $stagingArchive -Force
    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
    Move-Item -LiteralPath $stagingArchive -Destination (Join-Path $releaseDirectory 'starsaviorhelper-Windows.zip')
    "Created $releaseDirectory"
}
finally {
    if (Test-Path -LiteralPath $stagingDirectory) {
        Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
    }
    if (Test-Path -LiteralPath $stagingArchive) {
        Remove-Item -LiteralPath $stagingArchive -Force
    }
}
