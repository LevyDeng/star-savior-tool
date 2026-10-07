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
$taskBuildRoot = [System.IO.Path]::GetFullPath((Join-Path $taskRoot 'build'))
New-Item -ItemType Directory -Path $taskBuildRoot -Force | Out-Null
$taskBuildLock = $null
try {
    $taskBuildLock = [System.IO.File]::Open((Join-Path $taskBuildRoot 'android-build.lock'),
        [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    throw 'Another Android build script is running. Wait for it to finish before rebuilding.'
}
try {
    $env:JAVA_HOME = $JavaPath
    # Keep the app identity outside disposable build caches. Never replace an existing key.
    $taskSigningRoot = Join-Path $taskRoot '.signing'
    $taskSigningKey = Join-Path $taskSigningRoot 'android-debug.keystore'
    if (-not (Test-Path -LiteralPath $taskSigningKey)) {
        New-Item -ItemType Directory -Path $taskSigningRoot -Force | Out-Null
        $taskLegacyKey = Join-Path $taskBuildRoot 'android-home/debug.keystore'
        if (Test-Path -LiteralPath $taskLegacyKey) {
            Copy-Item -LiteralPath $taskLegacyKey -Destination $taskSigningKey
            Write-Output 'Preserved the existing project signing key in .signing/android-debug.keystore.'
        } else {
            throw 'No project signing key found. Restore .signing/android-debug.keystore from your private backup. For a NEW app identity only, create a debug-format key as documented in android/README.md.'
        }
    }
    $env:GRADLE_USER_HOME = Join-Path $taskRoot 'build/gradle-home'
    $env:ANDROID_USER_HOME = Join-Path $taskRoot 'build/android-home'
    $taskSdkProperty = 'sdk.dir=' + $SdkPath.Replace('\', '/')
    Set-Content -LiteralPath (Join-Path $taskRoot 'android/local.properties') -Value $taskSdkProperty -Encoding ASCII
    $taskWrapper = Join-Path $taskRoot 'android/gradlew.bat'
    $taskCacheRoot = [System.IO.Path]::GetFullPath((Join-Path $env:GRADLE_USER_HOME 'caches'))
    for ($taskAttempt = 1; $taskAttempt -le 2; $taskAttempt++) {
        $taskLog = Join-Path $taskBuildRoot "android-build-attempt-$taskAttempt.log"
        $taskErrorAction = $ErrorActionPreference
        try {
            # PowerShell 5 treats native stderr as errors; retain it in the build log.
            $ErrorActionPreference = 'Continue'
            & $taskWrapper -p (Join-Path $taskRoot 'android') :app:assembleDebug :app:testDebugUnitTest --no-daemon --no-watch-fs --no-parallel --max-workers=2 --console=plain 2>&1 |
                Tee-Object -FilePath $taskLog
            $taskExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $taskErrorAction
        }
        if ($taskExitCode -eq 0) { break }
        $taskLogText = Get-Content -LiteralPath $taskLog -Raw
        $taskMoves = [regex]::Matches($taskLogText,
            'Could not move temporary workspace \(([^\r\n)]+)\) to immutable location \(([^\r\n)]+)\)')
        if ($taskAttempt -eq 2 -or $taskMoves.Count -eq 0) {
            throw "Android build failed: $taskExitCode. See $taskLog"
        }
        Write-Output 'Gradle workspace move failed. Stopping this cache home and isolating affected transform entries before one retry.'
        & $taskWrapper --stop
        if ($LASTEXITCODE -ne 0) { throw "Unable to stop Gradle. See $taskLog" }
        $taskQuarantine = [System.IO.Path]::GetFullPath((Join-Path $taskBuildRoot ('gradle-cache-recovery/' + [guid]::NewGuid().ToString())))
        if (-not $taskQuarantine.StartsWith($taskBuildRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Cache recovery destination must stay inside the workspace build directory.'
        }
        New-Item -ItemType Directory -Path $taskQuarantine -Force | Out-Null
        $taskTargets = @($taskMoves | ForEach-Object { $_.Groups[1].Value; $_.Groups[2].Value }) | Sort-Object -Unique
        foreach ($taskTarget in $taskTargets) {
            $taskAbsolute = [System.IO.Path]::GetFullPath($taskTarget)
            $taskPrefix = $taskCacheRoot + [System.IO.Path]::DirectorySeparatorChar
            if (-not $taskAbsolute.StartsWith($taskPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing cache recovery outside the project Gradle cache: $taskAbsolute"
            }
            $taskRelative = $taskAbsolute.Substring($taskPrefix.Length)
            if ($taskRelative -notmatch '^\d+(\.\d+)*[\\/]transforms[\\/][a-f0-9]{32}(-[a-f0-9-]{36})?$') {
                throw "Refusing unexpected cache recovery path: $taskAbsolute"
            }
            if (Test-Path -LiteralPath $taskAbsolute) {
                $taskEntry = Get-Item -LiteralPath $taskAbsolute
                if (-not $taskEntry.PSIsContainer -or ($taskEntry.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                    throw "Refusing non-directory or linked cache entry: $taskAbsolute"
                }
                # Retain failed artifacts for inspection rather than deleting dependencies.
                $taskDestination = Join-Path $taskQuarantine ($taskRelative.Replace('\', '_').Replace('/', '_'))
                Move-Item -LiteralPath $taskAbsolute -Destination $taskDestination
            }
        }
        Write-Output "Affected transform entries retained in $taskQuarantine"
    }
    $taskOutput = Join-Path $taskRoot ('dist/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
    $taskApk = Join-Path $taskOutput 'starsaviorhelper-Android-demo.apk'
    Copy-Item -LiteralPath (Join-Path $taskRoot 'android/app/build/outputs/apk/debug/app-debug.apk') -Destination $taskApk
    $taskHash = (Get-FileHash -LiteralPath $taskApk -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $taskOutput 'SHA256SUMS.txt') -Value "$taskHash  starsaviorhelper-Android-demo.apk" -Encoding ASCII
    Write-Output "Android demo: $taskApk"
} finally {
    if ($taskBuildLock) { $taskBuildLock.Dispose() }
    $env:JAVA_HOME = $taskPreviousJava
    $env:GRADLE_USER_HOME = $taskPreviousGradle
    $env:ANDROID_USER_HOME = $taskPreviousAndroid
}
