param(
    [ValidateSet('zh-CN', 'zh-TW', 'en', 'ja', 'ko')]
    [string]$Locale = 'zh-CN'
)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$probeDirectory = Join-Path $projectDirectory 'build\webview2-probe'
$sdkDirectory = Join-Path $probeDirectory 'sdk'
$package = Join-Path $probeDirectory 'sdk.nupkg'
$sdkVersion = '1.0.4258.31'
$expectedHash = '56F7F4B8BF9AEE4B8EFEFBBDD4F67D5F74EBD1B100ED0806DA71BF76AF481AA9'
New-Item -ItemType Directory -Path $sdkDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $package)) {
    $packageUrl = "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$sdkVersion/microsoft.web.webview2.$sdkVersion.nupkg"
    Invoke-WebRequest -UseBasicParsing -Uri $packageUrl -OutFile $package -TimeoutSec 60
}
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'The pinned WebView2 SDK package checksum does not match'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($package)
try {
    foreach ($entryName in @('lib/net462/Microsoft.Web.WebView2.Core.dll', 'lib/net462/Microsoft.Web.WebView2.WinForms.dll', 'runtimes/win-x64/native/WebView2Loader.dll')) {
        $entry = $archive.GetEntry($entryName)
        $target = Join-Path $sdkDirectory ([System.IO.Path]::GetFileName($entryName))
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
    }
}
finally { $archive.Dispose() }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$executable = Join-Path $sdkDirectory 'WebView2Probe.exe'
$source = Join-Path $PSScriptRoot 'WebView2Probe.cs'
& $compiler /nologo /target:winexe /platform:x64 "/out:$executable" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/reference:$sdkDirectory\Microsoft.Web.WebView2.Core.dll" "/reference:$sdkDirectory\Microsoft.Web.WebView2.WinForms.dll" $source
if ($LASTEXITCODE -ne 0) { throw 'WebView2 probe compilation failed' }
$outputDirectory = Join-Path $probeDirectory $Locale
$extractor = Join-Path $projectDirectory 'shared\assets\espr-extract.js'
# Keep the verification window visible so a person can complete any site prompt.
$probeArguments = '"{0}" "{1}" "{2}"' -f $outputDirectory, $Locale, $extractor
$process = Start-Process -FilePath $executable -ArgumentList $probeArguments -WindowStyle Normal -Wait -PassThru
if ($process.ExitCode -ne 0) {
    $errorFile = Join-Path $outputDirectory 'error.txt'
    if (Test-Path -LiteralPath $errorFile) { Get-Content -LiteralPath $errorFile }
    throw "WebView2 probe failed: $($process.ExitCode)"
}
Get-Content -LiteralPath (Join-Path $outputDirectory 'report.json')
"Snapshot: $outputDirectory\snapshot.json"
