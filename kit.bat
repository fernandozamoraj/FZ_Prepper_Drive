@echo off
rem kit.bat (offline prepper kit v1.17.1): run a kit command on Windows. See README.md, or: kit.bat --help
rem   commands: setup, download, build-map, build-routing, build-places, build-bible, build-all, all, make-drive E:\
rem Uses the kit's portable Python (runtime\win-x64); if it isn't there yet, downloads it first (~30 MB).
setlocal
set "HERE=%~dp0"
set "PY=%HERE%runtime\win-x64\python\python.exe"
if exist "%PY%" goto run
echo Getting portable Python for Windows...
set "PYURL=https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16+20261026-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PYTGZ=%TEMP%\prepper-kit-python.tar.gz"
if not exist "%HERE%runtime\win-x64" mkdir "%HERE%runtime\win-x64"
curl.exe -fL --retry 3 -o "%PYTGZ%" "%PYURL%" || goto fail
tar.exe -xzf "%PYTGZ%" -C "%HERE%runtime\win-x64" || goto fail
del "%PYTGZ%"
:run
"%PY%" -I "%HERE%scripts\kit.py" %*
exit /b %ERRORLEVEL%
:fail
echo Could not download Python. Check the internet connection (Windows 10 or later is needed for curl and tar).
exit /b 1
