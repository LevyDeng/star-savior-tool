$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm StarSaviorHelper.spec
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
Compress-Archive -Path .\dist\StarSaviorHelper -DestinationPath .\dist\StarSaviorHelper-Windows.zip -Force
