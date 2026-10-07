# Android app

Native Kotlin application for Android 8.0 (API 26) and later. The application currently targets API 34 and is distributed as a sideloaded APK. Windows source and packaging remain in their existing locations.

## Build and install

Install JDK 17 or newer, Android SDK Platform 34 and Build Tools 34.0.0. Open this directory in Android Studio, or run from the repository root:

```powershell
./build-android.ps1 -SdkPath C:/Users/example/AppData/Local/Android/Sdk -JavaPath 'C:/Program Files/Java/jdk-21'
```

The checked-in Gradle wrapper uses Gradle 8.11.1. The first build downloads Gradle and Maven dependencies. The script runs JVM parity checks, then copies the debug-signed APK and SHA256 checksum to `dist/<timestamp>/`. This is a sideloaded development build.

### Stable signing and upgrades

All builds, including Android Studio, explicitly use `.signing/android-debug.keystore` at the repository root. The build script preserves the existing `build/android-home/debug.keystore` there on the first migration. The key is outside disposable caches and excluded from Git. Back it up privately and restore it on every build machine. The public debug password is not protection for the private key; do not share or upload this directory. This setup preserves the current development identity; it is not a production release-signing configuration.

Android requires the same application ID and signing certificate for an in-place update, even for sideloaded apps. A different certificate cannot update the installed app. Recover the original private key to retain compatibility; the APK alone cannot recover that key. Without it, uninstalling and reinstalling starts a new identity and removes the app's private data. Do not replace the persistent key when cleaning `build/` or `dist/`.

If neither persistent nor legacy project key exists, the build fails instead of silently creating an incompatible identity. Only for a new installation identity, explicitly create a key from the repository root (use your JDK's `keytool`):

```powershell
New-Item -ItemType Directory -Path .signing -Force
keytool -genkeypair -keystore .signing/android-debug.keystore -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Star Savior Helper Development'
```

## First run

1. Install `starsaviorhelper-Android.apk` and open starsaviorhelper. Existing package identity and private cache are retained when updating.
2. Choose game language from the header and journey difficulty, then synchronize the website guide.
3. Tap Start, grant overlay permission and authorize full-display capture. Android 14+ explicitly requests the default display rather than app-only sharing.
4. Open the game in fullscreen landscape and tap the glass star. Drag it to move; long-press for Open settings, Exit or Cancel. Long-press does not stop capture directly.
5. A light-blue animated rim appears while recognition runs. The button is briefly removed while acquiring a fresh image and then returns during OCR.

Screenshot import, region calibration and reset controls are removed. Recognition adapts the shared normalized title and choice regions to the fullscreen aspect ratio: wide phone screens get a lower title boundary and a higher choice boundary. Portrait scans report a clear instruction to switch to fullscreen landscape. There is no Android model-release control.

Capture consent is required again after stopping, process death, or the system ending the session. A single virtual display is created per consent token. Android 14 content-size callbacks resize the existing display and image surface; older versions respond to configuration changes. The foreground service is not sticky and does not reuse stored consent. Screen sharing requires Android's visible ongoing foreground-service notification; notification permission is requested on Android 13+.

The helper removes both overlays before reading a fresh frame, has an in-progress guard and an 800 ms cooldown, and reports a timeout rather than using a previous recognition. Screenshots are used locally and are not written to storage or uploaded by the recognition pipeline. OCR runs on a worker thread; recognizer sessions are closed after each query.

## Data and matching

The same six public JSON resources as Windows are synchronized. All five languages and three difficulties validate before an `AtomicFile` replacement of the private cache. No private server, account, accessibility service, automatic game interaction, or continuous OCR is used. HTTPS verification is enabled by default. SSL settings allow an explicit, persisted bypass for guide synchronization only, with a warning. The override is scoped to each download connection; process-wide TLS defaults remain unchanged. Android has no proxy setting.

The native adapter uses exported Windows vocabulary, language fallback, ordered option matching, grouped outcomes, conditions, reference descriptions and difficulty filtering. Only potential-point rewards receive the difficulty multiplier. Title and choices are cropped separately. The highest-scoring candidate is displayed immediately; alternatives and recognized text are collapsed by default. Match scores are heuristics, not probabilities.

ML Kit's bundled Latin, Chinese, Japanese and Korean models provide the five selected languages (Simplified/Traditional Chinese share one script model). This avoids the Play Services model-download path and increases APK size. Model performance and memory behavior require real-device measurements.

Support-card identity is retained in the data and candidate labels. Automatic card-image disambiguation is not yet implemented on Android; for identical titles and choices, inspect the card name and manually select the correct candidate. The top candidate may otherwise describe a different card. Likewise, letterboxing, system bars, protected content, orientation, and vendor overlay restrictions need testing on the actual game device. Fixed title and choice regions are relative to the full captured display; letterboxed or inset game layouts may require future adaptation.

## Verification

```powershell
cd android
./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

JVM checks compare matching scores/states against desktop golden cases and compare all 15 language/difficulty conversions, including potential-point-only scaling and malformed-reference rejection. If a private `build/live-conversion.json` is present, live-source event contents are also compared independent of JSON object iteration order.

Logs use Android Logcat tags `GuideRepository`, `MainActivity` and `CaptureService`. The private guide cache is `files/guide.json`; language, journey difficulty, SSL preference and button position are in the app's private SharedPreferences. No Windows data files are modified.

The Gradle build and JVM tests do not establish real-game screen-capture or OCR accuracy. Acceptance requires an installed APK on a phone: authorize capture, show a known event, tap Scan, verify title and every effect, retry without old results, rotate the device, stop/restart capture, test permission denial, and check duplicate support cards manually.

Build verification includes JVM parity tests and a connection-scoped TLS test, APK compilation, and Android lint. User testing confirmed text recognition in an earlier build. The updated full-display flow, long-press menu and animated overlay still require phone verification. Desktop tests cover rendering, timer visibility lifecycle, drag behavior, difficulty persistence and startup.

Implementation references: [Android MediaProjection](https://developer.android.com/media/grow/media-projection), [ML Kit text recognition](https://developers.google.com/ml-kit/vision/text-recognition/v2/android).

Application icons use a flat blue rounded square; floating buttons use a separate circular blue background. Both share a symmetric white four-point star with slightly rounded corners. Windows uses `star_savior/assets/app-icon.png` for the application and `floating-icon.png` for the overlay and its preview; the EXE embeds the multi-size ICO. Android uses `floating_icon.png` for its overlay and separate density-specific/adaptive launcher resources. Launcher masking remains controlled by Android. Run `tools/generate_app_icon.ps1` to regenerate all resources from the shared geometry.

## Windows Gradle cache recovery

The build script takes an exclusive workspace lock to prevent overlapping script builds, disables filesystem watching and parallel project execution, and limits Gradle workers to two. It writes each attempt to `build/android-build-attempt-1.log` or `build/android-build-attempt-2.log`. A temporary-to-immutable transform workspace move error triggers one recovery attempt: stop daemons belonging to the project Gradle user home, validate the exact paths from the log, and move only affected transform directories into `build/gradle-cache-recovery/`. Dependency downloads are retained. Other failures are reported without modifying caches. Do not run an Android Studio build concurrently with the script; external file locks may still prevent recovery.

Floating button size and transparency are adjustable with settings sliders and an actual-size preview. Size ranges from 40 to 160 dp (default 72); transparency ranges from 0 to 90 percent (default 0, fully opaque). Values persist and update the active overlay immediately. Overlay geometry is clamped to the display after size changes. Changes during frame capture do not reattach hidden controls. Device behavior still requires on-device verification.
