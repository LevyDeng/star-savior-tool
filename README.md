# StarSavior Guide Demo (Windows)

A local game screenshot OCR assistant using [Star Savior Arcana DB](https://star-savior-arcana-db.pages.dev/journey) as its only guide source.

## Start

For the portable build, extract `dist/StarSaviorHelper-Windows.zip` and double-click `StarSaviorHelper.exe` inside the extracted folder. Keep the `_internal` folder next to the executable. No Python installation or terminal window is required. All five OCR language models are bundled; guide synchronization still needs internet access. The executable uses the same per-user settings and database as the source version.

To run from source, install Python 3.11 and double-click `start.cmd`. The first launch installs pinned dependencies in `.venv` and automatically synchronizes if no website cache exists. Use the sync button for later updates. Daily lookup uses the offline cache.

## Windows portable build

Run `powershell -ExecutionPolicy Bypass -File build.ps1` after setting up the source environment. The script installs the pinned packaging tools and creates `dist/StarSaviorHelper-Windows.zip`; extract it and keep the `_internal` folder beside the executable. The PyInstaller work directory (`build/`) and distribution directory (`dist/`) are generated locally and excluded from Git.

To verify a packaged build, run `StarSaviorHelper.exe --self-test <isolated-output-directory>`. It opens the interface and runs local OCR in all five languages without changing the player's saved settings. Windowed execution writes diagnostics to `application.log` in the user data directory.

Tencent Docs, login, spreadsheet imports, copied tables, guide screenshot OCR, automated scrolling, and collection recovery have been removed. Existing legacy user files and browser sessions are untouched and are not queried.

## Website data

The importer downloads the six public JSON resources used by the website: journeys, arcanas, journey items, potentials, stat potentials, and journey buffs. All resources and all five language conversions must validate before the SQLite snapshot changes. Failed requests, invalid data, unknown reward types, and unresolved references preserve the previous cache.

Journey variants with identical ordered choices share an event whose effects retain all variants separately; different choice groups stay distinct. Support-card identities are retained. Conditions/costs, numeric ranges, success/failure outcomes, names/descriptions, and grouped alternatives are preserved. Within a reward group, alternatives are joined with OR; different groups remain separate. No probabilities are inferred. Choose Easy, Normal, or Hard to filter journey variants and apply its 1/1.5/2.5 multiplier to potential points only. Other stats and costs remain unchanged. No-choice automatic events are explicitly labeled.

The public data format is not a versioned API contract. Schema changes may require updating the adapter. Source data can differ from the current game; check the displayed choices against the game. Missing translations fall back to English then Korean. Raw source data remains in the cache.

Missing fixed effect labels in the website's Chinese interface do not imply missing numeric data. The app maps structured reward/stat codes to its own five-language terminology. Blank and markup-only translated strings fall back after text cleanup. Reference names/descriptions shown in effects mark fallback text with its original language code; title and choice text are kept free of such annotations for matching. No translation model is bundled, and missing free text remains source-language text rather than an unverified generated translation. A completely missing outcome or number is never inferred from translation.

Main results and candidate labels show human-readable phases and source/card names. Source event/card identifiers remain internal for validation and are available by hovering over the result or a candidate for diagnostics. They are not shown as dates or repeated in choice effects. Multiple outcome variants retain localized numbered variant labels and their conditions.

The app uses a restrained blue-white theme. Settings show guide synchronization and the source link on the first row, language and difficulty on the second row, and a circular Start button at the bottom right. Choice effects appear in the floating results window. Candidate selection and recognized source text are collapsed by default and reset to collapsed on each scan. The text itself has no inner scrollbars; the results window grows to fit until the available screen height is reached, after which the entire result panel scrolls. Long explanations wrap at the current window width, and expanding a detail section recalculates the required height.

## Languages and recognition

Select Simplified Chinese, Traditional Chinese, English, Japanese, or Korean. The selector changes interface labels, floating controls/results, guide text, match language, and RapidOCR recognition model. It is saved per user. All guide languages are synchronized together, and switching cached languages works offline. The portable build includes the OCR models for all five languages. When running from source, models download on first use and are cached locally. Other-language screenshot accuracy has not yet been measured.

Select the game window and click Start to enable the floating button. Click to scan; drag to move; right-click for settings or exit. Ctrl+Alt+S also triggers recognition. The app hides its controls and overlays before capture. Title and choices are independently read from the same frame. Adjust both regions when the layout/aspect ratio changes; settings are relative to the client area and saved by window title.

Both the floating scan button and results window prevent Windows mouse activation so clicks can be handled without taking foreground focus from the game. Capture preserves focus when the selected game is already foreground; an unsuccessful foreground switch is reported before attempting a screenshot. Opening settings intentionally activates the settings window.

The windowed executable suppresses console creation for default auxiliary subprocesses. On first OCR initialization, ONNX Runtime queries the Windows version through Python's `platform` module, which runs `cmd.exe /c ver`. Without console suppression, this can interrupt fullscreen focus even when the floating controls themselves do not activate. Source execution through `start.cmd` retains its existing console behavior. The packaged self-test checks that a console child has no console window, in addition to testing all five OCR languages.

A strong unique title can identify an event when choices are unreadable. When matching yields only one candidate, its effects are displayed automatically; weak or conflicting evidence still shows a reminder to verify conditions and choices. Multiple uncertain candidates require choosing a candidate, and unknown events show no effects. Match scores are heuristics, not probabilities. Screenshots stay local; no choices are clicked automatically. Capture uses visible pixels and can be affected by other windows, exclusive fullscreen, protected content, or Windows scaling.

## Storage and checks

Per-user Qt application data for `StarSaviorTool/StarSaviorGuideDemo` contains `website.sqlite3` and `settings.ini`. `STAR_SAVIOR_DATA_DIR` selects an isolated testing directory. Data updated shows the last successful local guide synchronization in the local timezone; its tooltip clarifies that meaning. Failed synchronization preserves the previous data and timestamp. Legacy guide data and collection files are unused.

Run checks with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Verified on 2026-10-04: public downloads and conversion produced 276 events in each of five languages. Checks cover matching, single-candidate display, capture with hidden overlays, child-process console suppression, interface switching, alternatives/costs, failed-sync preservation, cache reload, and unresolved references. The supplied game screenshot identifies the expected event title but has conflicting choices: the source has three training-material choices while the screenshot has four support choices. A sole candidate is displayed with a verification reminder; this source/game-version discrepancy is not an exact choice match. Live capture, Windows scaling, and representative screenshots in all languages remain acceptance checks.
