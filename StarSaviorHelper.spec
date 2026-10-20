"""Portable Windows distribution with local OCR models and no console."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path

app_datas = collect_data_files('rapidocr') + [('star_savior/assets/app-icon.png', 'star_savior/assets'), ('star_savior/assets/floating-icon.png', 'star_savior/assets'), ('shared/assets/espr-extract.js', 'star_savior/assets')]
bridge = Path('build/webview2-runtime')
if not (bridge / 'StarSaviorSync.exe').is_file():
    raise SystemExit('Build the system WebView2 bridge with tools/build_webview2.ps1 first')
app_datas += [(str(path), 'webview2-runtime') for path in bridge.iterdir() if path.is_file()]
ocr_imports = collect_submodules('rapidocr')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=app_datas,
    hiddenimports=ocr_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'paddle', 'tensorflow', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'],
    noarchive=False,
)
# Qt on Windows uses the operating system's ICU API. Unrelated ICU DLLs
# discovered on PATH (for example from Poppler) expose incompatible symbols.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='starsaviorhelper', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    icon='star_savior/assets/app-icon.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='starsaviorhelper')
