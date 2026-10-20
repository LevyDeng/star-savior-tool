param([switch]$Force)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$outputDirectory = Join-Path $projectDirectory 'build\webview2-runtime'
$source = Join-Path $projectDirectory 'star_savior\native\WebViewSync.cs'
$executable = Join-Path $outputDirectory 'StarSaviorSync.exe'
if (-not $Force -and (Test-Path -LiteralPath $executable) -and (Get-Item -LiteralPath $executable).LastWriteTimeUtc -gt (Get-Item -LiteralPath $source).LastWriteTimeUtc) {
    Write-Output "WebView2 bridge is current: $executable"
    exit 0
}
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$package = Join-Path $projectDirectory 'build\webview2-sdk.nupkg'
$probePackage = Join-Path $projectDirectory 'build\webview2-probe\sdk.nupkg'
if (-not (Test-Path -LiteralPath $package)) {
    if (Test-Path -LiteralPath $probePackage) { Copy-Item -LiteralPath $probePackage -Destination $package }
    else {
        Invoke-WebRequest -UseBasicParsing -Uri 'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.4258.31/microsoft.web.webview2.1.0.4258.31.nupkg' -OutFile $package -TimeoutSec 60
    }
}
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash -ne '56F7F4B8BF9AEE4B8EFEFBBDD4F67D5F74EBD1B100ED0806DA71BF76AF481AA9') {
    throw 'WebView2 SDK checksum mismatch'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($package)
try {
    foreach ($name in @('lib/net462/Microsoft.Web.WebView2.Core.dll', 'lib/net462/Microsoft.Web.WebView2.WinForms.dll', 'runtimes/win-x64/native/WebView2Loader.dll', 'LICENSE.txt', 'NOTICE.txt')) {
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($archive.GetEntry($name), (Join-Path $outputDirectory ([System.IO.Path]::GetFileName($name))), $true)
    }
}
finally { $archive.Dispose() }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:x64 "/out:$executable" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/reference:$outputDirectory\Microsoft.Web.WebView2.Core.dll" "/reference:$outputDirectory\Microsoft.Web.WebView2.WinForms.dll" $source
if ($LASTEXITCODE -ne 0) { throw 'WebView2 bridge compilation failed' }
"Built $executable"
