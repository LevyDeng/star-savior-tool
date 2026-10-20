# System WebView2 feasibility probe

Run `powershell -ExecutionPolicy Bypass -File tools/probe_webview2.ps1` from the repository. Pass `-Locale en` to verify English. An installed x64 Evergreen WebView2 Runtime and .NET Framework are required. The script downloads a pinned, SHA-256-checked Microsoft SDK from NuGet into `build/webview2-probe`, compiles a small standalone WinForms executable, and opens the public ESPR page in a visible window. Site verification, if shown, must be completed manually. No browser runtime is installed or bundled, no certificate checks are disabled, and no Qt libraries are loaded.

Each locale has an isolated persistent profile below `build/webview2-probe`. Results are written to `snapshot.json`, `report.json`, and `runtime.txt` in that locale directory. Failures go to `error.txt`. Only the expected HTTPS source and locale path are extracted. The shared read-only extractor retrieves the complete event payload, not just initially displayed cards. This is a feasibility tool, not a replacement for the application's production synchronization UI.

Verified locally on 2026-10-20 with system runtime `155.0.4283.62`:

- Fresh Chinese profile: 5.445 seconds, 238 events, 366 choices.
- Reused Chinese profile after process restart: 2.227 seconds.
- Fresh English profile: 8.273 seconds, 238 events, 366 choices.
- Chinese event IDs exactly match the previously verified Qt WebEngine snapshot. Both locales pass the existing converter at all three difficulties.
- Hard beach-volleyball preliminaries require Strength 500 and grant potential points 50; unrelated stats remain unchanged.
- The standalone executable plus three bridge DLLs total 944,672 bytes, excluding the already installed shared runtime. This is not a measurement of the final application ZIP.

The production integration now uses `star_savior/native/WebViewSync.cs` and `star_savior/browser_sync.py`. Build it with `tools/build_webview2.ps1`; the original probe remains an isolated feasibility tool and does not change application caches or settings. Production acceptance includes missing-runtime messages, cancellation, timeout, parent-state restoration, real synchronization, and a packaged-application check.
