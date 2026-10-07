param(
    [string]$SdkPath = $env:ANDROID_HOME,
    [string]$JavaPath = $env:JAVA_HOME
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
if (-not $SdkPath) { $SdkPath = Join-Path $env:LOCALAPPDATA 'Android/Sdk' }
if (-not $JavaPath) {
    foreach ($candidate in @('C:/Program Files/Java/jdk-21', 'C:/Program Files/Android/Android Studio/jbr')) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'lib/jvm.cfg')) { $JavaPath = $candidate; break }
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $SdkPath 'platforms/android-34/android.jar'))) {
    throw 'Install Android SDK Platform 34 and Build Tools 34.0.0, or pass -SdkPath.'
}
if (-not $JavaPath -or -not (Test-Path -LiteralPath (Join-Path $JavaPath 'bin/java.exe'))) {
    throw 'Install JDK 17 or newer and pass -JavaPath.'
}
$taskPreviousJava = $env:JAVA_HOME
$taskPreviousGradle = $env:GRADLE_USER_HOME
$taskPreviousAndroid = $env:ANDROID_USER_HOME
try {
    $env:JAVA_HOME = $JavaPath
    $env:GRADLE_USER_HOME = Join-Path $taskRoot 'build/gradle-home'
    $env:ANDROID_USER_HOME = Join-Path $taskRoot 'build/android-home'
    $taskSdkProperty = 'sdk.dir=' + $SdkPath.Replace('\', '/')
    Set-Content -LiteralPath (Join-Path $taskRoot 'android/local.properties') -Value $taskSdkProperty -Encoding ASCII
    & (Join-Path $taskRoot 'android/gradlew.bat') -p (Join-Path $taskRoot 'android') :app:assembleDebug :app:testDebugUnitTest --no-daemon
    if ($LASTEXITCODE -ne 0) { throw "Android build failed: $LASTEXITCODE" }
    $taskOutput = Join-Path $taskRoot ('dist/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
    $taskApk = Join-Path $taskOutput 'starsaviorhelper-Android-demo.apk'
    Copy-Item -LiteralPath (Join-Path $taskRoot 'android/app/build/outputs/apk/debug/app-debug.apk') -Destination $taskApk
    $taskHash = (Get-FileHash -LiteralPath $taskApk -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $taskOutput 'SHA256SUMS.txt') -Value "$taskHash  starsaviorhelper-Android-demo.apk" -Encoding ASCII
    Write-Output "Android demo: $taskApk"
} finally {
    $env:JAVA_HOME = $taskPreviousJava
    $env:GRADLE_USER_HOME = $taskPreviousGradle
    $env:ANDROID_USER_HOME = $taskPreviousAndroid
}
