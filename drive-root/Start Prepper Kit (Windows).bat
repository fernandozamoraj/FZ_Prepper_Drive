@echo off
rem Start Prepper Kit (Windows), offline prepper kit v1.13.2. Double-click this file to start the kit.
rem It uses the kit's own portable Python (runtime\win-x64), so nothing needs to be installed and no internet is needed.
rem Works when it sits next to the offline-prepper-kit folder (drive root) or inside it.
title Prepper Kit
cd /d "%~dp0"
set "KIT=%~dp0offline-prepper-kit"
if not exist "%KIT%\bin\intranet.py" set "KIT=%~dp0."
set "PY=%KIT%\runtime\win-x64\python\python.exe"
cls
echo ==============================================
echo    OFFLINE PREPPER KIT
echo    Library, Bible, maps and directions
echo ==============================================
echo.
if not exist "%PY%" (
  echo Could not find the kit's files next to this launcher.
  echo Keep this file next to the "offline-prepper-kit" folder.
  pause
  exit /b 1
)
"%PY%" -I "%KIT%\bin\intranet.py" --open
echo.
echo The Prepper Kit has stopped. You can close this window.
pause
